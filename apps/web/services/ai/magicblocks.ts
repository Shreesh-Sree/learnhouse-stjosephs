import { getAPIUrl } from '@services/config/config'
import { processSSEStream } from './sse_parser'
import type {
  MagicBlockContext,
  MagicBlockSession,
  StreamChunk,
} from '@components/Objects/Editor/Extensions/MagicBlocks/types'

/**
 * Start a new MagicBlock session with streaming response
 */
export async function startMagicBlockSession(
  activityUuid: string,
  blockUuid: string,
  prompt: string,
  context: MagicBlockContext,
  accessToken: string,
  onChunk: (chunk: string) => void,
  onComplete: (sessionUuid: string) => void,
  onError: (error: string) => void
): Promise<void> {
  const data = {
    activity_uuid: activityUuid,
    block_uuid: blockUuid,
    prompt,
    context,
  }

  try {
    const response = await fetch(`${getAPIUrl()}ai/magicblocks/start`, {
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
 * Continue an existing MagicBlock session with a new message
 */
export async function iterateMagicBlock(
  sessionUuid: string,
  activityUuid: string,
  blockUuid: string,
  message: string,
  accessToken: string,
  onChunk: (chunk: string) => void,
  onComplete: (sessionUuid: string) => void,
  onError: (error: string) => void,
  currentHtml?: string | null
): Promise<void> {
  const data = {
    session_uuid: sessionUuid,
    activity_uuid: activityUuid,
    block_uuid: blockUuid,
    message,
    current_html: currentHtml || undefined,
  }

  try {
    const response = await fetch(`${getAPIUrl()}ai/magicblocks/iterate`, {
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
 * Get the current state of a MagicBlock session
 */
export async function getMagicBlockSession(
  sessionUuid: string,
  accessToken: string
): Promise<{ success: boolean; data?: MagicBlockSession; error?: string }> {
  try {
    const response = await fetch(
      `${getAPIUrl()}ai/magicblocks/session/${sessionUuid}`,
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
  onChunk: (chunk: string) => void,
  onComplete: (sessionUuid: string) => void,
  onError: (error: string) => void
): Promise<void> {
  await processSSEStream(
    response,
    (jsonStr) => {
      try {
        const event: StreamChunk = JSON.parse(jsonStr)
        if (event.type === 'chunk' && event.content) {
          onChunk(event.content)
        } else if (event.type === 'done' && event.session_uuid) {
          onComplete(event.session_uuid)
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
