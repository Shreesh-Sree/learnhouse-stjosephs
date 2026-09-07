import { getAPIUrl } from '@services/config/config'
import { RequestBodyWithAuthHeader, getResponseMetadata } from '@services/utils/ts/requests'

export async function getCalendarFeedToken(access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}users/me/calendar_feed_token`,
    RequestBodyWithAuthHeader('GET', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}

export async function regenerateCalendarFeedToken(access_token: string) {
  const result: any = await fetch(
    `${getAPIUrl()}users/me/calendar_feed_token/regenerate`,
    RequestBodyWithAuthHeader('POST', null, null, access_token)
  )
  const res = await getResponseMetadata(result)
  return res
}
