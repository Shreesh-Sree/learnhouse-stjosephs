from typing import Optional, Any, List
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Column, Integer, ForeignKey, JSON, String, DateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLogBase(SQLModel):
    user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    org_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="SET NULL"), nullable=True),
    )
    action: str = Field(sa_column=Column(String, nullable=False))
    resource: str = Field(sa_column=Column(String, nullable=False))
    resource_id: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    method: str = Field(sa_column=Column(String(16), nullable=False))
    path: str = Field(sa_column=Column(String, nullable=False))
    status_code: int = Field(sa_column=Column(Integer, nullable=False))
    payload: Optional[Any] = Field(default=None, sa_column=Column(JSON, nullable=True))
    ip_address: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AuditLog(AuditLogBase, table=True):
    __tablename__ = "auditlog"
    id: Optional[int] = Field(default=None, primary_key=True)


class AuditLogRead(AuditLogBase):
    id: int
    username: Optional[str] = None
    avatar_url: Optional[str] = None


class AuditLogPaginated(SQLModel):
    items: List[AuditLogRead]
    total: int
    limit: int
    offset: int
