import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.integrations.openeducat import (
    check_openeducat_health,
    sync_student_to_openeducat,
    sync_course_completion_to_openeducat,
)


@pytest.mark.asyncio
async def test_check_openeducat_health_connected():
    with patch("src.services.integrations.openeducat._jsonrpc_call") as mock_rpc, \
         patch("src.services.integrations.openeducat.authenticate_openeducat", new_callable=AsyncMock, return_value=2):
        mock_rpc.return_value = {"server_version": "17.0"}

        res = await check_openeducat_health()
        assert res["enabled"] is True
        assert res["connected"] is True
        assert res["authenticated"] is True
        assert res["uid"] == 2
        assert res["server_version"] == "17.0"
        assert "latency_ms" in res


@pytest.mark.asyncio
async def test_check_openeducat_health_error():
    with patch("src.services.integrations.openeducat._jsonrpc_call", side_effect=Exception("Connection refused")):
        res = await check_openeducat_health()
        assert res["enabled"] is True
        assert res["connected"] is False
        assert "Connection refused" in res["error"]


@pytest.mark.asyncio
async def test_sync_student_to_openeducat_create():
    with patch("src.services.integrations.openeducat.authenticate_openeducat", new_callable=AsyncMock, return_value=2), \
         patch("src.services.integrations.openeducat._jsonrpc_call") as mock_rpc:
        # 1. search_read op.student -> empty (new student)
        # 2. create op.student -> 101
        # 3. search_read op.course -> [{'id': 39}]
        # 4. search_read op.batch -> [{'id': 20}]
        # 5. search_read op.student.course -> empty
        # 6. create op.student.course -> 55
        mock_rpc.side_effect = [
            [],  # op.student search_read
            101, # op.student create
            [{"id": 39}], # op.course
            [{"id": 20}], # op.batch
            [], # op.student.course search_read
            55, # op.student.course create
        ]

        res = await sync_student_to_openeducat(
            email="312421104010@stjosephstechnology.ac.in",
            first_name="Aadhavan",
            last_name="K",
            register_number="312421104010",
            department="CSE",
        )
        assert res["success"] is True
        assert res["action"] == "created"
        assert res["student_id"] == 101
        assert res["course_code"] == "BE-CSE"


@pytest.mark.asyncio
async def test_sync_student_to_openeducat_update():
    with patch("src.services.integrations.openeducat.authenticate_openeducat", new_callable=AsyncMock, return_value=2), \
         patch("src.services.integrations.openeducat._jsonrpc_call") as mock_rpc:
        mock_rpc.side_effect = [
            [{"id": 30, "name": "Aadhavan K", "gr_no": "312421104010", "email": "old@test.com"}], # op.student existing
            True, # op.student write
            [{"id": 39}], # op.course
            [{"id": 20}], # op.batch
            [{"id": 1}], # op.student.course existing
        ]

        res = await sync_student_to_openeducat(
            email="312421104010@stjosephstechnology.ac.in",
            first_name="Aadhavan",
            last_name="K",
            register_number="312421104010",
            department="CSE",
        )
        assert res["success"] is True
        assert res["action"] == "updated"
        assert res["student_id"] == 30


@pytest.mark.asyncio
async def test_sync_course_completion_to_openeducat():
    with patch("src.services.integrations.openeducat.authenticate_openeducat", new_callable=AsyncMock, return_value=2), \
         patch("src.services.integrations.openeducat._jsonrpc_call") as mock_rpc:
        mock_rpc.side_effect = [
            [{"id": 30, "name": "Aadhavan K"}], # op.student search_read
            1, # mail.message create
        ]

        res = await sync_course_completion_to_openeducat(
            student_email="312421104010@stjosephstechnology.ac.in",
            course_name="Full Stack Java Placement Sprint",
            completion_date="2026-09-09",
            certificate_url="https://learn.stjosephsplacements.in/cert/sjgi-101",
            register_number="312421104010",
        )
        assert res["success"] is True
        assert res["student_id"] == 30
        assert "LMS Course Completed" in res["logged_event"]
