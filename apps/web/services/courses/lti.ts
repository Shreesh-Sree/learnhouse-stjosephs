import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyWithAuthHeader,
  errorHandling,
  getResponseMetadata,
} from '@services/utils/ts/requests'

export interface LTILink {
  link_uuid: string
  course_id: number
  consumer_key: string
  label: string | null
  is_active: boolean
  launch_url: string
  created_by_user_id: number
  creation_date: string
}

export interface LTILinkCreated {
  link_uuid: string
  consumer_key: string
  consumer_secret: string
  label: string | null
  launch_url: string
  creation_date: string
}

export async function getCourseLTILinks(
  course_uuid: string,
  access_token: string | null | undefined
): Promise<LTILink[]> {
  const result: any = await fetch(
    `${getAPIUrl()}lti/courses/${course_uuid}/lti_links`,
    RequestBodyWithAuthHeader('GET', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}

export async function createCourseLTILink(
  course_uuid: string,
  label: string | null,
  access_token: string | null | undefined
): Promise<LTILinkCreated> {
  const result: any = await fetch(
    `${getAPIUrl()}lti/courses/${course_uuid}/lti_links`,
    RequestBodyWithAuthHeader('POST', { label }, null, access_token || undefined)
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

export async function revokeCourseLTILink(
  course_uuid: string,
  link_uuid: string,
  access_token: string | null | undefined
) {
  const result: any = await fetch(
    `${getAPIUrl()}lti/courses/${course_uuid}/lti_links/${link_uuid}`,
    RequestBodyWithAuthHeader('DELETE', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}
