from fastapi import Depends, APIRouter, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from src.services.health.health import check_health
from src.services.monitoring.metrics import get_prometheus_metrics
from src.core.events.database import get_db_session


router = APIRouter()

@router.get(
    "",
    summary="Health check",
    description="Returns the overall health of the service and its dependencies (e.g. database connectivity).",
    responses={
        200: {"description": "Service is healthy; includes per-dependency status."},
    },
)
async def health(db_session: AsyncSession = Depends(get_db_session)):
    return await check_health(db_session)


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Exposes application and platform health metrics in Prometheus exposition format.",
    responses={
        200: {
            "description": "Prometheus text format metrics",
            "content": {"text/plain": {}},
        },
    },
)
async def metrics(db_session: AsyncSession = Depends(get_db_session)):
    content = await get_prometheus_metrics(db_session)
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")