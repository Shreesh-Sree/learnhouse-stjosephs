"""OpenEduCat College ERP integration bridge for St. Joseph's Group of Institutions.

Syncs students, academic courses, batches, and course completions
between LearnHouse LMS and OpenEduCat (Odoo 17) via JSON-RPC.
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

OPENEDUCAT_ENABLED = os.environ.get("LEARNHOUSE_OPENEDUCAT_ENABLED", "True").lower() in ("true", "1", "yes")
OPENEDUCAT_URL = os.environ.get("LEARNHOUSE_OPENEDUCAT_URL", "https://erp.stjosephsplacements.in").rstrip("/")
OPENEDUCAT_DB = os.environ.get("LEARNHOUSE_OPENEDUCAT_DB", "openeducat")
OPENEDUCAT_USER = os.environ.get("LEARNHOUSE_OPENEDUCAT_USER", "admin")
OPENEDUCAT_PASSWORD = os.environ.get("LEARNHOUSE_OPENEDUCAT_PASSWORD", "Admin@StJosephs2026!")

# Department to Course Code Mapping
DEPT_COURSE_MAP = {
    "CSE": "BE-CSE",
    "CS": "BE-CSE",
    "IT": "BTECH-IT",
    "AIDS": "BTECH-AIDS",
    "AI&DS": "BTECH-AIDS",
    "AI-DS": "BTECH-AIDS",
    "ADS": "BTECH-AIDS",
    "ECE": "BE-ECE",
    "EEE": "BE-EEE",
    "MECH": "BE-MECH",
    "ME": "BE-MECH",
}


async def _jsonrpc_call(service: str, method: str, *args, timeout: float = 8.0) -> Any:
    """Execute a low-level Odoo JSON-RPC call."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": service,
            "method": method,
            "args": list(args),
        },
        "id": 1,
    }
    endpoint = f"{OPENEDUCAT_URL}/jsonrpc"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
        resp = await client.post(endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            error_msg = data["error"].get("data", {}).get("message") or data["error"].get("message")
            raise RuntimeError(f"OpenEduCat JSON-RPC error: {error_msg}")
        return data.get("result")


async def authenticate_openeducat() -> Optional[int]:
    """Authenticate with OpenEduCat and return the authenticated user ID."""
    uid = await _jsonrpc_call(
        "common",
        "authenticate",
        OPENEDUCAT_DB,
        OPENEDUCAT_USER,
        OPENEDUCAT_PASSWORD,
        {},
    )
    if not uid:
        logger.error("Authentication to OpenEduCat failed for user %s on db %s", OPENEDUCAT_USER, OPENEDUCAT_DB)
        return None
    return uid


async def check_openeducat_health() -> Dict[str, Any]:
    """Check connectivity, server version, and authentication against OpenEduCat."""
    if not OPENEDUCAT_ENABLED:
        return {"enabled": False, "connected": False, "detail": "OpenEduCat integration disabled"}

    start = time.perf_counter()
    try:
        # Check server version
        version_info = await _jsonrpc_call("common", "version", timeout=4.0)
        # Verify authentication
        uid = await authenticate_openeducat()
        latency = round((time.perf_counter() - start) * 1000, 1)

        if uid:
            return {
                "enabled": True,
                "connected": True,
                "authenticated": True,
                "uid": uid,
                "server_version": version_info.get("server_version", "17.0"),
                "latency_ms": latency,
                "url": OPENEDUCAT_URL,
                "database": OPENEDUCAT_DB,
            }
        else:
            return {
                "enabled": True,
                "connected": True,
                "authenticated": False,
                "latency_ms": latency,
                "url": OPENEDUCAT_URL,
                "error": "Authentication failed",
            }
    except Exception as e:
        logger.debug("OpenEduCat health check failed: %s", e)
        return {
            "enabled": True,
            "connected": False,
            "error": str(e),
            "url": OPENEDUCAT_URL,
        }


async def sync_student_to_openeducat(
    email: str,
    first_name: str,
    last_name: str = "",
    mobile_no: Optional[str] = None,
    register_number: Optional[str] = None,
    department: Optional[str] = None,
    degree: Optional[str] = None,
    batch: Optional[str] = None,
    cgpa: Optional[float] = None,
) -> Dict[str, Any]:
    """Provision or update a student record in OpenEduCat (`op.student` and `op.student.course`)."""
    if not OPENEDUCAT_ENABLED:
        return {"success": False, "detail": "OpenEduCat integration disabled"}

    reg_no = (register_number or email.split("@")[0]).strip()
    full_name = f"{first_name} {last_name}".strip() or email
    clean_email = email.strip().lower()
    clean_mobile = (mobile_no or "").strip()

    dept_norm = (department or "CSE").strip().upper()
    course_code = DEPT_COURSE_MAP.get(dept_norm, "BE-CSE")
    batch_code = f"{course_code}-2026"

    try:
        uid = await authenticate_openeducat()
        if not uid:
            return {"success": False, "error": "OpenEduCat authentication failed"}

        # 1. Check if student exists by registration number or email
        existing_students: List[Dict] = await _jsonrpc_call(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.student",
            "search_read",
            [["|", ("gr_no", "=", reg_no), ("email", "=", clean_email)]],
            {"fields": ["id", "name", "gr_no", "email"]},
        )

        if existing_students:
            student_id = existing_students[0]["id"]
            update_vals = {
                "name": full_name,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "email": clean_email,
            }
            if clean_mobile:
                update_vals["mobile"] = clean_mobile
            if reg_no and not existing_students[0].get("gr_no"):
                update_vals["gr_no"] = reg_no

            await _jsonrpc_call(
                "object",
                "execute_kw",
                OPENEDUCAT_DB,
                uid,
                OPENEDUCAT_PASSWORD,
                "op.student",
                "write",
                [[student_id], update_vals],
            )
            action = "updated"
        else:
            student_vals = {
                "name": full_name,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "gr_no": reg_no,
                "email": clean_email,
                "gender": "m",
            }
            if clean_mobile:
                student_vals["mobile"] = clean_mobile

            student_id = await _jsonrpc_call(
                "object",
                "execute_kw",
                OPENEDUCAT_DB,
                uid,
                OPENEDUCAT_PASSWORD,
                "op.student",
                "create",
                [student_vals],
            )
            action = "created"

        # 2. Check and link student to Course and Batch
        courses: List[Dict] = await _jsonrpc_call(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.course",
            "search_read",
            [[("code", "=", course_code)]],
            {"fields": ["id", "name"]},
        )
        course_id = courses[0]["id"] if courses else None

        batch_records: List[Dict] = await _jsonrpc_call(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.batch",
            "search_read",
            [[("code", "=", batch_code)]],
            {"fields": ["id", "name"]},
        )
        batch_id = batch_records[0]["id"] if batch_records else None

        if course_id:
            existing_enrollments: List[Dict] = await _jsonrpc_call(
                "object",
                "execute_kw",
                OPENEDUCAT_DB,
                uid,
                OPENEDUCAT_PASSWORD,
                "op.student.course",
                "search_read",
                [[("student_id", "=", student_id), ("course_id", "=", course_id)]],
                {"fields": ["id"]},
            )

            if not existing_enrollments:
                enrollment_vals = {
                    "student_id": student_id,
                    "course_id": course_id,
                    "roll_number": reg_no,
                }
                if batch_id:
                    enrollment_vals["batch_id"] = batch_id

                await _jsonrpc_call(
                    "object",
                    "execute_kw",
                    OPENEDUCAT_DB,
                    uid,
                    OPENEDUCAT_PASSWORD,
                    "op.student.course",
                    "create",
                    [enrollment_vals],
                )

        logger.info("Successfully %s student in OpenEduCat: %s (ID %s)", action, full_name, student_id)
        return {
            "success": True,
            "action": action,
            "student_id": student_id,
            "course_code": course_code,
            "register_number": reg_no,
        }

    except Exception as e:
        logger.error("Failed syncing student %s (%s) to OpenEduCat: %s", full_name, reg_no, e)
        return {"success": False, "error": str(e)}


async def sync_course_completion_to_openeducat(
    student_email: str,
    course_name: str,
    completion_date: str,
    certificate_url: Optional[str] = None,
    register_number: Optional[str] = None,
) -> Dict[str, Any]:
    """Record course completion or training progress into student's OpenEduCat profile."""
    if not OPENEDUCAT_ENABLED:
        return {"success": False, "detail": "OpenEduCat integration disabled"}

    reg_no = register_number or student_email.split("@")[0]

    try:
        uid = await authenticate_openeducat()
        if not uid:
            return {"success": False, "error": "OpenEduCat authentication failed"}

        students: List[Dict] = await _jsonrpc_call(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "op.student",
            "search_read",
            [["|", ("gr_no", "=", reg_no), ("email", "=", student_email.strip().lower())]],
            {"fields": ["id", "name"]},
        )

        if not students:
            return {"success": False, "error": f"Student not found in OpenEduCat for {student_email}"}

        student_id = students[0]["id"]
        # Log completion event note on student
        log_message = (
            f"LMS Course Completed: {course_name} on {completion_date}."
            + (f" Certificate: {certificate_url}" if certificate_url else "")
        )

        await _jsonrpc_call(
            "object",
            "execute_kw",
            OPENEDUCAT_DB,
            uid,
            OPENEDUCAT_PASSWORD,
            "mail.message",
            "create",
            [{
                "model": "op.student",
                "res_id": student_id,
                "body": f"<p>{log_message}</p>",
                "message_type": "comment",
                "subtype_id": 1,
            }],
        )

        return {
            "success": True,
            "student_id": student_id,
            "logged_event": log_message,
        }

    except Exception as e:
        logger.error("OpenEduCat course completion sync failed for %s: %s", student_email, e)
        return {"success": False, "error": str(e)}
