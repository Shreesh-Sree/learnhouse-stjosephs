"""Tests for src/services/auth/sso_oidc.py — the pure, no-DB, no-network
pieces: ID-token verification, PKCE, and provider validation.

The DB-writing paths (_resolve_or_provision_user, _join_org, the admin CRUD
functions) and the live discovery/token-exchange HTTP calls were verified by
hand against a real Postgres 16 database and a live backend in this session
(see PENDING_FEATURES.md) rather than committed here as a test — this
sandbox's outbound HTTPS is forced through a local intercepting proxy, which
makes assert_connected_peer_allowed's peer check reject every real external
call as a matter of course (see services/utils/ssrf_guard.py); nothing here
mocks around that, since doing so would test a code path that never actually
runs the way the mock pretends.
"""

import base64
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

import src.services.auth.sso_oidc as sso_oidc
from src.services.auth.sso_oidc import (
    SSOFlowError,
    _pkce_pair,
    _validate_provider,
    _verify_id_token,
    get_provider_catalog,
)


class TestProviderCatalog:
    def test_catalog_has_exactly_the_supported_providers(self):
        ids = {p.id for p in get_provider_catalog()}
        assert ids == {"keycloak", "okta", "auth0", "custom_oidc"}

    def test_every_provider_requires_issuer_and_client_id(self):
        for provider in get_provider_catalog():
            field_names = {f["name"] for f in provider.config_fields}
            assert "issuer" in field_names
            assert "client_id" in field_names

    @pytest.mark.parametrize("provider_id", ["keycloak", "okta", "auth0", "custom_oidc"])
    def test_validate_provider_accepts_supported(self, provider_id):
        _validate_provider(provider_id)  # must not raise

    @pytest.mark.parametrize("provider_id", ["workos", "custom_saml", "google", ""])
    def test_validate_provider_rejects_unsupported(self, provider_id):
        with pytest.raises(HTTPException) as exc_info:
            _validate_provider(provider_id)
        assert exc_info.value.status_code == 400


class TestPkce:
    def test_verifier_and_challenge_differ(self):
        verifier, challenge = _pkce_pair()
        assert verifier != challenge

    def test_challenge_is_sha256_s256_of_verifier(self):
        import hashlib
        verifier, challenge = _pkce_pair()
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        assert challenge == expected

    def test_two_calls_produce_different_verifiers(self):
        v1, _ = _pkce_pair()
        v2, _ = _pkce_pair()
        assert v1 != v2

    def test_challenge_has_no_padding_or_unsafe_chars(self):
        _, challenge = _pkce_pair()
        assert "=" not in challenge
        assert "+" not in challenge and "/" not in challenge


# ---------------------------------------------------------------------------
# ID token verification — real RS256 signatures against a real keypair, the
# JWKS fetch monkeypatched (the only network call _verify_id_token makes) so
# the actual jwt.decode() signature/claims verification runs unmocked.
# ---------------------------------------------------------------------------

ISSUER = "https://idp.test"
CLIENT_ID = "test-client"
NONCE = "test-nonce-123"


@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    numbers = private_key.public_key().public_numbers()

    def b64url_uint(n: int, length: int) -> str:
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

    jwk = {
        "kty": "RSA", "kid": "test-key-1", "use": "sig", "alg": "RS256",
        "n": b64url_uint(numbers.n, 256), "e": b64url_uint(numbers.e, 3),
    }
    return pem_private, jwk


def _make_id_token(pem_private, **overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "iss": ISSUER, "aud": CLIENT_ID, "sub": "user-123",
        "email": "student@school.dev", "email_verified": True,
        "nonce": NONCE, "exp": now + timedelta(minutes=5), "iat": now,
    }
    payload.update(overrides)
    return jwt.encode(payload, pem_private, algorithm="RS256", headers={"kid": "test-key-1"})


@pytest.fixture
def mock_jwks(monkeypatch, rsa_keypair):
    _, jwk = rsa_keypair

    async def fake_guarded_get_json(url):
        assert url == "https://idp.test/jwks"
        return {"keys": [jwk]}

    monkeypatch.setattr(sso_oidc, "_guarded_get_json", fake_guarded_get_json)


DISCOVERY = {"jwks_uri": "https://idp.test/jwks", "token_endpoint": "https://idp.test/token"}


class TestVerifyIdToken:
    @pytest.mark.asyncio
    async def test_valid_token_returns_claims(self, rsa_keypair, mock_jwks):
        pem_private, _ = rsa_keypair
        token = _make_id_token(pem_private)
        claims = await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)
        assert claims["email"] == "student@school.dev"
        assert claims["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_wrong_nonce_rejected(self, rsa_keypair, mock_jwks):
        pem_private, _ = rsa_keypair
        token = _make_id_token(pem_private, nonce="someone-elses-nonce")
        with pytest.raises(SSOFlowError):
            await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected(self, rsa_keypair, mock_jwks):
        pem_private, _ = rsa_keypair
        token = _make_id_token(pem_private, aud="some-other-client")
        with pytest.raises(SSOFlowError):
            await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)

    @pytest.mark.asyncio
    async def test_wrong_issuer_rejected(self, rsa_keypair, mock_jwks):
        pem_private, _ = rsa_keypair
        token = _make_id_token(pem_private, iss="https://evil.test")
        with pytest.raises(SSOFlowError):
            await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, rsa_keypair, mock_jwks):
        pem_private, _ = rsa_keypair
        now = datetime.now(timezone.utc)
        token = _make_id_token(pem_private, exp=now - timedelta(minutes=1), iat=now - timedelta(minutes=10))
        with pytest.raises(SSOFlowError):
            await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)

    @pytest.mark.asyncio
    async def test_unmatched_kid_rejected(self, rsa_keypair, monkeypatch):
        pem_private, jwk = rsa_keypair
        other_jwk = dict(jwk, kid="a-different-key")

        async def fake_guarded_get_json(url):
            return {"keys": [other_jwk]}

        monkeypatch.setattr(sso_oidc, "_guarded_get_json", fake_guarded_get_json)
        token = _make_id_token(pem_private)
        with pytest.raises(SSOFlowError):
            await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)

    @pytest.mark.asyncio
    async def test_token_signed_with_different_key_rejected(self, mock_jwks):
        # A token signed by a keypair the IdP's JWKS never advertised at all —
        # simulates an attacker with their own valid-shaped RS256 token.
        forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem_forged = forged_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        token = _make_id_token(pem_forged)
        with pytest.raises(SSOFlowError):
            await _verify_id_token(token, DISCOVERY, CLIENT_ID, ISSUER, NONCE)
