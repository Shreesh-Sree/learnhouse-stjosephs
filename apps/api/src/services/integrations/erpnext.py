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
ERPNEXT_URL = os.environ.get("LEARNHOUSE_ERPNEXT_URL", "https://erp.stjosephsplacements.in").rstrip("/")
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
    register_number: Optional[str] = None,
    department: Optional[str] = None,
    cgpa: Optional[float] = None,
) -> Dict[str, Any]:
    """Sync student profile to ERPNext Placement Student dossier."""
    if not ERPNEXT_ENABLED:
        return {"success": False, "detail": "ERPNext integration disabled"}

    reg_no = register_number or email.split("@")[0].upper()
    name = f"{first_name} {last_name}".strip() or email

    payload = {
        "register_number": reg_no,
        "student_name": name,
        "college_email": email,
        "department": department or "CSE",
        "degree": "B.E.",
        "batch": "2022-2026",
        "cgpa": cgpa or 7.50,
        "active_arrears": 0,
        "mobile_no": mobile_no or "",
        "placement_status": "Eligible",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=False) as client:
            headers = _get_auth_headers()
            resp = await client.post(
                f"{ERPNEXT_URL}/api/resource/Placement%20Student",
                json=payload,
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return {"success": True, "data": resp.json()}
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
    register_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Record course completion & LMS training verification in ERPNext Placement Student record."""
    if not ERPNEXT_ENABLED:
        return {"success": False, "detail": "ERPNext integration disabled"}

    reg_no = register_number or student_email.split("@")[0].upper()

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=False) as client:
            headers = _get_auth_headers()
            # Update the student's training_completed flag and append completed course
            payload = {
                "training_completed": 1,
                "lms_completed_courses": f"{course_name} (Completed: {completion_date})",
            }
            resp = await client.put(
                f"{ERPNEXT_URL}/api/resource/Placement%20Student/{reg_no}",
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
