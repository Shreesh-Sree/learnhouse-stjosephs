"""Peer review assignment and grading workflow.

See db.courses.peer_reviews' module docstring for the identity-anonymity
rule this module enforces in both directions: a reviewer never learns whose
submission they're reviewing, and a reviewee never learns who reviewed
them. Every read function here is written around that — the instructor-only
reads are the only ones that ever populate both identity fields.

Peer scores are ADVISORY. Nothing here ever writes to
AssignmentUserSubmission.grade — only the instructor's own grading action
(grade_assignment_submission / grade_group_assignment in
services.courses.activities.assignments) does that. This module surfaces
peer feedback for the instructor to read alongside their own judgment, not
to replace it — a self-hosted college using this for a real course grade
needs a human accountable for it, not an average of undergrads' opinions of
each other's work.
"""

from __future__ import annotations

import random
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignments import (
    Assignment,
    AssignmentTask,
    AssignmentTaskSubmission,
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
)
from src.db.courses.courses import Course
from src.db.courses.peer_reviews import PeerReview, PeerReviewRead, PeerReviewStatus
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.rbac import AccessAction, check_resource_access

# A submission counts as reviewable once it's actually been handed in.
_REVIEWABLE_STATUSES = (
    AssignmentUserSubmissionStatus.SUBMITTED,
    AssignmentUserSubmissionStatus.LATE,
    AssignmentUserSubmissionStatus.GRADED,
)


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


def _to_read(review: PeerReview, *, reveal_identities: bool) -> PeerReviewRead:
    return PeerReviewRead(
        review_uuid=review.review_uuid,
        score=review.score,
        feedback=review.feedback,
        status=review.status,
        creation_date=review.creation_date,
        update_date=review.update_date,
        submitted_at=review.submitted_at,
        reviewer_user_id=review.reviewer_user_id if reveal_identities else None,
        target_user_id=review.target_user_id if reveal_identities else None,
    )


async def assign_peer_reviews(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """Instructor-only. Hands every learner who has submitted this
    assignment `assignment.peer_reviews_per_submission` classmates'
    submissions to review, via a shuffled circular assignment (reviewer i
    reviews the next k candidates after them in the shuffled order) so
    reviews are spread evenly with nobody reviewing themselves.

    Idempotent: re-running this after new students submit only creates
    NEW (reviewer, target) pairs — the unique constraint means an existing
    pair is never duplicated, so calling this again doesn't reset anyone's
    in-progress review. It does NOT retroactively assign new reviewers for
    a student who submitted after the first run to every existing
    candidate, or vice versa — it's a fresh circular assignment over
    whoever is a candidate at call time, so some pairings from an earlier
    run and a later run can differ. Fine for the common case (run this once
    after the deadline), documented as a limitation for the "some students
    trickle in late" case.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    if not assignment.enable_peer_review:
        raise HTTPException(status_code=400, detail="This assignment does not use peer review.")

    statement = select(AssignmentUserSubmission.user_id).where(
        AssignmentUserSubmission.assignment_id == assignment.id,
        AssignmentUserSubmission.submission_status.in_(_REVIEWABLE_STATUSES),  # type: ignore[attr-defined]
    )
    candidates = list((await db_session.execute(statement)).scalars().all())
    if len(candidates) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough submitted attempts yet to assign peer reviews.",
        )

    k = max(1, min(int(assignment.peer_reviews_per_submission or 2), len(candidates) - 1))

    existing_statement = select(PeerReview.reviewer_user_id, PeerReview.target_user_id).where(
        PeerReview.assignment_id == assignment.id
    )
    existing_pairs = {(r, t) for r, t in (await db_session.execute(existing_statement)).all()}

    shuffled = list(candidates)
    random.shuffle(shuffled)
    n = len(shuffled)

    created = 0
    now_str = str(datetime.now())
    for i, reviewer_id in enumerate(shuffled):
        for j in range(1, k + 1):
            target_id = shuffled[(i + j) % n]
            if (reviewer_id, target_id) in existing_pairs:
                continue
            db_session.add(
                PeerReview(
                    review_uuid=f"peerreview_{uuid4()}",
                    assignment_id=assignment.id,
                    reviewer_user_id=reviewer_id,
                    target_user_id=target_id,
                    status=PeerReviewStatus.PENDING,
                    creation_date=now_str,
                    update_date=now_str,
                )
            )
            existing_pairs.add((reviewer_id, target_id))
            created += 1

    await db_session.commit()
    return {"message": f"Assigned {created} new peer review(s).", "created": created}


async def list_my_peer_reviews_to_do(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[PeerReviewRead]:
    """Every review assigned TO the caller as reviewer for this assignment.
    Never reveals the target's identity — see module docstring.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    statement = select(PeerReview).where(
        PeerReview.assignment_id == assignment.id,
        PeerReview.reviewer_user_id == current_user.id,
    ).order_by(PeerReview.creation_date.asc())
    reviews = (await db_session.execute(statement)).scalars().all()
    return [_to_read(r, reveal_identities=False) for r in reviews]


async def get_peer_review_submission_view(
    request: Request,
    assignment_uuid: str,
    review_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """The reviewer's view of the submission they're assigned to review:
    every task's definition (answer key stripped, same treatment a student
    gets) alongside the target's own submitted answer. Never includes any
    grade/feedback on the target's tasks, or the target's identity.
    """
    from src.services.courses.activities.assignments import _strip_answer_key

    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    statement = select(PeerReview).where(
        PeerReview.review_uuid == review_uuid,
        PeerReview.assignment_id == assignment.id,
    )
    review = (await db_session.execute(statement)).scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Peer review not found")
    if review.reviewer_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This peer review isn't assigned to you.")

    tasks_statement = select(AssignmentTask).where(AssignmentTask.assignment_id == assignment.id)
    tasks = (await db_session.execute(tasks_statement)).scalars().all()
    task_ids = [t.id for t in tasks if t.id is not None]

    submissions_by_task: dict = {}
    if task_ids:
        sub_statement = select(AssignmentTaskSubmission).where(
            AssignmentTaskSubmission.assignment_task_id.in_(task_ids),  # type: ignore[attr-defined]
            AssignmentTaskSubmission.user_id == review.target_user_id,
        )
        for row in (await db_session.execute(sub_statement)).scalars().all():
            submissions_by_task[row.assignment_task_id] = row

    tasks_out = []
    for task in tasks:
        submission = submissions_by_task.get(task.id)
        tasks_out.append({
            "assignment_task_uuid": task.assignment_task_uuid,
            "title": task.title,
            "description": task.description,
            "assignment_type": task.assignment_type,
            "contents": _strip_answer_key(task.contents, keep_answer_keys=False),
            "task_submission": submission.task_submission if submission else None,
        })

    return {
        "review_uuid": review.review_uuid,
        "status": review.status,
        "score": review.score,
        "feedback": review.feedback,
        "tasks": tasks_out,
    }


async def submit_peer_review(
    request: Request,
    assignment_uuid: str,
    review_uuid: str,
    score: int | None,
    feedback: str | None,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> PeerReviewRead:
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    statement = select(PeerReview).where(
        PeerReview.review_uuid == review_uuid,
        PeerReview.assignment_id == assignment.id,
    )
    review = (await db_session.execute(statement)).scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Peer review not found")
    if review.reviewer_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This peer review isn't assigned to you.")

    if score is not None and not (0 <= score <= 100):
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100.")

    review.score = score
    review.feedback = feedback
    review.status = PeerReviewStatus.COMPLETED
    review.submitted_at = str(datetime.now())
    review.update_date = review.submitted_at
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    return _to_read(review, reveal_identities=False)


async def list_peer_reviews_received(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """The caller's own received feedback. Withheld (only a progress count)
    until every review assigned to them as TARGET is COMPLETED — a partial
    reveal lets a student who got one harsh review early infer who wrote it
    once the rest land, which defeats the anonymity this is supposed to
    guarantee. Never reveals reviewer identity, complete or not.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.READ)

    statement = select(PeerReview).where(
        PeerReview.assignment_id == assignment.id,
        PeerReview.target_user_id == current_user.id,
    )
    reviews = (await db_session.execute(statement)).scalars().all()
    total = len(reviews)
    completed = [r for r in reviews if r.status == PeerReviewStatus.COMPLETED]

    if total == 0 or len(completed) < total:
        return {
            "revealed": False,
            "completed_count": len(completed),
            "total_count": total,
            "reviews": [],
        }

    return {
        "revealed": True,
        "completed_count": len(completed),
        "total_count": total,
        "reviews": [_to_read(r, reveal_identities=False) for r in completed],
    }


async def get_peer_review_summary_for_user(
    request: Request,
    assignment_uuid: str,
    target_user_id: int,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """Instructor-only: every review received by one student, with full
    reviewer identities and an average score — for the grading UI. Unlike
    `list_peer_reviews_received`, this is not gated on every review being
    complete; an instructor grading early should see partial peer feedback
    rather than nothing.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(PeerReview).where(
        PeerReview.assignment_id == assignment.id,
        PeerReview.target_user_id == target_user_id,
    ).order_by(PeerReview.creation_date.asc())
    reviews = (await db_session.execute(statement)).scalars().all()

    scored = [r.score for r in reviews if r.status == PeerReviewStatus.COMPLETED and r.score is not None]
    average = round(sum(scored) / len(scored), 1) if scored else None

    return {
        "average_score": average,
        "completed_count": sum(1 for r in reviews if r.status == PeerReviewStatus.COMPLETED),
        "total_count": len(reviews),
        "reviews": [_to_read(r, reveal_identities=True) for r in reviews],
    }
