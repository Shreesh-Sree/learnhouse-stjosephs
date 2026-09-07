"""Campus IP allowlisting for assignment submission.

ENFORCEMENT GATE: `_enforce_ip_allowlist_if_required`, called at the same
submission-mutating call sites as `_enforce_seb_if_required` in
`services.courses.activities.assignments`. Same exemptions: an instructor
previewing/grading isn't sitting the exam, and a token writing on behalf of a
learner is an authorized external integration that owns its own access
control.

Client IP resolution is delegated to `services.security.rate_limiting.
get_client_ip`, the one already-vetted place in this codebase that decides
when to trust `X-Forwarded-For`/`X-Real-IP` (only when the direct TCP peer is
itself a private/loopback address, i.e. a local reverse proxy) rather than
inventing a second, possibly-inconsistent implementation here.

FAIL-CLOSED ON MISCONFIGURATION: if the allowlist is turned on but contains
no parseable entries, no request matches, so every non-exempt request is
blocked rather than silently let through. A security toggle that can be
accidentally defeated by an empty text field is worse than one that visibly
locks everyone out until fixed — the instructor exemption means the teacher
who made the mistake can still get in to fix it.
"""

from __future__ import annotations

import ipaddress
from typing import Optional, Union

from fastapi import HTTPException, Request

from src.services.security.rate_limiting import get_client_ip

_IpNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def parse_ip_allowlist(raw: Optional[str]) -> list[_IpNetwork]:
    """Parse a newline/comma-separated allowlist into IP networks.

    Accepts bare addresses (widened to /32 or /128) and CIDR ranges.
    Blank lines and lines starting with ``#`` are ignored so a teacher can
    annotate entries ("# Lab 3 desktops"). Unparseable entries are silently
    skipped rather than raising — one typo shouldn't 500 the whole endpoint;
    it just doesn't grant access, which fail-closed already handles.
    """
    if not raw:
        return []

    entries: list[str] = []
    for line in raw.replace(",", "\n").splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            entries.append(entry)

    networks: list[_IpNetwork] = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return networks


def is_ip_allowed(client_ip: str, raw_allowlist: Optional[str]) -> bool:
    """True if ``client_ip`` falls inside any network in ``raw_allowlist``.

    False for an unparseable client IP (e.g. "unknown", when the request has
    no discoverable peer address at all) and for an allowlist with no valid
    entries — both fail closed, per the module docstring.
    """
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for network in parse_ip_allowlist(raw_allowlist):
        if addr in network:
            return True
    return False


def _enforce_ip_allowlist_if_required(
    assignment,
    request: Request,
    is_instructor: bool,
    is_token_submit: bool,
) -> None:
    """Raise 403 if this assignment restricts submission to an IP allowlist
    and this request's resolved client IP isn't in it.
    """
    if not getattr(assignment, "require_ip_allowlist", False):
        return
    if is_instructor or is_token_submit:
        return
    client_ip = get_client_ip(request)
    if not is_ip_allowed(client_ip, getattr(assignment, "ip_allowlist", None)):
        raise HTTPException(
            status_code=403,
            detail="This assignment can only be submitted from an allowed network.",
        )
