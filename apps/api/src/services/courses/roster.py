"""Bulk roster import (CSV) and gradebook export (CSV) for a course.

Both built on existing, already-hardened primitives rather than new
plumbing:

- Enrollment in this codebase IS a `TrailRun` row (see services.trail.trail)
  — bulk-enrolling an existing org member just ensures a `Trail` +
  `TrailRun` exists for them, the same write `add_course_to_trail` does for
  self-service enrollment, minus that function's self-only READ-access
  precondition (the ACTOR here is a verified course instructor acting on
  someone else's behalf, not the student enrolling themselves).
- A CSV row whose email has no account yet is NOT auto-provisioned — this
  reuses the existing org-invite flow (services.orgs.users.invite_batch_users)
  rather than inventing a second invite/signup mechanism, and reports back
  so the admin can re-run the import once the invited student has signed
  up. There is no "pending course enrollment for an email with no account"
  concept — that is a real, disclosed scope limit, not an oversight.
- Gradebook export reuses the exact grade computation every other grading
  surface in this app already relies on (`AssignmentUserSubmission.grade_display`,
  attached by read_assignment_submissions) rather than re-deriving grades.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignments import Assignment
from src.db.courses.courses import Course
from src.db.trail_runs import TrailRun
from src.db.trails import Trail
from src.db.user_audit_events import UserAuditEventType
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.security.org_auth import is_org_member
from src.security.rbac import AccessAction, check_resource_access
from src.services.audit.audit import record_audit_event
from src.services.orgs.users import _csv_safe, _looks_like_email
from src.services.trail.trail import check_trail_presence


def parse_roster_emails(csv_text: str) -> list[str]:
    """Extract an email list from CSV text. Accepts either a header row
    naming an "email" column (case-insensitive — the common case, matching
    a spreadsheet export from a registrar), or a plain single-column list
    with no header at all. Blank lines are skipped; everything else is
    returned as-is for the caller to validate/dedupe.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return []

    header = [cell.strip().lower() for cell in rows[0]]
    if "email" in header:
        email_col = header.index("email")
        data_rows = rows[1:]
        return [row[email_col].strip() for row in data_rows if len(row) > email_col and row[email_col].strip()]

    # No recognizable header — treat every row's first cell as an email,
    # header row included (a bare list of addresses has no header to skip).
    return [row[0].strip() for row in rows if row and row[0].strip()]


async def bulk_enroll_roster(
    request: Request,
    course_uuid: str,
    emails: list[str],
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """Instructor-only. Enrolls every email that already resolves to an org
    member; invites every other well-formed email to the ORG (not directly
    to the course — see module docstring) via the existing batch-invite
    flow; reports the rest as invalid.
    """
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    seen: set[str] = set()
    results: list[dict] = []
    to_invite: list[str] = []

    for raw_email in emails:
        email = raw_email.strip()
        if not email:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)

        if not _looks_like_email(email):
            results.append({"email": email, "status": "invalid_email"})
            continue

        user_statement = select(User).where(User.email == email)
        user = (await db_session.execute(user_statement)).scalars().first()

        if not user:
            to_invite.append(email)
            continue

        if not await is_org_member(user.id, course.org_id, db_session):
            results.append({"email": email, "status": "not_org_member"})
            continue

        existing_statement = select(TrailRun).where(
            TrailRun.course_id == course.id, TrailRun.user_id == user.id
        )
        existing = (await db_session.execute(existing_statement)).scalars().first()
        if existing:
            results.append({"email": email, "status": "already_enrolled"})
            continue

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

        # Audit only in bulk — not analytics/webhooks, to avoid a storm of
        # per-user events firing from one CSV upload. The audit row is
        # still recorded per student since that is a compliance record,
        # not a notification.
        await record_audit_event(
            event_type=UserAuditEventType.COURSE_ENROLLED,
            user_id=user.id,
            org_id=course.org_id,
            target_uuid=course.course_uuid,
            metadata={"course_name": course.name, "via": "bulk_roster_import"},
        )
        results.append({"email": email, "status": "enrolled"})

    invited_count = 0
    if to_invite:
        from src.services.orgs.users import invite_batch_users

        invite_res = await invite_batch_users(
            request=request,
            org_id=course.org_id,
            emails=",".join(to_invite),
            invite_code_uuid=None,
            db_session=db_session,
            current_user=current_user,
        )
        for row in invite_res.get("results", []):
            status_val = row.get("status")
            results.append({
                "email": row.get("email"),
                "status": "invited_pending_signup" if status_val == "sent" else status_val,
            })
            if status_val == "sent":
                invited_count += 1

    return {
        "message": (
            f"{sum(1 for r in results if r['status'] == 'enrolled')} enrolled, "
            f"{invited_count} invited to the organization (re-run this import once they sign up), "
            f"{sum(1 for r in results if r['status'] not in ('enrolled', 'invited_pending_signup'))} skipped."
        ),
        "results": results,
    }


async def export_course_gradebook_csv(
    request: Request,
    course_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> StreamingResponse:
    """Instructor-only. One row per enrolled student, one column per
    assignment, cells are each assignment's display_grade (blank if not
    yet graded). Reuses read_assignment_submissions' own grade computation
    rather than re-deriving it — see that function's grade_display field.
    """
    from src.services.courses.activities.assignments import (
        get_assignments_from_course,
        read_assignment_submissions,
    )

    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    assignments = await get_assignments_from_course(request, course_uuid, current_user, db_session)

    # user_id -> {"user": User, "grades": {assignment_uuid: display_grade}}
    students: dict[int, dict] = {}
    for assignment in assignments:
        assignment_uuid = assignment.assignment_uuid
        offset = 0
        page_size = 500
        while True:
            page = await read_assignment_submissions(
                request, assignment_uuid, current_user, db_session, limit=page_size, offset=offset
            )
            if not page:
                break
            for row in page:
                user_id = row.get("user_id")
                if user_id is None:
                    continue
                entry = students.setdefault(user_id, {"grades": {}})
                grade_display = row.get("grade_display")
                entry["grades"][assignment_uuid] = (
                    grade_display.get("display_grade") if isinstance(grade_display, dict) else None
                )
            if len(page) < page_size:
                break
            offset += page_size

    if students:
        users_statement = select(User).where(User.id.in_(list(students.keys())))  # type: ignore[attr-defined]
        for user in (await db_session.execute(users_statement)).scalars().all():
            students[user.id]["user"] = user

    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Name", "Username", "Email"] + [a.title for a in assignments]
    writer.writerow(header)

    for user_id, entry in sorted(
        students.items(), key=lambda kv: (getattr(kv[1].get("user"), "last_name", "") or "")
    ):
        user = entry.get("user")
        if user is None:
            continue
        row = [
            _csv_safe(f"{user.first_name or ''} {user.last_name or ''}".strip()),
            _csv_safe(user.username or ""),
            _csv_safe(user.email or ""),
        ]
        for a in assignments:
            grade = entry["grades"].get(a.assignment_uuid)
            row.append(_csv_safe(grade) if grade else "")
        writer.writerow(row)

    output.seek(0)
    filename = f"gradebook-{course.course_uuid}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
