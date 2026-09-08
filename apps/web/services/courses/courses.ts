import { getAPIUrl } from '@services/config/config'
import {
  RequestBodyFormWithAuthHeader,
  RequestBodyWithAuthHeader,
  errorHandling,
  getResponseMetadata,
} from '@services/utils/ts/requests'
import type { QueryClient } from '@tanstack/react-query'
import { queryKeys } from '@lib/query/keys'

/*
 This file includes only POST, PUT, DELETE requests
 GET requests are called from the frontend using SWR (https://swr.vercel.app/)
*/

export async function getOrgCourses(
  org_slug: string,
  next: any,
  access_token?: any,
  include_unpublished: boolean = false
) {
  const url = `${getAPIUrl()}courses/org_slug/${org_slug}/page/1/limit/100${include_unpublished ? '?include_unpublished=true' : ''}`
  const result: any = await fetch(
    url,
    RequestBodyWithAuthHeader('GET', null, next, access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function searchOrgCourses(
  org_slug: string,
  query: string,
  page: number = 1,
  limit: number = 10,
  next: any,
  access_token?: any
) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/org_slug/${org_slug}/search?query=${encodeURIComponent(query)}&page=${page}&limit=${limit}`,
    RequestBodyWithAuthHeader('GET', null, next, access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function getCourseMetadata(
  course_uuid: string,
  next: any,
  access_token: string | null | undefined,
  options?: { slim?: boolean; withUnpublishedActivities?: boolean }
) {
  const searchParams = new URLSearchParams()
  if (options?.slim) searchParams.set('slim', 'true')
  if (options?.withUnpublishedActivities !== undefined) {
    searchParams.set('with_unpublished_activities', String(options.withUnpublishedActivities))
  }
  const qs = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const result = await fetch(
    `${getAPIUrl()}courses/course_${course_uuid}/meta${qs}`,
    RequestBodyWithAuthHeader('GET', null, next, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}

/**
 * After a course-structure mutation (create/delete/reorder a chapter or
 * activity), push a genuinely fresh course-meta fetch directly into the
 * react-query cache with setQueryData rather than calling
 * invalidateQueries and hoping a background refetch lands.
 *
 * Why this exists: invalidateQueries()-triggered background refetches for
 * the withUnpublished course-meta query were observed, in real end-to-end
 * testing (Playwright against a live backend), to resolve with STALE data
 * — missing the activity/chapter that had just been created — even though
 * a plain fetch() to the exact same URL from the exact same page,
 * issued moments later, always returned the correct fresh data. The
 * failure was 100% reproducible: teachers would create a chapter or
 * activity and never see it appear without a full page reload. The root
 * cause inside react-query's invalidate → background-refetch pipeline
 * wasn't pinned down, but setQueryData sidesteps it entirely: it writes
 * directly into the cache (no fetch involved) and every subscribed
 * component — including CourseContext's own useQuery — re-renders from
 * that value synchronously.
 */
export async function refreshCourseStructureCache(
  queryClient: QueryClient,
  course_uuid: string,
  access_token: string | null | undefined,
  withUnpublishedActivities: boolean = true
) {
  const cleanUuid = course_uuid.replace(/^course_/, '')
  const fresh = await getCourseMetadata(cleanUuid, {}, access_token, { withUnpublishedActivities })
  const key = withUnpublishedActivities
    ? queryKeys.courses.metaWithUnpublished(cleanUuid)
    : queryKeys.courses.meta(cleanUuid)
  queryClient.setQueryData(key, fresh)
  return fresh
}

export async function updateCourse(course_uuid: any, data: any, access_token:any) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}`,
    RequestBodyWithAuthHeader('PUT', data, null,access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function setCoursePrerequisite(
  course_uuid: string,
  prerequisite_course_id: number | null,
  access_token: any
) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/prerequisite`,
    RequestBodyWithAuthHeader('PUT', { prerequisite_course_id }, null, access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function getCourse(course_uuid: string, next: any, access_token:any) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}`,
    RequestBodyWithAuthHeader('GET', null, next,access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function getCourseById(course_id: string, next: any, access_token:any) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/id/${course_id}`,
    RequestBodyWithAuthHeader('GET', null, next,access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function updateCourseThumbnail(course_uuid: any, formData: FormData, access_token:any) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/thumbnail`,
    RequestBodyFormWithAuthHeader('PUT', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function createNewCourse(
  org_id: string,
  course_body: any,
  thumbnail: any,
  access_token: any
) {
  // Send file thumbnail as form data
  const formData = new FormData()
  formData.append('name', course_body.name || '')
  formData.append('description', course_body.description || '')
  formData.append('public', course_body.visibility)
  formData.append('learnings', course_body.learnings || '')
  formData.append('tags', course_body.tags || '')
  formData.append('about', course_body.description || '')

  if (thumbnail) {
    formData.append('thumbnail', thumbnail)
  }

  const result = await fetch(
    `${getAPIUrl()}courses/?org_id=${org_id}`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function deleteCourseFromBackend(course_uuid: any, access_token:any) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}`,
    RequestBodyWithAuthHeader('DELETE', null, null,access_token)
  )
  const res = await errorHandling(result)
  return res
}

export async function cloneCourse(course_uuid: string, access_token: string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/clone`,
    RequestBodyWithAuthHeader('POST', null, null, access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function getCourseContributors(course_uuid: string, access_token:string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/contributors`,
    RequestBodyWithAuthHeader('GET', null, null,access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function editContributor(course_uuid: string, contributor_id: string, authorship: any, authorship_status: any, access_token:string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/contributors/${contributor_id}?authorship=${authorship}&authorship_status=${authorship_status}`,
    RequestBodyWithAuthHeader('PUT', null, null,access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function applyForContributor(course_uuid: string, data: any, access_token:string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/apply-contributor`,
    RequestBodyWithAuthHeader('POST', data, null,access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function bulkAddContributors(course_uuid: string, data: any, access_token:string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/bulk-add-contributors`,
    RequestBodyWithAuthHeader('POST', data, null,access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function bulkRemoveContributors(course_uuid: string, data: any, access_token: string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/bulk-remove-contributors`,
    RequestBodyWithAuthHeader('PUT', data, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}

// Instructor-only. Uploads a CSV roster (an "email" column, or a bare
// single-column list) to bulk-enroll existing org members and invite
// everyone else to the org.
export async function importCourseRoster(
  course_uuid: string,
  file: File,
  access_token: string | null | undefined
) {
  const formData = new FormData()
  formData.append('file', file)
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/roster/import`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}

export function getCourseGradebookExportUrl(course_uuid: string) {
  return `${getAPIUrl()}courses/${course_uuid}/gradebook/export`
}

export async function getCourseRights(course_uuid: string, access_token: string | null | undefined) {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/rights`,
    RequestBodyWithAuthHeader('GET', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}