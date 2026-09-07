"""Opportunistic webcam proctoring snapshots.

Deliberately NOT enforced anywhere: there is no check on any
submission-mutating path that requires a snapshot to exist, and none should
ever be added. A student who declines the frontend consent prompt
(AssignmentProctoringConsent.tsx) simply generates no rows here — a
consent-based feature must never become a reason a student cannot take the
exam. See ProctoringSnapshot's own docstring for the same point from the
model side.

Access is instructor-only in both directions: a student can upload their own
snapshots but can never list or view any (including their own) — a webcam
photo of a specific moment during someone's exam is not something to hand
back to them casually, and there is no legitimate student-facing use for it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request, Response, UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import Activity
from src.db.courses.assignments import Assignment
from src.db.courses.courses import Course
from src.db.courses.proctoring import ProctoringSnapshot, ProctoringSnapshotRead
from src.db.organizations import Organization
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.rbac import AccessAction, check_resource_access
from src.services.courses.transfer.storage_utils import delete_storage_directory
from src.services.utils.upload_content import read_content, upload_file

# A single low-res JPEG frame every ~90s (see the frontend capture interval)
# — generous but not unbounded, since these accumulate for the whole exam.
MAX_SNAPSHOT_SIZE = 2 * 1024 * 1024


async def _resolve_assignment_context(
    assignment_uuid: str, db_session: AsyncSession
) -> tuple[Assignment, Activity, Course, Organization]:
    statement = select(Assignment).where(Assignment.assignment_uuid == assignment_uuid)
    assignment = (await db_session.execute(statement)).scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    statement = select(Activity).where(Activity.id == assignment.activity_id)
    activity = (await db_session.execute(statement)).scalars().first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    statement = select(Course).where(Course.id == assignment.course_id)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    statement = select(Organization).where(Organization.id == course.org_id)
    org = (await db_session.execute(statement)).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return assignment, activity, course, org


def _snapshot_directory(course_uuid: str, activity_uuid: str, user_uuid: str) -> str:
    return f"courses/{course_uuid}/activities/{activity_uuid}/proctoring/{user_uuid}"


async def upload_proctoring_snapshot(
    request: Request,
    assignment_uuid: str,
    image_file: UploadFile,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> ProctoringSnapshotRead:
    """A student uploads one webcam frame for their own attempt.

    READ access is enough — this is the learner submitting something about
    themselves during their own attempt, the same bar as viewing the
    assignment, not an authoring action.
    """
    if isinstance(current_user, AnonymousUser) or isinstance(current_user, APITokenUser):
        raise HTTPException(status_code=401, detail="Authentication required")

    assignment, activity, course, org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    filename = await upload_file(
        file=image_file,
        directory=_snapshot_directory(course.course_uuid, activity.activity_uuid, str(current_user.id)),
        type_of_dir="orgs",
        uuid=org.org_uuid,
        allowed_types=["image"],
        filename_prefix="proctoring",
        max_size=MAX_SNAPSHOT_SIZE,
    )

    now_str = str(datetime.now())
    snapshot = ProctoringSnapshot(
        snapshot_uuid=f"proctoringsnapshot_{uuid4()}",
        org_id=org.id,
        course_id=course.id,
        activity_id=activity.id,
        assignment_id=assignment.id,
        user_id=current_user.id,
        filename=filename,
        captured_at=now_str,
        creation_date=now_str,
    )
    db_session.add(snapshot)
    await db_session.commit()
    await db_session.refresh(snapshot)
    return ProctoringSnapshotRead.model_validate(snapshot)


async def list_proctoring_snapshots(
    request: Request,
    assignment_uuid: str,
    target_user_id: int,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[ProctoringSnapshotRead]:
    """Instructor-only: every snapshot captured for one student's attempt."""
    assignment, _activity, course, _org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = (
        select(ProctoringSnapshot)
        .where(
            ProctoringSnapshot.assignment_id == assignment.id,
            ProctoringSnapshot.user_id == target_user_id,
        )
        .order_by(ProctoringSnapshot.creation_date.asc())
    )
    rows = (await db_session.execute(statement)).scalars().all()
    return [ProctoringSnapshotRead.model_validate(row) for row in rows]


async def serve_proctoring_snapshot(
    request: Request,
    snapshot_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> Response:
    """Instructor-only: stream one snapshot's image bytes."""
    statement = select(ProctoringSnapshot).where(ProctoringSnapshot.snapshot_uuid == snapshot_uuid)
    snapshot = (await db_session.execute(statement)).scalars().first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    statement = select(Course).where(Course.id == snapshot.course_id)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    statement = select(Organization).where(Organization.id == snapshot.org_id)
    org = (await db_session.execute(statement)).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    statement = select(Activity).where(Activity.id == snapshot.activity_id)
    activity = (await db_session.execute(statement)).scalars().first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    body = await read_content(
        directory=_snapshot_directory(course.course_uuid, activity.activity_uuid, str(snapshot.user_id)),
        type_of_dir="orgs",
        uuid=org.org_uuid,
        file_and_format=snapshot.filename,
    )
    return Response(content=body, media_type="image/jpeg")


async def delete_proctoring_snapshots(
    request: Request,
    assignment_uuid: str,
    target_user_id: int,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> int:
    """Instructor-only retention control: permanently delete every snapshot
    captured for one student's attempt on this assignment (storage + DB
    rows). Returns the number of rows deleted.
    """
    assignment, activity, course, org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(ProctoringSnapshot).where(
        ProctoringSnapshot.assignment_id == assignment.id,
        ProctoringSnapshot.user_id == target_user_id,
    )
    rows = (await db_session.execute(statement)).scalars().all()
    count = len(rows)
    for row in rows:
        await db_session.delete(row)
    await db_session.commit()

    delete_storage_directory(
        f"content/orgs/{org.org_uuid}/{_snapshot_directory(course.course_uuid, activity.activity_uuid, str(target_user_id))}"
    )
    return count
