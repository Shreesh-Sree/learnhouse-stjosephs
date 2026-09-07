import { getAPIUrl } from '@services/config/config'
import { RequestBodyWithAuthHeader, errorHandling, getResponseMetadata } from '@services/utils/ts/requests'

export interface LiveSession {
  session_uuid: string
  course_id: number
  title: string
  description: string | null
  meeting_url: string
  start_time: string
  end_time: string | null
  created_by_user_id: number
  creation_date: string
  update_date: string
}

export interface LiveSessionInput {
  title: string
  description?: string | null
  meeting_url: string
  start_time: string
  end_time?: string | null
}

export async function getCourseLiveSessions(
  course_uuid: string,
  access_token: string | null | undefined
): Promise<LiveSession[]> {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/live_sessions`,
    RequestBodyWithAuthHeader('GET', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}

async function throwing(result: any) {
  const res = await getResponseMetadata(result)
  if (!res.success) {
    const detail = res.data?.detail || res.data?.message || res.data
    const message = typeof detail === 'string' ? detail : JSON.stringify(detail)
    const error: any = new Error(message)
    error.status = res.status
    error.detail = detail
    throw error
  }
  return res.data
}

export async function createLiveSession(
  course_uuid: string,
  data: LiveSessionInput,
  access_token: string | null | undefined
): Promise<LiveSession> {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/live_sessions`,
    RequestBodyWithAuthHeader('POST', data, null, access_token || undefined)
  )
  return throwing(result)
}

export async function updateLiveSession(
  course_uuid: string,
  session_uuid: string,
  data: Partial<LiveSessionInput>,
  access_token: string | null | undefined
): Promise<LiveSession> {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/live_sessions/${session_uuid}`,
    RequestBodyWithAuthHeader('PUT', data, null, access_token || undefined)
  )
  return throwing(result)
}

export async function deleteLiveSession(
  course_uuid: string,
  session_uuid: string,
  access_token: string | null | undefined
) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/live_sessions/${session_uuid}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}
