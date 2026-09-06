from fastapi import APIRouter, Depends, Request, Response, UploadFile
from src.core.events.database import get_db_session
from src.db.courses.scorm import ScormResultRow, ScormTrackingDataRead, ScormTrackingDataUpdate
from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.services.courses.activities.scorm import (
    delete_scorm_package,
    get_scorm_tracking,
    list_scorm_results,
    serve_scorm_file,
    upload_scorm_package,
    upsert_scorm_tracking,
)

router = APIRouter()


@router.post(
    "/{activity_uuid}/package",
    summary="Upload a SCORM 1.2 package",
    description=(
        "Instructor-only. Extracts a SCORM 1.2 .zip package, parses its "
        "imsmanifest.xml, and points the activity at the resolved entry "
        "point. Replaces any package previously uploaded for this activity."
    ),
    responses={
        200: {"description": "Package uploaded and activity updated."},
        400: {"description": "Invalid SCORM package (bad zip, missing/unreadable manifest, SCORM 2004, no launchable content)"},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this activity"},
        404: {"description": "Activity not found"},
        413: {"description": "Package exceeds the maximum upload size"},
        415: {"description": "Uploaded file is not a ZIP"},
    },
)
async def api_upload_scorm_package(
    request: Request,
    activity_uuid: str,
    scorm_file: UploadFile,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    activity = await upload_scorm_package(request, activity_uuid, scorm_file, current_user, db_session)
    return {"success": True, "content": activity.content}


@router.delete(
    "/{activity_uuid}/package",
    summary="Remove an uploaded SCORM package",
    description="Instructor-only. Deletes the extracted package's storage and clears the activity's SCORM content fields. Existing learner tracking rows are kept.",
    responses={
        200: {"description": "Package removed."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this activity"},
        404: {"description": "Activity not found"},
    },
)
async def api_delete_scorm_package(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    activity = await delete_scorm_package(request, activity_uuid, current_user, db_session)
    return {"success": True, "content": activity.content}


@router.get(
    "/{activity_uuid}/results",
    response_model=list[ScormResultRow],
    summary="List every learner's SCORM tracking state",
    description="Instructor-only. One row per learner who has started this activity — status, score, time spent.",
    responses={
        200: {"description": "Results rows.", "model": list[ScormResultRow]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this activity's results"},
        404: {"description": "Activity not found"},
    },
)
async def api_list_scorm_results(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> list[ScormResultRow]:
    return await list_scorm_results(request, activity_uuid, current_user, db_session)


@router.get(
    "/{activity_uuid}/content/{file_path:path}",
    summary="Serve a file from an uploaded SCORM package",
    description="Streams one file out of the activity's extracted SCORM package by its relative path (e.g. index.html, scormcontent/data.js).",
    responses={
        200: {"description": "File bytes."},
        400: {"description": "Invalid file path"},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this activity"},
        404: {"description": "Activity, or the requested file within its package, not found"},
    },
)
async def api_serve_scorm_file(
    request: Request,
    activity_uuid: str,
    file_path: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> Response:
    return await serve_scorm_file(request, activity_uuid, file_path, current_user, db_session)


@router.get(
    "/{activity_uuid}/tracking",
    response_model=ScormTrackingDataRead,
    summary="Get this user's SCORM tracking state",
    description="The current user's cmi.core state for this activity — used by the player's SCORM API shim on LMSInitialize/LMSGetValue to resume where the learner left off.",
    responses={
        200: {"description": "Tracking data (defaults if the learner hasn't started yet).", "model": ScormTrackingDataRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this activity"},
        404: {"description": "Activity not found"},
    },
)
async def api_get_scorm_tracking(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> ScormTrackingDataRead:
    return await get_scorm_tracking(request, activity_uuid, current_user, db_session)


@router.put(
    "/{activity_uuid}/tracking",
    response_model=ScormTrackingDataRead,
    summary="Update this user's SCORM tracking state",
    description="Applied on every LMSCommit/LMSFinish from the player's SCORM API shim. A completing lesson_status (completed/passed) also marks the activity done in the course trail.",
    responses={
        200: {"description": "Updated tracking data.", "model": ScormTrackingDataRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this activity"},
        404: {"description": "Activity not found"},
    },
)
async def api_update_scorm_tracking(
    request: Request,
    activity_uuid: str,
    tracking_update: ScormTrackingDataUpdate,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> ScormTrackingDataRead:
    return await upsert_scorm_tracking(request, activity_uuid, tracking_update, current_user, db_session)
