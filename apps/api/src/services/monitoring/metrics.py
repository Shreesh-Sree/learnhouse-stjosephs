"""Prometheus metrics generation service for LearnHouse LMS."""

import time
import logging
from datetime import datetime, timezone
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.redis import get_redis_client

logger = logging.getLogger(__name__)

# Cache metrics output for 15 seconds to minimize database overhead from high-frequency scraping
_CACHED_METRICS: str = ""
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS: float = 15.0


async def get_prometheus_metrics(db_session: AsyncSession) -> str:
    """Generate Prometheus exposition format metrics for LearnHouse platform health and stats."""
    global _CACHED_METRICS, _CACHE_TIMESTAMP

    now = time.time()
    if _CACHED_METRICS and (now - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS:
        return _CACHED_METRICS

    # 1. Database Health Check
    db_healthy = 0
    try:
        res = await db_session.execute(text("SELECT 1"))
        if res.scalar() == 1:
            db_healthy = 1
    except Exception as e:
        logger.debug("Metrics DB health check failed: %s", e)
        db_healthy = 0

    # 2. Redis Health Check
    redis_healthy = 0
    try:
        r = get_redis_client()
        if r is not None and r.ping():
            redis_healthy = 1
    except Exception as e:
        logger.debug("Metrics Redis health check failed: %s", e)
        redis_healthy = 0

    # 3. Database Entity Counts (wrapped safely in try-except)
    users_count = 0
    courses_count = 0
    enrollments_count = 0
    completed_runs_count = 0
    certificates_count = 0
    live_sessions_count = 0
    audit_logs_count = 0

    if db_healthy:
        try:
            u_res = await db_session.execute(text('SELECT count(*) FROM "user"'))
            users_count = u_res.scalar() or 0
        except Exception:
            pass

        try:
            c_res = await db_session.execute(text("SELECT count(*) FROM course"))
            courses_count = c_res.scalar() or 0
        except Exception:
            pass

        try:
            tr_res = await db_session.execute(text("SELECT count(*) FROM trailrun"))
            enrollments_count = tr_res.scalar() or 0
        except Exception:
            pass

        try:
            tr_comp = await db_session.execute(text("SELECT count(*) FROM trailrun WHERE status = 'COMPLETED'"))
            completed_runs_count = tr_comp.scalar() or 0
        except Exception:
            pass

        try:
            cert_res = await db_session.execute(text("SELECT count(*) FROM certificateuser"))
            certificates_count = cert_res.scalar() or 0
        except Exception:
            pass

        try:
            ls_res = await db_session.execute(text("SELECT count(*) FROM live_session"))
            live_sessions_count = ls_res.scalar() or 0
        except Exception:
            pass

        try:
            al_res = await db_session.execute(text("SELECT count(*) FROM auditlog"))
            audit_logs_count = al_res.scalar() or 0
        except Exception:
            pass

    # Build Prometheus Exposition String
    lines = [
        "# HELP learnhouse_up Whether the LearnHouse LMS API server is operational",
        "# TYPE learnhouse_up gauge",
        "learnhouse_up 1",
        "",
        "# HELP learnhouse_database_healthy PostgreSQL database connection status (1 = healthy, 0 = unhealthy)",
        "# TYPE learnhouse_database_healthy gauge",
        f"learnhouse_database_healthy {db_healthy}",
        "",
        "# HELP learnhouse_redis_healthy Redis cache connection status (1 = healthy, 0 = unhealthy)",
        "# TYPE learnhouse_redis_healthy gauge",
        f"learnhouse_redis_healthy {redis_healthy}",
        "",
        "# HELP learnhouse_users_total Total registered platform users",
        "# TYPE learnhouse_users_total gauge",
        f"learnhouse_users_total {users_count}",
        "",
        "# HELP learnhouse_courses_total Total courses created",
        "# TYPE learnhouse_courses_total gauge",
        f"learnhouse_courses_total {courses_count}",
        "",
        "# HELP learnhouse_enrollments_total Total student course enrollments / trail runs",
        "# TYPE learnhouse_enrollments_total gauge",
        f"learnhouse_enrollments_total {enrollments_count}",
        "",
        "# HELP learnhouse_completed_enrollments_total Total completed course trail runs",
        "# TYPE learnhouse_completed_enrollments_total gauge",
        f"learnhouse_completed_enrollments_total {completed_runs_count}",
        "",
        "# HELP learnhouse_certificates_awarded_total Total course certificates awarded",
        "# TYPE learnhouse_certificates_awarded_total gauge",
        f"learnhouse_certificates_awarded_total {certificates_count}",
        "",
        "# HELP learnhouse_live_sessions_total Total scheduled live video sessions",
        "# TYPE learnhouse_live_sessions_total gauge",
        f"learnhouse_live_sessions_total {live_sessions_count}",
        "",
        "# HELP learnhouse_audit_logs_total Total security and activity audit logs recorded",
        "# TYPE learnhouse_audit_logs_total gauge",
        f"learnhouse_audit_logs_total {audit_logs_count}",
        "",
    ]

    output = "\n".join(lines)
    _CACHED_METRICS = output
    _CACHE_TIMESTAMP = now
    return output
