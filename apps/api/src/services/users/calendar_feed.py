"""ICS calendar feed of a student's assignment due dates and live sessions.

See db.calendar_feed_token's module docstring for the token-as-credential
trust model this endpoint relies on (the same one Canvas/Moodle use for
their own subscribable feeds) — a calendar client polls the feed URL on
its own schedule with no way to send a session Bearer token, so the opaque
token in the URL path IS the authentication.

SCOPE: assignment due dates and scheduled live sessions
(services.courses.live_sessions), across every course the user has a Trail
run for (i.e. is enrolled in) — not general course content, not other
activity types. Each student's OWN effective due date is used for
assignments (their extension's date if they have one — see
services.courses.activities.assignment_extensions.get_effective_due_date —
otherwise the assignment's own due_date), so an extended student's feed
shows the deadline that actually applies to them. A live session's VEVENT
carries its meeting_url in the standard ICS URL property, so most calendar
clients render it as a clickable join link right on the event.

TIMEZONE: due dates are stored as naive local-time strings with no offset
recorded anywhere in this codebase (see assignments.py's own
`_is_date_past` docstring). This feed emits them as "floating" ICS times
(no TZID, no trailing Z) — RFC 5545's explicit mechanism for a time with no
fixed timezone, which every mainstream calendar client renders in the
VIEWER's own local timezone. For a single-institution self-hosted
deployment where students and the deadline both live in the same timezone
this is the correct behavior; a multi-timezone deployment would see
mismatched displayed times, since nothing here can know which timezone a
"naive" due_date was actually authored in. A real per-org timezone setting
would fix this properly — out of scope for this pass.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.calendar_feed_token import CalendarFeedToken
from src.db.courses.assignments import Assignment
from src.db.courses.courses import Course
from src.db.courses.live_sessions import LiveSession
from src.db.trail_runs import TrailRun
from src.db.users import PublicUser
from src.services.courses.activities.assignment_extensions import get_effective_due_date


async def get_or_create_feed_token(current_user: PublicUser, db_session: AsyncSession) -> str:
    statement = select(CalendarFeedToken).where(CalendarFeedToken.user_id == current_user.id)
    existing = (await db_session.execute(statement)).scalars().first()
    if existing:
        return existing.token

    token = secrets.token_urlsafe(32)
    db_session.add(
        CalendarFeedToken(token=token, user_id=current_user.id, creation_date=str(datetime.now()))
    )
    await db_session.commit()
    return token


async def regenerate_feed_token(current_user: PublicUser, db_session: AsyncSession) -> str:
    statement = select(CalendarFeedToken).where(CalendarFeedToken.user_id == current_user.id)
    existing = (await db_session.execute(statement)).scalars().first()
    if existing:
        await db_session.delete(existing)
        await db_session.commit()
    return await get_or_create_feed_token(current_user, db_session)


def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold_line(line: str) -> str:
    """RFC 5545 line folding, approximated by character count rather than
    the spec's octet count — simpler, and safe from splitting a multi-byte
    UTF-8 sequence mid-character; the tradeoff is a very long line of
    non-ASCII text could fold a few characters later than strict spec. Real
    calendar clients tolerate this fine in practice.
    """
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(parts)


def _format_due_date(raw: str) -> tuple[str, bool]:
    """Returns (ICS DTSTART value, is_date_only). Mirrors the same
    defensive parsing `_is_date_past` uses elsewhere: an unparseable value
    is treated as absent by the caller, never as a crash.
    """
    raw_str = raw.strip()
    try:
        parsed = datetime.fromisoformat(raw_str)
    except (ValueError, TypeError):
        raise ValueError("unparseable date")
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    is_date_only = "T" not in raw_str and ":" not in raw_str
    if is_date_only:
        return parsed.strftime("%Y%m%d"), True
    return parsed.strftime("%Y%m%dT%H%M%S"), False


async def build_ics_feed(token: str, db_session: AsyncSession) -> str:
    statement = select(CalendarFeedToken).where(CalendarFeedToken.token == token)
    feed_token = (await db_session.execute(statement)).scalars().first()
    if not feed_token:
        raise HTTPException(status_code=404, detail="Calendar feed not found")

    runs_statement = select(TrailRun.course_id).where(TrailRun.user_id == feed_token.user_id)
    course_ids = list((await db_session.execute(runs_statement)).scalars().all())

    events: list[str] = []
    if course_ids:
        courses_statement = select(Course).where(Course.id.in_(course_ids))  # type: ignore[attr-defined]
        courses = {c.id: c for c in (await db_session.execute(courses_statement)).scalars().all()}

        assignments_statement = select(Assignment).where(
            Assignment.course_id.in_(course_ids),  # type: ignore[attr-defined]
            Assignment.published == True,  # noqa: E712
        )
        assignments = (await db_session.execute(assignments_statement)).scalars().all()

        now_stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        for assignment in assignments:
            effective_due = await get_effective_due_date(assignment, feed_token.user_id, db_session)
            if not effective_due or not str(effective_due).strip():
                continue
            try:
                dtstart, is_date_only = _format_due_date(str(effective_due))
            except ValueError:
                continue

            course = courses.get(assignment.course_id)
            course_name = course.name if course else ""
            summary = f"Due: {assignment.title}" + (f" ({course_name})" if course_name else "")

            dtstart_line = f"DTSTART;VALUE=DATE:{dtstart}" if is_date_only else f"DTSTART:{dtstart}"
            events.append("\r\n".join([
                "BEGIN:VEVENT",
                _fold_line(f"UID:assignment-{assignment.assignment_uuid}@learnhouse"),
                f"DTSTAMP:{now_stamp}",
                _fold_line(dtstart_line),
                _fold_line(f"SUMMARY:{_ics_escape(summary)}"),
                "END:VEVENT",
            ]))

        # Live sessions (services.courses.live_sessions) — every enrolled
        # course's scheduled sessions, same floating-time convention as
        # assignment due dates above (see this module's own docstring).
        sessions_statement = select(LiveSession).where(
            LiveSession.course_id.in_(course_ids)  # type: ignore[attr-defined]
        )
        live_sessions = (await db_session.execute(sessions_statement)).scalars().all()
        for live_session in live_sessions:
            try:
                dtstart, is_date_only = _format_due_date(live_session.start_time)
            except ValueError:
                continue

            course = courses.get(live_session.course_id)
            course_name = course.name if course else ""
            summary = f"{live_session.title}" + (f" ({course_name})" if course_name else "")

            lines = [
                "BEGIN:VEVENT",
                _fold_line(f"UID:livesession-{live_session.session_uuid}@learnhouse"),
                f"DTSTAMP:{now_stamp}",
                _fold_line(
                    f"DTSTART;VALUE=DATE:{dtstart}" if is_date_only else f"DTSTART:{dtstart}"
                ),
            ]
            if live_session.end_time:
                try:
                    dtend, end_is_date_only = _format_due_date(live_session.end_time)
                    lines.append(_fold_line(
                        f"DTEND;VALUE=DATE:{dtend}" if end_is_date_only else f"DTEND:{dtend}"
                    ))
                except ValueError:
                    pass
            lines.append(_fold_line(f"SUMMARY:{_ics_escape(summary)}"))
            if live_session.description:
                lines.append(_fold_line(f"DESCRIPTION:{_ics_escape(live_session.description)}"))
            lines.append(_fold_line(f"URL:{live_session.meeting_url}"))
            lines.append("END:VEVENT")
            events.append("\r\n".join(lines))

    body = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//St. Joseph's Placements and Training Cell//Assignment Due Dates and Live Sessions//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold_line("X-WR-CALNAME:St. Joseph's Placements and Training Cell schedule"),
        *events,
        "END:VCALENDAR",
    ])
    return body + "\r\n"
