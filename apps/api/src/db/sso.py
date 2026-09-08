"""SSO (OpenID Connect) — one connection per organization.

SCOPE DECISION: OIDC only, not SAML. The ``provider`` field on the table
(and this file's original migration) anticipated ``custom_saml`` as a value,
but a correct SAML 2.0 implementation needs XML canonicalization and XML
digital-signature verification done exactly right (XSW/wrapping-attack
resistance in particular) — the kind of thing you use a vetted library for,
not hand-roll, and this project has no SAML dependency. Every provider this
module actually supports — Keycloak, Okta, Auth0, or any other IdP via
``custom_oidc`` — is reached through the exact same generic OIDC
discovery + authorization-code-flow path, since they all expose a standard
``/.well-known/openid-configuration`` document. ``workos`` (a third-party
paid SSO-as-a-service product) is also not implemented — it would reintroduce
an external paid dependency for a project whose whole point is self-hosting
without vendor lock-in.

One ``SSOConnection`` row = one organization's OIDC configuration. The
``ix_ssoconnection_org_id`` unique index (already present in the original
migration) enforces one connection per org — simpler than a multi-IdP story
for a first implementation, and every provider this module supports covers
the "one campus IdP" case a self-hosted college actually has.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, JSON, Boolean, DateTime, func
from sqlmodel import Field, SQLModel

# The only provider values this module actually implements. Kept separate
# from the frontend's broader SSOProvider union (which also lists ``workos``
# and ``custom_saml``) — the API rejects anything outside this set rather
# than silently accepting a value it cannot act on.
SUPPORTED_OIDC_PROVIDERS: frozenset[str] = frozenset(
    {"keycloak", "okta", "auth0", "custom_oidc"}
)


class SSOConnection(SQLModel, table=True):
    """An organization's single OIDC SSO configuration."""

    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    provider: str = ""
    enabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    # List[str] of allowed email domains ("" / [] = no restriction, any
    # verified IdP email may sign in).
    domains: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))
    auto_provision_users: bool = Field(
        default=True, sa_column=Column(Boolean, nullable=False, server_default="true")
    )
    default_role_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, ForeignKey("role.id", ondelete="SET NULL"), nullable=True)
    )
    # {"issuer": ..., "client_id": ..., "client_secret_encrypted": ..., "scope": ...}
    # The secret is encrypted at rest with the same Fernet helper webhook
    # signing secrets use (services/webhooks/crypto.py) — never stored plain.
    provider_config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=True, server_default="{}"))
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


# ---------------------------------------------------------------------------
# Pydantic schemas — field names/shape match apps/web/services/auth/sso.ts
# exactly, since that client was already written against this contract.
# ---------------------------------------------------------------------------


class SSOProviderConfigIn(BaseModel):
    """What an admin actually types in. ``client_secret`` is write-only —
    never echoed back by any read endpoint."""

    issuer: str
    client_id: str
    client_secret: Optional[str] = None
    scope: Optional[str] = None


class SSOConfigCreate(BaseModel):
    provider: str
    enabled: bool = False
    domains: list[str] = []
    auto_provision_users: bool = True
    default_role_id: Optional[int] = None
    provider_config: SSOProviderConfigIn


class SSOConfigUpdate(BaseModel):
    provider: Optional[str] = None
    enabled: Optional[bool] = None
    domains: Optional[list[str]] = None
    auto_provision_users: Optional[bool] = None
    default_role_id: Optional[int] = None
    provider_config: Optional[SSOProviderConfigIn] = None


class SSOConfigRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    org_id: int
    provider: str
    enabled: bool
    domains: list[str]
    auto_provision_users: bool
    default_role_id: Optional[int]
    # client_secret deliberately omitted — write-only.
    provider_config: dict
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class SSOProviderInfo(BaseModel):
    id: str
    name: str
    description: str
    has_setup_portal: bool
    available: bool
    config_fields: list[dict]


class SSOLoginCheckResponse(BaseModel):
    sso_enabled: bool
    provider: Optional[str] = None


class SSOAuthorizationResponse(BaseModel):
    authorization_url: str
    state: str
