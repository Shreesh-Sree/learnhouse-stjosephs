"""Runs the audit-retention purge on a daily tick from inside the API — same
in-process asyncio pattern as services/digest/scheduler.py (Redis day-lock
as an optimisation only; re-running the purge twice in a day is idempotent,
just wasted work, since a row already deleted can't be deleted again). NOT
SaaS-gated — see services/audit/retention.py's module docstring — the only
gate is the ``LEARNHOUSE_AUDIT_RETENTION_ENABLED`` kill switch (default off).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

RUN_AT_HOUR_UTC = 3  # low-traffic hour; a bulk delete is cheap but no reason not to be polite
_LOCK_TTL_SECONDS = 6 * 60 * 60
STARTUP_DELAY_SECONDS = 45

_task: Optional[asyncio.Task] = None


def _lock_key(now: datetime) -> str:
    return f"learnhouse:audit_retention:{now.date().isoformat()}"


async def _claim_day(now: datetime) -> bool:
    try:
        from src.core.redis import get_redis_client

        client = get_redis_client()
        if client is None:
            return True
        acquired = await asyncio.to_thread(
            client.set, _lock_key(now), "1", nx=True, ex=_LOCK_TTL_SECONDS
        )
        return bool(acquired)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Audit retention lock unavailable, running anyway: %s", exc)
        return True


def _seconds_until_next_run(now: datetime) -> float:
    target = now.replace(hour=RUN_AT_HOUR_UTC, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _run_once() -> None:
    from src.core.events.database import _async_session_factory
    from src.services.audit.retention import purge_expired_audit_events

    async with _async_session_factory() as db_session:
        stats = await purge_expired_audit_events(db_session)
    logger.info("Audit retention purge complete: %s", stats.as_dict())


async def _tick() -> None:
    try:
        today = datetime.now(timezone.utc)
        if await _claim_day(today):
            await _run_once()
        else:
            logger.info("Today's audit retention purge was already handled elsewhere")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Audit retention purge failed, will retry tomorrow: %s", exc)


async def _loop() -> None:
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        await asyncio.sleep(_seconds_until_next_run(datetime.now(timezone.utc)))
        await _tick()


def start_scheduler() -> None:
    """Start the daily tick, unless the feature is switched off. Never
    raises: a background purge job must not be able to stop the API from
    booting."""
    global _task

    try:
        from src.services.audit.retention import retention_scheduler_enabled

        if not retention_scheduler_enabled():
            logger.info(
                "Audit retention scheduler idle: LEARNHOUSE_AUDIT_RETENTION_ENABLED is not set"
            )
            return
        if os.environ.get("LEARNHOUSE_AUDIT_RETENTION_NO_SCHEDULER"):
            logger.info("Audit retention scheduler disabled; drive it via your own cron")
            return

        _task = asyncio.create_task(_loop())
        logger.info("Audit retention scheduler started (daily at %02d:00 UTC)", RUN_AT_HOUR_UTC)
    except Exception as exc:
        logger.warning("Audit retention scheduler not started: %s", exc)


async def stop_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except (asyncio.CancelledError, Exception):
        pass
    finally:
        _task = None
