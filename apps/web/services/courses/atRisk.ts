import { getAPIUrl } from '@services/config/config'
import { RequestBodyWithAuthHeader, errorHandling } from '@services/utils/ts/requests'

export type AtRiskFlag = 'inactive' | 'failing' | 'missing_assignments' | 'low_progress'

export interface AtRiskStudent {
  user_id: number
  user_uuid: string
  username: string
  first_name: string
  last_name: string
  email: string
  flags: AtRiskFlag[]
  risk_level: 'medium' | 'high'
  days_since_activity: number | null
  last_login_at: string | null
  failing_assignments_count: number
  missing_assignments_count: number
  completion_percentage: number
  enrolled_since: string
}

export async function getAtRiskStudents(
  course_uuid: string,
  access_token: string | null | undefined
): Promise<AtRiskStudent[]> {
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/at_risk_students`,
    RequestBodyWithAuthHeader('GET', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}
