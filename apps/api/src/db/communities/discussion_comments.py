from typing import Optional
from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text, Index
from sqlmodel import Field, SQLModel
from src.db.users import UserReadAuthor


class DiscussionCommentBase(SQLModel):
    content: str = Field(sa_column=Column(Text))
    # Same anonymity model as Discussion.is_anonymous — see that field's
    # docstring. Write-once at creation, not editable afterward.
    is_anonymous: bool = Field(default=False, sa_column=Column(Boolean, default=False))


class DiscussionComment(DiscussionCommentBase, table=True):
    __tablename__ = "discussioncomment"
    __table_args__ = (
        Index("ix_discussioncomment_discussion_id", "discussion_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    discussion_id: int = Field(
        sa_column=Column(Integer, ForeignKey("discussion.id", ondelete="CASCADE"))
    )
    author_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))
    )
    comment_uuid: str = Field(default="", index=True)
    upvote_count: int = 0
    creation_date: str = ""
    update_date: str = ""


class DiscussionCommentCreate(DiscussionCommentBase):
    discussion_id: int = Field(default=None, foreign_key="discussion.id")
    author_id: int = Field(default=None, foreign_key="user.id")


class DiscussionCommentUpdate(SQLModel):
    content: Optional[str] = None


class DiscussionCommentRead(DiscussionCommentBase):
    id: int
    discussion_id: int = Field(default=None, foreign_key="discussion.id")
    # None for a reader who isn't shown the real author — see
    # services.communities.comments._resolve_author_for_reader.
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")
    comment_uuid: str
    upvote_count: int = 0
    creation_date: str
    update_date: str


class DiscussionCommentReadWithAuthor(DiscussionCommentRead):
    author: Optional[UserReadAuthor] = None


class DiscussionCommentReadWithVoteStatus(DiscussionCommentReadWithAuthor):
    has_voted: bool = False
