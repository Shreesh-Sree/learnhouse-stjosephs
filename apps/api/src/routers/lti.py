"""LTI 1.1 tool-provider endpoints.

- ``POST /lti/launch/{link_uuid}`` — the public launch endpoint an external
  LMS's LTI tool config points at. Deliberately carries NO auth dependency,
  same rationale as ``routers/calendar.py``: the caller is a *different
  server* (or a browser inside that server's iframe) presenting an OAuth
  1.0a-signed form POST, not a LearnHouse session.
- The remaining routes are ordinary authenticated course-admin endpoints for
  creating/listing/revoking a course's LTI links, mounted under
  ``/courses/{course_uuid}/lti_links`` to mirror the roster-import endpoints.
"""

from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from config.config import get_learnhouse_config
from src.core.events.database import get_db_session
from src.db.lti import LTILinkCreate, LTILinkCreatedResponse, LTILinkRead
from src.db.users import PublicUser
from src.security.auth import JWT_COOKIE_NAME, JWT_REFRESH_COOKIE_NAME, get_current_user
from src.services.lti.lti import (
    LTILaunchError,
    create_lti_link,
    get_lti_links_for_course,
    handle_lti_launch,
    revoke_lti_link,
)

router = APIRouter()


def _launch_error_page(reason: str) -> HTMLResponse:
    # A plain, dependency-free error page: this response has to render
    # meaningfully inside whatever iframe/window the external LMS opened for
    # the launch, which may not run LearnHouse's own frontend JS at all.
    safe_reason = (
        reason.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>LTI launch failed</title></head><body style="
            "\"font-family: sans-serif; max-width: 32rem; margin: 3rem auto; color: #333;\">"
            f"<h2>This link couldn&rsquo;t be opened</h2><p>{safe_reason}</p></body></html>"
        ),
        status_code=400,
    )


@router.post(
    "/launch/{link_uuid}",
    summary="LTI 1.1 tool-provider launch",
    description=(
        "Entry point an external LMS's LTI 1.1 tool configuration POSTs to. "
        "Verifies the OAuth 1.0a launch signature, resolves or provisions the "
        "corresponding LearnHouse account, enrolls it in the link's course, "
        "and redirects the browser to the course page with a new session."
    ),
    responses={
        302: {"description": "Signature verified; redirecting to the course with a new session"},
        400: {"description": "Launch rejected (bad signature, expired, unsupported message type, ...)"},
        404: {"description": "Unknown or revoked link"},
        409: {"description": "Target account requires a second factor this launch cannot satisfy"},
    },
)
async def api_lti_launch(
    request: Request,
    link_uuid: str,
    db_session: AsyncSession = Depends(get_db_session),
):
    form = await request.form()
    form_params = {k: str(v) for k, v in form.items()}

    # The exact URL the consumer signed — scheme + host + path, no query
    # string (LTI launches never carry one) and no fragment. Built from the
    # incoming request itself, not from any config-derived guess, since the
    # signature is only valid against whatever URL the external LMS actually
    # POSTed to.
    launch_url = str(request.url).split("?")[0]

    try:
        user, course, org, access_token, refresh_token = await handle_lti_launch(
            request, link_uuid, form_params, launch_url, db_session
        )
    except LTILaunchError as e:
        return _launch_error_page(e.reason)

    config = get_learnhouse_config()
    scheme = "https" if config.hosting_config.ssl else "http"
    redirect_url = f"{scheme}://{config.hosting_config.frontend_domain}/orgs/{org.slug}/course/{course.course_uuid}"

    response = RedirectResponse(url=redirect_url, status_code=302)

    # SameSite=None (not the app's usual "lax") is structurally required here:
    # the browser that needs these cookies is landing on this redirect FROM a
    # cross-site POST the external LMS's page/iframe submitted, so a "lax"
    # cookie would simply not be sent back on the very next request. This is
    # the same trade-off every LTI-embedding tool provider makes — the launch
    # is already authenticated by the OAuth-signed POST before any cookie is
    # set, so SameSite=None does not open a new forgery surface (there is no
    # state-changing action an attacker could trigger by forcing this
    # redirect; they would need the consumer secret to produce a valid
    # signature in the first place).
    is_secure = scheme == "https"
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="none" if is_secure else "lax",
        max_age=int(timedelta(hours=8).total_seconds()),
    )
    response.set_cookie(
        key=JWT_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="none" if is_secure else "lax",
        max_age=int(timedelta(days=30).total_seconds()),
    )
    return response


@router.post(
    "/courses/{course_uuid}/lti_links",
    response_model=LTILinkCreatedResponse,
    summary="Create an LTI link for a course",
    description=(
        "Creates a new LTI 1.1 tool-provider credential (consumer key + secret) "
        "bound to this course. The secret is returned only once; paste the "
        "launch_url, consumer_key and consumer_secret into the external LMS's "
        "LTI tool configuration."
    ),
)
async def api_create_lti_link(
    request: Request,
    course_uuid: str,
    link_create: LTILinkCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> LTILinkCreatedResponse:
    return await create_lti_link(request, course_uuid, link_create, current_user, db_session)


@router.get(
    "/courses/{course_uuid}/lti_links",
    response_model=List[LTILinkRead],
    summary="List a course's LTI links",
)
async def api_list_lti_links(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> List[LTILinkRead]:
    return await get_lti_links_for_course(request, course_uuid, current_user, db_session)


@router.delete(
    "/courses/{course_uuid}/lti_links/{link_uuid}",
    summary="Revoke an LTI link",
    description="Deactivates the link; existing provisioned accounts are unaffected, but the launch URL stops working.",
)
async def api_revoke_lti_link(
    request: Request,
    course_uuid: str,
    link_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await revoke_lti_link(request, course_uuid, link_uuid, current_user, db_session)
