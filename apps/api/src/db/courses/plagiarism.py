"""Cross-submission similarity ("plagiarism") checking.

DISTINCT FROM `anti_copy_paste`: that field is a behavioral deterrent (it
blocks paste events in the student's browser while they're answering,
discouraging copying FROM an external source). This module instead compares
students' submissions AGAINST EACH OTHER, after the fact, to surface
suspiciously similar answers for an instructor to review — it never blocks
or auto-penalizes anything.

Detection is in-house (no third-party API — this is a self-hosted
deployment with no assumed network egress to Turnitin/Copyleaks/etc.),
using k-shingle Jaccard similarity — the same core idea real similarity
detectors (MOSS and others) are built on, computed here in pure Python.
It is a legitimate, if unsophisticated, technique: real false positives are
possible (see services.courses.activities.plagiarism module docstring for
the specific failure mode with narrow-answer SHORT_ANSWER tasks), so this
is a REVIEW AID for an instructor, not an accusation or an automated
penalty — nothing here touches a grade.

Results are stored per (assignment_task, ordered user pair) so a re-run
doesn't accumulate duplicate rows for the same pair.
"""

from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


class PlagiarismMatchBase(SQLModel):
    similarity_percent: int


class PlagiarismMatch(PlagiarismMatchBase, table=True):
    __tablename__ = "plagiarism_match"
    __table_args__ = (
        UniqueConstraint(
            "assignment_task_id", "user_a_id", "user_b_id",
            name="uq_plagiarism_match_task_pair",
        ),
        Index("ix_plagiarism_match_assignment_id", "assignment_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    match_uuid: str = Field(default="", index=True)
    assignment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment.id", ondelete="CASCADE"), nullable=False)
    )
    assignment_task_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignmenttask.id", ondelete="CASCADE"), nullable=False)
    )
    # Canonical pair ordering (user_a_id < user_b_id), enforced by the
    # service layer that writes these rows — so (student X, student Y) is
    # never stored twice as two separate directional rows.
    user_a_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    user_b_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""


class PlagiarismMatchRead(PlagiarismMatchBase):
    match_uuid: str
    assignment_task_id: int
    user_a_id: int
    user_b_id: int
    creation_date: str
