"""ERPNext integration bridge for St. Joseph's Placements & Training Cell.

Syncs students, enrollments, assessment scores, and course completions
between LearnHouse LMS and ERPNext (Frappe v15).
"""

import os
import time
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

ERPNEXT_ENABLED = os.environ.get("LEARNHOUSE_ERPNEXT_ENABLED", "True").lower() in ("true", "1", "yes")
ERPNEXT_URL = os.environ.get("LEARNHOUSE_ERPNEXT_URL", "http://erp.stjosephsplacements.in").rstrip("/")
ERPNEXT_API_KEY = os.environ.get("LEARNHOUSE_ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = os.environ.get("LEARNHOUSE_ERPNEXT_API_SECRET", "")


def _get_auth_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if ERPNEXT_API_KEY and ERPNEXT_API_SECRET:
        headers["Authorization"] = f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}"
    return headers


async def check_erpnext_health() -> Dict[str, Any]:
    """Check connectivity and response time to the ERPNext server."""
    if not ERPNEXT_ENABLED:
        return {"enabled": False, "connected": False, "detail": "ERPNext integration disabled"}

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(f"{ERPNEXT_URL}/api/method/frappe.ping")
            latency = round((time.perf_counter() - start) * 1000, 1)
            connected = resp.status_code in (200, 301, 302, 401, 403)
            return {
                "enabled": True,
                "connected": connected,
                "status_code": resp.status_code,
                "latency_ms": latency,
                "url": ERPNEXT_URL,
            }
    except Exception as e:
        logger.debug("ERPNext health check failed: %s", e)
        return {
            "enabled": True,
            "connected": False,
            "error": str(e),
            "url": ERPNEXT_URL,
        }


async def sync_student_to_erpnext(
    email: str,
    first_name: str,
    last_name: str = "",
    mobile_no: Optional[str] = None,
) -> Dict[str, Any]:
    """Sync student profile to ERPNext Student / Contact record."""
    if not ERPNEXT_ENABLED:
        return {"success": False, "detail": "ERPNext integration disabled"}

    payload = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "mobile_no": mobile_no or "",
        "source": "LearnHouse LMS",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=False) as client:
            headers = _get_auth_headers()
            resp = await client.post(
                f"{ERPNEXT_URL}/api/resource/Student",
                json=payload,
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return {"success": True, "data": resp.json()}
            # If doc already exists or needs permission
            return {
                "success": False,
                "status_code": resp.status_code,
                "detail": resp.text[:200],
            }
    except Exception as e:
        logger.warning("Failed syncing student %s to ERPNext: %s", email, e)
        return {"success": False, "error": str(e)}


async def sync_course_completion_to_erpnext(
    student_email: str,
    course_name: str,
    completion_date: str,
    certificate_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Record course completion & certification event in ERPNext."""
    if not ERPNEXT_ENABLED:
        return {"success": False, "detail": "ERPNext integration disabled"}

    payload = {
        "student_email": student_email,
        "course_name": course_name,
        "completion_date": completion_date,
        "certificate_url": certificate_url or "",
        "status": "Completed",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=False) as client:
            headers = _get_auth_headers()
            # Post to generic doc event or custom training log
            resp = await client.post(
                f"{ERPNEXT_URL}/api/method/erpnext.sync_lms_completion",
                json=payload,
                headers=headers,
            )
            return {
                "success": resp.status_code in (200, 201),
                "status_code": resp.status_code,
            }
    except Exception as e:
        logger.debug("ERPNext completion sync failed: %s", e)
        return {"success": False, "error": str(e)}
