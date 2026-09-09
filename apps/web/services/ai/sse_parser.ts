/**
 * Robust Server-Sent Events (SSE) stream parser utility.
 * Handles \r\n\r\n, \n\n, and \r\r event boundaries, handles split chunks across
 * network packets, tolerates variable whitespace around the data: prefix,
 * and flushes trailing buffered events on stream close.
 */
export async function processSSEStream(
  response: Response,
  onMessage: (data: string) => void | Promise<void>,
  onError: (error: string) => void
): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    onError('No response body reader available')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  async function processBuffer(isFinal = false) {
    const parts = buffer.split(/(?:\r\n\r\n|\n\n|\r\r)/)
    if (!isFinal) {
      buffer = parts.pop() || ''
    } else {
      buffer = ''
    }

    for (const part of parts) {
      if (!part.trim()) continue
      const lines = part.split(/(?:\r\n|\n|\r)/)
      const dataLines: string[] = []
      for (const rawLine of lines) {
        const line = rawLine.trimStart()
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).replace(/^\s/, ''))
        }
      }
      if (dataLines.length > 0) {
        await onMessage(dataLines.join('\n'))
      }
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      await processBuffer(false)
    }
    await processBuffer(true)
  } catch (error) {
    onError(error instanceof Error ? error.message : 'Stream processing failed')
  } finally {
    reader.releaseLock()
  }
}
