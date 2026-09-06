from enum import Enum
from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class ScormVersionEnum(str, Enum):
    SCORM_12 = "SCORM_12"
    SCORM_2004 = "SCORM_2004"


class ScormLessonStatus(str, Enum):
    """cmi.core.lesson_status values, verbatim from the SCORM 1.2 spec.

    "passed"/"failed" only appear when the package has a mastery score;
    otherwise content reports "completed"/"incomplete" directly.
    """

    NOT_ATTEMPTED = "not_attempted"
    INCOMPLETE = "incomplete"
    COMPLETED = "completed"
    PASSED = "passed"
    FAILED = "failed"
    BROWSED = "browsed"


# lesson_status values that count as "the learner finished this" for trail
# completion purposes. "failed" deliberately does NOT count — a mastery-score
# package that marks a learner as failed hasn't completed it.
SCORM_COMPLETING_STATUSES = frozenset(
    {ScormLessonStatus.COMPLETED.value, ScormLessonStatus.PASSED.value}
)


class ScormTrackingDataBase(SQLModel):
    """The subset of the SCORM 1.2 cmi.core data model this player persists.

    Deliberately not the full CMI tree (interactions, objectives) — just
    enough for resume-where-you-left-off and completion/score reporting,
    which is what the trail and analytics actually consume.
    """

    lesson_status: ScormLessonStatus = ScormLessonStatus.NOT_ATTEMPTED
    score_raw: Optional[float] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    # cmi.core.lesson_location: content-defined bookmark string (e.g. a slide
    # index or internal page id), opaque to the player — just stored and
    # handed back verbatim so the SCO can resume where the learner left off.
    lesson_location: Optional[str] = None
    # cmi.suspend_data: content-defined free-form state blob, up to 4096
    # chars in the SCORM 1.2 spec (some real-world content exceeds it) —
    # Text, not a bounded varchar, so a slightly-oversized value from a
    # non-strict authoring tool doesn't get silently truncated.
    suspend_data: Optional[str] = None
    # cmi.core.session_time accumulates into total_time on each commit; kept
    # separate so a single long-lived tracking row never has to average two
    # different "how long was this session" figures into one field.
    session_time_seconds: int = 0
    total_time_seconds: int = 0


class ScormTrackingData(ScormTrackingDataBase, table=True):
    """One row per (activity, user): the learner's current SCORM CMI state."""

    __tablename__ = "scorm_tracking_data"
    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_scorm_tracking_activity_user"),
        Index("ix_scorm_tracking_activity_id", "activity_id"),
        Index("ix_scorm_tracking_user_id", "user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    )
    activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("activity.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )

    suspend_data: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # Same "plain string timestamp" convention as Activity/Assignment in this
    # codebase (str(datetime.now())), not a real timestamptz — this is
    # learner progress state, not the legal-grade audit log.
    creation_date: str = ""
    update_date: str = ""


class ScormTrackingDataRead(ScormTrackingDataBase):
    activity_uuid: Optional[str] = None
    update_date: Optional[str] = None


class ScormResultRow(SQLModel):
    """One learner's row in the instructor-facing results table."""

    user_id: int
    user_uuid: str
    username: str
    first_name: str
    last_name: str
    lesson_status: ScormLessonStatus
    score_raw: Optional[float] = None
    score_max: Optional[float] = None
    total_time_seconds: int = 0
    update_date: Optional[str] = None


class ScormTrackingDataUpdate(SQLModel):
    """Fields the SCORM API shim's LMSSetValue/LMSCommit can write.

    Every field optional: a single LMSCommit call only carries whichever CMI
    elements the content actually set during that session, so the update
    only touches those.
    """

    lesson_status: Optional[ScormLessonStatus] = None
    score_raw: Optional[float] = None
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    lesson_location: Optional[str] = None
    suspend_data: Optional[str] = None
    session_time_seconds: Optional[int] = None
