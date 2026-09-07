"""LTI 1.1 tool-provider launch support.

SCOPE DECISION (see PENDING_FEATURES.md for the full writeup): this makes
LearnHouse an LTI **Tool Provider** only — a course can be launched FROM
another LMS (Canvas, Moodle, Blackboard, ...) that embeds or links to it.
The reverse direction (LearnHouse as a Tool *Consumer*, embedding some other
LMS's tool inside a LearnHouse course) is not built. The protocol version is
LTI 1.1 (OAuth 1.0a-signed launch POST), not the newer LTI Advantage 1.3
(OIDC + JWT + a services ecosystem) — 1.1 is what the large majority of
existing campus LMS deployments still speak for basic launches, and it does
not require standing up a JWKS endpoint or an OIDC login-initiation dance.

One ``LTILink`` row = one (course, credential) pair: each link gets its own
``consumer_key``/``consumer_secret``, scoped to exactly one course, so
launching it always means "open this course" with no separate
course-selection step, and revoking one link cannot affect any other course.
"""

from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class LTILink(SQLModel, table=True):
    """A launchable LTI 1.1 tool-provider credential bound to one course."""

    __tablename__ = "lti_link"
    __table_args__ = (
        Index("ix_lti_link_link_uuid", "link_uuid"),
        Index("ix_lti_link_course_id", "course_id"),
        Index("ix_lti_link_consumer_key", "consumer_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    link_uuid: str = Field(default="", max_length=100)
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    course_id: int = Field(
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    )
    # Globally unique — this is what a launch is looked up by, independent of
    # link_uuid (the launch URL path segment; see services/lti/lti.py).
    consumer_key: str = Field(sa_column=Column(String(100), nullable=False, unique=True))
    consumer_secret_encrypted: str = Field(default="", sa_column=Column(Text, nullable=False))
    label: Optional[str] = Field(default=None, max_length=200)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    created_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""


class LTIUserMapping(SQLModel, table=True):
    """Links an external LMS's per-user LTI identity to a LearnHouse account.

    Keyed by (consumer_key, lti_user_id) — the LTI ``user_id`` launch
    parameter is only guaranteed stable for a given tool-consumer deployment
    (here, a given LTILink's consumer_key), not globally, so a user launching
    the same LearnHouse course through two different external LMS
    connections gets two independent mappings even if they resolve to the
    same LearnHouse account underneath. That is intentional: nothing here
    assumes two different consumers agree on what "the same learner" means.
    """

    __tablename__ = "lti_user_mapping"
    __table_args__ = (
        UniqueConstraint("consumer_key", "lti_user_id", name="uq_lti_user_mapping_key_user"),
        Index("ix_lti_user_mapping_consumer_key", "consumer_key"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    consumer_key: str = Field(sa_column=Column(String(100), nullable=False))
    lti_user_id: str = Field(sa_column=Column(String(255), nullable=False))
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LTILinkCreate(BaseModel):
    label: Optional[str] = None


class LTILinkRead(BaseModel):
    link_uuid: str
    course_id: int
    consumer_key: str
    label: Optional[str] = None
    is_active: bool
    launch_url: str
    created_by_user_id: int
    creation_date: str


class LTILinkCreatedResponse(BaseModel):
    """Returned only on create/regenerate — the only time the secret is shown."""

    link_uuid: str
    consumer_key: str
    consumer_secret: str  # plaintext, shown once
    label: Optional[str] = None
    launch_url: str
    creation_date: str
