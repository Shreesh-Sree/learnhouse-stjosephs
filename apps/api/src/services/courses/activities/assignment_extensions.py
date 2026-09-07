"""Per-student assignment deadline extensions.

See db.courses.assignment_extensions' module docstring for the core design
(one row per (assignment, student), REPLACING the deadline rather than only
ever pushing it later). `get_effective_due_date` is the single place every
deadline gate in services.courses.activities.assignments resolves through —
callers never read `assignment.due_date` directly once a per-student check
is needed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignment_extensions import AssignmentExtension, AssignmentExtensionRead
from src.db.courses.assignments import Assignment
from src.db.courses.courses import Course
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.rbac import AccessAction, check_resource_access


async def _resolve_assignment_and_course(
    assignment_uuid: str, db_session: AsyncSession
) -> tuple[Assignment, Course]:
    statement = select(Assignment).where(Assignment.assignment_uuid == assignment_uuid)
    assignment = (await db_session.execute(statement)).scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    statement = select(Course).where(Course.id == assignment.course_id)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return assignment, course


async def get_effective_due_date(assignment: Assignment, user_id: int, db_session: AsyncSession):
    """This student's actual deadline for ``assignment``: their own
    extension's date if one exists, otherwise the assignment's own
    ``due_date``. Pure DB lookup, no parsing — callers run the result
    through the same date-parsing rule ``_is_assignment_past_due`` already
    uses (see `_is_assignment_past_due_for_user`).
    """
    if assignment.id is None:
        return assignment.due_date
    statement = select(AssignmentExtension.extended_due_date).where(
        AssignmentExtension.assignment_id == assignment.id,
        AssignmentExtension.user_id == user_id,
    )
    extended = (await db_session.execute(statement)).scalars().first()
    return extended if extended is not None else assignment.due_date


async def grant_extension(
    request: Request,
    assignment_uuid: str,
    target_user_id: int,
    extended_due_date: str,
    reason: str | None,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> AssignmentExtensionRead:
    """Instructor-only. Creates or updates the one extension row for this
    student on this assignment.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    if not extended_due_date or not str(extended_due_date).strip():
        raise HTTPException(status_code=400, detail="An extended due date is required.")

    statement = select(AssignmentExtension).where(
        AssignmentExtension.assignment_id == assignment.id,
        AssignmentExtension.user_id == target_user_id,
    )
    existing = (await db_session.execute(statement)).scalars().first()

    now_str = str(datetime.now())
    if existing:
        existing.extended_due_date = extended_due_date
        existing.reason = reason
        existing.granted_by_user_id = current_user.id
        existing.update_date = now_str
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)
        return AssignmentExtensionRead.model_validate(existing)

    extension = AssignmentExtension(
        extension_uuid=f"assignmentextension_{uuid4()}",
        assignment_id=assignment.id,
        user_id=target_user_id,
        granted_by_user_id=current_user.id,
        extended_due_date=extended_due_date,
        reason=reason,
        creation_date=now_str,
        update_date=now_str,
    )
    db_session.add(extension)
    await db_session.commit()
    await db_session.refresh(extension)
    return AssignmentExtensionRead.model_validate(extension)


async def revoke_extension(
    request: Request,
    assignment_uuid: str,
    target_user_id: int,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    """Instructor-only. Removes this student's extension, if any — a no-op
    (not an error) when they don't have one, so a caller doesn't need to
    check existence first.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(AssignmentExtension).where(
        AssignmentExtension.assignment_id == assignment.id,
        AssignmentExtension.user_id == target_user_id,
    )
    existing = (await db_session.execute(statement)).scalars().first()
    if existing:
        await db_session.delete(existing)
        await db_session.commit()


async def list_extensions(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[AssignmentExtensionRead]:
    """Instructor-only: every extension granted on this assignment."""
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(AssignmentExtension).where(
        AssignmentExtension.assignment_id == assignment.id
    ).order_by(AssignmentExtension.creation_date.asc())
    rows = (await db_session.execute(statement)).scalars().all()
    return [AssignmentExtensionRead.model_validate(r) for r in rows]


async def get_my_extension(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> AssignmentExtensionRead | None:
    """The caller's own extension for this assignment, if any — so the
    student-facing deadline display can show it rather than the assignment's
    plain due_date.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    statement = select(AssignmentExtension).where(
        AssignmentExtension.assignment_id == assignment.id,
        AssignmentExtension.user_id == current_user.id,
    )
    existing = (await db_session.execute(statement)).scalars().first()
    return AssignmentExtensionRead.model_validate(existing) if existing else None
