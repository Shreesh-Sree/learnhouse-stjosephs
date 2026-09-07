"""Runs the weekly digest job on a weekly tick from inside the API, so no
external cron is required — same in-process asyncio pattern as
services/nudges/scheduler.py (Redis day-lock as an optimisation only,
ledger uniqueness as the actual correctness guarantee), but on a weekly
rather than daily cadence, and NOT gated to SaaS deployment mode: a
self-hosted college is exactly this feature's intended audience, so the
only gate is the ``LEARNHOUSE_WEEKLY_DIGEST_ENABLED`` kill switch checked
inside :func:`run_weekly_digest` itself.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Monday, mid-morning UTC. Sending a "here's your week" email on Monday
# reads naturally; the exact hour matters far less than the day.
RUN_ON_WEEKDAY = 0  # Monday (datetime.weekday(): Monday=0)
RUN_AT_HOUR_UTC = 8

_LOCK_TTL_SECONDS = 6 * 60 * 60
STARTUP_DELAY_SECONDS = 30

_task: Optional[asyncio.Task] = None


def _lock_key(now: datetime) -> str:
    iso_year, iso_week, _ = now.isocalendar()
    return f"learnhouse:weekly_digest:{iso_year}-W{iso_week:02d}"


async def _claim_week(now: datetime) -> bool:
    """Try to become the pod that runs this week's job.

    Returns True when Redis is unavailable: the ledger already guarantees a
    digest is sent once per (user, org, week), so running without the lock
    is wasteful rather than wrong.
    """
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
        logger.warning("Weekly digest lock unavailable, running anyway: %s", exc)
        return True


def _seconds_until_next_run(now: datetime) -> float:
    days_ahead = (RUN_ON_WEEKDAY - now.weekday()) % 7
    target = (now + timedelta(days=days_ahead)).replace(
        hour=RUN_AT_HOUR_UTC, minute=0, second=0, microsecond=0
    )
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


async def _run_once() -> None:
    from src.core.events.database import _async_session_factory
    from src.services.digest.weekly_digest import run_weekly_digest

    async with _async_session_factory() as db_session:
        stats = await run_weekly_digest(db_session)
    logger.info("Weekly digest run complete: %s", stats.as_dict())


async def _tick() -> None:
    try:
        today = datetime.now(timezone.utc)
        if today.weekday() != RUN_ON_WEEKDAY:
            return
        if await _claim_week(today):
            await _run_once()
        else:
            logger.info("This week's digest run was already handled elsewhere")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Weekly digest run failed, will retry next week: %s", exc)


async def _loop() -> None:
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    if datetime.now(timezone.utc).weekday() == RUN_ON_WEEKDAY:
        await _tick()

    while True:
        await asyncio.sleep(_seconds_until_next_run(datetime.now(timezone.utc)))
        await _tick()


def start_scheduler() -> None:
    """Start the weekly tick, unless the feature is switched off.

    Never raises: a background email job must not be able to stop the API
    from booting.
    """
    global _task

    try:
        from src.services.digest.weekly_digest import digest_enabled

        if not digest_enabled():
            logger.info(
                "Weekly digest scheduler idle: LEARNHOUSE_WEEKLY_DIGEST_ENABLED is not set"
            )
            return
        if os.environ.get("LEARNHOUSE_WEEKLY_DIGEST_NO_SCHEDULER"):
            logger.info("Weekly digest scheduler disabled; drive it via your own cron")
            return

        _task = asyncio.create_task(_loop())
        logger.info(
            "Weekly digest scheduler started (weekly on weekday=%s at %02d:00 UTC)",
            RUN_ON_WEEKDAY,
            RUN_AT_HOUR_UTC,
        )
    except Exception as exc:
        logger.warning("Weekly digest scheduler not started: %s", exc)


async def stop_scheduler() -> None:
    """Stop the tick. Never raises, for the same reason as `start_scheduler`."""
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
