"""ERPNext integration endpoints."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional

from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.services.integrations.erpnext import (
    check_erpnext_health,
    sync_student_to_erpnext,
    sync_course_completion_to_erpnext,
)

router = APIRouter(prefix="/erpnext", tags=["integrations", "erpnext"])


class StudentSyncRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str = ""
    mobile_no: Optional[str] = None


class CourseCompletionSyncRequest(BaseModel):
    student_email: EmailStr
    course_name: str
    completion_date: str
    certificate_url: Optional[str] = None


@router.get(
    "/status",
    summary="ERPNext integration status",
    description="Checks the health and connectivity to the St. Joseph's ERPNext instance.",
)
async def api_erpnext_status():
    return await check_erpnext_health()


@router.post(
    "/sync_student",
    summary="Sync student to ERPNext",
    description="Syncs a student account from LearnHouse to ERPNext.",
)
async def api_sync_student(
    payload: StudentSyncRequest,
    current_user: PublicUser = Depends(get_current_user),
):
    return await sync_student_to_erpnext(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        mobile_no=payload.mobile_no,
    )


@router.post(
    "/sync_completion",
    summary="Sync course completion to ERPNext",
    description="Records a course completion event in ERPNext.",
)
async def api_sync_completion(
    payload: CourseCompletionSyncRequest,
    current_user: PublicUser = Depends(get_current_user),
):
    return await sync_course_completion_to_erpnext(
        student_email=payload.student_email,
        course_name=payload.course_name,
        completion_date=payload.completion_date,
        certificate_url=payload.certificate_url,
    )
