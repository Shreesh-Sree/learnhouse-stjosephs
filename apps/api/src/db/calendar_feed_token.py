from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class CalendarFeedToken(SQLModel, table=True):
    """A random, opaque, per-user secret that stands in for authentication
    on the ICS feed endpoint — calendar apps (Google/Outlook/Apple
    Calendar) poll a subscribed URL unauthenticated on their own schedule,
    so the usual Bearer-token session auth this app uses everywhere else
    isn't reachable from a calendar client. The token itself IS the
    credential (same trust model Canvas/Moodle use for their own ICS
    feeds): whoever has the URL can read that one user's assignment due
    dates and nothing else — no write access, no other user's data.

    One row per user (regenerating replaces it, invalidating the old URL —
    the standard response if a link leaks).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(default="", index=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    )
    creation_date: str = ""
