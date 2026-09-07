from typing import List, Optional
from sqlalchemy import Column, Enum as SAEnum, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel
from enum import Enum
from pydantic import BaseModel
from src.db.users import UserRead
from src.db.trails import TrailRead
from src.db.courses.chapters import ChapterRead
from src.db.resource_authors import ResourceAuthorshipEnum, ResourceAuthorshipStatusEnum


class CourseSEO(BaseModel):
    """SEO configuration for a course stored as JSON"""
    # Basic SEO
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    canonical_url: Optional[str] = None
    # Open Graph
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    # Twitter Card
    twitter_card: Optional[str] = None  # 'summary' | 'summary_large_image'
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    # Robots & Structured Data
    robots_noindex: bool = False
    robots_nofollow: bool = False
    enable_jsonld: bool = True


class ThumbnailType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    BOTH = "both"


class AuthorWithRole(SQLModel):
    user: UserRead
    authorship: ResourceAuthorshipEnum
    authorship_status: ResourceAuthorshipStatusEnum
    creation_date: str
    update_date: str


class CourseBase(SQLModel):
    name: str
    description: Optional[str] = None
    about: Optional[str] = None
    learnings: Optional[str] = None
    tags: Optional[str] = None
    thumbnail_type: Optional[ThumbnailType] = Field(default=ThumbnailType.IMAGE)
    thumbnail_image: Optional[str] = Field(default="")
    thumbnail_video: Optional[str] = Field(default="")
    public: bool
    published: bool = Field(default=False)
    open_to_contributors: bool
    # Learning-path prerequisite: another course in the same org that must be
    # fully completed (services.courses.certifications.is_course_fully_completed)
    # before a learner may access this one. None = no prerequisite. Plain int
    # here (no FK) — only the `Course` table class below needs the real
    # ForeignKey; every other subclass just needs the id round-tripped.
    prerequisite_course_id: Optional[int] = None


class Course(CourseBase, table=True):
    __table_args__ = (
        Index("ix_course_org_public_published_created", "org_id", "public", "published", "creation_date"),
        {"extend_existing": True},
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    thumbnail_type: Optional[ThumbnailType] = Field(
        default=ThumbnailType.IMAGE,
        sa_column=Column(SAEnum(ThumbnailType, name="thumbnail_type"), nullable=True),
    )
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    )
    course_uuid: str = Field(default="", index=True)
    creation_date: str = ""
    update_date: str = ""
    seo: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    extra_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    # ON DELETE SET NULL rather than CASCADE: deleting the prerequisite course
    # should un-gate this one, never delete it as a side effect.
    prerequisite_course_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("course.id", ondelete="SET NULL"), nullable=True),
    )


class CourseCreate(CourseBase):
    org_id: int = Field(default=None, foreign_key="organization.id")
    thumbnail_type: Optional[ThumbnailType] = Field(default=ThumbnailType.IMAGE)
    thumbnail_image: Optional[str] = Field(default="")
    thumbnail_video: Optional[str] = Field(default="")
    extra_metadata: Optional[dict] = None
    pass


class CourseUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    about: Optional[str] = None
    learnings: Optional[str] = None
    tags: Optional[str] = None
    thumbnail_type: Optional[ThumbnailType] = None
    thumbnail_image: Optional[str] = None
    thumbnail_video: Optional[str] = None
    public: Optional[bool] = None
    published: Optional[bool] = None
    open_to_contributors: Optional[bool] = None
    seo: Optional[dict] = None
    extra_metadata: Optional[dict] = None
    # NOT here: update_course's generic update loop only ever SETS a non-None
    # field, never clears one to null (true for every field on this model,
    # not something introduced here) — a prerequisite genuinely needs to be
    # clearable, so it gets its own dedicated endpoint/service function
    # instead (services.courses.courses.set_course_prerequisite).


class CoursePrerequisiteUpdate(SQLModel):
    """This endpoint only ever touches one field, so there is no partial-update
    ambiguity to resolve: an id sets the prerequisite, null (or an omitted
    body field) clears it."""
    prerequisite_course_id: Optional[int] = None


class CourseRead(CourseBase):
    id: int
    org_id: int = Field(default=None, foreign_key="organization.id")
    authors: List[AuthorWithRole]
    course_uuid: str
    creation_date: str
    update_date: str
    thumbnail_type: Optional[ThumbnailType] = Field(default=ThumbnailType.IMAGE)
    thumbnail_image: Optional[str] = Field(default="")
    thumbnail_video: Optional[str] = Field(default="")
    seo: Optional[dict] = None
    extra_metadata: Optional[dict] = None


class FullCourseRead(CourseBase):
    id: int
    org_id: int
    org_uuid: Optional[str] = None
    course_uuid: Optional[str] = None
    creation_date: Optional[str] = None
    update_date: Optional[str] = None
    thumbnail_type: Optional[ThumbnailType] = Field(default=ThumbnailType.IMAGE)
    thumbnail_image: Optional[str] = Field(default="")
    thumbnail_video: Optional[str] = Field(default="")
    seo: Optional[dict] = None
    extra_metadata: Optional[dict] = None
    # Chapters, Activities
    chapters: List[ChapterRead]
    authors: List[AuthorWithRole]
    pass


class FullCourseReadWithTrail(CourseBase):
    id: int
    course_uuid: Optional[str] = None
    creation_date: Optional[str] = None
    update_date: Optional[str] = None
    org_id: int = Field(default=None, foreign_key="organization.id")
    seo: Optional[dict] = None
    extra_metadata: Optional[dict] = None
    authors: List[AuthorWithRole]
    # Chapters, Activities
    chapters: List[ChapterRead]
    # Trail
    trail: TrailRead | None = None
    pass
