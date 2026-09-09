import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.integrations.erpnext import (
    check_erpnext_health,
    sync_student_to_erpnext,
    sync_course_completion_to_erpnext,
)


@pytest.mark.asyncio
async def test_check_erpnext_health_connected():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        res = await check_erpnext_health()
        assert res["enabled"] is True
        assert res["connected"] is True
        assert res["status_code"] == 200
        assert "latency_ms" in res


@pytest.mark.asyncio
async def test_check_erpnext_health_error():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=Exception("Connection timed out")):
        res = await check_erpnext_health()
        assert res["enabled"] is True
        assert res["connected"] is False
        assert "Connection timed out" in res["error"]


@pytest.mark.asyncio
async def test_sync_student_to_erpnext_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"name": "STU-001"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await sync_student_to_erpnext(
            email="student@test.com",
            first_name="Arun",
            last_name="Kumar",
        )
        assert res["success"] is True
        assert res["data"]["name"] == "STU-001"


@pytest.mark.asyncio
async def test_sync_course_completion_to_erpnext():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock, return_value=mock_resp):
        res = await sync_course_completion_to_erpnext(
            student_email="student@test.com",
            course_name="Full Stack Placement Training",
            completion_date="2026-09-09",
            certificate_url="https://learn.stjosephsplacements.in/cert/123",
        )
        assert res["success"] is True
        assert res["status_code"] == 200
