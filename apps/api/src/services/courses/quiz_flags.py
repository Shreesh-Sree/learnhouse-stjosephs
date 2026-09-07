"""Student-flaggable quiz questions — create/list/resolve.

See db/courses/quiz_flags.py for the data-model scope decision (ungraded
in-content blockQuiz only; a flag snapshots the question text rather than
referencing a row, since a quiz question isn't one).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.activities import Activity
from src.db.courses.courses import Course
from src.db.courses.quiz_flags import (
    QuizFlagAuthor,
    QuizFlagRead,
    QuizFlagReason,
    QuizFlagStatus,
    QuizQuestionFlag,
)
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.security.rbac import AccessAction, authorization_verify_if_user_is_anon, check_resource_access

# Backstop against one student flooding a course's review queue — generous
# enough that no genuine use ever hits it (a real course has, at most, a few
# hundred quiz questions total), narrow enough to make spamming pointless.
MAX_OPEN_FLAGS_PER_USER_PER_COURSE = 50


def _find_question_text(content: dict, quiz_id: str, question_id: str) -> Optional[str]:
    """Walk an activity's Prosemirror content document for the blockQuiz
    node matching ``quiz_id`` and return the current text of ``question_id``
    within it, or None if either isn't found. Defends against a flag being
    raised against a stale or fabricated (quiz_id, question_id) pair."""
    nodes = content.get("content") if isinstance(content, dict) else None
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "blockQuiz":
            continue
        attrs = node.get("attrs") or {}
        if attrs.get("quizId") != quiz_id:
            continue
        for question in attrs.get("questions") or []:
            if isinstance(question, dict) and question.get("question_id") == question_id:
                return question.get("question") or ""
    return None


async def create_quiz_flag(
    request: Request,
    activity_uuid: str,
    quiz_id: str,
    question_id: str,
    reason: QuizFlagReason,
    note: Optional[str],
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> QuizFlagRead:
    await authorization_verify_if_user_is_anon(current_user.id)

    activity = (await db_session.execute(
        select(Activity).where(Activity.activity_uuid == activity_uuid)
    )).scalars().first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    course = (await db_session.execute(
        select(Course).where(Course.id == activity.course_id)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Anyone who can READ the activity's course may flag a question in it —
    # deliberately not gated any tighter (e.g. to "enrolled students only"),
    # since the same READ check already governs who can see the quiz at all.
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    question_text = _find_question_text(activity.content or {}, quiz_id, question_id)
    if question_text is None:
        raise HTTPException(status_code=404, detail="Question not found in this activity")

    # Idempotent: a second flag from the same student on the same still-open
    # question returns the existing row rather than creating a duplicate.
    existing = (await db_session.execute(
        select(QuizQuestionFlag).where(
            QuizQuestionFlag.activity_id == activity.id,
            QuizQuestionFlag.question_id == question_id,
            QuizQuestionFlag.flagged_by_user_id == current_user.id,
            QuizQuestionFlag.status == QuizFlagStatus.OPEN,
        )
    )).scalars().first()
    if existing:
        return await _to_read(existing, db_session)

    open_count = (await db_session.execute(
        select(func.count(QuizQuestionFlag.id)).where(
            QuizQuestionFlag.course_id == course.id,
            QuizQuestionFlag.flagged_by_user_id == current_user.id,
            QuizQuestionFlag.status == QuizFlagStatus.OPEN,
        )
    )).scalar_one()
    if open_count >= MAX_OPEN_FLAGS_PER_USER_PER_COURSE:
        raise HTTPException(
            status_code=429,
            detail="You have too many open flags in this course already — wait for an instructor to review them.",
        )

    flag = QuizQuestionFlag(
        flag_uuid=f"quizflag_{uuid4()}",
        org_id=course.org_id,
        course_id=course.id if course.id is not None else 0,
        activity_id=activity.id if activity.id is not None else 0,
        quiz_id=quiz_id,
        question_id=question_id,
        question_text_snapshot=question_text,
        reason=reason,
        note=(note or "").strip()[:2000] or None,
        status=QuizFlagStatus.OPEN,
        flagged_by_user_id=current_user.id,
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db_session.add(flag)
    await db_session.commit()
    await db_session.refresh(flag)

    return await _to_read(flag, db_session)


async def list_quiz_flags_for_course(
    request: Request,
    course_uuid: str,
    status_filter: Optional[QuizFlagStatus],
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[QuizFlagRead]:
    course = (await db_session.execute(
        select(Course).where(Course.course_uuid == course_uuid)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    query = select(QuizQuestionFlag).where(QuizQuestionFlag.course_id == course.id)
    if status_filter is not None:
        query = query.where(QuizQuestionFlag.status == status_filter)
    query = query.order_by(QuizQuestionFlag.creation_date.desc())  # type: ignore

    flags = (await db_session.execute(query)).scalars().all()
    return await _to_read_batch(flags, db_session)


async def resolve_quiz_flag(
    request: Request,
    flag_uuid: str,
    new_status: QuizFlagStatus,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> QuizFlagRead:
    flag = (await db_session.execute(
        select(QuizQuestionFlag).where(QuizQuestionFlag.flag_uuid == flag_uuid)
    )).scalars().first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    course = (await db_session.execute(
        select(Course).where(Course.id == flag.course_id)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    flag.status = new_status
    flag.resolved_by_user_id = current_user.id
    flag.resolved_at = str(datetime.now())
    flag.update_date = str(datetime.now())
    db_session.add(flag)
    await db_session.commit()
    await db_session.refresh(flag)

    return await _to_read(flag, db_session)


async def _to_read(flag: QuizQuestionFlag, db_session: AsyncSession) -> QuizFlagRead:
    return (await _to_read_batch([flag], db_session))[0]


async def _to_read_batch(
    flags: list[QuizQuestionFlag], db_session: AsyncSession
) -> list[QuizFlagRead]:
    """Batch-fetch every activity and user a page of flags references,
    instead of one query per flag per relation — the same pattern used for
    discussion/comment list reads elsewhere in this codebase."""
    if not flags:
        return []

    activity_ids = {f.activity_id for f in flags}
    activities_map: dict[int, Activity] = {}
    if activity_ids:
        activities = (await db_session.execute(
            select(Activity).where(Activity.id.in_(activity_ids))  # type: ignore[attr-defined]
        )).scalars().all()
        activities_map = {a.id: a for a in activities}

    user_ids = {
        uid
        for f in flags
        for uid in (f.flagged_by_user_id, f.resolved_by_user_id)
        if uid is not None
    }
    users_map: dict[int, User] = {}
    if user_ids:
        users = (await db_session.execute(
            select(User).where(User.id.in_(user_ids))  # type: ignore[attr-defined]
        )).scalars().all()
        users_map = {u.id: u for u in users}

    def _author(user_id: Optional[int]) -> Optional[QuizFlagAuthor]:
        user = users_map.get(user_id) if user_id is not None else None
        if not user:
            return None
        return QuizFlagAuthor(
            id=user.id,
            user_uuid=user.user_uuid,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    result = []
    for flag in flags:
        activity = activities_map.get(flag.activity_id)
        result.append(
            QuizFlagRead(
                flag_uuid=flag.flag_uuid,
                activity_uuid=activity.activity_uuid if activity else "",
                activity_name=activity.name if activity else "(deleted activity)",
                quiz_id=flag.quiz_id,
                question_id=flag.question_id,
                question_text_snapshot=flag.question_text_snapshot,
                reason=flag.reason,
                note=flag.note,
                status=flag.status,
                flagged_by=_author(flag.flagged_by_user_id),
                resolved_by=_author(flag.resolved_by_user_id),
                resolved_at=flag.resolved_at,
                creation_date=flag.creation_date,
            )
        )
    return result
