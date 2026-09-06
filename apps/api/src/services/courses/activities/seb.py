"""Safe Exam Browser (SEB) integration helpers.

Targets SEB's Config Key mechanism, not the Browser Exam Key: Browser Exam Key
needs SEB's own per-platform signed-executable hash database to verify
against, which isn't something a self-hosted server can replicate. Config Key
is derived purely from the .seb config file plus the loaded URL, which we can
compute and check with stdlib hashlib alone. Requires a current (2024+) SEB
client — this module does not implement the legacy
``X-SafeExamBrowser-RequestHash`` header older SEB releases used instead.

Quit flow: allowQuit is off for the whole exam, so there is no manual quit
button, no Ctrl-Q, no window-close — a student cannot leave mid-exam through
SEB's own UI. quitURL is a dedicated page the frontend navigates the SEB
browser to only after a final submission succeeds; SEB shows its own "Exit
SEB" button once it detects that URL was loaded, no password needed.
hashedQuitPassword gates SEB's *general* quit UI only, which is disabled here
by allowQuit=False — it is a proctor break-glass for a stuck session, not
part of the normal submit-then-exit path.
"""

from __future__ import annotations

import hashlib
import hmac
import plistlib
import secrets
from typing import Optional

from fastapi import Request

SEB_CONFIG_KEY_HEADER = "X-SafeExamBrowser-ConfigKeyHash"


def generate_seb_config_key() -> str:
    """A fresh, random per-assignment Config Key.

    Generated once, the first time SEB is enabled for an assignment, and
    never rotated after — every .seb file already downloaded by a student
    embeds this value, and rotating it would silently lock all of them out.
    """
    return secrets.token_hex(32)


def compute_config_key_hash(url: str, config_key: str) -> str:
    """SHA-256(url + config_key), hex-encoded.

    CAVEAT — NOT VERIFIED AGAINST SEB'S OWN SPEC: this is the commonly
    described form of SEB's Config Key hash (URL concatenated with the key,
    no separator, hashed once), but the primary source
    (safeexambrowser.org/developer) was unreachable from this environment
    (network egress to that domain is blocked here), so this has not been
    confirmed byte-for-byte against a real SEB client. Treat any 403 this
    produces as provisional until you've verified it: point a real SEB
    session at a logging endpoint, capture the actual header value it sends
    for a known URL, and confirm it matches this function's output before
    trusting this gate for a real exam. See the docstring on
    ``verify_seb_headers`` for the same caveat applied to the check itself.
    """
    return hashlib.sha256(f"{url}{config_key}".encode("utf-8")).hexdigest()


def verify_seb_headers(request: Request, config_key: str, expected_url: str) -> bool:
    """True only if this request carries a Config Key hash matching ours.

    ``expected_url`` must be the exact URL embedded as ``startURL`` in the
    .seb file handed to the student — persisted at generation time (see
    Phase 3), not recomputed per request — since SEB hashes the URL of the
    page it actually loaded, and that has to line up exactly with whatever
    we compare against.

    Uses a constant-time comparison since this is a security check, even
    though the inputs here are hex-encoded hashes rather than secrets
    themselves — cheap to do right, no reason not to.

    Same unverified-algorithm caveat as ``compute_config_key_hash`` applies
    here: this check is the enforcement boundary described in the SEB
    integration plan, and it has not yet been validated against a real SEB
    client's actual header value. Do not treat a passing check as a
    confirmed security guarantee until that validation has been done once,
    against a real exam-room machine.
    """
    received = request.headers.get(SEB_CONFIG_KEY_HEADER)
    if not received:
        return False
    expected = compute_config_key_hash(expected_url, config_key)
    return hmac.compare_digest(received.strip().lower(), expected.lower())


def hash_quit_password(password: str) -> str:
    """SHA-256 hex digest, the form SEB's hashedQuitPassword setting expects."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def build_seb_config_plist(
    exam_url: str,
    config_key: str,
    quit_url: str,
    quit_password: Optional[str] = None,
) -> bytes:
    """Build a plain (unencrypted) .seb config file as an XML plist.

    Unencrypted is a deliberate self-host simplification: the Config Key
    hash check works the same whether the .seb file itself is encrypted,
    and SEB's own file encryption adds a password-based key-derivation
    format that buys nothing here since you distribute the file to lab
    machines directly rather than over an untrusted channel.
    """
    config = {
        "startURL": exam_url,
        "sendBrowserExamKey": True,
        "browserExamKey": config_key,
        "allowQuit": False,
        "quitURL": quit_url,
        "quitURLConfirm": False,
    }
    if quit_password:
        config["hashedQuitPassword"] = hash_quit_password(quit_password)

    return plistlib.dumps(config)
