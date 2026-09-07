import { getAPIUrl } from '@services/config/config'
import { RequestBodyFormWithAuthHeader, getResponseMetadata } from '@services/utils/ts/requests'

export interface QTIImportResult {
  activity_uuid: string
  questions_imported: number
  questions_skipped: { identifier: string; reason: string }[]
  xml_parse_errors: number
}

export async function importQTIQuestionBank(
  course_uuid: string,
  chapter_id: number,
  activity_name: string | null,
  file: File,
  access_token: string | null | undefined
) {
  const formData = new FormData()
  formData.append('chapter_id', String(chapter_id))
  if (activity_name) formData.append('activity_name', activity_name)
  formData.append('file', file)
  const result: any = await fetch(
    `${getAPIUrl()}courses/${course_uuid}/qti_import`,
    RequestBodyFormWithAuthHeader('POST', formData, null, access_token || undefined)
  )
  const res = await getResponseMetadata(result)
  return res
}
