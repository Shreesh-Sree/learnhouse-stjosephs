from fastapi import APIRouter
from src.routers.audit_logs import router as audit_logs_router

router = APIRouter()

router.include_router(audit_logs_router, prefix="/audit_logs", tags=["audit_logs"])


@router.get("/status", tags=["ee"])
async def get_ee_status():
    """Return status and active enterprise-grade features in OSS mode."""
    return {
        "status": "active",
        "enabled": True,
        "edition": "oss",
        "features": ["audit_logs", "sso", "scorm"],
    }
