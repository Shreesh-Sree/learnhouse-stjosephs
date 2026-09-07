"""Student-flaggable quiz questions.

A quiz question is not its own database row (it lives inside a `blockQuiz`
node in an Activity's Prosemirror `content` document — see
services/ai/quiz.py's module docstring), so a flag cannot be a foreign key
to a question row. Instead it references the (activity, quiz, question) by
id and keeps a text SNAPSHOT of the question at flag time — content can be
edited (or the question deleted) after a flag is raised, and the review
queue must still show the instructor what a student actually saw, not
whatever the block currently contains.

Scope: only the ungraded, in-content `blockQuiz` self-check block. The
separate graded ASSIGNMENT quiz task type has a different question shape
entirely (see services/ai/quiz.py) and is not covered here.
"""

from typing import Optional
from enum import Enum
from sqlalchemy import Column, ForeignKey, Integer, String, Text, Index
from sqlmodel import Field, SQLModel


class QuizFlagReason(str, Enum):
    INCORRECT_ANSWER = "incorrect_answer"
    UNCLEAR_WORDING = "unclear_wording"
    TYPO = "typo"
    OTHER = "other"


class QuizFlagStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class QuizQuestionFlag(SQLModel, table=True):
    __tablename__ = "quiz_question_flag"
    __table_args__ = (
        Index("ix_quiz_question_flag_flag_uuid", "flag_uuid"),
        Index("ix_quiz_question_flag_course_status", "course_id", "status"),
        Index("ix_quiz_question_flag_activity_question", "activity_id", "question_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    flag_uuid: str = Field(default="", max_length=100)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    )
    activity_id: int = Field(
        sa_column=Column(Integer, ForeignKey("activity.id", ondelete="CASCADE"), nullable=False)
    )
    quiz_id: str = Field(sa_column=Column(String(100), nullable=False))
    question_id: str = Field(sa_column=Column(String(100), nullable=False))
    question_text_snapshot: str = Field(default="", sa_column=Column(Text, nullable=False))
    reason: QuizFlagReason = Field(sa_column=Column(String(30), nullable=False))
    note: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    status: QuizFlagStatus = Field(
        default=QuizFlagStatus.OPEN, sa_column=Column(String(20), nullable=False, server_default="open")
    )
    # SET NULL rather than CASCADE: a flag stays useful to instructors as a
    # content-quality signal even if the student who raised it, or the
    # instructor who resolved it, later leaves the org / is deleted.
    flagged_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    )
    resolved_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    )
    resolved_at: Optional[str] = None
    creation_date: str = ""
    update_date: str = ""


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
from pydantic import BaseModel


class QuizFlagCreate(BaseModel):
    quiz_id: str
    question_id: str
    reason: QuizFlagReason
    note: Optional[str] = None


class QuizFlagAuthor(BaseModel):
    id: int
    user_uuid: str
    username: str
    first_name: str
    last_name: str


class QuizFlagRead(BaseModel):
    flag_uuid: str
    activity_uuid: str
    activity_name: str
    quiz_id: str
    question_id: str
    question_text_snapshot: str
    reason: QuizFlagReason
    note: Optional[str] = None
    status: QuizFlagStatus
    flagged_by: Optional[QuizFlagAuthor] = None
    resolved_by: Optional[QuizFlagAuthor] = None
    resolved_at: Optional[str] = None
    creation_date: str


class QuizFlagResolve(BaseModel):
    status: QuizFlagStatus
