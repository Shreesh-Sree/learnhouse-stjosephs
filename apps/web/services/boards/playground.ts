import { getAPIUrl } from '@services/config/config'
import { processSSEStream } from '../ai/sse_parser'

interface BoardsPlaygroundContext {
  board_name: string
  board_description: string
}

interface StreamChunk {
  type: 'chunk' | 'done' | 'error'
  content?: string
  session_uuid?: string
  message?: string
}

export async function startBoardsPlaygroundSession(
  boardUuid: string,
  blockUuid: string,
  prompt: string,
  context: BoardsPlaygroundContext,
  accessToken: string,
  onChunk: (chunk: string) => void,
  onComplete: (sessionUuid: string) => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const response = await fetch(`${getAPIUrl()}boards/playground/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        board_uuid: boardUuid,
        block_uuid: blockUuid,
        prompt,
        context,
      }),
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

export async function iterateBoardsPlayground(
  sessionUuid: string,
  boardUuid: string,
  blockUuid: string,
  message: string,
  accessToken: string,
  onChunk: (chunk: string) => void,
  onComplete: (sessionUuid: string) => void,
  onError: (error: string) => void,
  currentHtml?: string | null
): Promise<void> {
  try {
    const response = await fetch(`${getAPIUrl()}boards/playground/iterate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        session_uuid: sessionUuid,
        board_uuid: boardUuid,
        block_uuid: blockUuid,
        message,
        current_html: currentHtml || undefined,
      }),
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
