"""Student gamification: points, streaks, and badges.

SCOPE DECISION: a low-key, private, self-service view of ONE student's OWN
participation in ONE org — never a public leaderboard, never pushed via
notification or email. PENDING_FEATURES.md's own brainstorm entry flagged
that gamification "fits some course types far better than others"; keeping
it opt-in-visible on the student's own profile (rather than a
cross-student ranking) sidesteps most of that concern without deciding it
for every institution.

Everything here is a LIVE aggregation over existing durable data — no new
table, no stored point ledger — the same "pure aggregation, not a new
source of truth" approach services/courses/at_risk.py already took. Points
and badge thresholds are a code-level catalog below, not configurable per
org: they are product decisions, not data, the same way
services/nudges/catalog.py's specs are code rather than an admin-editable
table.

Points sources, all read from the durable ``user_audit_event`` log except
community participation (which has no audit-log mirror by design — see
that model's own docstring — so discussions/comments are read directly):
completing an activity, submitting an assignment, a graded assignment
that PASSED (bonus on top of the submission point), finishing a course,
earning a certificate, posting a discussion, posting a comment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.communities.discussion_comments import DiscussionComment
from src.db.communities.discussions import Discussion
from src.db.user_audit_events import UserAuditEvent, UserAuditEventType

# Points per durable audit-event type. Anything not listed here (LOGIN,
# LOGOUT) earns nothing — showing up is not an achievement, doing
# something is.
EVENT_POINTS: dict[str, int] = {
    UserAuditEventType.ACTIVITY_COMPLETED: 5,
    UserAuditEventType.ASSIGNMENT_SUBMITTED: 5,
    UserAuditEventType.COURSE_COMPLETED: 100,
    UserAuditEventType.CERTIFICATE_CLAIMED: 50,
}
# On top of the ASSIGNMENT_SUBMITTED point already earned for that same
# submission — passing is worth more than merely attempting, but attempting
# is never worthless (retries and partial credit still count for something).
GRADED_PASS_BONUS = 10
DISCUSSION_POINTS = 10
COMMENT_POINTS = 3

# Event types that count as "active today" for the streak — every type that
# represents the student actually doing coursework in this org. LOGIN is
# deliberately excluded: opening the app is not participation.
STREAK_EVENT_TYPES = frozenset({
    UserAuditEventType.ACTIVITY_COMPLETED,
    UserAuditEventType.ASSIGNMENT_SUBMITTED,
    UserAuditEventType.COURSE_ENROLLED,
    UserAuditEventType.ASSIGNMENT_GRADED,
    UserAuditEventType.CERTIFICATE_CLAIMED,
    UserAuditEventType.COURSE_COMPLETED,
})


class Badge(BaseModel):
    id: str
    label: str
    description: str
    icon: str
    earned: bool


class GamificationStats(BaseModel):
    points: int
    current_streak_days: int
    longest_streak_days: int
    completed_activity_count: int
    certificate_count: int
    discussion_count: int
    comment_count: int
    badges: list[Badge]


@dataclass(frozen=True)
class _BadgeSpec:
    id: str
    label: str
    description: str
    icon: str  # lucide-react icon name, frontend's choice of set
    check: Callable[[dict], bool]


def _badge_catalog() -> list[_BadgeSpec]:
    """Code-defined, not DB-backed — see module docstring."""
    return [
        _BadgeSpec(
            "first_steps", "First Steps", "Complete your first activity", "footprints",
            lambda s: s["completed_activity_count"] >= 1,
        ),
        _BadgeSpec(
            "going_strong", "Going Strong", "Keep a 7-day activity streak", "flame",
            lambda s: s["longest_streak_days"] >= 7,
        ),
        _BadgeSpec(
            "unstoppable", "Unstoppable", "Keep a 30-day activity streak", "flame",
            lambda s: s["longest_streak_days"] >= 30,
        ),
        _BadgeSpec(
            "discussion_starter", "Discussion Starter", "Start your first discussion", "message-square",
            lambda s: s["discussion_count"] >= 1,
        ),
        _BadgeSpec(
            "helpful_peer", "Helpful Peer", "Post 10 comments helping classmates", "heart",
            lambda s: s["comment_count"] >= 10,
        ),
        _BadgeSpec(
            "certified", "Certified", "Earn your first certificate", "award",
            lambda s: s["certificate_count"] >= 1,
        ),
        _BadgeSpec(
            "high_achiever", "High Achiever", "Earn 3 certificates", "award",
            lambda s: s["certificate_count"] >= 3,
        ),
        _BadgeSpec(
            "century_club", "Century Club", "Reach 100 points", "star",
            lambda s: s["points"] >= 100,
        ),
        _BadgeSpec(
            "dedicated_scholar", "Dedicated Scholar", "Reach 500 points", "star",
            lambda s: s["points"] >= 500,
        ),
    ]


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw or not str(raw).strip():
        return None
    try:
        return datetime.fromisoformat(str(raw).strip()).date()
    except (ValueError, TypeError):
        return None


def compute_streaks(active_dates: set[date], today: date) -> tuple[int, int]:
    """Returns ``(current_streak_days, longest_streak_days)``.

    The current streak allows "yesterday" to still count as unbroken — a
    student who was active yesterday but hasn't opened the app yet today
    should not see their streak reset to 0 the moment midnight passes; it
    only truly breaks once a full day goes by with no activity at all.
    """
    if not active_dates:
        return 0, 0

    current = 0
    cursor = today if today in active_dates else today - timedelta(days=1)
    while cursor in active_dates:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    prev: Optional[date] = None
    for d in sorted(active_dates):
        run = run + 1 if prev is not None and d == prev + timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d

    return current, longest


async def get_gamification_stats(
    db_session: AsyncSession, user_id: int, org_id: int, today: Optional[date] = None
) -> GamificationStats:
    today = today or datetime.now(timezone.utc).date()

    events = (await db_session.execute(
        select(UserAuditEvent).where(
            UserAuditEvent.user_id == user_id, UserAuditEvent.org_id == org_id
        )
    )).scalars().all()

    points = 0
    completed_activity_count = 0
    certificate_count = 0
    active_dates: set[date] = set()

    for event in events:
        if event.event_type in STREAK_EVENT_TYPES:
            active_dates.add(event.created_at.date())

        points += EVENT_POINTS.get(event.event_type, 0)

        if event.event_type == UserAuditEventType.ACTIVITY_COMPLETED:
            completed_activity_count += 1
        elif event.event_type == UserAuditEventType.CERTIFICATE_CLAIMED:
            certificate_count += 1
        elif event.event_type == UserAuditEventType.ASSIGNMENT_GRADED:
            if (event.audit_metadata or {}).get("passed") is True:
                points += GRADED_PASS_BONUS

    discussions = (await db_session.execute(
        select(Discussion).where(Discussion.author_id == user_id, Discussion.org_id == org_id)
    )).scalars().all()
    discussion_count = len(discussions)
    points += discussion_count * DISCUSSION_POINTS
    for d in discussions:
        parsed = _parse_date(d.creation_date)
        if parsed:
            active_dates.add(parsed)

    # Comments have no org column — scope via which discussions in this org
    # exist at all (same approach services/audit/dossier.py's _community
    # uses), then keep only this user's comments on those.
    org_discussion_ids = set((await db_session.execute(
        select(Discussion.id).where(Discussion.org_id == org_id)
    )).scalars().all())

    all_user_comments = (await db_session.execute(
        select(DiscussionComment).where(DiscussionComment.author_id == user_id)
    )).scalars().all()
    comments_in_org = [c for c in all_user_comments if c.discussion_id in org_discussion_ids]
    comment_count = len(comments_in_org)
    points += comment_count * COMMENT_POINTS
    for c in comments_in_org:
        parsed = _parse_date(c.creation_date)
        if parsed:
            active_dates.add(parsed)

    current_streak, longest_streak = compute_streaks(active_dates, today)

    stats_for_badges = {
        "points": points,
        "completed_activity_count": completed_activity_count,
        "certificate_count": certificate_count,
        "discussion_count": discussion_count,
        "comment_count": comment_count,
        "longest_streak_days": longest_streak,
    }
    badges = [
        Badge(id=spec.id, label=spec.label, description=spec.description, icon=spec.icon,
              earned=spec.check(stats_for_badges))
        for spec in _badge_catalog()
    ]

    return GamificationStats(
        points=points,
        current_streak_days=current_streak,
        longest_streak_days=longest_streak,
        completed_activity_count=completed_activity_count,
        certificate_count=certificate_count,
        discussion_count=discussion_count,
        comment_count=comment_count,
        badges=badges,
    )
