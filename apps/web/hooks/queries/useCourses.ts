'use client'

import { useQuery } from '@tanstack/react-query'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { queryKeys } from '@lib/query/keys'
import { getOrgCourses, getCourseMetadata } from '@services/courses/courses'

export function useCourses(orgSlug: string) {
  const session = useLHSession() as any
  const accessToken = session?.data?.tokens?.access_token as string | undefined

  return useQuery({
    queryKey: queryKeys.courses.list(orgSlug),
    queryFn: () => getOrgCourses(orgSlug, {}, accessToken),
    enabled: !!orgSlug,
    staleTime: 60_000,
  })
}

export function useCourseMeta(courseUuid: string) {
  const session = useLHSession() as any
  const accessToken = session?.data?.tokens?.access_token as string | undefined
  // getCourseMetadata prepends "course_" itself, so it needs the bare uuid.
  // Callers pass whatever they have on hand — often the raw "course_..."
  // route param — so normalise here rather than trusting every call site.
  const cleanUuid = courseUuid?.replace('course_', '')

  return useQuery({
    queryKey: queryKeys.courses.meta(cleanUuid),
    queryFn: () => getCourseMetadata(cleanUuid, {}, accessToken, { slim: true }),
    enabled: !!cleanUuid,
    staleTime: 60_000,
  })
}
