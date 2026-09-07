"""Group/team membership for group assignments.

See db.courses.assignment_groups module docstring for the overall design
(row-level fan-out on top of the existing per-user submission tables, not a
schema restructure). This module owns group CRUD and membership only — the
write-time fan-out that actually makes a group behave like a team (syncing
task answers, submitting together, grading together) lives in
services.courses.activities.assignments, next to the single-user code it
reuses.

VISIBILITY: a student sees every group's name, size and fullness (so they
can decide which one to join), but member IDENTITIES only for their OWN
group. An instructor sees everything. There's no legitimate reason for one
student to browse who's in a classmate's group before joining it — that's
the same instinct behind PENDING_FEATURES' "no analytics view naming
individual learners to other learners" pattern.

SELF-SERVICE membership: students create/join/leave groups themselves,
mirroring how a real classroom usually forms teams. An instructor can
additionally delete a group or remove a member (roster cleanup, or breaking
up a non-functional team) but there's no forced-assignment/auto-balancing
tool — teachers who want assigned (not self-picked) teams can remove/re-add
members to get there, which covers the classroom-scale case this is built
for.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignment_groups import (
    AssignmentGroup,
    AssignmentGroupMember,
    AssignmentGroupMemberRead,
    AssignmentGroupRead,
)
from src.db.courses.assignments import Assignment
from src.db.courses.courses import Course
from src.db.organizations import Organization
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.rbac import AccessAction, authorization_verify_based_on_roles, check_resource_access


async def _resolve_assignment_context(
    assignment_uuid: str, db_session: AsyncSession
) -> tuple[Assignment, Course, Organization]:
    statement = select(Assignment).where(Assignment.assignment_uuid == assignment_uuid)
    assignment = (await db_session.execute(statement)).scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    statement = select(Course).where(Course.id == assignment.course_id)
    course = (await db_session.execute(statement)).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    statement = select(Organization).where(Organization.id == course.org_id)
    org = (await db_session.execute(statement)).scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return assignment, course, org


async def _get_membership(
    assignment_id: int, user_id: int, db_session: AsyncSession
) -> AssignmentGroupMember | None:
    statement = select(AssignmentGroupMember).where(
        AssignmentGroupMember.assignment_id == assignment_id,
        AssignmentGroupMember.user_id == user_id,
    )
    return (await db_session.execute(statement)).scalars().first()


async def get_group_member_ids(
    assignment_id: int, user_id: int, db_session: AsyncSession
) -> list[int]:
    """Every member of ``user_id``'s own group for this assignment,
    including themselves. Degrades to ``[user_id]`` when the assignment
    isn't a group assignment or this user isn't in a group yet — callers can
    always call this and iterate, without a separate "is this a group
    assignment" branch.
    """
    membership = await _get_membership(assignment_id, user_id, db_session)
    if membership is None:
        return [user_id]
    statement = select(AssignmentGroupMember.user_id).where(
        AssignmentGroupMember.group_id == membership.group_id
    )
    ids = [row for row in (await db_session.execute(statement)).scalars().all()]
    return ids or [user_id]


async def _member_count(group_id: int, db_session: AsyncSession) -> int:
    statement = select(AssignmentGroupMember.id).where(AssignmentGroupMember.group_id == group_id)
    return len((await db_session.execute(statement)).scalars().all())


async def _to_read(
    group: AssignmentGroup,
    db_session: AsyncSession,
    *,
    max_size: int | None,
    reveal_members: bool,
) -> AssignmentGroupRead:
    statement = select(AssignmentGroupMember).where(AssignmentGroupMember.group_id == group.id).order_by(
        AssignmentGroupMember.creation_date.asc()
    )
    members = (await db_session.execute(statement)).scalars().all()
    count = len(members)
    return AssignmentGroupRead(
        name=group.name,
        group_uuid=group.group_uuid,
        creation_date=group.creation_date,
        member_count=count,
        is_full=bool(max_size) and count >= max_size,
        members=(
            [AssignmentGroupMemberRead(user_id=m.user_id, creation_date=m.creation_date) for m in members]
            if reveal_members
            else None
        ),
    )


async def create_group(
    request: Request,
    assignment_uuid: str,
    name: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> AssignmentGroupRead:
    """A student creates a new group for this assignment and is immediately
    its first member. Also usable by an instructor to pre-seed an empty
    group for students to join.
    """
    assignment, course, org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    if not assignment.allow_group_submission:
        raise HTTPException(status_code=400, detail="This assignment does not use group submission.")

    is_instructor = await authorization_verify_based_on_roles(
        request, current_user.id, "update", course.course_uuid, db_session
    )
    if not is_instructor:
        existing = await _get_membership(assignment.id, current_user.id, db_session)
        if existing is not None:
            raise HTTPException(status_code=400, detail="You are already in a group for this assignment.")

    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required.")

    now_str = str(datetime.now())
    group = AssignmentGroup(
        name=name,
        group_uuid=f"assignmentgroup_{uuid4()}",
        assignment_id=assignment.id,
        org_id=org.id,
        course_id=course.id,
        creation_date=now_str,
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)

    if not is_instructor:
        member = AssignmentGroupMember(
            group_id=group.id,
            assignment_id=assignment.id,
            user_id=current_user.id,
            creation_date=now_str,
        )
        db_session.add(member)
        await db_session.commit()

    return await _to_read(group, db_session, max_size=assignment.group_max_size, reveal_members=True)


async def list_groups(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[AssignmentGroupRead]:
    assignment, course, _org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    is_instructor = await authorization_verify_based_on_roles(
        request, current_user.id, "update", course.course_uuid, db_session
    )
    own_membership = None if is_instructor else await _get_membership(assignment.id, current_user.id, db_session)
    own_group_id = own_membership.group_id if own_membership else None

    statement = select(AssignmentGroup).where(AssignmentGroup.assignment_id == assignment.id).order_by(
        AssignmentGroup.creation_date.asc()
    )
    groups = (await db_session.execute(statement)).scalars().all()

    return [
        await _to_read(
            g,
            db_session,
            max_size=assignment.group_max_size,
            reveal_members=is_instructor or g.id == own_group_id,
        )
        for g in groups
    ]


async def join_group(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> AssignmentGroupRead:
    assignment, course, _org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    if not assignment.allow_group_submission:
        raise HTTPException(status_code=400, detail="This assignment does not use group submission.")

    statement = select(AssignmentGroup).where(
        AssignmentGroup.group_uuid == group_uuid,
        AssignmentGroup.assignment_id == assignment.id,
    )
    group = (await db_session.execute(statement)).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    existing = await _get_membership(assignment.id, current_user.id, db_session)
    if existing is not None:
        if existing.group_id == group.id:
            return await _to_read(group, db_session, max_size=assignment.group_max_size, reveal_members=True)
        raise HTTPException(status_code=400, detail="You are already in a different group for this assignment.")

    if assignment.group_max_size:
        count = await _member_count(group.id, db_session)
        if count >= assignment.group_max_size:
            raise HTTPException(status_code=403, detail="This group is full.")

    member = AssignmentGroupMember(
        group_id=group.id,
        assignment_id=assignment.id,
        user_id=current_user.id,
        creation_date=str(datetime.now()),
    )
    db_session.add(member)
    await db_session.commit()

    return await _to_read(group, db_session, max_size=assignment.group_max_size, reveal_members=True)


async def leave_group(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    assignment, course, _org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    statement = select(AssignmentGroup).where(
        AssignmentGroup.group_uuid == group_uuid,
        AssignmentGroup.assignment_id == assignment.id,
    )
    group = (await db_session.execute(statement)).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    membership = await _get_membership(assignment.id, current_user.id, db_session)
    if membership is None or membership.group_id != group.id:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    await db_session.delete(membership)
    await db_session.commit()

    # Clean up an emptied group rather than leaving an orphan row a student
    # (or another instructor) would otherwise have to notice and delete by
    # hand.
    remaining = await _member_count(group.id, db_session)
    if remaining == 0:
        await db_session.delete(group)
        await db_session.commit()


async def instructor_delete_group(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    assignment, course, _org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(AssignmentGroup).where(
        AssignmentGroup.group_uuid == group_uuid,
        AssignmentGroup.assignment_id == assignment.id,
    )
    group = (await db_session.execute(statement)).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db_session.delete(group)  # cascades to members via ondelete=CASCADE
    await db_session.commit()


async def instructor_remove_member(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    target_user_id: int,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> None:
    assignment, course, _org = await _resolve_assignment_context(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(AssignmentGroup).where(
        AssignmentGroup.group_uuid == group_uuid,
        AssignmentGroup.assignment_id == assignment.id,
    )
    group = (await db_session.execute(statement)).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    statement = select(AssignmentGroupMember).where(
        AssignmentGroupMember.group_id == group.id,
        AssignmentGroupMember.user_id == target_user_id,
    )
    membership = (await db_session.execute(statement)).scalars().first()
    if not membership:
        raise HTTPException(status_code=404, detail="This user is not a member of this group.")

    await db_session.delete(membership)
    await db_session.commit()

    remaining = await _member_count(group.id, db_session)
    if remaining == 0:
        await db_session.delete(group)
        await db_session.commit()
