"""At-risk student dashboard: a per-course, instructor-facing view flagging
students who show one or more warning signs, computed entirely from
existing durable Postgres data — no new tracking table, and deliberately
NOT the lossy, TTL'd Tinybird analytics stream (services/analytics/) this
app also has, since a retention signal needs to be reliable months later,
not just for the analytics window.

SCOPE DECISION: this project has no course-schedule/syllabus model (no
start/end dates, no weekly pacing plan) to compare a student's progress
against, so "falling behind pace" is approximated as "enrolled a while ago
but has completed very little" rather than compared against a real
schedule — see LOW_PROGRESS_MIN_ENROLLMENT_DAYS below. That is a real,
disclosed limitation, not an oversight.

Four independent signals, each computed per enrolled student:
- inactive: no login (org-wide) and no activity in THIS course for a while.
- failing: multiple GRADED submissions in this course came back failed.
- missing_assignments: multiple published assignments are past this
  student's own effective due date (extensions honored) with NO
  submission row at all.
- low_progress: enrolled a while ago, completion percentage still low.

A student with zero signals is not "at risk" and is left out of the
response entirely — the queue is meant to be short enough to act on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import Activity
from src.db.courses.assignments import Assignment, AssignmentUserSubmissionStatus
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.courses import Course
from src.db.trail_runs import TrailRun
from src.db.trail_steps import TrailStep
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.security.rbac import AccessAction, check_resource_access
from src.services.courses.activities.assignment_extensions import get_effective_due_date
from src.services.courses.activities.assignments import _is_date_past, read_assignment_submissions

INACTIVITY_THRESHOLD_DAYS = 14
LOW_PROGRESS_MIN_ENROLLMENT_DAYS = 14
LOW_PROGRESS_THRESHOLD_PCT = 25.0
FAILING_ASSIGNMENTS_THRESHOLD = 2
MISSING_ASSIGNMENTS_THRESHOLD = 2


class AtRiskStudent(BaseModel):
    user_id: int
    user_uuid: str
    username: str
    first_name: str
    last_name: str
    email: str
    flags: list[str]
    risk_level: str  # "medium" | "high"
    days_since_activity: Optional[int] = None
    last_login_at: Optional[str] = None
    failing_assignments_count: int = 0
    missing_assignments_count: int = 0
    completion_percentage: float = 0.0
    enrolled_since: str


def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


async def get_at_risk_students(
    request: Request,
    course_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[AtRiskStudent]:
    course = (await db_session.execute(
        select(Course).where(Course.course_uuid == course_uuid)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    trail_runs = (await db_session.execute(
        select(TrailRun).where(TrailRun.course_id == course.id)
    )).scalars().all()

    if not trail_runs:
        return []

    enrolled_user_ids = [tr.user_id for tr in trail_runs]
    enrolled_since_by_user = {tr.user_id: tr.creation_date for tr in trail_runs}

    users = (await db_session.execute(
        select(User).where(User.id.in_(enrolled_user_ids))  # type: ignore[attr-defined]
    )).scalars().all()
    users_by_id = {u.id: u for u in users}

    # --- Activity recency: most recent TrailStep per (user), for THIS course ---
    step_rows = (await db_session.execute(
        select(TrailStep.user_id, func.max(TrailStep.creation_date))
        .where(TrailStep.course_id == course.id, TrailStep.user_id.in_(enrolled_user_ids))  # type: ignore[attr-defined]
        .group_by(TrailStep.user_id)
    )).all()
    last_course_activity_by_user: dict[int, str] = {row[0]: row[1] for row in step_rows}

    # --- Progress: completed steps vs total published activities in the course ---
    total_activities = (await db_session.execute(
        select(func.count(func.distinct(ChapterActivity.activity_id)))
        .join(Activity, Activity.id == ChapterActivity.activity_id)
        .where(ChapterActivity.course_id == course.id, Activity.published == True)  # noqa: E712
    )).scalar_one() or 0

    completed_rows = (await db_session.execute(
        select(TrailStep.user_id, func.count(func.distinct(TrailStep.activity_id)))
        .where(
            TrailStep.course_id == course.id,
            TrailStep.user_id.in_(enrolled_user_ids),  # type: ignore[attr-defined]
            TrailStep.complete == True,  # noqa: E712
        )
        .group_by(TrailStep.user_id)
    )).all()
    completed_by_user: dict[int, int] = {row[0]: row[1] for row in completed_rows}

    # --- Grading signal: failing counts, via the same computed grade_display
    # every other grading surface (gradebook export, submission views) uses,
    # rather than re-deriving pass/fail here. ---
    assignments = (await db_session.execute(
        select(Assignment).where(Assignment.course_id == course.id, Assignment.published == True)  # noqa: E712
    )).scalars().all()

    failing_count_by_user: dict[int, int] = {uid: 0 for uid in enrolled_user_ids}
    submitted_assignment_ids_by_user: dict[int, set[int]] = {uid: set() for uid in enrolled_user_ids}

    for assignment in assignments:
        offset = 0
        page_size = 500
        while True:
            page = await read_assignment_submissions(
                request, assignment.assignment_uuid, current_user, db_session, limit=page_size, offset=offset
            )
            if not page:
                break
            for row in page:
                user_id = row.get("user_id")
                if user_id not in failing_count_by_user:
                    continue  # a submission from someone no longer enrolled
                submitted_assignment_ids_by_user[user_id].add(assignment.id)
                grade_display = row.get("grade_display")
                if isinstance(grade_display, dict) and grade_display.get("passed") is False:
                    failing_count_by_user[user_id] += 1
            if len(page) < page_size:
                break
            offset += page_size

    # --- Missing-work signal: published assignment past THIS student's own
    # effective due date (extensions honored) with no submission row at all. ---
    missing_count_by_user: dict[int, int] = {uid: 0 for uid in enrolled_user_ids}
    for assignment in assignments:
        if assignment.due_date is None:
            continue
        for user_id in enrolled_user_ids:
            if assignment.id in submitted_assignment_ids_by_user.get(user_id, set()):
                continue
            effective_due = await get_effective_due_date(assignment, user_id, db_session)
            if _is_date_past(effective_due):
                missing_count_by_user[user_id] += 1

    now = datetime.now()
    results: list[AtRiskStudent] = []
    for user_id in enrolled_user_ids:
        user = users_by_id.get(user_id)
        if not user:
            continue

        last_login_dt = _parse_dt(getattr(user, "last_login_at", None))
        last_course_activity_dt = _parse_dt(last_course_activity_by_user.get(user_id))
        enrolled_since_dt = _parse_dt(enrolled_since_by_user.get(user_id))

        candidates = [d for d in (last_login_dt, last_course_activity_dt) if d is not None]
        last_seen = max(candidates) if candidates else None
        days_since_activity = (now - last_seen).days if last_seen else None

        failing_count = failing_count_by_user.get(user_id, 0)
        missing_count = missing_count_by_user.get(user_id, 0)
        completed = completed_by_user.get(user_id, 0)
        completion_pct = (completed / total_activities * 100.0) if total_activities else 0.0

        days_enrolled = (now - enrolled_since_dt).days if enrolled_since_dt else 0

        flags: list[str] = []
        if days_since_activity is not None and days_since_activity >= INACTIVITY_THRESHOLD_DAYS:
            flags.append("inactive")
        if failing_count >= FAILING_ASSIGNMENTS_THRESHOLD:
            flags.append("failing")
        if missing_count >= MISSING_ASSIGNMENTS_THRESHOLD:
            flags.append("missing_assignments")
        if (
            days_enrolled >= LOW_PROGRESS_MIN_ENROLLMENT_DAYS
            and completion_pct < LOW_PROGRESS_THRESHOLD_PCT
        ):
            flags.append("low_progress")

        if not flags:
            continue

        results.append(
            AtRiskStudent(
                user_id=user.id,
                user_uuid=user.user_uuid,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                flags=flags,
                risk_level="high" if len(flags) >= 2 else "medium",
                days_since_activity=days_since_activity,
                last_login_at=getattr(user, "last_login_at", None),
                failing_assignments_count=failing_count,
                missing_assignments_count=missing_count,
                completion_percentage=round(completion_pct, 1),
                enrolled_since=enrolled_since_by_user.get(user_id) or "",
            )
        )

    # Worst first.
    results.sort(key=lambda s: (s.risk_level != "high", -len(s.flags)))
    return results
