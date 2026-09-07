import { getAPIUrl } from '@services/config/config'
import { RequestBodyWithAuthHeader, errorHandling } from '@services/utils/ts/requests'

export interface GamificationBadge {
  id: string
  label: string
  description: string
  icon: string
  earned: boolean
}

export interface GamificationStats {
  points: number
  current_streak_days: number
  longest_streak_days: number
  completed_activity_count: number
  certificate_count: number
  discussion_count: number
  comment_count: number
  badges: GamificationBadge[]
}

export async function getMyGamificationStats(
  org_id: number,
  access_token: string | null | undefined
): Promise<GamificationStats> {
  const result: any = await fetch(
    `${getAPIUrl()}users/me/gamification/${org_id}`,
    RequestBodyWithAuthHeader('GET', null, null, access_token || undefined)
  )
  const res = await errorHandling(result)
  return res
}
