"""Weekly student digest: "here's what's due, what you haven't started".

Deliberately a much smaller sibling of services/nudges — one email type, one
weekly cadence, no catalog/spec system, no per-track pacing rules. It is also
NOT SaaS-gated (unlike nudges): a self-hosted college is exactly the
deployment this exists for, so the only gate is the
``LEARNHOUSE_WEEKLY_DIGEST_ENABLED`` kill switch (default off, same
safe-by-default posture as nudges) and each student's own opt-out
(``EmailPreference.weekly_digest_opt_out`` — independent of the admin
lifecycle-nudge opt-out; see that field's docstring).

Same correctness pattern as NudgeSend: the ledger row is inserted (and
committed) BEFORE the provider is called, so a crash mid-send loses one email
rather than risking a duplicate, and two processes racing the same weekly
tick collide on the dedupe_key's unique constraint rather than in a
student's inbox.

SCOPE DECISION: "what you haven't started" only ever lists unsubmitted
ASSIGNMENTS, never ordinary reading/content activities — a content page has
no deadline pressure, and listing every unread page in a course would make
the email noisy rather than useful. An assignment already past its own
effective due date is also excluded from both sections: an overdue item is
the at-risk dashboard's job (services/courses/at_risk.py), not this email's;
repeating "this is late" every Monday for weeks is a nag, not a digest.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignments import Assignment, AssignmentUserSubmission
from src.db.courses.courses import Course
from src.db.organization_config import OrganizationConfig
from src.db.organizations import Organization
from src.db.trail_runs import TrailRun
from src.db.users import User
from src.db.weekly_digest import WeeklyDigestSend, WeeklyDigestSendStatus
from src.services.courses.activities.assignment_extensions import get_effective_due_date
from src.services.email.utils import get_media_base_url
from src.services.nudges import links
from src.services.nudges.preferences import get_weekly_digest_opted_out_user_ids
from src.services.nudges.tokens import CATEGORY_WEEKLY_DIGEST
from src.services.orgs.orgs import get_org_default_language, resolve_org_sender_name
from src.services.users.emails import send_weekly_digest_email

logger = logging.getLogger(__name__)

DUE_WINDOW_DAYS = 7
MAX_ITEMS_PER_SECTION = 5


def digest_enabled() -> bool:
    raw = os.environ.get("LEARNHOUSE_WEEKLY_DIGEST_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _org_is_active(config: Optional[OrganizationConfig]) -> bool:
    """v2 configs can mark an org inactive; absent means active. Duplicated
    from services.nudges.eligibility's own private helper rather than
    imported, since that one is module-private there too."""
    if config is None or not config.config:
        return True
    value = config.config.get("active")
    return True if value is None else bool(value)


def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


def dedupe_key(user_id: int, org_id: int, now: datetime, dry_run: bool = False) -> str:
    iso_year, iso_week, _ = now.isocalendar()
    key = f"{user_id}:{org_id}:{iso_year}-W{iso_week:02d}"
    return f"dryrun:{key}" if dry_run else key


@dataclass
class RunStats:
    considered: int = 0
    sent: int = 0
    skipped_dedupe: int = 0
    skipped_optout: int = 0
    skipped_empty: int = 0
    skipped_inactive_org: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {
            "considered": self.considered,
            "sent": self.sent,
            "skipped_dedupe": self.skipped_dedupe,
            "skipped_optout": self.skipped_optout,
            "skipped_empty": self.skipped_empty,
            "skipped_inactive_org": self.skipped_inactive_org,
            "failed": self.failed,
        }


async def _build_digest_content(
    db_session: AsyncSession, user_id: int, course_ids: set[int], now: datetime
) -> tuple[list[dict], list[dict]]:
    """Returns ``(due_this_week, not_started)`` item dicts, each capped at
    :data:`MAX_ITEMS_PER_SECTION` and formatted for
    ``send_weekly_digest_email``."""
    if not course_ids:
        return [], []

    assignments = (await db_session.execute(
        select(Assignment).where(
            Assignment.course_id.in_(course_ids), Assignment.published == True  # noqa: E712
        )
    )).scalars().all()
    if not assignments:
        return [], []

    courses = (await db_session.execute(
        select(Course).where(Course.id.in_(course_ids))  # type: ignore[attr-defined]
    )).scalars().all()
    course_name_by_id = {c.id: c.name for c in courses}

    assignment_ids = [a.id for a in assignments if a.id is not None]
    submitted_ids: set[int] = set()
    if assignment_ids:
        rows = (await db_session.execute(
            select(AssignmentUserSubmission.assignment_id).where(
                AssignmentUserSubmission.assignment_id.in_(assignment_ids),  # type: ignore[attr-defined]
                AssignmentUserSubmission.user_id == user_id,
            )
        )).scalars().all()
        submitted_ids = set(rows)

    window_end = now + timedelta(days=DUE_WINDOW_DAYS)
    due_this_week: list[tuple[datetime, dict]] = []
    not_started: list[dict] = []

    for assignment in assignments:
        if assignment.id in submitted_ids:
            continue
        course_name = course_name_by_id.get(assignment.course_id, "")
        effective_due = await get_effective_due_date(assignment, user_id, db_session)
        due_dt = _parse_dt(effective_due)

        if due_dt is not None:
            if due_dt < now:
                continue  # overdue — the at-risk dashboard's job, not this email's
            if due_dt <= window_end:
                due_this_week.append(
                    (due_dt, {
                        "title": assignment.title,
                        "course_name": course_name,
                        "due_date": due_dt.strftime("%b %d"),
                    })
                )
                continue

        not_started.append({"title": assignment.title, "course_name": course_name})

    due_this_week.sort(key=lambda pair: pair[0])
    return (
        [item for _dt, item in due_this_week[:MAX_ITEMS_PER_SECTION]],
        not_started[:MAX_ITEMS_PER_SECTION],
    )


async def run_weekly_digest(
    db_session: AsyncSession,
    *,
    dry_run: bool = False,
    now: Optional[datetime] = None,
    org_id: Optional[int] = None,
) -> RunStats:
    """Evaluate every (student, org) enrollment and send this week's digest
    where there is something worth sending."""
    stats = RunStats()
    now = now or datetime.now(timezone.utc)

    if not dry_run and not digest_enabled():
        logger.info("Weekly digest skipped: LEARNHOUSE_WEEKLY_DIGEST_ENABLED is not set")
        return stats

    trailrun_statement = select(TrailRun.user_id, TrailRun.org_id, TrailRun.course_id)
    if org_id is not None:
        trailrun_statement = trailrun_statement.where(TrailRun.org_id == org_id)
    rows = (await db_session.execute(trailrun_statement)).all()

    courses_by_user_org: dict[tuple[int, int], set[int]] = {}
    for uid, oid, cid in rows:
        courses_by_user_org.setdefault((uid, oid), set()).add(cid)

    if not courses_by_user_org:
        return stats

    all_user_ids = {uid for uid, _oid in courses_by_user_org}
    all_org_ids = {oid for _uid, oid in courses_by_user_org}

    opted_out = await get_weekly_digest_opted_out_user_ids(db_session, all_user_ids)

    users = (await db_session.execute(
        select(User).where(User.id.in_(all_user_ids))  # type: ignore[attr-defined]
    )).scalars().all()
    users_by_id = {u.id: u for u in users}

    orgs = (await db_session.execute(
        select(Organization).where(Organization.id.in_(all_org_ids))  # type: ignore[attr-defined]
    )).scalars().all()
    orgs_by_id = {o.id: o for o in orgs}

    configs = (await db_session.execute(
        select(OrganizationConfig).where(OrganizationConfig.org_id.in_(all_org_ids))  # type: ignore[attr-defined]
    )).scalars().all()
    config_by_org = {c.org_id: c for c in configs}

    media_base = get_media_base_url(None)

    for (user_id, this_org_id), course_ids in courses_by_user_org.items():
        stats.considered += 1

        user = users_by_id.get(user_id)
        org = orgs_by_id.get(this_org_id)
        if not user or not org:
            continue

        if user_id in opted_out:
            stats.skipped_optout += 1
            continue

        config = config_by_org.get(this_org_id)
        if not _org_is_active(config):
            stats.skipped_inactive_org += 1
            continue

        due_this_week, not_started = await _build_digest_content(db_session, user_id, course_ids, now)
        if not due_this_week and not not_started:
            stats.skipped_empty += 1
            continue

        key = dedupe_key(user_id, this_org_id, now, dry_run)
        row = WeeklyDigestSend(
            dedupe_key=key,
            org_id=this_org_id,
            user_id=user_id,
            status=WeeklyDigestSendStatus.DRY_RUN if dry_run else WeeklyDigestSendStatus.CLAIMED,
            claimed_at=str(now),
        )
        db_session.add(row)
        try:
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            stats.skipped_dedupe += 1
            continue

        if dry_run:
            stats.sent += 1
            logger.info("[dry-run] weekly digest -> user %s org %s", user_id, this_org_id)
            continue

        lang = get_org_default_language(config)
        sender_name = resolve_org_sender_name(config)
        base_url = await links.org_base_url(org.slug, db_session, this_org_id)

        logo_url = None
        if getattr(org, "logo_image", None) and org.org_uuid and media_base:
            logo_url = f"{media_base}/content/orgs/{org.org_uuid}/logos/{org.logo_image}"

        result = send_weekly_digest_email(
            email=user.email,
            org_name=org.name,
            cta_url=links.student_courses_url(base_url),
            unsubscribe_url=links.unsubscribe_url(media_base, user.user_uuid, category=CATEGORY_WEEKLY_DIGEST),
            due_this_week=due_this_week,
            not_started=not_started,
            lang=lang,
            logo_url=logo_url,
            sender_name=sender_name,
        )

        if result is False:
            row.status = WeeklyDigestSendStatus.FAILED
            row.error = "provider rejected or unavailable"
            stats.failed += 1
        else:
            row.status = WeeklyDigestSendStatus.SENT
            row.sent_at = str(now)
            if isinstance(result, dict) and result.get("id"):
                row.provider_id = str(result["id"])
            stats.sent += 1

        db_session.add(row)
        await db_session.commit()

    logger.info("Weekly digest run finished: %s", stats.as_dict())
    return stats
