from fastapi import APIRouter, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import Depends

from src.core.events.database import get_db_session
from src.services.users.calendar_feed import build_ics_feed

# Deliberately no auth dependency anywhere in this router — see
# services.users.calendar_feed's module docstring for why: a calendar
# client subscribes to this URL and polls it unauthenticated on its own
# schedule, so the opaque token in the path is the only credential this
# endpoint can rely on.
router = APIRouter()


@router.get(
    "/feed/{token}.ics",
    summary="ICS feed of a student's assignment due dates",
    description=(
        "Subscribable calendar feed, authenticated by the opaque token in "
        "the path rather than a session — see GET /users/me/calendar_feed_token "
        "to obtain your own token."
    ),
    responses={
        200: {"description": "iCalendar (.ics) feed.", "content": {"text/calendar": {}}},
        404: {"description": "Unknown or revoked token"},
    },
)
async def api_calendar_feed(
    token: str,
    db_session: AsyncSession = Depends(get_db_session),
) -> Response:
    body = await build_ics_feed(token, db_session)
    return Response(content=body, media_type="text/calendar; charset=utf-8")
