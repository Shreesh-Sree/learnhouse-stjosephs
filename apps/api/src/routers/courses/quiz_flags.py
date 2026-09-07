from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.courses.quiz_flags import QuizFlagCreate, QuizFlagRead, QuizFlagResolve, QuizFlagStatus
from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.services.courses.quiz_flags import create_quiz_flag, list_quiz_flags_for_course, resolve_quiz_flag

router = APIRouter()


@router.post(
    "/activities/{activity_uuid}/quiz_flags",
    response_model=QuizFlagRead,
    summary="Flag a quiz question",
    description=(
        "Report a problem with a specific question in this activity's quiz "
        "block (wrong answer key, unclear wording, a typo, ...). Anyone who "
        "can view the activity may flag a question; a repeat flag from the "
        "same person on the same still-open question is idempotent."
    ),
    responses={
        200: {"description": "Flag created (or the existing open flag, if already raised)."},
        403: {"description": "User lacks read access to this activity's course"},
        404: {"description": "Activity, course, or question not found"},
        429: {"description": "Too many open flags already raised by this user in this course"},
    },
)
async def api_create_quiz_flag(
    request: Request,
    activity_uuid: str,
    body: QuizFlagCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> QuizFlagRead:
    return await create_quiz_flag(
        request, activity_uuid, body.quiz_id, body.question_id, body.reason, body.note, current_user, db_session
    )


@router.get(
    "/courses/{course_uuid}/quiz_flags",
    response_model=List[QuizFlagRead],
    summary="List a course's flagged quiz questions",
    description="Instructor-only review queue. Filter by status (default: all).",
    responses={
        200: {"description": "List of flags, most recent first.", "model": List[QuizFlagRead]},
        403: {"description": "User lacks permission to manage this course"},
        404: {"description": "Course not found"},
    },
)
async def api_list_quiz_flags(
    request: Request,
    course_uuid: str,
    status: Optional[QuizFlagStatus] = Query(None),
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[QuizFlagRead]:
    return await list_quiz_flags_for_course(request, course_uuid, status, current_user, db_session)


@router.put(
    "/quiz_flags/{flag_uuid}",
    response_model=QuizFlagRead,
    summary="Resolve or dismiss a flagged quiz question",
    description="Instructor-only. Sets the flag's status and records who acted on it and when.",
    responses={
        200: {"description": "Updated flag.", "model": QuizFlagRead},
        403: {"description": "User lacks permission to manage this flag's course"},
        404: {"description": "Flag not found"},
    },
)
async def api_resolve_quiz_flag(
    request: Request,
    flag_uuid: str,
    body: QuizFlagResolve,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> QuizFlagRead:
    return await resolve_quiz_flag(request, flag_uuid, body.status, current_user, db_session)
