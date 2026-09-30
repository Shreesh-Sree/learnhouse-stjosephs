from fastapi import APIRouter
from src.core.deployment_mode import get_deployment_mode
from src.routers.audit_logs import router as audit_logs_router

router = APIRouter()

router.include_router(audit_logs_router, prefix="/audit_logs", tags=["audit_logs"])


@router.get("/status", tags=["ee"])
async def get_ee_status():
    """Return status and active enterprise-grade features."""
    mode = get_deployment_mode()
    all_features = [
        "audit_logs",
        "sso",
        "scorm",
        "advanced_analytics",
        "custom_domains",
        "white_label",
        "custom_roles",
        "webhooks",
        "api_tokens",
        "lti",
        "certifications",
        "collaboration",
        "code_execution",
        "ai_tutor",
    ]
    return {
        "status": "active",
        "enabled": True,
        "edition": mode,
        "features": all_features if mode == "ee" else ["audit_logs", "sso", "scorm"],
    }
