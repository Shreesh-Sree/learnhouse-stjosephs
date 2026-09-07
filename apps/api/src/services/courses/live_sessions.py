"""Scheduled live video sessions — CRUD + the student-facing list.

See db/courses/live_sessions.py's module docstring for the embedded-link
scope decision. This module is the same shape as roster.py/qti_import.py:
resolve the course, check RBAC, do the thing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.courses import Course
from src.db.courses.live_sessions import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionRead,
    LiveSessionUpdate,
)
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.rbac import AccessAction, check_resource_access


def _validate_meeting_url(url: str) -> str:
    """Reject anything that isn't a plain http(s) link — this value is
    rendered as a clickable "Join" href and, unescaped, would otherwise be
    a javascript:/data: XSS vector for whoever clicks it."""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Meeting URL must be a valid http(s) link")
    return url


def _to_read(session: LiveSession) -> LiveSessionRead:
    return LiveSessionRead(
        session_uuid=session.session_uuid,
        course_id=session.course_id,
        title=session.title,
        description=session.description,
        meeting_url=session.meeting_url,
        start_time=session.start_time,
        end_time=session.end_time,
        created_by_user_id=session.created_by_user_id,
        creation_date=session.creation_date,
        update_date=session.update_date,
    )


async def _get_course_or_404(course_uuid: str, db_session: AsyncSession) -> Course:
    course = (await db_session.execute(
        select(Course).where(Course.course_uuid == course_uuid)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


async def create_live_session(
    request: Request,
    course_uuid: str,
    body: LiveSessionCreate,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> LiveSessionRead:
    course = await _get_course_or_404(course_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.CREATE)

    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if not body.start_time.strip():
        raise HTTPException(status_code=400, detail="Start time is required")
    meeting_url = _validate_meeting_url(body.meeting_url)

    session = LiveSession(
        session_uuid=f"livesession_{uuid4()}",
        org_id=course.org_id,
        course_id=course.id if course.id is not None else 0,
        title=body.title.strip(),
        description=body.description,
        meeting_url=meeting_url,
        start_time=body.start_time.strip(),
        end_time=(body.end_time or "").strip() or None,
        created_by_user_id=current_user.id,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return _to_read(session)


async def list_live_sessions_for_course(
    request: Request,
    course_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[LiveSessionRead]:
    course = await _get_course_or_404(course_uuid, db_session)
    # READ access — students see the schedule too, not just instructors.
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    sessions = (await db_session.execute(
        select(LiveSession)
        .where(LiveSession.course_id == course.id)
        .order_by(LiveSession.start_time.asc())  # type: ignore
    )).scalars().all()
    return [_to_read(s) for s in sessions]


async def update_live_session(
    request: Request,
    course_uuid: str,
    session_uuid: str,
    body: LiveSessionUpdate,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> LiveSessionRead:
    course = await _get_course_or_404(course_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    session = (await db_session.execute(
        select(LiveSession).where(LiveSession.session_uuid == session_uuid, LiveSession.course_id == course.id)
    )).scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found")

    if body.title is not None:
        if not body.title.strip():
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        session.title = body.title.strip()
    if body.description is not None:
        session.description = body.description
    if body.meeting_url is not None:
        session.meeting_url = _validate_meeting_url(body.meeting_url)
    if body.start_time is not None:
        if not body.start_time.strip():
            raise HTTPException(status_code=400, detail="Start time cannot be empty")
        session.start_time = body.start_time.strip()
    if body.end_time is not None:
        session.end_time = body.end_time.strip() or None

    session.update_date = str(datetime.now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return _to_read(session)


async def delete_live_session(
    request: Request,
    course_uuid: str,
    session_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    course = await _get_course_or_404(course_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.DELETE)

    session = (await db_session.execute(
        select(LiveSession).where(LiveSession.session_uuid == session_uuid, LiveSession.course_id == course.id)
    )).scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found")

    await db_session.delete(session)
    await db_session.commit()
    return {"detail": "Live session deleted"}
