"""OpenEduCat integration endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional

from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.services.integrations.openeducat import (
    check_openeducat_health,
    sync_student_to_openeducat,
    sync_course_completion_to_openeducat,
)

router = APIRouter(prefix="/openeducat", tags=["integrations", "openeducat"])


class OpenEduCatStudentSyncRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str = ""
    mobile_no: Optional[str] = None
    register_number: Optional[str] = None
    department: Optional[str] = None
    degree: Optional[str] = None
    batch: Optional[str] = None
    cgpa: Optional[float] = None


class OpenEduCatCourseCompletionSyncRequest(BaseModel):
    student_email: EmailStr
    course_name: str
    completion_date: str
    certificate_url: Optional[str] = None
    register_number: Optional[str] = None


@router.get(
    "/status",
    summary="OpenEduCat integration status",
    description="Checks the health, server version, and connectivity to St. Joseph's OpenEduCat ERP instance.",
)
async def api_openeducat_status():
    return await check_openeducat_health()


@router.post(
    "/sync_student",
    summary="Sync student to OpenEduCat",
    description="Syncs a student profile and enrollment to OpenEduCat.",
)
async def api_sync_student(
    payload: OpenEduCatStudentSyncRequest,
    current_user: PublicUser = Depends(get_current_user),
):
    return await sync_student_to_openeducat(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        mobile_no=payload.mobile_no,
        register_number=payload.register_number,
        department=payload.department,
        degree=payload.degree,
        batch=payload.batch,
        cgpa=payload.cgpa,
    )


@router.post(
    "/sync_completion",
    summary="Sync course completion to OpenEduCat",
    description="Records a course completion event in student's OpenEduCat timeline.",
)
async def api_sync_completion(
    payload: OpenEduCatCourseCompletionSyncRequest,
    current_user: PublicUser = Depends(get_current_user),
):
    return await sync_course_completion_to_openeducat(
        student_email=payload.student_email,
        course_name=payload.course_name,
        completion_date=payload.completion_date,
        certificate_url=payload.certificate_url,
        register_number=payload.register_number,
    )
