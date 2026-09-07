"""Group/team assignment membership.

DESIGN: groups are formed on top of the existing per-user submission model,
not a replacement for it. `AssignmentUserSubmission` and
`AssignmentTaskSubmission` stay keyed to a single `user_id`, exactly as
every other part of the grading/certificate/activity-trail pipeline already
assumes. A group only changes how those per-user rows get FILLED IN and
GRADED — see `services.courses.activities.assignment_groups` for the
membership CRUD and `services.courses.activities.assignments`'s
`_fanout_group_task_answer`, `submit_group_assignment` and
`grade_group_assignment` for the write-time fan-out that keeps every
member's own rows in sync. Restructuring the submission tables themselves
to be group-keyed would touch grading, certificates, the activity trail and
analytics everywhere they read AssignmentUserSubmission by user_id — a much
larger and riskier change than this deployment's actual need (a teacher
wants a team to hand in once and be graded together).
"""

from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


class AssignmentGroupBase(SQLModel):
    name: str


class AssignmentGroup(AssignmentGroupBase, table=True):
    __tablename__ = "assignment_group"
    __table_args__ = (
        Index("ix_assignment_group_assignment_id", "assignment_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    group_uuid: str = Field(default="", index=True)
    assignment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment.id", ondelete="CASCADE"), nullable=False)
    )
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""


class AssignmentGroupMember(SQLModel, table=True):
    __tablename__ = "assignment_group_member"
    __table_args__ = (
        # A student belongs to at most one group per assignment. assignment_id
        # is denormalized from the parent group purely so this single-table
        # unique constraint can express that — a cross-table check (unique on
        # (group.assignment_id, member.user_id)) isn't something a plain
        # UniqueConstraint can enforce, and both target DBs here (Postgres in
        # production, SQLite in tests) support this simpler form identically.
        UniqueConstraint("assignment_id", "user_id", name="uq_assignment_group_member_assignment_user"),
        Index("ix_assignment_group_member_group_id", "group_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment_group.id", ondelete="CASCADE"), nullable=False)
    )
    assignment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""


class AssignmentGroupMemberRead(SQLModel):
    user_id: int
    creation_date: str


class AssignmentGroupRead(AssignmentGroupBase):
    group_uuid: str
    creation_date: str
    member_count: int = 0
    is_full: bool = False
    # Populated for the caller's own group, or for an instructor viewing any
    # group. Withheld (None) for a student looking at a DIFFERENT group they
    # could join — see the service module docstring for why member identity
    # of a group you're not in is not something to hand a classmate.
    members: Optional[list[AssignmentGroupMemberRead]] = None
