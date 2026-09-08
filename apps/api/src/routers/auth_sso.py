"""SSO (OpenID Connect) endpoints.

Mounted under ``/auth`` (see router.py), so these paths are
``/api/v1/auth/sso/...`` — exactly what apps/web/services/auth/sso.ts (an
already-existing frontend client, written against this contract before this
backend existed) calls. See src/db/sso.py for the scope decision.

Two trust levels, deliberately not a single router-level dependency:
- ``/sso/providers`` and ``/sso/{org_id}/config`` (+ setup-url): admin-only,
  gated by ``require_org_admin`` per route.
- ``/sso/check``, ``/sso/authorize``, ``/sso/callback``: public — the caller
  is either an anonymous visitor on the login page or the IdP's own redirect,
  neither of which carries a LearnHouse session.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.sso import SSOConfigCreate, SSOConfigRead, SSOConfigUpdate, SSOProviderInfo
from src.security.auth import JWT_COOKIE_NAME, JWT_REFRESH_COOKIE_NAME
from src.security.features_utils.dependencies import require_org_admin, require_org_admin_query
from src.services.auth.sso_oidc import (
    SSOFlowError,
    build_authorization_url,
    check_sso_enabled,
    create_sso_config,
    delete_sso_config,
    get_org_sso_config,
    get_provider_catalog,
    handle_sso_callback,
    update_sso_config,
)
from config.config import get_learnhouse_config

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin (require_org_admin)
# ---------------------------------------------------------------------------


@router.get("/sso/providers", response_model=List[SSOProviderInfo])
async def api_sso_providers(_admin: bool = Depends(require_org_admin_query)):
    return get_provider_catalog()


@router.get("/sso/{org_id}/config", response_model=Optional[SSOConfigRead])
async def api_get_sso_config(
    org_id: int,
    _admin: bool = Depends(require_org_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    from fastapi import HTTPException
    config = await get_org_sso_config(org_id, db_session)
    if config is None:
        raise HTTPException(status_code=404, detail="No SSO configuration for this organization")
    return config


@router.post("/sso/{org_id}/config", response_model=SSOConfigRead)
async def api_create_sso_config(
    org_id: int,
    data: SSOConfigCreate,
    _admin: bool = Depends(require_org_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    return await create_sso_config(org_id, data, db_session)


@router.put("/sso/{org_id}/config", response_model=SSOConfigRead)
async def api_update_sso_config(
    org_id: int,
    data: SSOConfigUpdate,
    _admin: bool = Depends(require_org_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    return await update_sso_config(org_id, data, db_session)


@router.delete("/sso/{org_id}/config")
async def api_delete_sso_config(
    org_id: int,
    _admin: bool = Depends(require_org_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    await delete_sso_config(org_id, db_session)
    return {"detail": "SSO configuration deleted"}


@router.get("/sso/{org_id}/setup-url")
async def api_sso_setup_url(
    org_id: int,
    return_url: str = Query(...),
    _admin: bool = Depends(require_org_admin),
):
    # Only WorkOS has a hosted admin-portal concept; not implemented here.
    # 404 so the frontend's own "don't throw, just hide the button" handling
    # (getSetupUrl) applies with no special-casing needed.
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="No setup portal for this provider")


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@router.get("/sso/check")
async def api_sso_check(
    org_slug: str = Query(...),
    db_session: AsyncSession = Depends(get_db_session),
):
    return await check_sso_enabled(org_slug, db_session)


@router.get("/sso/authorize")
async def api_sso_authorize(
    org_slug: str = Query(...),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        return await build_authorization_url(org_slug, db_session)
    except SSOFlowError as exc:
        raise exc.to_http_exception()


@router.get("/sso/callback")
async def api_sso_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Redirects the browser straight to the org, with session cookies set —
    matching the LTI launch redirect pattern (routers/lti.py) rather than
    returning JSON, since this endpoint is reached by the IdP's own
    redirect, not an XHR the frontend's handleSSOCallback fetch() controls."""
    try:
        result = await handle_sso_callback(request, code, state, db_session)
    except SSOFlowError as exc:
        raise exc.to_http_exception()

    config = get_learnhouse_config()
    is_secure = config.hosting_config.ssl
    response = RedirectResponse(url=result.redirect_url, status_code=302)
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=result.access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=int(60 * 60 * 8),
    )
    response.set_cookie(
        key=JWT_REFRESH_COOKIE_NAME,
        value=result.refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=int(60 * 60 * 24 * 30),
    )
    return response
