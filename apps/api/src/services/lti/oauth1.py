"""Minimal OAuth 1.0a request-signature verification, for LTI 1.1 launches.

LTI 1.1 (the version this integration targets — see services/lti/lti.py for the
scope decision) signs its launch POST with OAuth 1.0a HMAC-SHA1 over the launch
parameters themselves, using a consumer key/secret shared out-of-band with the
external LMS. There is no OAuth *token* in an LTI launch (no three-legged
flow) — only the two-legged consumer-key/consumer-secret signature, so
``token_secret`` below is always empty.

Hand-rolled rather than an ``oauthlib`` dependency, to stay inside an LTI
launch's narrow, fully-specified signing scheme (HMAC-SHA1 over a
x-www-form-urlencoded POST body) rather than pulling in a general-purpose
three-legged OAuth client/server library for one signature check.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import quote


def _percent_encode(value: str) -> str:
    """RFC 3986 percent-encoding, OAuth 1.0a's unreserved set (RFC 5849 §3.6):
    ``A-Za-z0-9-._~`` are never encoded. ``urllib.parse.quote``'s default
    ``safe="/"`` would leave slashes in parameter values un-encoded, which is
    wrong here — every reserved character in a value must be escaped.
    """
    return quote(value, safe="-._~")


def _normalize_params(params: dict[str, str]) -> str:
    """Build the normalized parameter string: percent-encode every key/value,
    then sort the pairs lexicographically by (encoded key, encoded value) and
    join as ``key=value`` pairs with ``&`` (RFC 5849 §3.4.1.3.2).
    """
    encoded_pairs = [
        (_percent_encode(str(k)), _percent_encode(str(v))) for k, v in params.items()
    ]
    encoded_pairs.sort()
    return "&".join(f"{k}={v}" for k, v in encoded_pairs)


def build_signature_base_string(
    http_method: str, base_url: str, params: dict[str, str]
) -> str:
    """RFC 5849 §3.4.1: method + base URL (no query/fragment) + normalized
    params, each percent-encoded and joined with ``&``. ``params`` must
    already exclude ``oauth_signature`` (it signs everything else, including
    itself being absent) and ``realm`` (not part of the signature).
    """
    normalized = _normalize_params(params)
    return "&".join(
        [
            http_method.upper(),
            _percent_encode(base_url),
            _percent_encode(normalized),
        ]
    )


def compute_signature(
    http_method: str,
    base_url: str,
    params: dict[str, str],
    consumer_secret: str,
    token_secret: str = "",
) -> str:
    """Return the base64-encoded HMAC-SHA1 signature for the request."""
    base_string = build_signature_base_string(http_method, base_url, params)
    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"
    digest = hmac.new(
        signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_signature(
    http_method: str,
    base_url: str,
    params: dict[str, str],
    consumer_secret: str,
    provided_signature: str,
    token_secret: str = "",
) -> bool:
    """Constant-time comparison of the request's own ``oauth_signature``
    against the one we compute from every OTHER parameter it sent.
    ``params`` must have ``oauth_signature`` already removed by the caller.
    """
    expected = compute_signature(
        http_method, base_url, params, consumer_secret, token_secret
    )
    return hmac.compare_digest(expected, provided_signature)
