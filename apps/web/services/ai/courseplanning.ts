import { getAPIUrl } from '@services/config/config'
import { processSSEStream } from './sse_parser'

// Feature flag: Enable activity content generation (disabled for now)
export const ENABLE_ACTIVITY_CONTENT_GENERATION = true

export interface Attachment {
  id: string
  type: 'image' | 'video' | 'file' | 'youtube'
  name: string
  url?: string
  file?: File
  preview?: string
}

export interface AttachmentData {
  type: 'image' | 'video' | 'file' | 'youtube'
  name: string
  url?: string
  content_base64?: string
  mime_type?: string
}

export interface ActivityPlan {
  name: string
  type: string
  description: string
  suggested_blocks: string[]
}

export interface ChapterPlan {
  name: string
  description: string
  activities: ActivityPlan[]
}

export interface CoursePlan {
  name: string
  description: string
  learnings: string
  tags: string[]
  chapters: ChapterPlan[]
}

export interface CoursePlanningMessage {
  role: 'user' | 'model'
  content: string
}

export interface CoursePlanningSession {
  session_uuid: string
  planning_iteration_count: number
  max_planning_iterations: number
  current_plan: CoursePlan | null
  message_history: CoursePlanningMessage[]
  course_id: number | null
}

export interface CreatedChapter {
  chapter_uuid: string
  chapter_id: number
  name: string
  activities: {
    activity_uuid: string
    activity_id: number
    name: string
    description: string
    suggested_blocks: string[]
  }[]
}

export interface FinalizeCoursePlanResponse {
  course_uuid: string
  course_id: number
  chapters: CreatedChapter[]
}

interface StreamChunk {
  type: 'chunk' | 'done' | 'error'
  content?: string
  session_uuid?: string
  message?: string
}

/**
 * Convert File to base64 string
 */
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Remove the data URL prefix (e.g., "data:image/png;base64,")
      const base64 = result.split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * Convert attachments to API format
 */
async function prepareAttachments(attachments: Attachment[]): Promise<AttachmentData[]> {
  const prepared: AttachmentData[] = []

  for (const attachment of attachments) {
    if (attachment.type === 'youtube' && attachment.url) {
      prepared.push({
        type: 'youtube',
        name: attachment.name,
        url: attachment.url,
      })
    } else if (attachment.file) {
      const base64 = await fileToBase64(attachment.file)
      prepared.push({
        type: attachment.type,
        name: attachment.name,
        content_base64: base64,
        mime_type: attachment.file.type,
      })
    }
  }

  return prepared
}

/**
 * Start a new course planning session with streaming response
 */
export async function startCoursePlanningSession(
  orgId: number,
  prompt: string,
  accessToken: string,
  onChunk: (_chunk: string) => void,
  onComplete: (_sessionUuid: string) => void,
  onError: (_error: string) => void,
  language: string = 'en',
  attachments?: Attachment[]
): Promise<void> {
  // Prepare attachments if provided (only send if there are actual attachments)
  const attachmentData = attachments && attachments.length > 0
    ? await prepareAttachments(attachments)
    : undefined

  const data: Record<string, unknown> = {
    org_id: orgId,
    prompt,
    language,
  }

  // Only include attachments if we have them
  if (attachmentData && attachmentData.length > 0) {
    data.attachments = attachmentData
  }

  try {
    const response = await fetch(`${getAPIUrl()}ai/courseplanning/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP error ${response.status}`)
    }

    await processStream(response, onChunk, onComplete, onError)
  } catch (error) {
    onError(error instanceof Error ? error.message : 'Unknown error occurred')
  }
}

/**
 * Continue an existing course planning session with a new message
 */
export async function iterateCoursePlanning(
  sessionUuid: string,
  message: string,
  accessToken: string,
  onChunk: (_chunk: string) => void,
  onComplete: (_sessionUuid: string) => void,
  onError: (_error: string) => void,
  currentPlan?: CoursePlan | null,
  attachments?: Attachment[]
): Promise<void> {
  // Prepare attachments if provided (only send if there are actual attachments)
  const attachmentData = attachments && attachments.length > 0
    ? await prepareAttachments(attachments)
    : undefined

  const data: Record<string, unknown> = {
    session_uuid: sessionUuid,
    message,
    current_plan: currentPlan || undefined,
  }

  // Only include attachments if we have them
  if (attachmentData && attachmentData.length > 0) {
    data.attachments = attachmentData
  }

  try {
    const response = await fetch(`${getAPIUrl()}ai/courseplanning/iterate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP error ${response.status}`)
    }

    await processStream(response, onChunk, onComplete, onError)
  } catch (error) {
    onError(error instanceof Error ? error.message : 'Unknown error occurred')
  }
}

/**
 * Finalize the course plan and create the course structure in the database
 */
export async function finalizeCoursePlan(
  sessionUuid: string,
  plan: CoursePlan,
  accessToken: string
): Promise<{ success: boolean; data?: FinalizeCoursePlanResponse; error?: string }> {
  try {
    const response = await fetch(`${getAPIUrl()}ai/courseplanning/finalize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        session_uuid: sessionUuid,
        plan,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `HTTP error ${response.status}`,
      }
    }

    const data = await response.json()
    return { success: true, data }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    }
  }
}

/**
 * Generate content for a specific activity with streaming response
 */
export async function generateActivityContent(
  sessionUuid: string,
  activityUuid: string,
  activityName: string,
  activityDescription: string,
  chapterName: string,
  courseName: string,
  courseDescription: string,
  accessToken: string,
  onChunk: (_chunk: string) => void,
  onComplete: (_sessionUuid: string) => void,
  onError: (_error: string) => void,
  prompt?: string
): Promise<void> {
  const data = {
    session_uuid: sessionUuid,
    activity_uuid: activityUuid,
    activity_name: activityName,
    activity_description: activityDescription,
    chapter_name: chapterName,
    course_name: courseName,
    course_description: courseDescription,
    prompt: prompt || undefined,
  }

  try {
    const response = await fetch(`${getAPIUrl()}ai/courseplanning/generate-activity`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP error ${response.status}`)
    }

    await processStream(response, onChunk, onComplete, onError)
  } catch (error) {
    onError(error instanceof Error ? error.message : 'Unknown error occurred')
  }
}

/**
 * Save AI-generated content to an activity
 */
export async function saveActivityContent(
  activityUuid: string,
  content: any,
  accessToken: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch(`${getAPIUrl()}ai/courseplanning/save-activity-content`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        activity_uuid: activityUuid,
        content: content,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      console.error('[saveActivityContent] Error:', errorData)
      return {
        success: false,
        error: errorData.detail || `HTTP error ${response.status}`,
      }
    }

    // Drain the body so the connection can be reused; the payload isn't needed.
    await response.json().catch(() => ({}))
    return { success: true }
  } catch (error) {
    console.error('[saveActivityContent] Exception:', error)
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    }
  }
}

/**
 * Get the current state of a course planning session
 */
export async function getCoursePlanningSession(
  sessionUuid: string,
  accessToken: string
): Promise<{ success: boolean; data?: CoursePlanningSession; error?: string }> {
  try {
    const response = await fetch(
      `${getAPIUrl()}ai/courseplanning/session/${sessionUuid}`,
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      }
    )

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `HTTP error ${response.status}`,
      }
    }

    const data = await response.json()
    return { success: true, data }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    }
  }
}

/**
 * Process Server-Sent Events stream
 */
async function processStream(
  response: Response,
  onChunk: (_chunk: string) => void,
  onComplete: (_sessionUuid: string) => void | Promise<void>,
  onError: (_error: string) => void
): Promise<void> {
  await processSSEStream(
    response,
    async (jsonStr) => {
      try {
        const event: StreamChunk = JSON.parse(jsonStr)
        if (event.type === 'chunk' && event.content) {
          onChunk(event.content)
        } else if (event.type === 'done' && event.session_uuid) {
          await onComplete(event.session_uuid)
        } else if (event.type === 'error' && event.message) {
          onError(event.message)
        }
      } catch {
        // Ignore malformed JSON event payload
      }
    },
    onError
  )
}

/**
 * Robust JSON repair and parser for AI model streaming responses.
 * Handles:
 * - <think>...</think> tags from reasoning models
 * - Markdown code fences (```json ... ``` or ``` ... ```)
 * - Leading/trailing non-JSON text
 * - Missing commas between properties or array items across lines
 * - Trailing commas before } or ]
 * - Unescaped literal newlines and control characters inside string literals
 */
export function repairAndParseJson<T = any>(str: string): T | null {
  if (!str || typeof str !== 'string') return null

  // 1. Remove thinking tags (<think>...</think>)
  let cleaned = str.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()

  // 2. Remove markdown code fences
  if (cleaned.includes('```json')) {
    const start = cleaned.indexOf('```json') + 7
    const end = cleaned.indexOf('```', start)
    if (end !== -1) {
      cleaned = cleaned.substring(start, end).trim()
    }
  } else if (cleaned.includes('```')) {
    const start = cleaned.indexOf('```') + 3
    const end = cleaned.indexOf('```', start)
    if (end !== -1) {
      cleaned = cleaned.substring(start, end).trim()
    }
  }

  // 3. Find boundaries of outer JSON object
  const start = cleaned.indexOf('{')
  const end = cleaned.lastIndexOf('}')
  if (start !== -1 && end !== -1 && end > start) {
    cleaned = cleaned.substring(start, end + 1)
  }

  // Fast path: try native JSON.parse directly
  try {
    return JSON.parse(cleaned) as T
  } catch {
    // Proceed with progressive repair
  }

  try {
    // 4. Strip single-line comments // ...
    let repaired = cleaned.replace(/^\s*\/\/.*$/gm, '')

    // 5. Fix unescaped literal newlines, tabs, and carriage returns inside quoted strings
    let inString = false
    let escaped = false
    const chars: string[] = []
    for (let i = 0; i < repaired.length; i++) {
      const ch = repaired[i]
      if (ch === '\\' && inString) {
        escaped = !escaped
        chars.push(ch)
        continue
      }
      if (ch === '"' && !escaped) {
        inString = !inString
      }
      if (inString && (ch === '\n' || ch === '\r')) {
        chars.push(ch === '\n' ? '\\n' : '\\r')
      } else if (inString && ch === '\t') {
        chars.push('\\t')
      } else {
        chars.push(ch)
      }
      escaped = false
    }
    repaired = chars.join('')

    // 6. Fix missing commas between properties or array items on adjacent lines
    repaired = repaired.replace(/(["\d]|true|false|null|\}|\])\s*\n(\s*["{\[])/g, '$1,\n$2')

    // 7. Remove trailing commas before closing braces or brackets
    repaired = repaired.replace(/,(\s*[}\]])/g, '$1')

    return JSON.parse(repaired) as T
  } catch {
    // Fallback: strip all trailing commas and retry
    try {
      let fallback = cleaned.replace(/,(\s*[}\]])/g, '$1')
      fallback = fallback.replace(/(["\d]|true|false|null|\}|\])\s*\n(\s*["{\[])/g, '$1,\n$2')
      fallback = fallback.replace(/,(\s*[}\]])/g, '$1')
      return JSON.parse(fallback) as T
    } catch {
      return null
    }
  }
}

/**
 * Parse a course plan from streaming content
 */
export function parseCoursePlanFromStream(streamContent: string): CoursePlan | null {
  if (!streamContent || streamContent.trim().startsWith('Error:')) {
    return null
  }
  return repairAndParseJson<CoursePlan>(streamContent)
}

/**
 * Validate ProseMirror document structure
 */
function validateProseMirrorDoc(content: any): { valid: boolean; error?: string } {
  if (!content || typeof content !== 'object') {
    return { valid: false, error: 'Content must be a JSON object' }
  }

  if (content.type !== 'doc') {
    return { valid: false, error: `Root must have type "doc", got "${content.type}"` }
  }

  if (!Array.isArray(content.content)) {
    return { valid: false, error: 'Content must have a "content" array' }
  }

  // Valid block types that the editor supports
  const validBlockTypes = new Set([
    'paragraph', 'heading', 'bulletList', 'orderedList', 'listItem',
    'codeBlock', 'blockQuiz', 'flipcard', 'calloutInfo', 'calloutWarning',
    'blockEmbed', 'blockImage', 'blockVideo', 'blockPDF', 'blockMathEquation',
    'table', 'tableRow', 'tableCell', 'tableHeader', 'horizontalRule',
    'hardBreak', 'text', 'scenarios', 'blockUser', 'blockWebPreview', 'button', 'badge',
    'blockLibrary', 'flipcardGrid'
  ])

  function checkNode(node: any, path: string): { valid: boolean; error?: string } {
    if (!node || typeof node !== 'object') {
      return { valid: false, error: `Node at ${path} must be an object` }
    }

    if (!node.type) {
      return { valid: false, error: `Node at ${path} missing "type" field` }
    }

    if (!validBlockTypes.has(node.type) && node.type !== 'doc') {
      console.warn(`[parseActivityContent] Unknown block type "${node.type}" at ${path}`)
    }

    if (Array.isArray(node.content)) {
      for (let i = 0; i < node.content.length; i++) {
        const result = checkNode(node.content[i], `${path}.content[${i}]`)
        if (!result.valid) {
          return result
        }
      }
    }

    return { valid: true }
  }

  for (let i = 0; i < content.content.length; i++) {
    const result = checkNode(content.content[i], `content[${i}]`)
    if (!result.valid) {
      return result
    }
  }

  return { valid: true }
}

/**
 * Parse activity content from streaming content
 */
export function parseActivityContentFromStream(streamContent: string): any | null {
  try {
    if (!streamContent || streamContent.trim().startsWith('Error:')) {
      return null
    }

    const parsed = repairAndParseJson<any>(streamContent)
    if (!parsed || typeof parsed !== 'object') {
      return null
    }

    // Validate ProseMirror structure
    const validation = validateProseMirrorDoc(parsed)
    if (!validation.valid) {
      console.error('[parseActivityContent] Validation failed:', validation.error)
      return null
    }

    return parsed
  } catch (error) {
    console.error('[parseActivityContent] Failed to parse activity content:', error)
    return null
  }
}
