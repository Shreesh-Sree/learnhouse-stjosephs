import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyWithAuthHeader,
  errorHandling,
  getResponseMetadata,
} from '@services/utils/ts/requests'

export type QuizFlagReason = 'incorrect_answer' | 'unclear_wording' | 'typo' | 'other'
export type QuizFlagStatus = 'open' | 'resolved' | 'dismissed'

export interface QuizFlagAuthor {
  id: number
  user_uuid: string
  username: string
  first_name: string
  last_name: string
}

export interface QuizFlag {
  flag_uuid: string
  activity_uuid: string
  activity_name: string
  quiz_id: string
  question_id: string
  question_text_snapshot: string
  reason: QuizFlagReason
  note: string | null
  status: QuizFlagStatus
  flagged_by: QuizFlagAuthor | null
  resolved_by: QuizFlagAuthor | null
  resolved_at: string | null
  creation_date: string
}

export async function createQuizFlag(
  activity_uuid: string,
  quiz_id: string,
  question_id: string,
  reason: QuizFlagReason,
  note: string | null,
  access_token: string | null | undefined
): Promise<QuizFlag> {
  const result: any = await fetch(
    `${getAPIUrl()}activities/${activity_uuid}/quiz_flags`,
    RequestBodyWithAuthHeader(
      'POST',
      { quiz_id, question_id, reason, note },
      null,
      access_token || undefined
    )
  )
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

export async function getCourseQuizFlags(
  course_uuid: string,
  status: QuizFlagStatus | null,
  access_token: string | null | undefined
): Promise<QuizFlag[]> {
  const url = `${getAPIUrl()}courses/${course_uuid}/quiz_flags${status ? `?status=${status}` : ''}`
  const result: any = await fetch(
    url,
    RequestBodyWithAuthHeader('GET', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}

export async function resolveQuizFlag(
  flag_uuid: string,
  status: QuizFlagStatus,
  access_token: string | null | undefined
): Promise<QuizFlag> {
  const result: any = await fetch(
    `${getAPIUrl()}quiz_flags/${flag_uuid}`,
    RequestBodyWithAuthHeader('PUT', { status }, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}
