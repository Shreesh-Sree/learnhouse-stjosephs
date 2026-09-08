"""Per-org retention policy for the student audit log (``user_audit_event``).

Genuinely new — unlike the dossier/export/advanced-analytics gate fix (see
routers/audit.py, routers/analytics.py), no retention/purge mechanism existed
anywhere in this codebase before this. The table's own docstring calls it
"append-only... never updated or deleted", which is correct for legal-record
purposes but means every row lives forever by default — fine for a small
college, a real long-term privacy/storage concern once volume grows.

SCOPE: retention is per-org and applies ONLY to org-scoped rows
(``org_id`` set — course/assignment/certificate events). Login/logout events
carry no ``org_id`` (a user authenticates once, not per-org — see
db/user_audit_events.py), so which org's policy would apply to them is
ambiguous; they are deliberately left out of automatic purge in this pass
rather than guessed at. A null/absent ``retention_days`` means keep forever
(the existing, safe-by-default behavior) — nothing purges until an admin
opts in.

Not SaaS-gated, matching the weekly digest precedent: retention is a data-
minimization concern every deployment eventually needs, not a paid tier.
Kill-switched by ``LEARNHOUSE_AUDIT_RETENTION_ENABLED`` (default off) for the
background scheduler only — the manual CLI/API purge always works so an
admin can run it on demand regardless of the switch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.organization_config import OrganizationConfig
from src.db.organizations import Organization
from src.db.user_audit_events import UserAuditEvent

# A retention window shorter than this is almost certainly a mistake (typing
# days when you meant months), and would silently start deleting audit rows
# an admin is very unlikely to have actually wanted gone within a week.
MIN_RETENTION_DAYS = 30


def retention_scheduler_enabled() -> bool:
    raw = os.environ.get("LEARNHOUSE_AUDIT_RETENTION_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def get_retention_days(config: Optional[OrganizationConfig]) -> Optional[int]:
    if config is None or not config.config:
        return None
    audit_cfg = config.config.get("audit") or {}
    value = audit_cfg.get("retention_days")
    return int(value) if isinstance(value, (int, float)) and value > 0 else None


async def set_retention_days(
    org_id: int, retention_days: Optional[int], db_session: AsyncSession
) -> OrganizationConfig:
    if retention_days is not None and retention_days < MIN_RETENTION_DAYS:
        raise ValueError(f"retention_days must be at least {MIN_RETENTION_DAYS} (or null to keep forever)")

    config = (await db_session.execute(
        select(OrganizationConfig).where(OrganizationConfig.org_id == org_id)
    )).scalars().first()
    if config is None:
        raise ValueError(f"No OrganizationConfig for org {org_id}")

    new_config = dict(config.config or {})
    audit_cfg = dict(new_config.get("audit") or {})
    if retention_days is None:
        audit_cfg.pop("retention_days", None)
    else:
        audit_cfg["retention_days"] = retention_days
    new_config["audit"] = audit_cfg
    config.config = new_config

    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@dataclass
class PurgeStats:
    orgs_with_policy: int = 0
    rows_deleted: int = 0
    per_org: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "orgs_with_policy": self.orgs_with_policy,
            "rows_deleted": self.rows_deleted,
            "per_org": self.per_org,
        }


async def purge_expired_audit_events(
    db_session: AsyncSession, *, org_id: Optional[int] = None, dry_run: bool = False
) -> PurgeStats:
    """Delete org-scoped ``UserAuditEvent`` rows older than that org's
    configured retention window. Pass ``org_id`` to purge a single org
    (used by the on-demand admin endpoint); omit it to sweep every org with
    a policy set (used by the scheduler and the CLI).

    ``dry_run=True`` counts what WOULD be deleted without deleting anything —
    an admin should always be able to preview a purge before running it for
    real, same as every other "irreversible bulk action" in this project.
    """
    stats = PurgeStats()
    now = datetime.now(timezone.utc)

    org_statement = select(Organization) if org_id is None else select(Organization).where(Organization.id == org_id)
    orgs = (await db_session.execute(org_statement)).scalars().all()

    for org in orgs:
        config = (await db_session.execute(
            select(OrganizationConfig).where(OrganizationConfig.org_id == org.id)
        )).scalars().first()
        retention_days = get_retention_days(config)
        if retention_days is None:
            continue

        cutoff = now - timedelta(days=retention_days)
        stats.orgs_with_policy += 1

        count_stmt = select(UserAuditEvent).where(
            UserAuditEvent.org_id == org.id, UserAuditEvent.created_at < cutoff
        )
        rows = (await db_session.execute(count_stmt)).scalars().all()
        row_count = len(rows)
        if row_count == 0:
            continue

        stats.rows_deleted += row_count
        stats.per_org[org.slug] = row_count

        if not dry_run:
            await db_session.execute(
                delete(UserAuditEvent).where(
                    UserAuditEvent.org_id == org.id, UserAuditEvent.created_at < cutoff
                )
            )
            await db_session.commit()

    return stats
