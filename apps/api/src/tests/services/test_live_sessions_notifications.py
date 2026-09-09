import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.courses.live_sessions_notifications import (
    _parse_iso_time,
    send_live_session_scheduled_email,
    send_live_session_starting_soon_email,
    notify_enrolled_students_on_creation,
    check_and_send_upcoming_reminders,
)
from src.db.courses.courses import Course
from src.db.courses.live_sessions import LiveSession
from src.db.organizations import Organization
from src.db.trail_runs import TrailRun
from src.db.users import User


def test_parse_iso_time():
    # Naive ISO
    dt = _parse_iso_time("2026-09-15T10:00:00")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2026 and dt.hour == 10

    # Explicit UTC ISO
    dt_z = _parse_iso_time("2026-09-15T10:00:00Z")
    assert dt_z is not None
    assert dt_z.tzinfo == timezone.utc

    # Standard formats
    dt_space = _parse_iso_time("2026-09-15 14:30:00")
    assert dt_space is not None and dt_space.hour == 14

    # Invalid / empty
    assert _parse_iso_time("") is None
    assert _parse_iso_time("invalid-date") is None


def test_send_live_session_scheduled_email():
    with patch("src.services.courses.live_sessions_notifications._send_notification_email", return_value=True) as mock_send:
        success = send_live_session_scheduled_email(
            user_email="student@test.com",
            user_name="John Doe",
            course_name="Machine Learning 101",
            session_title="Q&A Session",
            start_time_str="2026-09-15T10:00:00Z",
            meeting_url="https://meet.google.com/abc-def-ghi",
            description="Bring your questions!",
            org_name="St. Joseph's Placements and Training Cell",
        )
        assert success is True
        assert mock_send.call_count == 1
        args, kwargs = mock_send.call_args
        assert kwargs["to"] == "student@test.com"
        assert "Q&A Session" in kwargs["subject"]
        assert "Machine Learning 101" in kwargs["subject"]
        assert "https://meet.google.com/abc-def-ghi" in kwargs["body"]
        assert "Bring your questions!" in kwargs["body"]


def test_send_live_session_starting_soon_email():
    with patch("src.services.courses.live_sessions_notifications._send_notification_email", return_value=True) as mock_send:
        success = send_live_session_starting_soon_email(
            user_email="student@test.com",
            user_name="John Doe",
            course_name="Machine Learning 101",
            session_title="Live Coding Workshop",
            start_time_str="2026-09-15T10:00:00Z",
            meeting_url="https://meet.google.com/xyz-uvw-rst",
            org_name="St. Joseph's Placements and Training Cell",
        )
        assert success is True
        assert mock_send.call_count == 1
        args, kwargs = mock_send.call_args
        assert kwargs["to"] == "student@test.com"
        assert "starting soon" in kwargs["subject"].lower()
        assert "https://meet.google.com/xyz-uvw-rst" in kwargs["body"]


@pytest.mark.asyncio
async def test_notify_enrolled_students_on_creation():
    mock_session = LiveSession(
        id=1,
        session_uuid="livesession_123",
        org_id=1,
        course_id=10,
        title="Python Deep Dive",
        meeting_url="https://zoom.us/j/123456",
        start_time="2026-09-20T10:00:00",
        created_by_user_id=1,
    )
    mock_course = Course(
        id=10,
        course_uuid="course_10",
        name="Advanced Python",
        org_id=1,
    )
    mock_org = Organization(id=1, name="St. Joseph's", slug="stjosephs")
    mock_student = User(id=5, email="student@example.com", username="student1")

    fake_db = MagicMock()
    
    # Configure mock execute responses
    def fake_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt).lower()
        if "live_session" in stmt_str:
            mock_result.scalars.return_value.first.return_value = mock_session
        elif "trailrun" in stmt_str or '"user"' in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_student]
        elif "course" in stmt_str:
            mock_result.scalars.return_value.first.return_value = mock_course
        elif "organization" in stmt_str:
            mock_result.scalars.return_value.first.return_value = mock_org
        return mock_result

    fake_db.execute = AsyncMock(side_effect=fake_execute)

    class FakeSessionFactory:
        async def __aenter__(self):
            return fake_db
        async def __aexit__(self, *args):
            pass

    with patch("src.core.events.database._async_session_factory", return_value=FakeSessionFactory()):
        with patch("src.services.courses.live_sessions_notifications.send_live_session_scheduled_email", return_value=True) as mock_send_mail:
            sent = await notify_enrolled_students_on_creation(session_id=1, course_id=10)
            assert sent == 1
            assert mock_send_mail.call_count == 1
            assert mock_send_mail.call_args.kwargs["user_email"] == "student@example.com"
            assert mock_send_mail.call_args.kwargs["session_title"] == "Python Deep Dive"


@pytest.mark.asyncio
async def test_check_and_send_upcoming_reminders():
    # Session starting in 15 minutes
    start_time = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    mock_session = LiveSession(
        id=2,
        session_uuid="livesession_upcoming",
        org_id=1,
        course_id=10,
        title="Interview Preparation Live",
        meeting_url="https://meet.google.com/test",
        start_time=start_time,
        created_by_user_id=1,
    )
    mock_course = Course(id=10, course_uuid="course_10", name="Placement Prep", org_id=1)
    mock_org = Organization(id=1, name="St. Joseph's", slug="stjosephs")
    mock_student = User(id=8, email="candidate@example.com", username="candidate")

    fake_db = MagicMock()

    def fake_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt).lower()
        if "live_session" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_session]
        elif "trailrun" in stmt_str or '"user"' in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_student]
        elif "course" in stmt_str:
            mock_result.scalars.return_value.first.return_value = mock_course
        elif "organization" in stmt_str:
            mock_result.scalars.return_value.first.return_value = mock_org
        return mock_result

    fake_db.execute = AsyncMock(side_effect=fake_execute)

    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # not yet sent

    with patch("src.core.redis.get_redis_client", return_value=mock_redis):
        with patch("src.services.courses.live_sessions_notifications.send_live_session_starting_soon_email", return_value=True) as mock_send_mail:
            reminders = await check_and_send_upcoming_reminders(fake_db)
            assert reminders == 1
            assert mock_send_mail.call_count == 1
            assert mock_send_mail.call_args.kwargs["user_email"] == "candidate@example.com"
            # Redis set dedupe key check
            assert mock_redis.set.call_count == 1
