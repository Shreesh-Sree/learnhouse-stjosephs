"""Peer review assignment/tracking.

DESIGN: an instructor-triggered action ("assign_peer_reviews") creates one
row per (reviewer, target) pair for an assignment — who owes a review to
whom. The review's own content (score + written feedback) lives on that
same row rather than a separate table, since a review only ever has one
author and one subject and never needs a history of edits beyond "not done
yet" vs "submitted".

ANONYMITY is asymmetric and NOT configurable in either direction:
  - The REVIEWER sees the target's submission content but never the
    target's identity (services.courses.activities.peer_reviews never
    returns target_user_id to a reviewer-facing read).
  - The REVIEWEE sees the feedback/score they received but never who wrote
    it (same treatment in the other direction).
This mirrors how peer review actually needs to work to be honest — a
"transparent" peer review just becomes a popularity contest or a source of
social friction between classmates, and a self-hosted college deployment
has no legitimate case for either identity ever crossing that line. Only
the instructor sees both sides for every review.
"""

from enum import Enum
from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


class PeerReviewStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class PeerReviewBase(SQLModel):
    score: Optional[int] = None
    feedback: Optional[str] = None
    status: PeerReviewStatus = PeerReviewStatus.PENDING


class PeerReview(PeerReviewBase, table=True):
    __tablename__ = "peer_review"
    __table_args__ = (
        # A student reviews a given peer's submission on this assignment at
        # most once — re-running assign_peer_reviews must not create a
        # second obligation for a pair that already has one.
        UniqueConstraint(
            "assignment_id", "reviewer_user_id", "target_user_id",
            name="uq_peer_review_reviewer_target",
        ),
        Index("ix_peer_review_assignment_target", "assignment_id", "target_user_id"),
        Index("ix_peer_review_assignment_reviewer", "assignment_id", "reviewer_user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    review_uuid: str = Field(default="", index=True)
    assignment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment.id", ondelete="CASCADE"), nullable=False)
    )
    reviewer_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    target_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""
    submitted_at: Optional[str] = None


class PeerReviewRead(PeerReviewBase):
    review_uuid: str
    creation_date: str
    update_date: str
    submitted_at: Optional[str] = None
    # Populated selectively by the service layer depending on who's asking
    # — see the module docstring. Both default to None (withheld) and are
    # only ever filled in for the instructor-facing read.
    reviewer_user_id: Optional[int] = None
    target_user_id: Optional[int] = None
