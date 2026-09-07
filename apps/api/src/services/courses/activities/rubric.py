"""Rubric-based grading.

A task's rubric lives in its OWN ``contents["rubric"]`` field, the same
"no migration" opaque-JSON pattern already used for pool_size/
shuffle_questions/response_type elsewhere in this codebase — a task is
authored once and its rubric is just more of that authoring data. A rubric
is a plain list of criteria:

    [{"criterion_uuid": "...", "title": "...", "description": "...", "max_points": 10}, ...]

Grading against it writes per-criterion points to
AssignmentTaskSubmission.rubric_scores (``{criterion_uuid: awarded_points}``)
rather than a free-form number — `compute_rubric_grade` then derives the
task's normal 0-100 `grade` field from that server-side, so every existing
downstream consumer (aggregate grading, certificates, the activity trail)
keeps reading the exact same `grade` column it always has, completely
unaware a rubric was involved.
"""

from __future__ import annotations

from typing import Optional


def _iter_criteria(rubric) -> list[dict]:
    if not isinstance(rubric, list):
        return []
    out = []
    for c in rubric:
        if isinstance(c, dict) and c.get("criterion_uuid") and isinstance(c.get("max_points"), (int, float)):
            out.append(c)
    return out


def compute_rubric_grade(rubric, scores: Optional[dict]) -> Optional[int]:
    """0-100 grade derived from ``scores`` (``{criterion_uuid: points}``)
    against ``rubric``'s per-criterion max_points. Each per-criterion score
    is clamped to [0, max_points] — a client sending an inflated point value
    for one row can't push the total past what that row is actually worth.

    Returns None when the rubric has no valid criteria (nothing to grade
    against) or none of the criteria were scored — callers should fall back
    to whatever grade they already have rather than treating None as zero.
    """
    criteria = _iter_criteria(rubric)
    if not criteria:
        return None

    total_possible = sum(float(c["max_points"]) for c in criteria)
    if total_possible <= 0:
        return None

    scores = scores or {}
    awarded = 0.0
    any_scored = False
    for c in criteria:
        raw = scores.get(c["criterion_uuid"])
        if raw is None:
            continue
        any_scored = True
        max_points = float(c["max_points"])
        awarded += max(0.0, min(float(raw), max_points))

    if not any_scored:
        return None

    return round(100 * awarded / total_possible)


def clamp_rubric_scores(rubric, scores: Optional[dict]) -> dict:
    """The stored version of ``scores``: every value clamped to its
    criterion's [0, max_points], and any key not naming a real criterion on
    this rubric dropped. Keeps a malformed/stale client payload from
    persisting scores against criteria that don't exist (e.g. after a
    teacher edits the rubric).
    """
    criteria = {c["criterion_uuid"]: float(c["max_points"]) for c in _iter_criteria(rubric)}
    scores = scores or {}
    clamped = {}
    for criterion_uuid, max_points in criteria.items():
        raw = scores.get(criterion_uuid)
        if raw is None:
            continue
        try:
            clamped[criterion_uuid] = max(0.0, min(float(raw), max_points))
        except (TypeError, ValueError):
            continue
    return clamped
