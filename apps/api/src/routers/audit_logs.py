import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast
from sqlmodel import and_, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.audit_logs import AuditLog, AuditLogPaginated, AuditLogRead
from src.db.user_organizations import UserOrganization
from src.db.users import AnonymousUser, APITokenUser, PublicUser, User
from src.routers.analytics import _verify_org_admin, _verify_org_membership
from src.security.auth import get_current_user, resolve_acting_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


async def _require_org_admin(
    current_user: PublicUser | AnonymousUser | APITokenUser,
    org_id: int,
    db_session: AsyncSession,
) -> int:
    if isinstance(current_user, AnonymousUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if isinstance(current_user, APITokenUser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API token not allowed for audit log operations",
        )
    acting_id = resolve_acting_user_id(current_user)
    await _verify_org_membership(acting_id, org_id, db_session)
    await _verify_org_admin(acting_id, org_id, db_session)
    return acting_id


def _apply_filters(
    statement,
    count_statement,
    *,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    name: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    status_code: Optional[int] = None,
    ip_address: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    if user_id:
        filt = cast(AuditLog.user_id, String).ilike(f"%{user_id}%")
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if username:
        filt = User.username.ilike(f"%{username}%")
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if name:
        filt = or_(
            User.first_name.ilike(f"%{name}%"),
            User.last_name.ilike(f"%{name}%"),
            (User.first_name + " " + User.last_name).ilike(f"%{name}%"),
        )
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if action:
        filt = AuditLog.action.ilike(f"%{action}%")
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if resource and resource != "all":
        filt = AuditLog.resource.ilike(f"%{resource}%")
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if status_code is not None:
        filt = AuditLog.status_code == status_code
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if ip_address:
        filt = AuditLog.ip_address.ilike(f"%{ip_address}%")
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if start_date:
        filt = AuditLog.created_at >= start_date
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)
    if end_date:
        filt = AuditLog.created_at <= end_date
        statement = statement.where(filt)
        count_statement = count_statement.where(filt)

    return statement, count_statement


@router.get(
    "/export",
    summary="Export audit logs as CSV",
    description="Export audit logs for an organization as a CSV file.",
)
async def export_audit_logs(
    *,
    request: Request,
    org_id: int,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    name: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    status_code: Optional[int] = None,
    ip_address: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: PublicUser | AnonymousUser | APITokenUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await _require_org_admin(current_user, org_id, db_session)

    # Org member IDs for connection/global events
    member_stmt = select(UserOrganization.user_id).where(UserOrganization.org_id == org_id)
    member_ids = list((await db_session.execute(member_stmt)).scalars().all())

    org_filter = or_(
        AuditLog.org_id == org_id,
        and_(AuditLog.org_id.is_(None), AuditLog.user_id.in_(member_ids)) if member_ids else False,
    )

    statement = (
        select(AuditLog, User.username)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(org_filter)
    )
    count_stmt = select(func.count(AuditLog.id)).outerjoin(User, AuditLog.user_id == User.id).where(org_filter)

    statement, _ = _apply_filters(
        statement,
        count_stmt,
        user_id=user_id,
        username=username,
        name=name,
        action=action,
        resource=resource,
        status_code=status_code,
        ip_address=ip_address,
        start_date=start_date,
        end_date=end_date,
    )

    statement = statement.order_by(desc(AuditLog.created_at)).limit(5000)
    results = (await db_session.execute(statement)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID",
        "Timestamp",
        "User ID",
        "Username",
        "Action",
        "Resource",
        "Resource ID",
        "Method",
        "Path",
        "Status Code",
        "IP Address",
    ])

    for log, uname in results:
        writer.writerow([
            log.id,
            log.created_at.isoformat() if log.created_at else "",
            log.user_id or "System",
            uname or "System",
            log.action,
            log.resource,
            log.resource_id or "",
            log.method,
            log.path,
            log.status_code,
            log.ip_address or "",
        ])

    output.seek(0)
    filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "",
    response_model=AuditLogPaginated,
    summary="List audit logs",
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=AuditLogPaginated,
    summary="List audit logs",
)
async def get_audit_logs(
    *,
    request: Request,
    org_id: int,
    offset: int = 0,
    limit: int = Query(default=20, lte=100),
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    name: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    status_code: Optional[int] = None,
    ip_address: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: PublicUser | AnonymousUser | APITokenUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    await _require_org_admin(current_user, org_id, db_session)

    member_stmt = select(UserOrganization.user_id).where(UserOrganization.org_id == org_id)
    member_ids = list((await db_session.execute(member_stmt)).scalars().all())

    org_filter = or_(
        AuditLog.org_id == org_id,
        and_(AuditLog.org_id.is_(None), AuditLog.user_id.in_(member_ids)) if member_ids else False,
    )

    statement = (
        select(AuditLog, User.username, User.avatar_image)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(org_filter)
    )
    count_stmt = (
        select(func.count(AuditLog.id))
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(org_filter)
    )

    statement, count_stmt = _apply_filters(
        statement,
        count_stmt,
        user_id=user_id,
        username=username,
        name=name,
        action=action,
        resource=resource,
        status_code=status_code,
        ip_address=ip_address,
        start_date=start_date,
        end_date=end_date,
    )

    total = (await db_session.execute(count_stmt)).scalar() or 0
    statement = statement.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    results = (await db_session.execute(statement)).all()

    audit_logs_read = []
    for log, uname, avatar in results:
        log_dict = log.model_dump()
        log_dict["username"] = uname
        log_dict["avatar_url"] = avatar
        audit_logs_read.append(AuditLogRead(**log_dict))

    return {
        "items": audit_logs_read,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
