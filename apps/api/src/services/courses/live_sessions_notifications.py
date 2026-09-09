"""Automated email and push notifications for course live sessions.

Dispatches:
1. Scheduled notification: Sent to enrolled students when a new live session is created.
2. 15-30 minute reminder: Automated background check that emails enrolled students
   with the meeting URL shortly before the session starts.
"""

import asyncio
import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.courses.courses import Course
from src.db.courses.live_sessions import LiveSession
from src.db.organizations import Organization
from src.db.trail_runs import TrailRun
from src.db.users import User
from src.services.users.emails import (
    LOGO_SVG,
    STYLES,
    _email_layout,
    _send_notification_email,
)

logger = logging.getLogger(__name__)

_REMINDER_LOCK_KEY = "learnhouse:live_sessions:reminders_tick"
_REMINDER_DEDUPE_PREFIX = "learnhouse:live_session_reminder:"
_DEDUPE_TTL_SECONDS = 48 * 3600  # 48 hours


def _parse_iso_time(time_str: str) -> Optional[datetime]:
    """Parse naive or tz-aware ISO timestamp into UTC datetime."""
    if not time_str:
        return None
    time_str = time_str.strip()
    try:
        dt = datetime.fromisoformat(time_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def send_live_session_scheduled_email(
    user_email: str,
    user_name: str,
    course_name: str,
    session_title: str,
    start_time_str: str,
    meeting_url: str,
    description: Optional[str] = None,
    org_name: str = "St. Joseph's Placements and Training Cell",
) -> bool:
    """Notify a student when a new live session is scheduled."""
    safe_user = html.escape(user_name or "Student")
    safe_course = html.escape(course_name)
    safe_title = html.escape(session_title)
    safe_time = html.escape(start_time_str)
    safe_org = html.escape(org_name)

    desc_html = ""
    if description and description.strip():
        desc_html = f'<p style="{STYLES["p"]}">{html.escape(description.strip())}</p>'

    body_content = f"""
        <h1 style="{STYLES['h1']}">Live Session Scheduled</h1>
        <p style="{STYLES['p']}">
            Hello {safe_user}, a new live session <strong>{safe_title}</strong> has been scheduled for your course <strong>{safe_course}</strong>.
        </p>
        <div style="margin: 20px 0; padding: 16px; background-color: #fafafa; border-radius: 12px; border: 1px solid #e5e5e5; text-align: left;">
            <p style="margin: 0 0 8px 0; font-size: 13px; color: #555;"><strong>Date & Time:</strong> {safe_time}</p>
            <p style="margin: 0; font-size: 13px; color: #555;"><strong>Course:</strong> {safe_course}</p>
        </div>
        {desc_html}
        <a href="{html.escape(meeting_url)}" style="{STYLES['button']}">Join Meeting Link</a>
        <p style="{STYLES['link_text']}">{html.escape(meeting_url)}</p>
    """

    return _send_notification_email(
        to=user_email,
        subject=f"New Live Session: {session_title} - {course_name}",
        body=_email_layout(
            title=f"Live Session: {safe_title}",
            body_content=body_content,
            footer_note=f"{safe_org} Live Sessions",
            logo_html=LOGO_SVG,
        ),
    )


def send_live_session_starting_soon_email(
    user_email: str,
    user_name: str,
    course_name: str,
    session_title: str,
    start_time_str: str,
    meeting_url: str,
    org_name: str = "St. Joseph's Placements and Training Cell",
) -> bool:
    """Send an urgent reminder 15-30 minutes before the session starts."""
    safe_user = html.escape(user_name or "Student")
    safe_course = html.escape(course_name)
    safe_title = html.escape(session_title)
    safe_time = html.escape(start_time_str)
    safe_org = html.escape(org_name)

    body_content = f"""
        <h1 style="{STYLES['h1']}">Starting Soon: Live Session</h1>
        <p style="{STYLES['p']}">
            Hello {safe_user}, your live session <strong>{safe_title}</strong> for <strong>{safe_course}</strong> is starting soon!
        </p>
        <div style="margin: 20px 0; padding: 16px; background-color: #fdf2f8; border-radius: 12px; border: 1px solid #fbcfe8; text-align: left;">
            <p style="margin: 0 0 8px 0; font-size: 14px; color: #9d174d; font-weight: bold;">Starting at: {safe_time}</p>
            <p style="margin: 0; font-size: 13px; color: #701a75;">Please join a few minutes early to test your audio and video.</p>
        </div>
        <a href="{html.escape(meeting_url)}" style="{STYLES['button']}">Join Live Session Now</a>
        <p style="{STYLES['link_text']}">{html.escape(meeting_url)}</p>
    """

    return _send_notification_email(
        to=user_email,
        subject=f"Reminder: Live Session starting soon: {session_title}",
        body=_email_layout(
            title=f"Starting Soon: {safe_title}",
            body_content=body_content,
            footer_note=f"{safe_org} Live Sessions",
            logo_html=LOGO_SVG,
        ),
    )


async def notify_enrolled_students_on_creation(
    session_id: int,
    course_id: int,
) -> int:
    """Asynchronously send scheduling notifications to all enrolled students with independent DB session."""
    from src.core.events.database import _async_session_factory

    try:
        async with _async_session_factory() as db_session:
            live_session = (await db_session.execute(
                select(LiveSession).where(LiveSession.id == session_id)
            )).scalars().first()
            if not live_session:
                return 0

            course = (await db_session.execute(
                select(Course).where(Course.id == course_id)
            )).scalars().first()
            if not course:
                return 0

            org = (await db_session.execute(
                select(Organization).where(Organization.id == course.org_id)
            )).scalars().first()
            org_name = org.name if org else "St. Joseph's Placements and Training Cell"

            # Find all enrolled students
            enrolled_users_query = select(User).join(
                TrailRun, TrailRun.user_id == User.id
            ).where(
                TrailRun.course_id == course.id,
            ).distinct()

            students = (await db_session.execute(enrolled_users_query)).scalars().all()
            sent_count = 0

            for student in students:
                if not student.email:
                    continue
                full_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
                name = full_name or student.username or "Student"
                try:
                    success = send_live_session_scheduled_email(
                        user_email=student.email,
                        user_name=name,
                        course_name=course.name,
                        session_title=live_session.title,
                        start_time_str=live_session.start_time,
                        meeting_url=live_session.meeting_url,
                        description=live_session.description,
                        org_name=org_name,
                    )
                    if success:
                        sent_count += 1
                except Exception as e:
                    logger.debug("Failed sending live session announcement to %s: %s", student.email, e)

            logger.info(
                "Dispatched live session announcement for '%s' to %s student(s)",
                live_session.title, sent_count
            )
            return sent_count
    except Exception as e:
        logger.warning("Error notifying students of new live session: %s", e)
        return 0


async def check_and_send_upcoming_reminders(db_session: AsyncSession) -> int:
    """Scan database for live sessions starting in the next 30 minutes and notify students."""
    from src.core.redis import get_redis_client

    redis_client = get_redis_client()
    now_utc = datetime.now(timezone.utc)
    lookahead_window = now_utc + timedelta(minutes=30)
    past_buffer = now_utc - timedelta(minutes=10)  # include sessions started <= 10m ago

    sessions = (await db_session.execute(select(LiveSession))).scalars().all()
    reminders_sent = 0

    for session in sessions:
        start_dt = _parse_iso_time(session.start_time)
        if not start_dt:
            continue

        # Check if session start time falls within our alert window: [now - 10m, now + 30m]
        if not (past_buffer <= start_dt <= lookahead_window):
            continue

        course = (await db_session.execute(
            select(Course).where(Course.id == session.course_id)
        )).scalars().first()
        if not course:
            continue

        org = (await db_session.execute(
            select(Organization).where(Organization.id == session.org_id)
        )).scalars().first()
        org_name = org.name if org else "St. Joseph's Placements and Training Cell"

        enrolled_query = select(User).join(
            TrailRun, TrailRun.user_id == User.id
        ).where(
            TrailRun.course_id == course.id,
        ).distinct()

        students = (await db_session.execute(enrolled_query)).scalars().all()

        for student in students:
            if not student.email:
                continue

            dedupe_key = f"{_REMINDER_DEDUPE_PREFIX}{session.session_uuid}:{student.id}"

            # Check / set Redis dedupe key
            if redis_client is not None:
                try:
                    already_sent = await asyncio.to_thread(redis_client.get, dedupe_key)
                    if already_sent:
                        continue
                except Exception:
                    pass

            full_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
            name = full_name or student.username or "Student"
            try:
                sent = send_live_session_starting_soon_email(
                    user_email=student.email,
                    user_name=name,
                    course_name=course.name,
                    session_title=session.title,
                    start_time_str=session.start_time,
                    meeting_url=session.meeting_url,
                    org_name=org_name,
                )
                if sent:
                    reminders_sent += 1
                    if redis_client is not None:
                        try:
                            await asyncio.to_thread(
                                redis_client.set, dedupe_key, "1", ex=_DEDUPE_TTL_SECONDS
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("Failed sending upcoming reminder to %s: %s", student.email, e)

    return reminders_sent


# ---------------------------------------------------------------------------
# Background Scheduler
# ---------------------------------------------------------------------------

_scheduler_task: Optional[asyncio.Task] = None
SCHEDULER_INTERVAL_SECONDS = 300  # Run every 5 minutes


async def _reminders_loop():
    from src.core.events.database import _async_session_factory

    logger.info("Live session reminders background scheduler started.")
    await asyncio.sleep(15)  # initial delay after boot

    while True:
        try:
            async with _async_session_factory() as session:
                sent = await check_and_send_upcoming_reminders(session)
                if sent > 0:
                    logger.info("Sent %d live session starting-soon reminder(s)", sent)
        except asyncio.CancelledError:
            logger.info("Live session reminders loop cancelled.")
            break
        except Exception as e:
            logger.warning("Error in live session reminders loop: %s", e)

        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


def start_live_session_reminders_scheduler():
    """Start background scheduler if not already running."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_reminders_loop())
        logger.info("Spawned live session reminders background task.")


def stop_live_session_reminders_scheduler():
    """Stop background scheduler."""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
