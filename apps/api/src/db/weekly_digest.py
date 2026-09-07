"""Weekly student digest send ledger.

Mirrors db/nudges.py's NudgeSend in spirit — a dedupe_key written *before* the
send is attempted, so a crash mid-send cannot double-send and two processes
racing the same weekly tick collide on the unique constraint rather than in a
student's inbox — but far smaller: one email type, one weekly cadence, no
catalog/spec system, no per-track pacing. See services/digest/weekly_digest.py
for the send loop and the scope decision behind what counts as "at risk" vs
"digest-worthy".
"""

from typing import Optional
from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class WeeklyDigestSendStatus:
    CLAIMED = "claimed"
    SENT = "sent"
    FAILED = "failed"
    DRY_RUN = "dry_run"


class WeeklyDigestSend(SQLModel, table=True):
    __tablename__ = "weekly_digest_send"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_weekly_digest_send_dedupe"),
        Index("ix_weekly_digest_send_user_org", "user_id", "org_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # "<user_id>:<org_id>:<iso_year>-W<iso_week>", or "dryrun:" prefixed.
    dedupe_key: str = Field(sa_column=Column(String(100), nullable=False))
    org_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    status: str = Field(default=WeeklyDigestSendStatus.CLAIMED, sa_column=Column(String(20), nullable=False))
    claimed_at: Optional[str] = None
    sent_at: Optional[str] = None
    error: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    provider_id: Optional[str] = None
