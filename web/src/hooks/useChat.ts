import { useState, useEffect, useRef } from 'react'
import { isAxiosError } from 'axios'
import client, { TOKEN_KEY, signOut } from '../api/client'
import type { RefusalReason } from '../types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  confidence?: number | null
  follow_ups?: string[]
  /** True when the assistant declined without generating an answer. */
  refused?: boolean
  /** Which check declined; undefined on turns stored before #269. */
  refusal_reason?: RefusalReason | null
  /** Set once this turn has been handed to a person. See EscalateButton. */
  escalation_id?: string
  /**
   * The server's stable name for this turn, from the stream's `done` event or
   * a conversation load. Escalation sends it instead of a position, because a
   * failed generation leaves this list longer than the stored one. See #84.
   */
  message_id?: string
  /**
   * A bubble this client wrote after a failure, which the server never stored.
   * It has no message_id and cannot be escalated.
   */
  error?: boolean
  /**
   * Provider-busy 503 / retryable SSE error. One retry is offered; a second
   * failure of the same question stays generic so the client cannot loop.
   */
  retryable?: boolean
  /** Seconds from Retry-After (or the API default) before the retry control enables. */
  retryAfter?: number
}

interface UseChatOptions {
  sessionId: string | null
  onSessionCreated: (sessionId: string) => void
  /**
   * The conversation in the URL is not this browser's, or no longer exists.
   * Conversations belong to the browser that made them (#290), so an old
   * link, a bookmark, or one opened in another browser answers 404. The page
   * should drop the id, or every question would go to a conversation the
   * server refuses.
   */
  onSessionMissing?: () => void
}

interface SendOptions {
  /** Resend the last question without appending another user turn. */
  reuseUserTurn?: boolean
}

const GENERIC_ERROR = 'Sorry, something went wrong. Please try again.'
/** Matches `RETRY_AFTER_SECONDS` on the chat routes when the header or SSE event omits it. */
const DEFAULT_RETRY_AFTER_SECONDS = 1

function parseRetryAfter(header: string | null): number {
  if (header == null || header === '') return DEFAULT_RETRY_AFTER_SECONDS
  const seconds = Number(header)
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds)
  return DEFAULT_RETRY_AFTER_SECONDS
}

function isRetryableEnvelope(value: unknown): value is { error: string; retryable: true } {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return record.retryable === true && typeof record.error === 'string' && record.error.length > 0
}

async function readRetryableBusy(
  response: Response,
): Promise<{ error: string; retryAfter: number } | null> {
  if (response.status !== 503) return null
  const retryAfter = parseRetryAfter(response.headers.get('Retry-After'))
  try {
    const raw = await response.text()
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (isRetryableEnvelope(parsed)) return { error: parsed.error, retryAfter }
  } catch {
    return null
  }
  return null
}

function errorBubble(content: string, retryable: boolean, retryAfter?: number): ChatMessage {
  if (retryable) {
    return {
      role: 'assistant',
      content,
      error: true,
      retryable: true,
      retryAfter: retryAfter ?? DEFAULT_RETRY_AFTER_SECONDS,
    }
  }
  return { role: 'assistant', content, error: true }
}

function lastUserQuestion(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'user') return messages[i].content
  }
  return null
}

export function useChat({ sessionId, onSessionCreated, onSessionMissing }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)    // true = waiting for first token (show dots)
  const [streaming, setStreaming] = useState(false) // true = tokens arriving (input disabled)
  const activeSessionId = useRef<string | null>(sessionId)
  const skipNextFetch = useRef(false)
  const messagesRef = useRef(messages)
  const sendGeneration = useRef(0)
  // `loading`/`streaming` publish on the next render; this claims the request now.
  const inFlightRef = useRef(false)
  // Read by the load effect, which runs per conversation, not per render.
  const onSessionMissingRef = useRef(onSessionMissing)

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    onSessionMissingRef.current = onSessionMissing
  }, [onSessionMissing])

  useEffect(() => {
    activeSessionId.current = sessionId
  }, [sessionId])

  useEffect(() => {
    return () => {
      sendGeneration.current += 1
    }
  }, [])

  // Leaving a conversation (sessionId becomes null) empties the list during
  // this render rather than in an effect, so there is no frame showing the old
  // messages and no cascading re-render. This is React's "adjust state when a
  // prop changes" pattern; the rendered id is tracked so it runs once per change.
  const [renderedSessionId, setRenderedSessionId] = useState(sessionId)
  if (sessionId !== renderedSessionId) {
    setRenderedSessionId(sessionId)
    if (!sessionId) setMessages([])
  }

  // A conversation load can outlive the conversation that started it: the
  // user clicks a second chat before the first has loaded. A late response
  // used to write into whichever list was on screen. The cleanup flag drops
  // any response that belongs to a conversation the user has already left.
  useEffect(() => {
    if (!sessionId) return
    if (skipNextFetch.current) {
      skipNextFetch.current = false
      return
    }
    let cancelled = false
    client.get(`/api/conversations/${sessionId}`).then((res) => {
      if (cancelled) return
      const raw: {
        role: string
        content: string
        sources?: string[]
        confidence?: number | null
        refused?: boolean
        refusal_reason?: RefusalReason | null
        escalation_id?: string
        message_id?: string
        follow_ups?: string[]
      }[] = res.data.messages ?? []
      const mapped: ChatMessage[] = raw.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        sources: m.sources,
        confidence: m.confidence,
        refused: m.refused,
        refusal_reason: m.refusal_reason,
        escalation_id: m.escalation_id,
        message_id: m.message_id,
        follow_ups: m.follow_ups,
      }))
      setMessages(mapped)
    }).catch((error: unknown) => {
      if (cancelled) return
      if (isAxiosError(error) && error.response?.status === 404) onSessionMissingRef.current?.()
    })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  async function sendMessage(question: string, options: SendOptions = {}) {
    if (loading || streaming || inFlightRef.current) return
    inFlightRef.current = true

    const reuseUserTurn = options.reuseUserTurn === true
    const generation = sendGeneration.current
    const startedSession = activeSessionId.current

    const isLive = (sid: string | null) =>
      sendGeneration.current === generation && activeSessionId.current === sid

    let sid = startedSession
    try {
      setLoading(true)
      if (!reuseUserTurn) {
        setMessages((prev) => [...prev, { role: 'user', content: question }])
      } else {
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          return last?.error ? prev.slice(0, -1) : prev
        })
      }

      // Create conversation on first message
      if (!sid) {
        const res = await client.post('/api/conversations', { title: question.slice(0, 60) })
        if (sendGeneration.current !== generation) return
        if (activeSessionId.current !== startedSession) return
        sid = res.data.session_id as string
        activeSessionId.current = sid
        skipNextFetch.current = true
        onSessionCreated(sid)
      }

      const token = localStorage.getItem(TOKEN_KEY) ?? ''

      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        // History is deliberately NOT sent. The server reads it from the
        // conversation record, so a client cannot inject forged turns into the
        // prompt. See the module docstring in sourcebook/api/routes/chat.py.
        body: JSON.stringify({ question, session_id: sid }),
      })

      if (response.status === 401) {
        // Stream uses raw fetch, so it bypasses the axios 401 interceptor.
        // An expired token must sign the user out, not look like a chat error.
        signOut()
        return
      }

      if (!response.ok) {
        const busy = await readRetryableBusy(response)
        if (!isLive(sid)) return
        if (busy) {
          const allowRetry = !reuseUserTurn
          setMessages((prev) => [...prev, errorBubble(busy.error, allowRetry, busy.retryAfter)])
          return
        }
        throw new Error(`HTTP ${response.status}`)
      }

      if (!response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantPushed = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        // The user opened another conversation or "New chat" mid-stream.
        // Stop rendering so chunks do not land in the wrong list (or on an
        // empty one), but keep reading: closing the connection would make the
        // server persist a fragment, and draining lets it save the whole
        // answer for when the user comes back.
        if (!isLive(sid)) {
          while (!(await reader.read()).done) { /* discard */ }
          return
        }

        // Decode incrementally; buffer handles chunks that split across SSE boundaries
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? '' // last element may be an incomplete line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (!payload) continue

          let data: Record<string, unknown>
          try { data = JSON.parse(payload) } catch { continue }

          if (data.chunk) {
            if (!assistantPushed) {
              // First token: swap loading dots for the assistant bubble in one update
              assistantPushed = true
              setLoading(false)
              setStreaming(true)
              setMessages((prev) => [...prev, { role: 'assistant', content: data.chunk as string }])
            } else {
              // Append subsequent tokens to the last message
              setMessages((prev) => {
                const last = prev[prev.length - 1]
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: last.content + (data.chunk as string) },
                ]
              })
            }
          } else if (data.done) {
            // Attach sources + confidence immediately; follow_ups arrive in the next event
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  sources: data.sources as string[],
                  confidence: data.confidence as number | null,
                  refused: Boolean(data.refused),
                  refusal_reason: data.refusal_reason as RefusalReason | null | undefined,
                  message_id: data.message_id as string | undefined,
                },
              ]
            })
          } else if (data.follow_ups) {
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              return [
                ...prev.slice(0, -1),
                { ...last, follow_ups: data.follow_ups as string[] },
              ]
            })
          } else if (data.error) {
            setLoading(false)
            const allowRetry = data.retryable === true && !reuseUserTurn
            const bubble = errorBubble(String(data.error), allowRetry)
            if (assistantPushed) {
              setMessages((prev) => [...prev.slice(0, -1), bubble])
            } else {
              setMessages((prev) => [...prev, bubble])
            }
          }
        }
      }
    } catch {
      if (!isLive(sid)) return
      setMessages((prev) => [...prev, errorBubble(GENERIC_ERROR, false)])
    } finally {
      inFlightRef.current = false
      if (sendGeneration.current === generation) {
        setLoading(false)
        setStreaming(false)
      }
    }
  }

  /**
   * Resend the question that produced the last retryable error. The user turn
   * stays as-is; a second busy response is not retryable.
   */
  function retryLastQuestion() {
    if (loading || streaming || inFlightRef.current) return
    const current = messagesRef.current
    const last = current[current.length - 1]
    if (!last?.error || !last.retryable) return
    const question = lastUserQuestion(current)
    if (!question) return
    void sendMessage(question, { reuseUserTurn: true })
  }

  /** Record that a message was escalated, so the button shows its reference. */
  function markEscalated(index: number, escalationId: string) {
    setMessages((prev) =>
      prev.map((m, i) => (i === index ? { ...m, escalation_id: escalationId } : m))
    )
  }

  return { messages, loading, streaming, sendMessage, retryLastQuestion, markEscalated }
}
