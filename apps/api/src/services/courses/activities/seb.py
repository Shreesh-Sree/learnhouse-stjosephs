"""Safe Exam Browser (SEB) integration helpers.

ENFORCEMENT GATE: the User-Agent check (`is_seb_user_agent`). Every SEB build
identifies itself with a "SEB/<version>" token in its User-Agent (e.g.
"...SEB/3.6.2 (SEB_WIN)"), consistent across the Windows/Mac/iOS clients. This
is what `assignments.py`'s submission checks actually gate on. It is a plain
string check, not a cryptographic proof — a student's own HTTP client could
fake it — but it is something this module can actually stand behind, unlike
the alternative below.

WHY NOT THE CONFIG KEY HASH: SEB also sends `X-SafeExamBrowser-ConfigKeyHash`,
computed (confirmed against SEB's own open-source
SafeExamBrowser.Configuration/Cryptography/KeyGenerator.cs) as:

    SHA256(url_with_fragment_stripped + configurationKey), lowercase hex

`configurationKey` there is NOT a value an admin sets in the .seb file — there
is no such field in SEB's config schema (checked the full key list in
SafeExamBrowser.Configuration/ConfigurationData/Keys.cs). SEB derives it
internally by hashing its own loaded settings file's content, using
canonicalization rules that are not published anywhere reachable from this
environment (safeexambrowser.org and docs.moodle.org are both blocked by this
session's network egress). Reproducing that hash server-side would mean
matching SEB's exact internal serialization byte-for-byte, unverified and
version-dependent — a check that could either always fail (blocking every
real student) or, worse, look like a security guarantee while verifying
nothing. So this module captures that header for an audit trail
(`capture_seb_headers`) but does not gate anything on it. If you want a
stronger gate than User-Agent later, the only reliable path is empirical:
capture the actual header value from a real SEB session against a known URL
and work out what it's hashing from that, rather than guess further.

Quit flow (unaffected by the above): allowQuit is off for the whole exam, so
there is no manual quit button, no Ctrl-Q, no window-close — a student cannot
leave mid-exam through SEB's own UI. quitURL is a dedicated page the frontend
navigates the SEB browser to only after a final submission succeeds; SEB
shows its own "Exit SEB" button once it detects that URL was loaded, no
password needed. hashedQuitPassword gates SEB's *general* quit UI only, which
is disabled here by allowQuit=False — it is a proctor break-glass for a stuck
session, not part of the normal submit-then-exit path. All four plist key
names (allowQuit, quitURL, quitURLConfirm, hashedQuitPassword) are confirmed
literal, verbatim, against SEB's own Keys.cs.
"""

from __future__ import annotations

import hashlib
import plistlib
import re
import secrets
from typing import Optional

from fastapi import Request

SEB_CONFIG_KEY_HEADER = "X-SafeExamBrowser-ConfigKeyHash"
# Legacy header from older SEB releases. Not implemented as a gate — this
# integration targets current SEB only (see the integration plan) — kept
# here only so `capture_seb_headers` can log it if a stray old client sends
# it, for troubleshooting.
SEB_LEGACY_REQUEST_HASH_HEADER = "X-SafeExamBrowser-RequestHash"

_SEB_USER_AGENT_RE = re.compile(r"\bSEB[/ ]", re.IGNORECASE)


def is_seb_user_agent(request: Request) -> bool:
    """True if this request's User-Agent identifies a Safe Exam Browser client.

    This is the enforcement gate — see the module docstring for why it's a
    User-Agent check rather than a cryptographic one. A student who
    deliberately spoofs their User-Agent defeats this; it stops accidental
    or casual use of a regular browser, which is the realistic threat for a
    self-hosted deployment, not a nation-state adversary.
    """
    user_agent = request.headers.get("user-agent", "")
    return bool(_SEB_USER_AGENT_RE.search(user_agent))


def generate_seb_config_key() -> str:
    """A fresh, random per-assignment token, stored so the same value is
    reused across every .seb file regenerated for this assignment. Not a
    SEB-verified secret (see module docstring) — used only as the salt-like
    input to `compute_config_key_hash` for audit-log comparison, and as a
    stable identifier tying a .seb download back to the assignment that
    issued it.
    """
    return secrets.token_hex(32)


def compute_config_key_hash(url: str, config_key: str) -> str:
    """Reproduces SEB's outer hashing step for X-SafeExamBrowser-ConfigKeyHash.

    AUDIT-LOGGING HELPER ONLY — see the module docstring for why this is not
    a verification gate: SEB's real `configurationKey` input is derived
    internally from the loaded config file, which nothing here recomputes,
    so ``config_key`` here is at best a placeholder. What IS confirmed
    correct, against SEB's own KeyGenerator.cs, is the outer shape: strip the
    URL fragment, concatenate with the key, SHA-256, lowercase hex.
    """
    url_without_fragment = url.split("#", 1)[0]
    return hashlib.sha256(
        f"{url_without_fragment}{config_key}".encode("utf-8")
    ).hexdigest()


def capture_seb_headers(request: Request) -> dict[str, Optional[str]]:
    """Raw SEB-related headers off this request, for the submission's audit
    trail. Recorded, not verified — see module docstring."""
    return {
        "config_key_hash": request.headers.get(SEB_CONFIG_KEY_HEADER),
        "legacy_request_hash": request.headers.get(SEB_LEGACY_REQUEST_HASH_HEADER),
        "user_agent": request.headers.get("user-agent"),
    }


def hash_quit_password(password: str) -> str:
    """SHA-256 hex digest, the form SEB's hashedQuitPassword setting expects."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def build_seb_config_plist(
    exam_url: str,
    quit_url: str,
    quit_password: Optional[str] = None,
) -> bytes:
    """Build a plain (unencrypted) .seb config file as an XML plist.

    Unencrypted is a deliberate self-host simplification: you distribute this
    file to lab machines directly rather than over an untrusted channel, so
    SEB's own file encryption (a separate password-based key-derivation
    format) buys nothing here.

    Every plist key below is confirmed literal against SEB's own
    SafeExamBrowser.Configuration/ConfigurationData/Keys.cs — this file does
    NOT include a made-up "browserExamKey" field (an earlier draft of this
    module invented one; there is no such field in SEB's schema).
    """
    config = {
        "startURL": exam_url,
        "sendBrowserExamKey": True,
        "allowQuit": False,
        "quitURL": quit_url,
        "quitURLConfirm": False,
    }
    if quit_password:
        config["hashedQuitPassword"] = hash_quit_password(quit_password)

    return plistlib.dumps(config)
