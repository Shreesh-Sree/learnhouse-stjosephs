"""Scheduled live video sessions for a course.

SCOPE DECISION (see PENDING_FEATURES.md for the full writeup): this is an
EMBEDDED-MEETING-LINK model — an instructor pastes a Zoom/Meet/Teams/
whatever URL and a scheduled time, and students get a "Join" link plus a
calendar entry. There is no native WebRTC session, no signaling server, no
TURN/STUN infrastructure — that would be a categorically larger
undertaking (a real-time media server, NAT traversal, room/participant
management) than a hand-rolled feature in one pass can responsibly deliver.
The actual video call happens entirely on the third-party platform the
meeting_url points at; LearnHouse only schedules it and hands out the link.
"""

from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String, Text, Index
from sqlmodel import Field, SQLModel


class LiveSession(SQLModel, table=True):
    __tablename__ = "live_session"
    __table_args__ = (
        Index("ix_live_session_session_uuid", "session_uuid"),
        Index("ix_live_session_course_start", "course_id", "start_time"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    session_uuid: str = Field(default="", max_length=100)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    )
    title: str = Field(sa_column=Column(String(200), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    meeting_url: str = Field(sa_column=Column(String(2048), nullable=False))
    # Naive local-time ISO strings, same convention as Assignment.due_date —
    # see calendar_feed.py's own docstring for why (no per-org timezone
    # setting exists anywhere in this codebase to record an offset against).
    start_time: str = Field(sa_column=Column(String(40), nullable=False))
    end_time: Optional[str] = Field(default=None, sa_column=Column(String(40), nullable=True))
    created_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LiveSessionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_url: str
    start_time: str
    end_time: Optional[str] = None


class LiveSessionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_url: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class LiveSessionRead(BaseModel):
    session_uuid: str
    course_id: int
    title: str
    description: Optional[str] = None
    meeting_url: str
    start_time: str
    end_time: Optional[str] = None
    created_by_user_id: int
    creation_date: str
    update_date: str
