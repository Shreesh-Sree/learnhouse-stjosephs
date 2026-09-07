"""LTI 1.1 tool-provider links and launch handling.

See db/lti.py for the scope decision (Tool Provider only, LTI 1.1 not 1.3)
and the per-course-link credential model. This module has two halves:

- Admin-facing: create/list/revoke an ``LTILink`` for a course (mirrors the
  webhook-endpoint admin flow in services/webhooks/webhooks.py).
- Launch-facing: verify an incoming OAuth 1.0a-signed launch POST, resolve or
  provision the LearnHouse account it belongs to, enroll it in the link's
  course, and mint a real session for it.
"""

from __future__ import annotations

import hashlib
import logging
import random
import secrets
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config.config import get_learnhouse_config
from src.db.courses.courses import Course
from src.db.lti import LTILink, LTILinkCreate, LTILinkCreatedResponse, LTILinkRead, LTIUserMapping
from src.db.organizations import Organization
from src.db.trail_runs import TrailRun
from src.db.user_audit_events import UserAuditEventType
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User, UserCreate
from src.security.rbac import AccessAction, check_resource_access
from src.security.session_context import AUTH_METHOD_LTI
from src.services.audit.audit import record_audit_event
from src.services.auth.session import issue_session_or_challenge
from src.services.trail.trail import check_trail_presence
from src.services.webhooks.crypto import decrypt_secret, encrypt_secret
from src.services.lti.oauth1 import verify_signature

logger = logging.getLogger(__name__)

# How long an incoming launch's oauth_timestamp may lag behind "now" before
# it is refused as stale. Generous enough for real clock skew between a
# college's LMS server and this one; short enough that a captured launch POST
# cannot be replayed hours or days later even if its nonce were somehow not
# checked.
LAUNCH_FRESHNESS_SECONDS = 5 * 60


def _build_launch_url(link_uuid: str) -> str:
    config = get_learnhouse_config()
    scheme = "https" if config.hosting_config.ssl else "http"
    # Deliberately the API's own domain (not frontend_domain): the launch POST
    # from the external LMS lands directly on the backend, which verifies the
    # signature and only then redirects the browser to the frontend course
    # page. There is no existing "API base URL" config helper — signup/email
    # links all resolve to the *frontend* — so this is read directly from the
    # same LEARNHOUSE_API_DOMAIN-shaped setting API clients already use.
    import os

    api_domain = os.environ.get("LEARNHOUSE_API_DOMAIN") or f"api.{config.hosting_config.frontend_domain}"
    return f"{scheme}://{api_domain}/lti/launch/{link_uuid}"


async def create_lti_link(
    request: Request,
    course_uuid: str,
    link_create: LTILinkCreate,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> LTILinkCreatedResponse:
    """Instructor-only. Mints a fresh consumer_key/secret pair bound to this
    one course. The plaintext secret is returned only here — it is stored
    encrypted (see services/webhooks/crypto.py) and never re-shown."""
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    consumer_key = secrets.token_urlsafe(24)
    consumer_secret = secrets.token_urlsafe(32)
    link_uuid = f"ltilink_{uuid4()}"

    link = LTILink(
        link_uuid=link_uuid,
        org_id=course.org_id,
        course_id=course.id if course.id is not None else 0,
        consumer_key=consumer_key,
        consumer_secret_encrypted=encrypt_secret(consumer_secret),
        label=link_create.label,
        created_by_user_id=current_user.id,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)

    return LTILinkCreatedResponse(
        link_uuid=link.link_uuid,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        label=link.label,
        launch_url=_build_launch_url(link.link_uuid),
        creation_date=link.creation_date,
    )


async def get_lti_links_for_course(
    request: Request,
    course_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[LTILinkRead]:
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    links = (await db_session.execute(
        select(LTILink).where(LTILink.course_id == course.id).order_by(LTILink.creation_date.desc())  # type: ignore
    )).scalars().all()

    return [
        LTILinkRead(
            link_uuid=link.link_uuid,
            course_id=link.course_id,
            consumer_key=link.consumer_key,
            label=link.label,
            is_active=link.is_active,
            launch_url=_build_launch_url(link.link_uuid),
            created_by_user_id=link.created_by_user_id,
            creation_date=link.creation_date,
        )
        for link in links
    ]


async def revoke_lti_link(
    request: Request,
    course_uuid: str,
    link_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    link_statement = select(LTILink).where(
        LTILink.link_uuid == link_uuid, LTILink.course_id == course.id
    )
    link = (await db_session.execute(link_statement)).scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="LTI link not found")

    # Soft-revoke rather than delete: keeps the LTIUserMapping rows (and the
    # launch history they imply) intact, and a stale/misconfigured external
    # tool config that still POSTs to this URL gets a clean rejection instead
    # of a confusing "link not found".
    link.is_active = False
    link.update_date = str(datetime.now())
    db_session.add(link)
    await db_session.commit()

    return {"detail": "LTI link revoked"}


class LTILaunchError(Exception):
    """Raised for any launch that must be rejected before a session can be
    minted. Carries a human-readable reason for the error page."""

    def __init__(self, reason: str, status_code: int = 401):
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


def _check_nonce_fresh(consumer_key: str, nonce: str, timestamp: str) -> None:
    """Reject a launch whose timestamp is stale, or whose (consumer_key,
    nonce) pair has already been used — the two independent defenses RFC
    5849 §3.3 calls for against replaying a captured launch POST.

    Best-effort: if Redis is unavailable, skip the nonce-dedup half rather
    than failing every launch (the signature check + timestamp freshness
    already rule out a launch older than ``LAUNCH_FRESHNESS_SECONDS``, so a
    Redis outage narrows replay protection to "rare and attacker doesn't get
    the cache state" rather than eliminating it as a backend outage would).
    """
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        raise LTILaunchError("Invalid oauth_timestamp")

    if abs(time.time() - ts) > LAUNCH_FRESHNESS_SECONDS:
        raise LTILaunchError("Launch request has expired — check server clocks and retry")

    redis_url = get_learnhouse_config().redis_config.redis_connection_string
    if not redis_url:
        return
    r = None
    try:
        import redis as _redis

        r = _redis.Redis.from_url(redis_url)
        key = f"lti_nonce:{consumer_key}:{nonce}"
        # NX: first writer wins. A second launch presenting the same nonce
        # within the freshness window is a replay.
        if not r.set(key, "1", nx=True, ex=LAUNCH_FRESHNESS_SECONDS + 60):
            raise LTILaunchError("This launch has already been used (replayed nonce)")
    except LTILaunchError:
        raise
    except Exception:
        logger.warning("LTI nonce-dedup check failed open (Redis unavailable)", exc_info=True)
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:
                pass


async def _resolve_or_provision_user(
    request: Request,
    link: LTILink,
    lti_user_id: str,
    email: Optional[str],
    given_name: str,
    family_name: str,
    db_session: AsyncSession,
) -> User:
    mapping_statement = select(LTIUserMapping).where(
        LTIUserMapping.consumer_key == link.consumer_key,
        LTIUserMapping.lti_user_id == lti_user_id,
    )
    mapping = (await db_session.execute(mapping_statement)).scalars().first()
    if mapping:
        user = (await db_session.execute(
            select(User).where(User.id == mapping.user_id)
        )).scalars().first()
        if user:
            return user
        # The mapped account was deleted out from under the mapping — fall
        # through and provision/re-match a fresh one rather than erroring.

    # No mapping yet. If the launch carried a verified-looking email that
    # already belongs to an org member, link to that account instead of
    # creating a duplicate — the common case of a student who already has a
    # LearnHouse account from a direct signup.
    user: Optional[User] = None
    if email:
        from src.security.org_auth import is_org_member

        existing = (await db_session.execute(
            select(User).where(User.email == email)
        )).scalars().first()
        if existing and await is_org_member(existing.id, link.org_id, db_session):
            user = existing

    if user is None:
        # Provision a brand-new account. No email was usable — not every LMS
        # releases it by default (Canvas/Moodle both gate it behind an
        # explicit "include email" privacy setting on the tool config) — so
        # fall back to a synthetic, clearly-marked placeholder address under
        # the IANA-reserved .invalid TLD (RFC 2606 §2) rather than either
        # failing the launch or guessing a real-looking address that might
        # collide with someone else's.
        if not email:
            digest = hashlib.sha256(f"{link.consumer_key}:{lti_user_id}".encode()).hexdigest()[:16]
            email = f"lti.{digest}@lti.invalid"

        username_parts = [p for p in (given_name, family_name) if p]
        if not username_parts:
            username_parts = [email.split("@")[0]]
        username = "".join(username_parts) + str(random.randint(100000, 999999))

        user_object = UserCreate(
            email=email,
            username=username,
            password="",
            first_name=given_name,
            last_name=family_name,
        )
        from src.services.users.users import create_user

        user = await create_user(
            request,
            db_session,
            AnonymousUser(),
            user_object,
            link.org_id,
            is_oauth=True,
            signup_provider="lti",
        )
        assert user.id is not None

    db_session.add(
        LTIUserMapping(
            consumer_key=link.consumer_key,
            lti_user_id=lti_user_id,
            user_id=user.id,
            creation_date=str(datetime.now()),
        )
    )
    await db_session.commit()
    return user


async def _ensure_enrolled(request: Request, user: User, course: Course, db_session: AsyncSession) -> None:
    existing = (await db_session.execute(
        select(TrailRun).where(TrailRun.course_id == course.id, TrailRun.user_id == user.id)
    )).scalars().first()
    if existing:
        return

    trail = await check_trail_presence(
        org_id=course.org_id, user_id=user.id, request=request, user=user, db_session=db_session
    )
    db_session.add(
        TrailRun(
            trail_id=trail.id if trail.id is not None else 0,
            course_id=course.id if course.id is not None else 0,
            org_id=course.org_id,
            user_id=user.id,
            creation_date=str(datetime.now()),
            update_date=str(datetime.now()),
        )
    )
    await db_session.commit()
    await record_audit_event(
        event_type=UserAuditEventType.COURSE_ENROLLED,
        user_id=user.id,
        org_id=course.org_id,
        target_uuid=course.course_uuid,
        metadata={"course_name": course.name, "via": "lti_launch"},
    )


async def handle_lti_launch(
    request: Request,
    link_uuid: str,
    form_params: dict[str, str],
    launch_url: str,
    db_session: AsyncSession,
) -> tuple[User, Course, Organization, str, str]:
    """Verify the launch and return ``(user, course, org, access_token,
    refresh_token)`` for the router to turn into a redirect + cookies.

    Raises :class:`LTILaunchError` for any rejection — the router renders it
    as a small error page rather than a redirect, since there is no
    authenticated user yet to send anywhere.
    """
    link_statement = select(LTILink).where(LTILink.link_uuid == link_uuid, LTILink.is_active == True)  # noqa: E712
    link = (await db_session.execute(link_statement)).scalars().first()
    if not link:
        raise LTILaunchError("This LTI link is invalid or has been revoked", status_code=404)

    provided_consumer_key = form_params.get("oauth_consumer_key")
    if provided_consumer_key != link.consumer_key:
        raise LTILaunchError("Consumer key does not match this link")

    provided_signature = form_params.get("oauth_signature")
    if not provided_signature:
        raise LTILaunchError("Missing oauth_signature")

    signed_params = {k: v for k, v in form_params.items() if k != "oauth_signature"}
    consumer_secret = decrypt_secret(link.consumer_secret_encrypted)
    if not verify_signature("POST", launch_url, signed_params, consumer_secret, provided_signature):
        raise LTILaunchError("Invalid OAuth signature")

    _check_nonce_fresh(
        link.consumer_key,
        form_params.get("oauth_nonce", ""),
        form_params.get("oauth_timestamp", "0"),
    )

    message_type = form_params.get("lti_message_type", "")
    if message_type != "basic-lti-launch-request":
        raise LTILaunchError(f"Unsupported lti_message_type: {message_type!r}")

    lti_user_id = form_params.get("user_id")
    if not lti_user_id:
        raise LTILaunchError("Launch did not include a user_id")

    course_statement = select(Course).where(Course.id == link.course_id)
    course = (await db_session.execute(course_statement)).scalars().first()
    if not course:
        raise LTILaunchError("The course this link points to no longer exists", status_code=404)

    org_statement = select(Organization).where(Organization.id == link.org_id)
    org = (await db_session.execute(org_statement)).scalars().first()
    if not org:
        raise LTILaunchError("Organization not found", status_code=404)

    email = form_params.get("lis_person_contact_email_primary") or None
    given_name = form_params.get("lis_person_name_given", "")
    family_name = form_params.get("lis_person_name_family", "")

    user = await _resolve_or_provision_user(
        request, link, lti_user_id, email, given_name, family_name, db_session
    )
    await _ensure_enrolled(request, user, course, db_session)

    issue = await issue_session_or_challenge(db_session, user, amr=AUTH_METHOD_LTI, org_id=org.id)
    if issue.mfa_required:
        # No channel to prompt for a TOTP code inside an LMS-embedded launch.
        # Documented limitation — see PENDING_FEATURES.md.
        raise LTILaunchError(
            "This account has two-factor authentication enabled; please sign in "
            "directly on LearnHouse instead of through this LTI launch.",
            status_code=409,
        )

    await record_audit_event(
        event_type=UserAuditEventType.LOGIN,
        user_id=user.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"method": "lti", "course_uuid": course.course_uuid},
    )

    assert issue.access_token is not None and issue.refresh_token is not None
    return user, course, org, issue.access_token, issue.refresh_token
