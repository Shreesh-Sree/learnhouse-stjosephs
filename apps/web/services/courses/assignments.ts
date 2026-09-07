import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyFormWithAuthHeader,
  RequestBodyWithAuthHeader,
  getResponseMetadata,
  secureFetch,
} from '@services/utils/ts/requests'

export async function createAssignment(body: any, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/`,
    RequestBodyWithAuthHeader('POST', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function updateAssignment(
  body: any,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}`,
    RequestBodyWithAuthHeader('PUT', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Model answer ("corrigé") document for the whole assignment. Instructor only —
// the API withholds the stored filename from learners until the assignment's
// reveal rule unlocks it.
export async function updateAssignmentSolutionFile(
  file: any,
  assignmentUUID: string,
  access_token: string
) {
  const formData = new FormData()

  if (file) {
    formData.append('solution_file', file)
  }
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/solution_file`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function deleteAssignmentSolutionFile(
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/solution_file`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getAssignmentFromActivityUUID(
  activityUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/activity/${activityUUID}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only: fetch the generated .seb config file (a downloadable
// blob, not JSON) and hand back a File the caller can offer for download.
// The server derives the filename from the assignment UUID.
export async function downloadAssignmentSebConfig(
  assignmentUUID: string,
  access_token: string
) {
  const url = `${getAPIUrl()}assignments/${assignmentUUID}/seb_config`
  const result = await secureFetch(
    url,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  if (!result.ok) {
    throw new Error(`Failed to download SEB config (${result.status})`)
  }
  const blob = await result.blob()
  return new File([blob], `${assignmentUUID}.seb`, {
    type: 'application/octet-stream',
  })
}

// Whether the CURRENT request looks like it came from Safe Exam Browser.
// Always seb_ok: true when the assignment doesn't require it.
export async function checkAssignmentSebStatus(
  assignmentUUID: string,
  access_token: string
): Promise<{ seb_ok: boolean }> {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/seb_status`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res.data ?? { seb_ok: true }
}

// Whether the CURRENT request's resolved client IP is allowed to submit this
// assignment. Always allowed: true when the assignment doesn't require an
// allowlist. client_ip is returned so a blocked student can relay it to
// campus IT.
export async function checkAssignmentIpAllowlistStatus(
  assignmentUUID: string,
  access_token: string
): Promise<{ allowed: boolean; client_ip: string }> {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/ip_allowlist_status`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res.data ?? { allowed: true, client_ip: '' }
}

// Delete an assignment
export async function deleteAssignment(
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function deleteAssignmentUsingActivityUUID(
  activityUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/activity/${activityUUID}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// tasks

export async function createAssignmentTask(
  body: any,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks`,
    RequestBodyWithAuthHeader('POST', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getAssignmentTask(
  assignmentTaskUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/task/${assignmentTaskUUID}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getAssignmentTaskSubmissionsMe(
  assignmentTaskUUID: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}/submissions/me`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getAssignmentTaskSubmissionsUser(
  assignmentTaskUUID: string,
  user_id: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}/submissions/user/${user_id}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function handleAssignmentTaskSubmission(
  body: any,
  assignmentTaskUUID: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}/submissions`,
    RequestBodyWithAuthHeader('PUT', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function updateAssignmentTask(
  body: any,
  assignmentTaskUUID: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}`,
    RequestBodyWithAuthHeader('PUT', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function deleteAssignmentTask(
  assignmentTaskUUID: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function updateReferenceFile(
  file: any,
  assignmentTaskUUID: string,
  assignmentUUID: string,
  access_token: string
) {
  // Send file thumbnail as form data
  const formData = new FormData()

  if (file) {
    formData.append('reference_file', file)
  }
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}/ref_file`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function updateSubFile(
  file: any,
  assignmentTaskUUID: string,
  assignmentUUID: string,
  access_token: string
) {
  // Send file thumbnail as form data
  const formData = new FormData()

  if (file) {
    formData.append('sub_file', file)
  }
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/tasks/${assignmentTaskUUID}/sub_file`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// submissions

// Assignment groups (team submission) //

export async function createAssignmentGroup(
  assignmentUUID: string,
  name: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups`,
    RequestBodyWithAuthHeader('POST', { name }, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getAssignmentGroups(
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function joinAssignmentGroup(
  assignmentUUID: string,
  groupUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups/${groupUUID}/join`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function leaveAssignmentGroup(
  assignmentUUID: string,
  groupUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups/${groupUUID}/leave`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only.
export async function deleteAssignmentGroup(
  assignmentUUID: string,
  groupUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups/${groupUUID}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only.
export async function removeAssignmentGroupMember(
  assignmentUUID: string,
  groupUUID: string,
  userId: number,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups/${groupUUID}/members/${userId}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Submits for every member of the group at once — see the backend
// endpoint's docstring for how teammates' rows get synced and advanced.
export async function submitAssignmentGroupForGrading(
  assignmentUUID: string,
  groupUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups/${groupUUID}/submit`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only: finalizes the same grade + feedback for every member of
// the group at once.
export async function gradeAssignmentGroup(
  assignmentUUID: string,
  groupUUID: string,
  access_token: string,
  overall_feedback?: string | null
) {
  const body =
    overall_feedback !== undefined && overall_feedback !== null
      ? { overall_feedback }
      : null
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/groups/${groupUUID}/grade`,
    RequestBodyWithAuthHeader('POST', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Peer review //

// Instructor-only.
export async function assignPeerReviews(assignmentUUID: string, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/peer_reviews/assign`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getMyPeerReviewsToDo(assignmentUUID: string, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/peer_reviews/to_do`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getPeerReviewSubmissionView(
  assignmentUUID: string,
  reviewUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/peer_reviews/${reviewUUID}/submission`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function submitPeerReview(
  assignmentUUID: string,
  reviewUUID: string,
  score: number | null,
  feedback: string | null,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/peer_reviews/${reviewUUID}/submit`,
    RequestBodyWithAuthHeader('POST', { score, feedback }, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getMyPeerReviewsReceived(assignmentUUID: string, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/peer_reviews/received`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only.
export async function getPeerReviewSummaryForUser(
  assignmentUUID: string,
  userId: number,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/peer_reviews/user/${userId}/summary`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function submitAssignmentForGrading(
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function deleteUserSubmission(
  user_id: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions/${user_id}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function putUserSubmission(
  body: any,
  user_id: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions/${user_id}`,
    RequestBodyWithAuthHeader('PUT', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function putFinalGrade(
  user_id: string,
  assignmentUUID: string,
  access_token: string,
  overall_feedback?: string | null
) {
  // Only send a body when the caller actually passed feedback — otherwise the
  // backend leaves any existing note alone.
  const body =
    overall_feedback !== undefined && overall_feedback !== null
      ? { overall_feedback }
      : null
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions/${user_id}/grade`,
    RequestBodyWithAuthHeader('POST', body, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getFinalGrade(
  user_id: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions/${user_id}/grade`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Starts a timed assignment's per-attempt clock. Safe to call even when the
// assignment has no time limit set — idempotent either way.
export async function startAssignmentAttempt(
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/start`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Uploads one webcam frame for the CURRENT user's own attempt. Opportunistic
// — nothing on the backend requires this to have been called before a
// submission is accepted.
export async function uploadProctoringSnapshot(
  assignmentUUID: string,
  imageBlob: Blob,
  access_token: string
) {
  const formData = new FormData()
  formData.append('image_file', imageBlob, 'snapshot.jpg')
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/proctoring/snapshots`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only.
export async function getProctoringSnapshots(
  assignmentUUID: string,
  userId: number,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/proctoring/snapshots/user/${userId}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only retention control.
export async function deleteProctoringSnapshots(
  assignmentUUID: string,
  userId: number,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/proctoring/snapshots/user/${userId}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export function getProctoringSnapshotUrl(assignmentUUID: string, snapshotUuid: string) {
  return `${getAPIUrl()}assignments/${assignmentUUID}/proctoring/snapshots/file/${snapshotUuid}`
}

export async function retryAssignmentSubmission(
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions/me/retry`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function markActivityAsDoneForUser(
  user_id: string,
  assignmentUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/${assignmentUUID}/submissions/${user_id}/done`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getAssignmentsFromACourse(
  courseUUID: string,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}assignments/course/${courseUUID}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}
