from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from src.db.courses.activities import ActivityRead


class LockType(str, Enum):
    PUBLIC = "public"                # anyone, including anonymous, can view
    AUTHENTICATED = "authenticated"  # must be signed in
    RESTRICTED = "restricted"        # only members of assigned usergroups (via UserGroupResource)


class ChapterBase(SQLModel):
    name: str
    description: Optional[str] = ""
    thumbnail_image: Optional[str] = ""
    lock_type: LockType = LockType.PUBLIC
    org_id: int = Field(
        sa_column=Column("org_id", Integer, ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    )
    course_id: int = Field(
        sa_column=Column("course_id", Integer, ForeignKey("course.id", ondelete="CASCADE"), index=True)
    )
    # Learning-path prerequisite: another chapter IN THE SAME COURSE that must
    # be fully completed before a learner may access this one — see
    # services.courses.locks' prerequisite check. None = no prerequisite.
    # Plain int here (no FK) — only the `Chapter` table class below needs the
    # real ForeignKey.
    prerequisite_chapter_id: Optional[int] = None


class Chapter(ChapterBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chapter_uuid: str = Field(default="", index=True)
    creation_date: str = ""
    update_date: str = ""
    extra_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    # ON DELETE SET NULL rather than CASCADE: deleting the prerequisite
    # chapter should un-gate this one, never delete it as a side effect.
    prerequisite_chapter_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("chapter.id", ondelete="SET NULL"), nullable=True),
    )


class ChapterCreate(ChapterBase):
    # referenced order here will be ignored and just used for validation
    # used order will be the next available.
    extra_metadata: Optional[dict] = None
    pass


class ChapterUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    thumbnail_image: Optional[str] = None
    lock_type: Optional[LockType] = None
    extra_metadata: Optional[dict] = None


class ChapterPrerequisiteUpdate(SQLModel):
    """An id sets the prerequisite chapter; null (or an omitted field) clears
    it. See services.courses.chapters.set_chapter_prerequisite."""
    prerequisite_chapter_id: Optional[int] = None


class ChapterRead(ChapterBase):
    id: int
    activities: List[ActivityRead]
    chapter_uuid: str
    creation_date: str
    update_date: str
    extra_metadata: Optional[dict] = None
    # Computed per-request: whether current user is denied access to this chapter's
    # content (and, by cascade, its activities). Metadata (name, thumbnail) is still
    # returned so TOC navigation still renders a lock placeholder.
    is_locked: bool = False
    # Computed per-request, only meaningful when is_locked is True: which of
    # the two independent gates caused it. "restricted" = usergroup lock
    # (lock_type/UserGroupResource, pre-existing); "prerequisite" = this
    # chapter's own prerequisite_chapter_id isn't fully completed yet by this
    # user (new). A chapter can be locked by either, but never shows both —
    # the restricted check runs first since it is the stricter of the two.
    lock_reason: Optional[str] = None
    pass


class ActivityOrder(BaseModel):
    activity_id: int


class ChapterOrder(BaseModel):
    chapter_id: int
    activities_order_by_ids: List[ActivityOrder]


class ChapterUpdateOrder(BaseModel):
    chapter_order_by_ids: List[ChapterOrder]


class DepreceatedChaptersRead(BaseModel):
    chapterOrder: Any
    chapters: Any
    activities: Any
    pass
