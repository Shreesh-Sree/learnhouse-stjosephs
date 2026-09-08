"""OIDC-based SSO — see src/db/sso.py for the scope decision (OIDC only, not
SAML/WorkOS) and the one-connection-per-org data model.

Three moving pieces:

- Admin config CRUD (create/read/update/delete an org's ``SSOConnection``).
- ``build_authorization_url`` — starts a login: fetches the IdP's discovery
  document, generates PKCE + a nonce, and returns the authorization URL plus
  an opaque ``state``.
- ``handle_sso_callback`` — finishes it: verifies ``state`` (a signed JWT, not
  a server-side session — see below), exchanges the code for tokens, verifies
  the ID token's signature via the IdP's JWKS, finds-or-provisions the
  LearnHouse account, and mints a real session.

STATE HANDLING: ``state`` is itself a short-lived signed JWT (HS256, the
app's own secret) carrying the org, nonce, and PKCE code_verifier — not a key
into a server-side store. This makes the flow work correctly whether or not
Redis is configured (Redis is optional throughout this project), at the cost
of the state token being a bit bigger than a random opaque string. It cannot
be forged or extended without the app's JWT secret, and it expires exactly
like every other token this app issues.
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request
from jwt.algorithms import RSAAlgorithm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config.config import get_learnhouse_config
from src.db.organizations import Organization
from src.db.roles import Role
from src.db.sso import (
    SSOConnection,
    SSOConfigCreate,
    SSOConfigRead,
    SSOConfigUpdate,
    SSOProviderInfo,
    SUPPORTED_OIDC_PROVIDERS,
)
from src.db.user_audit_events import UserAuditEventType
from src.db.user_organizations import UserOrganization
from src.db.users import User, UserCreate
from src.security.auth import create_access_token, decode_jwt
from src.security.session_context import AUTH_METHOD_SSO
from src.services.audit.audit import record_audit_event
from src.services.auth.session import issue_session_or_challenge
from src.services.utils.ssrf_guard import (
    SSRFBlockedError,
    assert_connected_peer_allowed,
    resolve_and_validate_url,
)
from src.services.webhooks.crypto import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

SSO_STATE_PURPOSE = "sso_state"
SSO_STATE_TTL = timedelta(minutes=10)
_HTTP_TIMEOUT = 10.0


class SSOFlowError(Exception):
    """Structured error matching the frontend's ``SSOErrorDetail`` shape
    (apps/web/services/auth/sso.ts) — every error code used here is one the
    frontend's ``getErrorMessage`` already has a human-readable string for.
    """

    def __init__(self, error_code: str, message: str, status_code: int = 400):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=self.status_code,
            detail={
                "error": "sso_error",
                "error_code": self.error_code,
                "error_description": self.message,
                "message": self.message,
            },
        )


# ---------------------------------------------------------------------------
# Provider catalog
# ---------------------------------------------------------------------------

_PROVIDER_CATALOG: list[SSOProviderInfo] = [
    SSOProviderInfo(
        id="keycloak",
        name="Keycloak",
        description="Self-hosted or managed Keycloak realm, via its OIDC discovery document.",
        has_setup_portal=False,
        available=True,
        config_fields=[
            {"name": "issuer", "type": "text", "required": True, "description": "Realm issuer URL", "placeholder": "https://keycloak.example.edu/realms/campus"},
            {"name": "client_id", "type": "text", "required": True, "description": "OIDC client ID"},
            {"name": "client_secret", "type": "password", "required": True, "description": "OIDC client secret", "hidden": True},
        ],
    ),
    SSOProviderInfo(
        id="okta",
        name="Okta",
        description="An Okta org's default authorization server, via OIDC.",
        has_setup_portal=False,
        available=True,
        config_fields=[
            {"name": "issuer", "type": "text", "required": True, "description": "Okta issuer URL", "placeholder": "https://your-org.okta.com/oauth2/default"},
            {"name": "client_id", "type": "text", "required": True, "description": "OIDC client ID"},
            {"name": "client_secret", "type": "password", "required": True, "description": "OIDC client secret", "hidden": True},
        ],
    ),
    SSOProviderInfo(
        id="auth0",
        name="Auth0",
        description="An Auth0 tenant, via OIDC.",
        has_setup_portal=False,
        available=True,
        config_fields=[
            {"name": "issuer", "type": "text", "required": True, "description": "Auth0 tenant issuer URL", "placeholder": "https://your-tenant.auth0.com/"},
            {"name": "client_id", "type": "text", "required": True, "description": "OIDC client ID"},
            {"name": "client_secret", "type": "password", "required": True, "description": "OIDC client secret", "hidden": True},
        ],
    ),
    SSOProviderInfo(
        id="custom_oidc",
        name="Custom OIDC provider",
        description="Any OpenID Connect-compliant IdP (Google Workspace, Microsoft Entra ID/Azure AD, generic) that publishes a /.well-known/openid-configuration document.",
        has_setup_portal=False,
        available=True,
        config_fields=[
            {"name": "issuer", "type": "text", "required": True, "description": "IdP issuer URL (its /.well-known/openid-configuration must resolve under this)"},
            {"name": "client_id", "type": "text", "required": True, "description": "OIDC client ID"},
            {"name": "client_secret", "type": "password", "required": True, "description": "OIDC client secret", "hidden": True},
            {"name": "scope", "type": "text", "required": False, "description": "Space-separated scopes (default: openid email profile)"},
        ],
    ),
]


def get_provider_catalog() -> list[SSOProviderInfo]:
    return _PROVIDER_CATALOG


def _redirect_uri() -> str:
    config = get_learnhouse_config()
    scheme = "https" if config.hosting_config.ssl else "http"
    return f"{scheme}://{config.hosting_config.domain}/api/v1/auth/sso/callback"


# ---------------------------------------------------------------------------
# Admin config CRUD
# ---------------------------------------------------------------------------


def _to_read(conn: SSOConnection) -> SSOConfigRead:
    # Never echo the encrypted secret blob back over the API — write-only.
    redacted_config = dict(conn.provider_config or {})
    redacted_config.pop("client_secret_encrypted", None)
    return SSOConfigRead(
        id=conn.id,
        org_id=conn.org_id,
        provider=conn.provider,
        enabled=conn.enabled,
        domains=list(conn.domains or []),
        auto_provision_users=conn.auto_provision_users,
        default_role_id=conn.default_role_id,
        provider_config=redacted_config,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


def _validate_provider(provider: str) -> None:
    if provider not in SUPPORTED_OIDC_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported SSO provider {provider!r}. Supported: "
                f"{sorted(SUPPORTED_OIDC_PROVIDERS)}. SAML and WorkOS are not "
                "implemented — see src/db/sso.py for why."
            ),
        )


async def get_org_sso_config(org_id: int, db_session: AsyncSession) -> Optional[SSOConfigRead]:
    conn = await _get_connection(org_id, db_session)
    return _to_read(conn) if conn else None


async def _get_connection(org_id: int, db_session: AsyncSession) -> Optional[SSOConnection]:
    statement = select(SSOConnection).where(SSOConnection.org_id == org_id)
    return (await db_session.execute(statement)).scalars().first()


def _build_provider_config_dict(cfg, existing: Optional[dict] = None) -> dict:
    """Merge a partial ``SSOProviderConfigIn`` onto ``existing`` stored config,
    encrypting the secret only when a new one is actually provided (an update
    that omits it keeps the previously-stored one)."""
    result = dict(existing or {})
    if cfg.issuer is not None:
        result["issuer"] = cfg.issuer.rstrip("/")
    if cfg.client_id is not None:
        result["client_id"] = cfg.client_id
    if cfg.scope is not None:
        result["scope"] = cfg.scope
    if cfg.client_secret:
        result["client_secret_encrypted"] = encrypt_secret(cfg.client_secret)
    return result


async def create_sso_config(
    org_id: int, data: SSOConfigCreate, db_session: AsyncSession
) -> SSOConfigRead:
    _validate_provider(data.provider)
    existing = await _get_connection(org_id, db_session)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This organization already has an SSO configuration. Use PUT to update it.",
        )
    if not data.provider_config.client_secret:
        raise HTTPException(status_code=400, detail="client_secret is required")

    now = datetime.utcnow()
    conn = SSOConnection(
        org_id=org_id,
        provider=data.provider,
        enabled=data.enabled,
        domains=data.domains,
        auto_provision_users=data.auto_provision_users,
        default_role_id=data.default_role_id,
        provider_config=_build_provider_config_dict(data.provider_config),
        created_at=now,
        updated_at=now,
    )
    db_session.add(conn)
    await db_session.commit()
    await db_session.refresh(conn)
    return _to_read(conn)


async def update_sso_config(
    org_id: int, data: SSOConfigUpdate, db_session: AsyncSession
) -> SSOConfigRead:
    conn = await _get_connection(org_id, db_session)
    if not conn:
        raise HTTPException(status_code=404, detail="No SSO configuration for this organization")

    if data.provider is not None:
        _validate_provider(data.provider)
        conn.provider = data.provider
    if data.enabled is not None:
        conn.enabled = data.enabled
    if data.domains is not None:
        conn.domains = data.domains
    if data.auto_provision_users is not None:
        conn.auto_provision_users = data.auto_provision_users
    if data.default_role_id is not None:
        conn.default_role_id = data.default_role_id
    if data.provider_config is not None:
        conn.provider_config = _build_provider_config_dict(data.provider_config, conn.provider_config)

    conn.updated_at = datetime.utcnow()
    db_session.add(conn)
    await db_session.commit()
    await db_session.refresh(conn)
    return _to_read(conn)


async def delete_sso_config(org_id: int, db_session: AsyncSession) -> None:
    conn = await _get_connection(org_id, db_session)
    if not conn:
        raise HTTPException(status_code=404, detail="No SSO configuration for this organization")
    await db_session.delete(conn)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Public: login-page check
# ---------------------------------------------------------------------------


async def check_sso_enabled(org_slug: str, db_session: AsyncSession) -> dict:
    org = (await db_session.execute(
        select(Organization).where(Organization.slug == org_slug)
    )).scalars().first()
    if not org:
        return {"sso_enabled": False, "provider": None}
    conn = await _get_connection(org.id, db_session)
    if not conn or not conn.enabled:
        return {"sso_enabled": False, "provider": None}
    return {"sso_enabled": True, "provider": conn.provider}


# ---------------------------------------------------------------------------
# Outbound HTTP with the SSRF guard every other admin-URL-driven call in this
# codebase uses (services/webhooks/dispatch.py, services/utils/link_preview.py)
# ---------------------------------------------------------------------------


async def _guarded_get_json(url: str) -> dict:
    try:
        validated_ips = resolve_and_validate_url(url, allow_http=False)
    except SSRFBlockedError as exc:
        raise SSOFlowError("sso_misconfigured", f"IdP URL rejected: {exc}") from exc

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=False) as client:
        async with client.stream("GET", url) as resp:
            try:
                assert_connected_peer_allowed(resp, validated_ips)
            except SSRFBlockedError as exc:
                raise SSOFlowError("sso_misconfigured", f"IdP connection rejected: {exc}") from exc
            body = await resp.aread()
            if resp.status_code != 200:
                raise SSOFlowError(
                    "sso_misconfigured", f"IdP request to {url} failed ({resp.status_code})"
                )
            return json.loads(body)


async def _guarded_post_form(url: str, data: dict) -> dict:
    try:
        validated_ips = resolve_and_validate_url(url, allow_http=False)
    except SSRFBlockedError as exc:
        raise SSOFlowError("token_exchange_failed", f"IdP token URL rejected: {exc}") from exc

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=False) as client:
        async with client.stream("POST", url, data=data) as resp:
            try:
                assert_connected_peer_allowed(resp, validated_ips)
            except SSRFBlockedError as exc:
                raise SSOFlowError("token_exchange_failed", f"IdP connection rejected: {exc}") from exc
            body = await resp.aread()
            if resp.status_code != 200:
                raise SSOFlowError(
                    "token_exchange_failed", f"Token exchange failed ({resp.status_code}): {body[:200]!r}"
                )
            return json.loads(body)


async def _discover(issuer: str) -> dict:
    return await _guarded_get_json(issuer.rstrip("/") + "/.well-known/openid-configuration")


# ---------------------------------------------------------------------------
# Authorization start
# ---------------------------------------------------------------------------


def _b64url(raw: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) for PKCE S256 — used even though this
    is a confidential client, as defense in depth against authorization-code
    interception (RFC 7636 is written for public clients, but nothing about
    it is harmful for a confidential one, and several IdPs now require it)."""
    import hashlib
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


async def build_authorization_url(org_slug: str, db_session: AsyncSession) -> dict:
    org = (await db_session.execute(
        select(Organization).where(Organization.slug == org_slug)
    )).scalars().first()
    if not org:
        raise SSOFlowError("sso_not_enabled", "Organization not found", status_code=404)

    conn = await _get_connection(org.id, db_session)
    if not conn or not conn.enabled:
        raise SSOFlowError("sso_not_enabled", "SSO is not enabled for this organization.")

    issuer = conn.provider_config.get("issuer")
    client_id = conn.provider_config.get("client_id")
    if not issuer or not client_id:
        raise SSOFlowError("sso_misconfigured", "SSO is not configured correctly. Please contact your administrator.")

    discovery = await _discover(issuer)
    authorization_endpoint = discovery.get("authorization_endpoint")
    if not authorization_endpoint:
        raise SSOFlowError("sso_misconfigured", "IdP discovery document has no authorization_endpoint")

    nonce = secrets.token_urlsafe(24)
    code_verifier, code_challenge = _pkce_pair()
    redirect_uri = _redirect_uri()

    state = create_access_token(
        data={
            "sub": SSO_STATE_PURPOSE,
            "purpose": SSO_STATE_PURPOSE,
            "org_id": org.id,
            "org_slug": org.slug,
            "nonce": nonce,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        expires_delta=SSO_STATE_TTL,
    )

    scope = conn.provider_config.get("scope") or "openid email profile"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return {"authorization_url": f"{authorization_endpoint}?{urlencode(params)}", "state": state}


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------


def _decode_state(state: str) -> dict:
    payload = decode_jwt(state)
    if not payload or payload.get("purpose") != SSO_STATE_PURPOSE:
        raise SSOFlowError("state_invalid_or_expired", "Your SSO session has expired. Please try logging in again.")
    return payload


async def _verify_id_token(id_token: str, discovery: dict, client_id: str, issuer: str, expected_nonce: str) -> dict:
    jwks_uri = discovery.get("jwks_uri")
    if not jwks_uri:
        raise SSOFlowError("sso_misconfigured", "IdP discovery document has no jwks_uri")

    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as exc:
        raise SSOFlowError("token_exchange_failed", f"Malformed ID token: {exc}") from exc
    kid = unverified_header.get("kid")

    jwks = await _guarded_get_json(jwks_uri)
    matching_key = None
    for key in jwks.get("keys", []):
        if kid is None or key.get("kid") == kid:
            matching_key = key
            break
    if matching_key is None:
        raise SSOFlowError("token_exchange_failed", "No matching signing key found in IdP JWKS")

    try:
        public_key = RSAAlgorithm.from_jwk(json.dumps(matching_key))
        claims = jwt.decode(
            id_token,
            key=public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise SSOFlowError("token_exchange_failed", f"ID token verification failed: {exc}") from exc

    if claims.get("nonce") != expected_nonce:
        raise SSOFlowError("token_exchange_failed", "ID token nonce does not match — possible replay")

    return claims


@dataclass
class SSOCallbackResult:
    user: User
    org: Organization
    access_token: str
    refresh_token: str
    redirect_url: str


async def handle_sso_callback(
    request: Request, code: str, state: str, db_session: AsyncSession
) -> SSOCallbackResult:
    state_claims = _decode_state(state)
    org_id = state_claims["org_id"]
    org_slug = state_claims["org_slug"]
    nonce = state_claims["nonce"]
    code_verifier = state_claims["code_verifier"]
    redirect_uri = state_claims["redirect_uri"]

    org = (await db_session.execute(select(Organization).where(Organization.id == org_id))).scalars().first()
    if not org:
        raise SSOFlowError("sso_not_enabled", "Organization not found", status_code=404)

    conn = await _get_connection(org_id, db_session)
    if not conn or not conn.enabled:
        raise SSOFlowError("sso_not_enabled", "SSO is not enabled for this organization.")

    issuer = conn.provider_config.get("issuer")
    client_id = conn.provider_config.get("client_id")
    encrypted_secret = conn.provider_config.get("client_secret_encrypted")
    if not issuer or not client_id or not encrypted_secret:
        raise SSOFlowError("sso_misconfigured", "SSO is not configured correctly. Please contact your administrator.")
    client_secret = decrypt_secret(encrypted_secret)

    discovery = await _discover(issuer)
    token_endpoint = discovery.get("token_endpoint")
    if not token_endpoint:
        raise SSOFlowError("sso_misconfigured", "IdP discovery document has no token_endpoint")

    token_response = await _guarded_post_form(
        token_endpoint,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": code_verifier,
        },
    )
    id_token = token_response.get("id_token")
    if not id_token:
        raise SSOFlowError("token_exchange_failed", "IdP token response had no id_token")

    claims = await _verify_id_token(id_token, discovery, client_id, issuer, nonce)

    email = claims.get("email")
    email_verified = claims.get("email_verified", True)  # some IdPs omit this claim entirely when true
    if not email or not email_verified:
        raise SSOFlowError(
            "user_creation_failed",
            "Your identity provider did not return a verified email address.",
        )
    email = email.lower()

    if conn.domains:
        domain = email.rsplit("@", 1)[-1].lower()
        allowed_domains = {d.lstrip("@").lower() for d in conn.domains}
        if domain not in allowed_domains:
            raise SSOFlowError(
                "domain_not_allowed",
                "Your email domain is not allowed for this organization.",
            )

    given_name = claims.get("given_name") or (claims.get("name") or "").split(" ")[0]
    family_name = claims.get("family_name") or ""

    user = await _resolve_or_provision_user(
        request, org, conn, email, given_name, family_name, db_session
    )

    issue = await issue_session_or_challenge(db_session, user, amr=AUTH_METHOD_SSO, org_id=org.id)
    if issue.mfa_required:
        raise SSOFlowError(
            "callback_failed",
            "This account has two-factor authentication enabled; please sign in "
            "directly on LearnHouse instead of through SSO.",
            status_code=409,
        )
    assert issue.access_token is not None and issue.refresh_token is not None

    await record_audit_event(
        event_type=UserAuditEventType.LOGIN,
        user_id=user.id,
        org_id=org.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"method": "sso", "provider": conn.provider},
    )

    config = get_learnhouse_config()
    scheme = "https" if config.hosting_config.ssl else "http"
    redirect_url = f"{scheme}://{config.hosting_config.frontend_domain}/orgs/{org.slug}/home"

    return SSOCallbackResult(
        user=user, org=org, access_token=issue.access_token, refresh_token=issue.refresh_token,
        redirect_url=redirect_url,
    )


async def _resolve_or_provision_user(
    request: Request,
    org: Organization,
    conn: SSOConnection,
    email: str,
    given_name: str,
    family_name: str,
    db_session: AsyncSession,
) -> User:
    existing = (await db_session.execute(select(User).where(User.email == email))).scalars().first()

    if existing:
        membership = (await db_session.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == existing.id, UserOrganization.org_id == org.id
            )
        )).scalars().first()
        if membership:
            return existing
        if not conn.auto_provision_users:
            raise SSOFlowError(
                "auto_provision_disabled",
                "Your account does not exist. Please contact your administrator for access.",
            )
        await _join_org(existing, org, conn, db_session)
        return existing

    if not conn.auto_provision_users:
        raise SSOFlowError(
            "auto_provision_disabled",
            "Your account does not exist. Please contact your administrator for access.",
        )

    import random as _random
    username_parts = [p for p in (given_name, family_name) if p] or [email.split("@")[0]]
    username = "".join(username_parts) + str(_random.randint(100000, 999999))

    from src.services.users.users import create_user
    from src.db.users import AnonymousUser

    user = await create_user(
        request,
        db_session,
        AnonymousUser(),
        UserCreate(email=email, username=username, password="", first_name=given_name, last_name=family_name),
        org.id,
        is_oauth=True,
        signup_provider="sso",
    )
    assert user.id is not None

    # create_user() already created the UserOrganization row above, but always
    # with the hardcoded default role_id=4 — override it if this connection
    # names a different default_role_id.
    if conn.default_role_id is not None and conn.default_role_id != 4:
        membership = (await db_session.execute(
            select(UserOrganization).where(UserOrganization.user_id == user.id, UserOrganization.org_id == org.id)
        )).scalars().first()
        if membership:
            membership.role_id = conn.default_role_id
            db_session.add(membership)
            await db_session.commit()

    return user


async def _join_org(user: User, org: Organization, conn: SSOConnection, db_session: AsyncSession) -> None:
    """create_user already adds the FIRST org a brand-new account is created
    in; this only runs for an EXISTING account that has no membership in
    THIS org yet, so it must be idempotent-safe on its own."""
    existing_membership = (await db_session.execute(
        select(UserOrganization).where(UserOrganization.user_id == user.id, UserOrganization.org_id == org.id)
    )).scalars().first()
    if existing_membership:
        return

    role_id = conn.default_role_id
    if role_id is None:
        default_role = (await db_session.execute(
            select(Role).where(Role.org_id == org.id, Role.name == "User")
        )).scalars().first()
        role_id = default_role.id if default_role else 4  # global "User" role id, same fallback join.py uses

    now = str(datetime.now())
    db_session.add(UserOrganization(user_id=user.id, org_id=org.id, role_id=role_id, creation_date=now, update_date=now))
    await db_session.commit()

    from src.routers.users import _invalidate_session_cache
    _invalidate_session_cache(user.id)
