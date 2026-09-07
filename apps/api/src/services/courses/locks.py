"""Lock-based access checks for chapters and activities.

Mirrors the Playground access-type pattern but keyed on chapter_uuid /
activity_uuid in ``usergroupresource``. Lock tiers:

- ``public``:        anyone, including anonymous, can read
- ``authenticated``: must be signed in
- ``restricted``:    must be in an assigned usergroup (or an org admin)

Batch helpers are provided for TOC-style reads where many resources need
to be checked at once without N+1 queries.
"""

from typing import Iterable

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import Activity
from src.db.courses.chapter_activities import ChapterActivity
from src.db.trail_steps import TrailStep
from src.db.user_organizations import UserOrganization
from src.db.usergroup_resources import UserGroupResource
from src.db.usergroup_user import UserGroupUser
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.auth import resolve_acting_user_id
from src.security.rbac.constants import ADMIN_OR_MAINTAINER_ROLE_IDS


async def is_org_admin(user_id: int, org_id: int, db_session: AsyncSession) -> bool:
    """True if user is admin/maintainer on this org (bypasses all locks)."""
    uo = (await db_session.execute(
        select(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.org_id == org_id,
        )
    )).scalars().first()
    return bool(uo and uo.role_id in ADMIN_OR_MAINTAINER_ROLE_IDS)


async def batch_accessible_restricted_uuids(
    user_id: int,
    resource_uuids: Iterable[str],
    db_session: AsyncSession,
) -> set[str]:
    """Return the subset of resource_uuids the user can access via usergroup."""
    uuids = [u for u in resource_uuids if u]
    if not uuids:
        return set()

    ugrs = (await db_session.execute(
        select(
            UserGroupResource.resource_uuid,
            UserGroupResource.usergroup_id,
        ).where(UserGroupResource.resource_uuid.in_(uuids))
    )).all()
    if not ugrs:
        return set()

    ug_ids = list({row[1] for row in ugrs})
    member_ug_ids = set(
        (await db_session.execute(
            select(UserGroupUser.usergroup_id).where(
                UserGroupUser.usergroup_id.in_(ug_ids),
                UserGroupUser.user_id == user_id,
            )
        )).scalars().all()
    )
    return {resource_uuid for resource_uuid, ug_id in ugrs if ug_id in member_ug_ids}


async def is_locked_for_user(
    lock_type: str | None,
    resource_uuid: str,
    org_id: int,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
    *,
    accessible_restricted_uuids: set[str] | None = None,
    is_admin: bool | None = None,
) -> bool:
    """True if the resource should be hidden from current_user.

    ``accessible_restricted_uuids`` and ``is_admin`` are pre-computed escape
    hatches for batch callers -- they avoid repeating the same queries for
    every row. When absent, this function resolves them on its own.
    """
    lt = (lock_type or "public").lower()
    if lt == "public":
        return False

    is_anon = isinstance(current_user, AnonymousUser)
    if lt == "authenticated":
        return is_anon

    if lt != "restricted":
        # Unknown value -- fail safe (treat as public to avoid accidentally
        # locking people out after a rename/migration mishap).
        return False

    if is_anon:
        return True

    acting_user_id = resolve_acting_user_id(current_user)
    admin = is_admin if is_admin is not None else await is_org_admin(acting_user_id, org_id, db_session)
    if admin:
        return False

    if accessible_restricted_uuids is not None:
        return resource_uuid not in accessible_restricted_uuids

    accessible = await batch_accessible_restricted_uuids(
        acting_user_id, [resource_uuid], db_session
    )
    return resource_uuid not in accessible


async def is_chapter_fully_completed(
    user_id: int, chapter_id: int, db_session: AsyncSession
) -> bool:
    """Pure completion check for one chapter: True iff every PUBLISHED
    activity in it has a completed TrailStep for this user. Mirrors
    services.courses.certifications.is_course_fully_completed exactly, just
    scoped to a chapter instead of a whole course — kept as a separate
    function rather than a parameter on that one so neither caller has to
    reason about the other's scope.

    An empty chapter (no published activities) is treated as NOT completed —
    same reasoning as the course-level check: a prerequisite that can never
    be satisfied should read as "still blocked", not silently pass everyone.
    """
    total_activities = (await db_session.execute(
        select(func.count(ChapterActivity.id))
        .join(Activity, Activity.id == ChapterActivity.activity_id)
        .where(ChapterActivity.chapter_id == chapter_id, Activity.published == True)  # noqa: E712
    )).scalar_one()
    if not total_activities:
        return False

    completed_activities = (await db_session.execute(
        select(func.count(func.distinct(TrailStep.activity_id)))
        .join(
            ChapterActivity,
            (ChapterActivity.activity_id == TrailStep.activity_id)
            & (ChapterActivity.chapter_id == chapter_id),
        )
        .join(Activity, Activity.id == ChapterActivity.activity_id)
        .where(
            TrailStep.user_id == user_id,
            TrailStep.complete == True,  # noqa: E712
            Activity.published == True,  # noqa: E712
        )
    )).scalar_one()

    return completed_activities >= total_activities
