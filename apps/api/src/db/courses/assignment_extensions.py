"""Per-student assignment deadline extensions.

One row per (assignment, student): the extension REPLACES the assignment's
own `due_date` for that student outright, rather than only ever pushing it
later — a teacher can just as legitimately need to enter an earlier
individual deadline (e.g. an accommodation that front-loads a due date, or
correcting a mistaken extension) as a later one, and a single "effective
due date" override covers both without a second field. Every deadline gate
in services.courses.activities.assignments (file upload, task-answer save,
submit-for-grading, start-attempt, retry) resolves the effective deadline
per-student through this table before checking it — see
`get_effective_due_date`.
"""

from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


class AssignmentExtensionBase(SQLModel):
    extended_due_date: str
    reason: Optional[str] = None


class AssignmentExtension(AssignmentExtensionBase, table=True):
    __tablename__ = "assignment_extension"
    __table_args__ = (
        # One extension per student per assignment — granting a new one
        # updates this row rather than stacking a second, ambiguous one.
        UniqueConstraint("assignment_id", "user_id", name="uq_assignment_extension_assignment_user"),
        Index("ix_assignment_extension_assignment_id", "assignment_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    extension_uuid: str = Field(default="", index=True)
    assignment_id: int = Field(
        sa_column=Column(Integer, ForeignKey("assignment.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    granted_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""


class AssignmentExtensionRead(AssignmentExtensionBase):
    extension_uuid: str
    user_id: int
    granted_by_user_id: int
    creation_date: str
    update_date: str


class AssignmentExtensionUpsert(SQLModel):
    """Body for granting/updating an extension. `extended_due_date` uses the
    same free-form ISO-ish string convention as Assignment.due_date (date-only
    or with a time component) so it goes through the identical parsing rule.
    """

    extended_due_date: str
    reason: Optional[str] = None
