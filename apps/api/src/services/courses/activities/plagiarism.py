"""Cross-submission similarity ("plagiarism") checking.

See db.courses.plagiarism's module docstring for what this is (an in-house
review aid using k-shingle Jaccard similarity) and what it is NOT (a
third-party API call, an automated penalty, or the same thing as
`anti_copy_paste`).

FALSE-POSITIVE WARNING, worth being explicit about: this compares raw text
similarity with no understanding of the task. A SHORT_ANSWER task with a
single narrow correct answer (e.g. "What is the capital of France?") will
show near-100% "similarity" between every student who simply got it right —
that is not plagiarism, it's convergent correctness. `_MIN_TOKENS_FOR_COMPARISON`
filters out the shortest, most convergence-prone answers, but does not
eliminate the problem for longer narrow-answer tasks. This tool is most
meaningful for CODE and open-ended SHORT_ANSWER tasks where genuine
solution diversity is expected — an instructor reviewing a flagged pair is
still the one making the actual judgment call, which is why this never
touches a grade on its own.
"""

from __future__ import annotations

import re
from datetime import datetime
from itertools import combinations
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.assignments import (
    Assignment,
    AssignmentTask,
    AssignmentTaskSubmission,
    AssignmentTaskTypeEnum,
)
from src.db.courses.courses import Course
from src.db.courses.plagiarism import PlagiarismMatch, PlagiarismMatchRead
from src.db.users import AnonymousUser, APITokenUser, PublicUser
from src.security.rbac import AccessAction, check_resource_access

# Task types with free-form text worth comparing. FILE_SUBMISSION is
# excluded — the submitted content is a binary/document reference, not
# inline text this module can shingle without a separate text-extraction
# pipeline (a real gap, not an oversight — see PENDING_FEATURES.md).
_SIMILARITY_TASK_TYPES = (AssignmentTaskTypeEnum.CODE, AssignmentTaskTypeEnum.SHORT_ANSWER)

# Below this many tokens, shingle similarity is dominated by how short two
# answers both happen to be rather than genuine overlap — skip the pair
# rather than report a misleading number.
_MIN_TOKENS_FOR_COMPARISON = 20
_SHINGLE_SIZE = 5


def _extract_text(assignment_type, task_submission) -> str:
    if not isinstance(task_submission, dict):
        return ""
    if assignment_type == AssignmentTaskTypeEnum.CODE:
        return str(task_submission.get("source_code") or "")
    if assignment_type == AssignmentTaskTypeEnum.SHORT_ANSWER:
        return str(task_submission.get("answer") or "")
    return ""


def _shingles(text: str, k: int = _SHINGLE_SIZE) -> set[str] | None:
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < _MIN_TOKENS_FOR_COMPARISON:
        return None
    if len(tokens) < k:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def compute_similarity_percent(text_a: str, text_b: str) -> int | None:
    """0-100 Jaccard similarity between two texts' k-shingle sets, or None
    when either text is too short to compare meaningfully (see
    _MIN_TOKENS_FOR_COMPARISON).
    """
    shingles_a = _shingles(text_a)
    shingles_b = _shingles(text_b)
    if shingles_a is None or shingles_b is None or not shingles_a or not shingles_b:
        return None
    intersection = len(shingles_a & shingles_b)
    union = len(shingles_a | shingles_b)
    if union == 0:
        return None
    return round(100 * intersection / union)


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


async def run_plagiarism_check(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> dict:
    """Instructor-only. Recomputes similarity for every CODE/SHORT_ANSWER
    task on this assignment, across every pair of students who submitted
    one, and replaces the stored matches at or above
    ``assignment.plagiarism_similarity_threshold`` with the fresh result —
    a full recompute each run (existing rows for this assignment are
    cleared first) rather than an incremental update, since re-running
    after more students submit is the expected use and a stale partial
    result would be worse than a clean one.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    if not assignment.enable_plagiarism_check:
        raise HTTPException(status_code=400, detail="This assignment does not use plagiarism checking.")

    threshold = int(assignment.plagiarism_similarity_threshold or 70)

    tasks_statement = select(AssignmentTask).where(
        AssignmentTask.assignment_id == assignment.id,
        AssignmentTask.assignment_type.in_(_SIMILARITY_TASK_TYPES),  # type: ignore[attr-defined]
    )
    tasks = (await db_session.execute(tasks_statement)).scalars().all()

    # Clear this assignment's existing matches before recomputing.
    existing_statement = select(PlagiarismMatch).where(PlagiarismMatch.assignment_id == assignment.id)
    for row in (await db_session.execute(existing_statement)).scalars().all():
        await db_session.delete(row)
    await db_session.commit()

    now_str = str(datetime.now())
    flagged = 0
    compared_pairs = 0
    for task in tasks:
        if task.id is None:
            continue
        submissions_statement = select(AssignmentTaskSubmission).where(
            AssignmentTaskSubmission.assignment_task_id == task.id
        )
        submissions = (await db_session.execute(submissions_statement)).scalars().all()
        texts_by_user = {
            s.user_id: _extract_text(task.assignment_type, s.task_submission)
            for s in submissions
        }
        texts_by_user = {uid: text for uid, text in texts_by_user.items() if text.strip()}

        for (user_a, text_a), (user_b, text_b) in combinations(texts_by_user.items(), 2):
            compared_pairs += 1
            similarity = compute_similarity_percent(text_a, text_b)
            if similarity is None or similarity < threshold:
                continue
            flagged += 1
            lo, hi = sorted((user_a, user_b))
            db_session.add(
                PlagiarismMatch(
                    match_uuid=f"plagiarismmatch_{uuid4()}",
                    assignment_id=assignment.id,
                    assignment_task_id=task.id,
                    user_a_id=lo,
                    user_b_id=hi,
                    similarity_percent=similarity,
                    creation_date=now_str,
                )
            )

    await db_session.commit()
    return {
        "message": f"Checked {compared_pairs} submission pair(s) across {len(tasks)} task(s); {flagged} flagged.",
        "tasks_checked": len(tasks),
        "pairs_compared": compared_pairs,
        "flagged": flagged,
        "threshold": threshold,
    }


async def list_plagiarism_matches(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser | AnonymousUser | APITokenUser,
    db_session: AsyncSession,
) -> list[PlagiarismMatchRead]:
    """Instructor-only: every flagged pair on this assignment, most similar
    first.
    """
    assignment, course = await _resolve_assignment_and_course(assignment_uuid, db_session)
    await check_resource_access(request, db_session, current_user, course.course_uuid, AccessAction.UPDATE)

    statement = select(PlagiarismMatch).where(
        PlagiarismMatch.assignment_id == assignment.id
    ).order_by(PlagiarismMatch.similarity_percent.desc())
    rows = (await db_session.execute(statement)).scalars().all()
    return [PlagiarismMatchRead.model_validate(r) for r in rows]
