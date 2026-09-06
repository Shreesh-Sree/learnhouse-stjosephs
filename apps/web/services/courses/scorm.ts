import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyFormWithAuthHeader,
  RequestBodyWithAuthHeader,
  getResponseMetadata,
} from '@services/utils/ts/requests'

export type ScormLessonStatus =
  | 'not_attempted'
  | 'incomplete'
  | 'completed'
  | 'passed'
  | 'failed'
  | 'browsed'

export interface ScormTrackingData {
  activity_uuid?: string | null
  lesson_status: ScormLessonStatus
  score_raw?: number | null
  score_min?: number | null
  score_max?: number | null
  lesson_location?: string | null
  suspend_data?: string | null
  session_time_seconds?: number
  total_time_seconds?: number
  update_date?: string | null
}

export async function getScormTracking(activityUuid: string, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}scorm/${activityUuid}/tracking`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function updateScormTracking(
  activityUuid: string,
  data: Partial<ScormTrackingData>,
  access_token: string
) {
  const result: any = await fetch(
    `${getAPIUrl()}scorm/${activityUuid}/tracking`,
    RequestBodyWithAuthHeader('PUT', data, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// Instructor-only. Backend field name is `scorm_file` (matches the FastAPI
// UploadFile parameter name in routers/courses/activities/scorm.py).
export async function uploadScormPackage(
  activityUuid: string,
  file: File,
  access_token: string
) {
  const formData = new FormData()
  formData.append('scorm_file', file)
  const result: any = await fetch(
    `${getAPIUrl()}scorm/${activityUuid}/package`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

// entryPoint may contain subdirectories (e.g. "scormcontent/index.html") —
// passed straight through, matching the API's {file_path:path} route which
// accepts slashes raw rather than percent-encoded.
export function getScormContentUrl(activityUuid: string, entryPoint: string) {
  return `${getAPIUrl()}scorm/${activityUuid}/content/${entryPoint}`
}

// Instructor-only.
export async function deleteScormPackage(activityUuid: string, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}scorm/${activityUuid}/package`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export interface ScormResultRow {
  user_id: number
  user_uuid: string
  username: string
  first_name: string
  last_name: string
  lesson_status: ScormLessonStatus
  score_raw: number | null
  score_max: number | null
  total_time_seconds: number
  update_date: string | null
}

// Instructor-only.
export async function getScormResults(activityUuid: string, access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}scorm/${activityUuid}/results`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}
