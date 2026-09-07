from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlmodel import Field, SQLModel


class ProctoringSnapshotBase(SQLModel):
    # Stored filename, same convention as every other upload_content-backed
    # field in this codebase (Assignment.solution_file, etc.) — the caller
    # builds the servable path from org/course/activity uuids + this name,
    # never a raw filesystem path.
    filename: str
    captured_at: str = ""


class ProctoringSnapshot(ProctoringSnapshotBase, table=True):
    """One webcam capture from a proctored assignment attempt.

    Opportunistic, not enforced: a student who declines the consent prompt
    (see AssignmentProctoringConsent.tsx) simply never generates any rows
    here — there is no server-side check anywhere that blocks a submission
    for having none, by design (a proctoring requirement must never become a
    reason a student literally cannot take the exam).
    """

    __tablename__ = "proctoring_snapshot"
    __table_args__ = (
        Index("ix_proctoring_snapshot_assignment_user", "assignment_id", "user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_uuid: str = Field(default="", index=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    )
    activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("activity.id", ondelete="CASCADE"), nullable=False)
    )
    assignment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""


class ProctoringSnapshotRead(ProctoringSnapshotBase):
    snapshot_uuid: str
    creation_date: str
