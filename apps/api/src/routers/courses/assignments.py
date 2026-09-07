from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile, HTTPException
from pydantic import BaseModel
from src.db.courses.assignments import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentTaskCreate,
    AssignmentTaskSubmissionUpdate,
    AssignmentTaskUpdate,
    AssignmentUpdate,
    AssignmentUserSubmissionCreate,
    AssignmentUserSubmissionRead,
)
from src.db.courses.proctoring import ProctoringSnapshotRead
from src.db.courses.assignment_groups import AssignmentGroupRead
from src.db.users import PublicUser
from src.core.events.database import get_db_session
from src.security.auth import get_current_user
from src.services.courses.activities.proctoring import (
    delete_proctoring_snapshots,
    list_proctoring_snapshots,
    serve_proctoring_snapshot,
    upload_proctoring_snapshot,
)
from src.services.courses.activities.assignment_groups import (
    create_group,
    instructor_delete_group,
    instructor_remove_member,
    join_group,
    leave_group,
    list_groups,
)
from src.services.courses.activities.assignments import (
    check_assignment_ip_allowlist_status,
    check_assignment_seb_status,
    create_assignment,
    create_assignment_submission,
    create_assignment_task,
    delete_assignment,
    delete_assignment_from_activity_uuid,
    delete_assignment_submission,
    delete_assignment_task,
    delete_assignment_solution_file,
    delete_assignment_task_submission,
    get_assignment_seb_config,
    get_assignments_from_course,
    get_grade_assignment_submission,
    grade_assignment_submission,
    grade_group_assignment,
    handle_assignment_task_submission,
    mark_activity_as_done_for_user,
    put_assignment_solution_file,
    put_assignment_task_reference_file,
    put_assignment_task_submission_file,
    read_assignment,
    read_assignment_from_activity_uuid,
    read_assignment_submissions,
    read_assignment_task,
    read_assignment_task_submissions,
    read_assignment_tasks,
    read_user_assignment_submissions,
    read_user_assignment_submissions_me,
    read_user_assignment_task_submissions,
    read_user_assignment_task_submissions_me,
    read_user_assignment_task_submissions_me_batch,
    retry_assignment_submission,
    start_assignment_attempt,
    submit_group_assignment,
    update_assignment,
    update_assignment_submission,
    update_assignment_task,
)


class GradeSubmissionBody(BaseModel):
    """Optional body for the final-grade endpoint. Lets the instructor leave
    an overall feedback note at the same time they finalize the grade."""

    overall_feedback: Optional[str] = None


router = APIRouter()

## ASSIGNMENTS ##


@router.post(
    "/",
    response_model=AssignmentRead,
    summary="Create assignment",
    description="Create a new assignment attached to an activity. The authenticated user must have permission to edit the parent course.",
    responses={
        200: {"description": "Assignment created and returned.", "model": AssignmentRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to create assignments in this course"},
        404: {"description": "Parent activity or course not found"},
    },
)
async def api_create_assignments(
    request: Request,
    assignment_object: AssignmentCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentRead:
    """
    Create new activity
    """
    return await create_assignment(request, assignment_object, current_user, db_session)


@router.get(
    "/{assignment_uuid}",
    response_model=AssignmentRead,
    summary="Get assignment",
    description="Read an assignment by its UUID.",
    responses={
        200: {"description": "Assignment returned.", "model": AssignmentRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_read_assignment(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentRead:
    """
    Read an assignment
    """
    return await read_assignment(request, assignment_uuid, current_user, db_session)


@router.get(
    "/activity/{activity_uuid}",
    response_model=AssignmentRead,
    summary="Get assignment by activity",
    description="Read the assignment attached to a given activity UUID.",
    responses={
        200: {"description": "Assignment returned.", "model": AssignmentRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Activity or assignment not found"},
    },
)
async def api_read_assignment_from_activity(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentRead:
    """
    Read an assignment
    """
    return await read_assignment_from_activity_uuid(
        request, activity_uuid, current_user, db_session
    )


@router.get(
    "/{assignment_uuid}/seb_status",
    summary="Check Safe Exam Browser status",
    description=(
        "Whether this request looks like it came from Safe Exam Browser. "
        "Always true when the assignment doesn't require it. Used by the "
        "student-facing gate, which can't read its own outgoing headers."
    ),
    responses={
        200: {"description": "SEB status for this request."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_check_assignment_seb_status(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> dict:
    seb_ok = await check_assignment_seb_status(
        request, assignment_uuid, current_user, db_session
    )
    return {"seb_ok": seb_ok}


@router.get(
    "/{assignment_uuid}/ip_allowlist_status",
    summary="Check IP allowlist status",
    description=(
        "Whether this request's resolved client IP is allowed to submit "
        "this assignment. Always true when the assignment doesn't require "
        "an allowlist. Also returns the resolved client IP so a blocked "
        "student can relay it to campus IT."
    ),
    responses={
        200: {"description": "IP allowlist status for this request."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_check_assignment_ip_allowlist_status(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> dict:
    allowed, client_ip = await check_assignment_ip_allowlist_status(
        request, assignment_uuid, current_user, db_session
    )
    return {"allowed": allowed, "client_ip": client_ip}


@router.get(
    "/{assignment_uuid}/seb_config",
    summary="Download Safe Exam Browser config",
    description=(
        "Instructor-only. Generates (or reuses) this assignment's Config Key "
        "and returns a downloadable .seb config file to distribute to exam "
        "machines."
    ),
    responses={
        200: {"description": ".seb config file.", "content": {"application/octet-stream": {}}},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_get_assignment_seb_config(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> Response:
    plist_bytes, filename = await get_assignment_seb_config(
        request, assignment_uuid, current_user, db_session
    )
    return Response(
        content=plist_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{assignment_uuid}/proctoring/snapshots",
    response_model=ProctoringSnapshotRead,
    summary="Upload a webcam proctoring snapshot",
    description=(
        "The current user uploads one webcam frame captured during their own "
        "attempt. Opportunistic only — nothing checks that these exist before "
        "allowing a submission; a student who declined the consent prompt "
        "simply never calls this."
    ),
    responses={
        200: {"description": "Snapshot stored.", "model": ProctoringSnapshotRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
        413: {"description": "Image exceeds the maximum upload size"},
    },
)
async def api_upload_proctoring_snapshot(
    request: Request,
    assignment_uuid: str,
    image_file: UploadFile,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> ProctoringSnapshotRead:
    return await upload_proctoring_snapshot(request, assignment_uuid, image_file, current_user, db_session)


@router.get(
    "/{assignment_uuid}/proctoring/snapshots/user/{user_id}",
    response_model=list[ProctoringSnapshotRead],
    summary="List a student's proctoring snapshots",
    description="Instructor-only. Every webcam snapshot captured for one student's attempt on this assignment.",
    responses={
        200: {"description": "Snapshot list.", "model": list[ProctoringSnapshotRead]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_list_proctoring_snapshots(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> list[ProctoringSnapshotRead]:
    return await list_proctoring_snapshots(request, assignment_uuid, user_id, current_user, db_session)


@router.delete(
    "/{assignment_uuid}/proctoring/snapshots/user/{user_id}",
    summary="Delete a student's proctoring snapshots",
    description="Instructor-only retention control. Permanently deletes every webcam snapshot captured for one student's attempt on this assignment.",
    responses={
        200: {"description": "Snapshots deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_delete_proctoring_snapshots(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    deleted_count = await delete_proctoring_snapshots(request, assignment_uuid, user_id, current_user, db_session)
    return {"success": True, "deleted_count": deleted_count}


@router.get(
    "/{assignment_uuid}/proctoring/snapshots/file/{snapshot_uuid}",
    summary="Serve a proctoring snapshot's image",
    description="Instructor-only. Streams one webcam snapshot's JPEG bytes.",
    responses={
        200: {"description": "Image bytes."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Snapshot not found"},
    },
)
async def api_serve_proctoring_snapshot(
    request: Request,
    assignment_uuid: str,
    snapshot_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> Response:
    return await serve_proctoring_snapshot(request, snapshot_uuid, current_user, db_session)


## ASSIGNMENT GROUPS ##


class CreateGroupBody(BaseModel):
    name: str


@router.post(
    "/{assignment_uuid}/groups",
    response_model=AssignmentGroupRead,
    summary="Create an assignment group",
    description="Create a new group for a group-submission assignment. A student is immediately its first member; an instructor can create an empty group for students to join.",
    responses={
        200: {"description": "Group created.", "model": AssignmentGroupRead},
        400: {"description": "Assignment doesn't use group submission, missing name, or already in a group"},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_create_group(
    request: Request,
    assignment_uuid: str,
    body: CreateGroupBody,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentGroupRead:
    return await create_group(request, assignment_uuid, body.name, current_user, db_session)


@router.get(
    "/{assignment_uuid}/groups",
    response_model=list[AssignmentGroupRead],
    summary="List assignment groups",
    description="Every group for this assignment. A student sees every group's name/size (to decide which to join) but member identities only for their own group; an instructor sees everything.",
    responses={
        200: {"description": "Group list.", "model": list[AssignmentGroupRead]},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_list_groups(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> list[AssignmentGroupRead]:
    return await list_groups(request, assignment_uuid, current_user, db_session)


@router.post(
    "/{assignment_uuid}/groups/{group_uuid}/join",
    response_model=AssignmentGroupRead,
    summary="Join an assignment group",
    description="Join a group for this assignment. Fails if you're already in a different group for it, or the group is full.",
    responses={
        200: {"description": "Group joined.", "model": AssignmentGroupRead},
        400: {"description": "Assignment doesn't use group submission, or already in a different group"},
        401: {"description": "Authentication required"},
        403: {"description": "Group is full"},
        404: {"description": "Assignment or group not found"},
    },
)
async def api_join_group(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentGroupRead:
    return await join_group(request, assignment_uuid, group_uuid, current_user, db_session)


@router.post(
    "/{assignment_uuid}/groups/{group_uuid}/leave",
    summary="Leave an assignment group",
    description="Leave a group you belong to for this assignment. The group is deleted automatically if you were its last member.",
    responses={
        200: {"description": "Left the group."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment, group, or membership not found"},
    },
)
async def api_leave_group(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    await leave_group(request, assignment_uuid, group_uuid, current_user, db_session)
    return {"success": True}


@router.delete(
    "/{assignment_uuid}/groups/{group_uuid}",
    summary="Delete an assignment group",
    description="Instructor-only. Deletes a group and every membership row in it.",
    responses={
        200: {"description": "Group deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment or group not found"},
    },
)
async def api_delete_group(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    await instructor_delete_group(request, assignment_uuid, group_uuid, current_user, db_session)
    return {"success": True}


@router.delete(
    "/{assignment_uuid}/groups/{group_uuid}/members/{user_id}",
    summary="Remove a member from an assignment group",
    description="Instructor-only. Removes one member from a group; deletes the group automatically if that was its last member.",
    responses={
        200: {"description": "Member removed."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment, group, or membership not found"},
    },
)
async def api_remove_group_member(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    await instructor_remove_member(request, assignment_uuid, group_uuid, user_id, current_user, db_session)
    return {"success": True}


@router.post(
    "/{assignment_uuid}/groups/{group_uuid}/submit",
    summary="Submit an assignment for the whole group",
    description="The caller must be a member of this group. Syncs the caller's current task answers onto every teammate's own row, then advances every member's own submission to SUBMITTED.",
    responses={
        200: {"description": "Group submission result (per-member success/skip list)."},
        400: {"description": "Assignment doesn't use group submission"},
        401: {"description": "Authentication required"},
        403: {"description": "Not a member of this group, or a submission-time gate (SEB/IP/time limit/deadline) failed"},
        404: {"description": "Assignment or group not found"},
    },
)
async def api_submit_group_assignment(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    return await submit_group_assignment(request, assignment_uuid, group_uuid, current_user, db_session)


@router.post(
    "/{assignment_uuid}/groups/{group_uuid}/grade",
    summary="Finalize the grade for a whole group",
    description="Instructor-only. Applies the same grade + optional overall feedback to every member of a group who has handed in an attempt; a member who hasn't is skipped and reported.",
    responses={
        200: {"description": "Group grading result (per-member grade + skip list)."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to grade this assignment"},
        404: {"description": "Assignment or group not found"},
    },
)
async def api_grade_group_assignment(
    request: Request,
    assignment_uuid: str,
    group_uuid: str,
    body: Optional[GradeSubmissionBody] = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    return await grade_group_assignment(
        request,
        assignment_uuid,
        group_uuid,
        current_user,
        db_session,
        overall_feedback=body.overall_feedback if body else None,
    )


@router.put(
    "/{assignment_uuid}",
    response_model=AssignmentRead,
    summary="Update assignment",
    description="Update an assignment by its UUID. The authenticated user must have permission to edit the parent course.",
    responses={
        200: {"description": "Assignment updated and returned.", "model": AssignmentRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to update this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_update_assignment(
    request: Request,
    assignment_uuid: str,
    assignment_object: AssignmentUpdate,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentRead:
    """
    Update an assignment
    """
    return await update_assignment(
        request, assignment_uuid, assignment_object, current_user, db_session
    )


@router.post(
    "/{assignment_uuid}/solution_file",
    response_model=AssignmentRead,
    summary="Upload the assignment model answer document",
    description=(
        "Upload or replace the model answer document for an assignment. "
        "Instructor only. The document is withheld from learners until the "
        "assignment's solution_reveal rule unlocks it."
    ),
    responses={
        200: {"description": "Solution file stored.", "model": AssignmentRead},
        400: {"description": "No solution file provided"},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_put_assignment_solution_file(
    request: Request,
    assignment_uuid: str,
    solution_file: UploadFile | None = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentRead:
    """
    Upload the assignment's model answer document
    """
    return await put_assignment_solution_file(
        request, db_session, assignment_uuid, current_user, solution_file
    )


@router.delete(
    "/{assignment_uuid}/solution_file",
    response_model=AssignmentRead,
    summary="Remove the assignment model answer document",
    description="Detach the model answer document from an assignment. Instructor only.",
    responses={
        200: {"description": "Solution file detached.", "model": AssignmentRead},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_delete_assignment_solution_file(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentRead:
    """
    Remove the assignment's model answer document
    """
    return await delete_assignment_solution_file(
        request, db_session, assignment_uuid, current_user
    )


@router.delete(
    "/{assignment_uuid}",
    summary="Delete assignment",
    description="Delete an assignment by its UUID. The authenticated user must have permission to edit the parent course.",
    responses={
        200: {"description": "Assignment deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to delete this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_delete_assignment(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Delete an assignment
    """
    return await delete_assignment(request, assignment_uuid, current_user, db_session)


@router.delete(
    "/activity/{activity_uuid}",
    summary="Delete assignment by activity",
    description="Delete the assignment attached to the given activity UUID.",
    responses={
        200: {"description": "Assignment deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to delete this assignment"},
        404: {"description": "Activity or assignment not found"},
    },
)
async def api_delete_assignment_from_activity(
    request: Request,
    activity_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Delete an assignment
    """
    return await delete_assignment_from_activity_uuid(
        request, activity_uuid, current_user, db_session
    )


## ASSIGNMENTS Tasks ##


@router.post(
    "/{assignment_uuid}/tasks",
    summary="Create assignment task",
    description="Create a new task under an assignment. The authenticated user must have permission to edit the parent course.",
    responses={
        200: {"description": "Assignment task created."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_create_assignment_tasks(
    request: Request,
    assignment_uuid: str,
    assignment_task_object: AssignmentTaskCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Create new tasks for an assignment
    """
    return await create_assignment_task(
        request, assignment_uuid, assignment_task_object, current_user, db_session
    )


@router.get(
    "/{assignment_uuid}/tasks",
    summary="List assignment tasks",
    description="Read all tasks for the given assignment.",
    responses={
        200: {"description": "List of assignment tasks."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_read_assignment_tasks(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read tasks for an assignment
    """
    return await read_assignment_tasks(
        request, assignment_uuid, current_user, db_session
    )


@router.get(
    "/task/{assignment_task_uuid}",
    summary="Get assignment task",
    description="Read a single assignment task by its UUID.",
    responses={
        200: {"description": "Assignment task returned."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this task"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_read_assignment_task(
    request: Request,
    assignment_task_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read task for an assignment
    """
    return await read_assignment_task(
        request, assignment_task_uuid, current_user, db_session
    )


@router.put(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}",
    summary="Update assignment task",
    description="Update an assignment task by its UUID. The authenticated user must have permission to edit the parent course.",
    responses={
        200: {"description": "Assignment task updated."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this task"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_update_assignment_tasks(
    request: Request,
    assignment_task_uuid: str,
    assignment_task_object: AssignmentTaskUpdate,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Update tasks for an assignment
    """
    return await update_assignment_task(
        request, assignment_task_uuid, assignment_task_object, current_user, db_session
    )


@router.post(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/ref_file",
    summary="Upload task reference file",
    description="Upload or replace the reference file for an assignment task. Instructors use this to attach a canonical solution or prompt attachment.",
    responses={
        200: {"description": "Reference file stored."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to edit this task"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_put_assignment_task_ref_file(
    request: Request,
    assignment_task_uuid: str,
    reference_file: UploadFile | None = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Update tasks for an assignment
    """
    return await put_assignment_task_reference_file(
        request, db_session, assignment_task_uuid, current_user, reference_file
    )


@router.post(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/sub_file",
    summary="Upload task submission file",
    description="Upload or replace the submission file for an assignment task on behalf of the current user.",
    responses={
        200: {"description": "Submission file stored."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to submit to this task"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_put_assignment_task_sub_file(
    request: Request,
    assignment_task_uuid: str,
    sub_file: UploadFile | None = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Update tasks for an assignment
    """
    return await put_assignment_task_submission_file(
        request, db_session, assignment_task_uuid, current_user, sub_file
    )


@router.delete(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}",
    summary="Delete assignment task",
    description="Delete an assignment task by its UUID. The authenticated user must have permission to edit the parent course.",
    responses={
        200: {"description": "Assignment task deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to delete this task"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_delete_assignment_tasks(
    request: Request,
    assignment_task_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Delete tasks for an assignment
    """
    return await delete_assignment_task(
        request, assignment_task_uuid, current_user, db_session
    )


## ASSIGNMENTS Tasks Submissions ##


@router.put(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/submissions",
    summary="Upsert assignment task submission",
    description="Create or update the current user's submission for an assignment task.",
    responses={
        200: {"description": "Task submission stored."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to submit to this task"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_handle_assignment_task_submissions(
    request: Request,
    assignment_task_submission_object: AssignmentTaskSubmissionUpdate,
    assignment_task_uuid: str,
    on_behalf_of_user_id: int | None = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Create new task submissions for an assignment.

    Sessions write their own submission. An API token with ``assignments.create``
    may submit on behalf of a learner by passing ``on_behalf_of_user_id`` (the
    learner's LearnHouse user id; the learner must belong to the token's org).
    """
    return await handle_assignment_task_submission(
        request,
        assignment_task_uuid,
        assignment_task_submission_object,
        current_user,
        db_session,
        on_behalf_of_user_id=on_behalf_of_user_id,
    )


@router.get(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/submissions/user/{user_id}",
    summary="List task submissions for user",
    description="Read the task submissions made by a specific user for the given assignment task.",
    responses={
        200: {"description": "List of task submissions for the user."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view these submissions"},
        404: {"description": "Assignment task or user not found"},
    },
)
async def api_read_user_assignment_task_submissions(
    request: Request,
    assignment_task_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read task submissions for an assignment from a user
    """
    return await read_user_assignment_task_submissions(
        request, assignment_task_uuid, user_id, current_user, db_session
    )


@router.get(
    "/{assignment_uuid}/tasks/submissions/me",
    summary="Batch read current user's task submissions",
    description="Read all current-user task submissions for an assignment in one round trip. Returns a map keyed by assignment_task_uuid (value is null if no submission). Registered before the per-task variant so the literal submissions path segment isn't shadowed.",
    responses={
        200: {"description": "Map of task_uuid -> submission (or null)."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_read_user_assignment_task_submissions_me_batch(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read all current-user task submissions for an assignment in one round trip.
    Returns a map keyed by assignment_task_uuid (value is null if no submission).
    Registered before the per-task variant so the literal `submissions` path
    segment isn't shadowed by `{assignment_task_uuid}`.
    """
    return await read_user_assignment_task_submissions_me_batch(
        request, assignment_uuid, current_user, db_session
    )


@router.get(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/submissions/me",
    summary="Get current user's task submission",
    description="Read the current user's submission for a specific assignment task. Returns 404 if the user has no submission yet.",
    responses={
        200: {"description": "Current user's task submission."},
        401: {"description": "Authentication required"},
        404: {"description": "Assignment Task Submission not found"},
    },
)
async def api_read_user_assignment_task_submissions_me(
    request: Request,
    assignment_task_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read task submissions for an assignment from a user
    """
    result = await read_user_assignment_task_submissions_me(
        request, assignment_task_uuid, current_user, db_session
    )
    if result is None:
        # Return 404 if no submission exists (maintains current frontend behavior)
        raise HTTPException(
            status_code=404,
            detail="Assignment Task Submission not found",
        )
    return result


@router.get(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/submissions",
    summary="List task submissions",
    description="Read all submissions for a given assignment task (instructor view).",
    responses={
        200: {"description": "List of task submissions."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view these submissions"},
        404: {"description": "Assignment task not found"},
    },
)
async def api_read_assignment_task_submissions(
    request: Request,
    assignment_task_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Read task submissions for an assignment from a user
    """
    return await read_assignment_task_submissions(
        request, assignment_task_uuid, current_user, db_session, limit, offset
    )


@router.delete(
    "/{assignment_uuid}/tasks/{assignment_task_uuid}/submissions/{assignment_task_submission_uuid}",
    summary="Delete task submission",
    description="Delete a specific task submission by its UUID.",
    responses={
        200: {"description": "Task submission deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to delete this submission"},
        404: {"description": "Task submission not found"},
    },
)
async def api_delete_assignment_task_submissions(
    request: Request,
    assignment_task_submission_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Delete task submissions for an assignment from a user
    """
    return await delete_assignment_task_submission(
        request, assignment_task_submission_uuid, current_user, db_session
    )


## ASSIGNMENTS Submissions ##


@router.post(
    "/{assignment_uuid}/submissions",
    summary="Create assignment submission",
    description="Create a new assignment-level submission for the current user on the given assignment.",
    responses={
        200: {"description": "Assignment submission created."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to submit to this assignment"},
        404: {"description": "Assignment not found"},
    },
)
async def api_create_assignment_submissions(
    request: Request,
    assignment_uuid: str,
    on_behalf_of_user_id: int | None = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Create new submissions for an assignment.

    Sessions submit for themselves. An API token with ``assignments.create`` may
    submit on behalf of a learner by passing ``on_behalf_of_user_id``.
    """
    return await create_assignment_submission(
        request, assignment_uuid, current_user, db_session,
        on_behalf_of_user_id=on_behalf_of_user_id,
    )


@router.get(
    "/{assignment_uuid}/submissions",
    summary="List assignment submissions",
    description="Read all assignment-level submissions for the given assignment (instructor view).",
    responses={
        200: {"description": "List of assignment submissions."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view these submissions"},
        404: {"description": "Assignment not found"},
    },
)
async def api_read_assignment_submissions(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Read submissions for an assignment
    """
    return await read_assignment_submissions(
        request, assignment_uuid, current_user, db_session, limit, offset
    )


@router.get(
    "/{assignment_uuid}/submissions/me",
    summary="Get current user's assignment submission",
    description="Read the current user's assignment-level submission for the given assignment.",
    responses={
        200: {"description": "Current user's assignment submission."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this assignment"},
        404: {"description": "Assignment or submission not found"},
    },
)
async def api_read_user_assignment_submission_me(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read submissions for an assignment from the current user
    """
    return await read_user_assignment_submissions_me(
        request, assignment_uuid, current_user, db_session
    )


@router.get(
    "/{assignment_uuid}/submissions/{user_id}",
    summary="Get assignment submission for user",
    description="Read the assignment-level submission for a specific user on the given assignment (instructor view).",
    responses={
        200: {"description": "Assignment submission for the user."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this submission"},
        404: {"description": "Assignment, user, or submission not found"},
    },
)
async def api_read_user_assignment_submissions(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Read submissions for an assignment from a user
    """
    return await read_user_assignment_submissions(
        request, assignment_uuid, user_id, current_user, db_session
    )


@router.put(
    "/{assignment_uuid}/submissions/{user_id}",
    summary="Update assignment submission for user",
    description="Update a user's assignment-level submission on the given assignment.",
    responses={
        200: {"description": "Assignment submission updated."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to update this submission"},
        404: {"description": "Assignment, user, or submission not found"},
    },
)
async def api_update_user_assignment_submissions(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    assignment_submission: AssignmentUserSubmissionCreate,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Update submissions for an assignment from a user
    """
    return await update_assignment_submission(
        request, user_id, assignment_uuid, assignment_submission, current_user, db_session
    )


@router.delete(
    "/{assignment_uuid}/submissions/{user_id}",
    summary="Delete assignment submission for user",
    description="Delete a user's assignment-level submission on the given assignment.",
    responses={
        200: {"description": "Assignment submission deleted."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to delete this submission"},
        404: {"description": "Assignment, user, or submission not found"},
    },
)
async def api_delete_user_assignment_submissions(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Delete submissions for an assignment from a user
    """
    return await delete_assignment_submission(
        request, user_id, assignment_uuid, current_user, db_session
    )


@router.get(
    "/{assignment_uuid}/submissions/{user_id}/grade",
    summary="Get assignment submission grade",
    description="Read the computed grade for a user's assignment submission.",
    responses={
        200: {"description": "Grade information for the submission."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this grade"},
        404: {"description": "Assignment, user, or submission not found"},
    },
)
async def api_get_submission_grade(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Grade submissions for an assignment from a user
    """

    return await get_grade_assignment_submission(
        request, user_id, assignment_uuid, current_user, db_session
    )


@router.post(
    "/{assignment_uuid}/submissions/{user_id}/grade",
    summary="Finalize assignment submission grade",
    description="Compute and store the final grade for an assignment submission. Accepts an optional overall_feedback note that will be stored alongside the grade.",
    responses={
        200: {"description": "Final grade stored."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to grade this submission"},
        404: {"description": "Assignment, user, or submission not found"},
    },
)
async def api_final_grade_submission(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    body: Optional[GradeSubmissionBody] = None,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Compute and store the final grade for an assignment submission. Accepts
    an optional overall_feedback note that will be stored alongside the grade.
    """

    return await grade_assignment_submission(
        request,
        user_id,
        assignment_uuid,
        current_user,
        db_session,
        overall_feedback=body.overall_feedback if body else None,
    )


@router.post(
    "/{assignment_uuid}/start",
    response_model=AssignmentUserSubmissionRead,
    summary="Start a timed assignment attempt",
    description=(
        "Starts the per-attempt clock for an assignment with time_limit_minutes "
        "set. Idempotent — calling it again after the attempt has already "
        "started returns the existing started_at rather than resetting it. "
        "Safe to call even when the assignment has no time limit at all."
    ),
    responses={
        200: {"description": "Attempt started (or already-started state returned).", "model": AssignmentUserSubmissionRead},
        400: {"description": "Assignment has already been submitted"},
        401: {"description": "Authentication required"},
        403: {"description": "Not enrolled, deadline passed, or SEB required and not detected"},
        404: {"description": "Assignment not found"},
    },
)
async def api_start_assignment_attempt(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> AssignmentUserSubmissionRead:
    return await start_assignment_attempt(request, assignment_uuid, current_user, db_session)


@router.post(
    "/{assignment_uuid}/submissions/me/retry",
    summary="Retry assignment for current user",
    description=(
        "Reset the current user's submission so they can attempt the "
        "assignment again. Only allowed when the assignment has "
        "allow_retries=true, the existing submission is in GRADED state, "
        "and the attempt counter is still below max_retries (0 means "
        "unlimited). Wipes per-task submissions, resets the trail step, "
        "and revokes any course certificate."
    ),
    responses={
        200: {"description": "Submission reset; returns the new attempt info."},
        400: {"description": "Submission is not in a retryable state"},
        401: {"description": "Authentication required"},
        403: {"description": "Retries disabled or attempt limit reached"},
        404: {"description": "Assignment or submission not found"},
    },
)
async def api_retry_assignment_submission(
    request: Request,
    assignment_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Reset the current user's submission so they can re-attempt the
    assignment. Strictly self-service — instructors who want to force a
    retry should reject the submission via the existing delete endpoint.
    """
    return await retry_assignment_submission(
        request, assignment_uuid, current_user, db_session
    )


@router.post(
    "/{assignment_uuid}/submissions/{user_id}/done",
    summary="Mark assignment as done for user",
    description="Mark the underlying activity as completed for a user once their assignment submission is accepted.",
    responses={
        200: {"description": "Activity marked as done for the user."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to mark this submission as done"},
        404: {"description": "Assignment, user, or submission not found"},
    },
)
async def api_submission_mark_as_done(
    request: Request,
    assignment_uuid: str,
    user_id: int,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Grade submissions for an assignment from a user
    """

    return await mark_activity_as_done_for_user(
        request, user_id, assignment_uuid, current_user, db_session
    )


@router.get(
    "/course/{course_uuid}",
    summary="List course assignments",
    description="Get all assignments attached to activities within the given course.",
    responses={
        200: {"description": "List of assignments for the course."},
        401: {"description": "Authentication required"},
        403: {"description": "User lacks permission to view this course"},
        404: {"description": "Course not found"},
    },
)
async def api_get_assignments(
    request: Request,
    course_uuid: str,
    current_user: PublicUser = Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """
    Get assignments for a course
    """
    return await get_assignments_from_course(
        request, course_uuid, current_user, db_session
    )
