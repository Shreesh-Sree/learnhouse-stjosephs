from typing import List

from fastapi import APIRouter, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.courses.live_sessions import LiveSessionCreate, LiveSessionRead, LiveSessionUpdate
from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.services.courses.live_sessions import (
    create_live_session,
    delete_live_session,
    list_live_sessions_for_course,
    update_live_session,
)

router = APIRouter()


@router.post(
    "/{course_uuid}/live_sessions",
    response_model=LiveSessionRead,
    summary="Schedule a live session",
    description=(
        "Instructor-only. Schedules a live video session (an embedded "
        "meeting link — Zoom, Google Meet, Teams, or any http(s) URL — "
        "not a native in-app video call; see services/courses/"
        "live_sessions.py for the scope decision)."
    ),
    responses={
        200: {"description": "Live session created.", "model": LiveSessionRead},
        400: {"description": "Invalid title, start time, or meeting URL"},
        403: {"description": "User lacks permission to add content to this course"},
        404: {"description": "Course not found"},
    },
)
async def api_create_live_session(
    request: Request,
    course_uuid: str,
    body: LiveSessionCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> LiveSessionRead:
    return await create_live_session(request, course_uuid, body, current_user, db_session)


@router.get(
    "/{course_uuid}/live_sessions",
    response_model=List[LiveSessionRead],
    summary="List a course's live sessions",
    description="Readable by anyone with course READ access — students see the schedule too, not just instructors.",
    responses={
        200: {"description": "Live sessions, earliest first.", "model": List[LiveSessionRead]},
        403: {"description": "User lacks read access to this course"},
        404: {"description": "Course not found"},
    },
)
async def api_list_live_sessions(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[LiveSessionRead]:
    return await list_live_sessions_for_course(request, course_uuid, current_user, db_session)


@router.put(
    "/{course_uuid}/live_sessions/{session_uuid}",
    response_model=LiveSessionRead,
    summary="Update a live session",
    description="Instructor-only.",
    responses={
        200: {"description": "Live session updated.", "model": LiveSessionRead},
        400: {"description": "Invalid title, start time, or meeting URL"},
        403: {"description": "User lacks permission to modify this course"},
        404: {"description": "Course or live session not found"},
    },
)
async def api_update_live_session(
    request: Request,
    course_uuid: str,
    session_uuid: str,
    body: LiveSessionUpdate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> LiveSessionRead:
    return await update_live_session(request, course_uuid, session_uuid, body, current_user, db_session)


@router.delete(
    "/{course_uuid}/live_sessions/{session_uuid}",
    summary="Cancel a live session",
    description="Instructor-only.",
    responses={
        200: {"description": "Live session deleted."},
        403: {"description": "User lacks permission to modify this course"},
        404: {"description": "Course or live session not found"},
    },
)
async def api_delete_live_session(
    request: Request,
    course_uuid: str,
    session_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await delete_live_session(request, course_uuid, session_uuid, current_user, db_session)
