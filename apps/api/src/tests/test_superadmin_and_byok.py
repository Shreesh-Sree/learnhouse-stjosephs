import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, Request

from src.services.ai.ai import _extract_and_resolve_byok
from src.services.ai.schemas.ai import StartActivityAIChatSession, SendActivityAIChatMessage


def test_byok_resolution_google_key():
    req = MagicMock(spec=Request)
    req.headers = {}

    session_obj = StartActivityAIChatSession(
        activity_uuid="act_123",
        message="Hello AI",
        byok_api_key="AIzaSyDummyGoogleKey12345",
    )

    model, is_byok, model_name = _extract_and_resolve_byok(req, session_obj)
    assert is_byok is True
    assert model_name == "gemini-1.5-flash"
    assert model is not None


def test_byok_resolution_groq_key():
    req = MagicMock(spec=Request)
    req.headers = {}

    session_obj = SendActivityAIChatMessage(
        aichat_uuid="chat_123",
        activity_uuid="act_123",
        message="Explain this code",
        byok_api_key="gsk_DummyGroqKey12345",
    )

    model, is_byok, model_name = _extract_and_resolve_byok(req, session_obj)
    assert is_byok is True
    assert model_name == "llama-3.3-70b-versatile"
    assert model is not None


def test_byok_resolution_headers():
    req = MagicMock(spec=Request)
    req.headers = {
        "x-byok-api-key": "AIzaSyDummyGoogleKeyFromHeader",
        "x-byok-provider": "gemini",
        "x-byok-model": "gemini-2.0-flash",
    }

    session_obj = StartActivityAIChatSession(
        activity_uuid="act_123",
        message="Header test",
    )

    model, is_byok, model_name = _extract_and_resolve_byok(req, session_obj)
    assert is_byok is True
    assert model_name == "gemini-2.0-flash"
    assert model is not None


def test_byok_required_when_configured():
    old_env = os.environ.get("LEARNHOUSE_STUDENT_AI_BYOK")
    os.environ["LEARNHOUSE_STUDENT_AI_BYOK"] = "true"

    try:
        req = MagicMock(spec=Request)
        req.headers = {}
        session_obj = StartActivityAIChatSession(
            activity_uuid="act_123",
            message="No key provided",
        )

        with pytest.raises(HTTPException) as exc_info:
            _extract_and_resolve_byok(req, session_obj)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail.get("code") == "BYOK_REQUIRED"
    finally:
        if old_env is not None:
            os.environ["LEARNHOUSE_STUDENT_AI_BYOK"] = old_env
        else:
            os.environ.pop("LEARNHOUSE_STUDENT_AI_BYOK", None)


@pytest.mark.asyncio
async def test_superadmin_protection_deletion():
    from src.services.users.users import delete_user_by_id
    from src.db.users import PublicUser, User

    req = MagicMock(spec=Request)
    admin_user = PublicUser(
        id=1,
        user_uuid="user_root",
        username="admin",
        first_name="Admin",
        last_name="SuperAdmin",
        email="admin@stjosephsplacements.in",
        is_superadmin=True,
    )

    target_user = User(
        id=1,
        user_uuid="user_root",
        username="admin",
        first_name="Admin",
        last_name="SuperAdmin",
        email="admin@stjosephsplacements.in",
        is_superadmin=True,
        password_hash="hash",
    )

    mock_exec = MagicMock()
    mock_exec.scalars.return_value.first.return_value = target_user
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_exec

    # Attempting to delete admin@stjosephsplacements.in must fail with 403
    with pytest.raises(HTTPException) as exc_info:
        await delete_user_by_id(
            request=req,
            db_session=mock_db,
            current_user=admin_user,
            user_id=1,
        )
    assert exc_info.value.status_code == 403
    assert "The root SuperAdmin account (admin@stjosephsplacements.in) is protected and cannot be deleted." in exc_info.value.detail


@pytest.mark.asyncio
async def test_superadmin_protection_role_update_admin_service():
    from src.services.admin.admin import change_user_role
    from src.db.users import User, APITokenUser

    token_user = APITokenUser(
        id=1,
        org_id=1,
        user_uuid="apitoken_1",
        username="token",
    )

    target_user = User(
        id=1,
        user_uuid="user_root",
        username="admin",
        first_name="Admin",
        last_name="SuperAdmin",
        email="admin@stjosephsplacements.in",
        is_superadmin=True,
        password_hash="hash",
    )

    mock_db = AsyncMock()

    with patch("src.services.admin.admin._get_user_in_org", new=AsyncMock(return_value=target_user)):
        with pytest.raises(HTTPException) as exc_info:
            await change_user_role(
                token_user=token_user,
                user_id=1,
                new_role_id=2,
                db_session=mock_db,
            )
        assert exc_info.value.status_code == 403
        assert "The role of the root SuperAdmin account (admin@stjosephsplacements.in) is protected and cannot be changed." in exc_info.value.detail


@pytest.mark.asyncio
async def test_superadmin_protection_removal_admin_service():
    from src.services.admin.admin import remove_user_from_org_admin
    from src.db.users import User, APITokenUser

    token_user = APITokenUser(
        id=1,
        org_id=1,
        user_uuid="apitoken_1",
        username="token",
    )

    target_user = User(
        id=1,
        user_uuid="user_root",
        username="admin",
        first_name="Admin",
        last_name="SuperAdmin",
        email="admin@stjosephsplacements.in",
        is_superadmin=True,
        password_hash="hash",
    )

    mock_db = AsyncMock()

    with patch("src.services.admin.admin._get_user_in_org", new=AsyncMock(return_value=target_user)):
        with pytest.raises(HTTPException) as exc_info:
            await remove_user_from_org_admin(
                token_user=token_user,
                user_id=1,
                db_session=mock_db,
            )
        assert exc_info.value.status_code == 403
        assert "The root SuperAdmin account (admin@stjosephsplacements.in) is protected and cannot be removed from organizations." in exc_info.value.detail
