import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import client, { TOKEN_KEY } from '../api/client'

const signOut = vi.hoisted(() => vi.fn())

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    signOut,
  }
})

import { useChat } from './useChat'

function axiosData<T>(data: T): AxiosResponse<T> {
  return { data } as AxiosResponse<T>
}

/** SSE body the chat stream parser accepts (`data: …` lines). */
function sseBody(events: Record<string, unknown>[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  const text = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text))
      controller.close()
    },
  })
}

function jsonResponse(body: ReadableStream<Uint8Array>, status = 200): Response {
  return new Response(body, {
    status,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

const PROVIDER_BUSY =
  'The assistant is answering as many questions as it can right now. Please try again in a moment.'

function retryable503(retryAfter = '1', error = PROVIDER_BUSY): Response {
  return new Response(JSON.stringify({ error, retryable: true }), {
    status: 503,
    headers: { 'Content-Type': 'application/json', 'Retry-After': retryAfter },
  })
}

async function mountChat(sessionId: string | null) {
  const hook = renderHook(
    (props: { sessionId: string | null }) =>
      useChat({ sessionId: props.sessionId, onSessionCreated: vi.fn() }),
    { initialProps: { sessionId } },
  )
  if (sessionId) {
    await waitFor(() => expect(client.get).toHaveBeenCalled())
    await act(async () => {
      await Promise.resolve()
    })
  }
  return hook
}

describe('useChat', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    signOut.mockReset()
    localStorage.setItem(TOKEN_KEY, 'test-token')
    vi.spyOn(client, 'get').mockResolvedValue(axiosData({ messages: [] }))
  })

  it('creates a session, streams the answer, and never sends chat history', async () => {
    vi.spyOn(client, 'post').mockResolvedValue(axiosData({ session_id: 'sess-1' }))
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        sseBody([
          { chunk: 'You get ' },
          { chunk: '15 days.' },
          { done: true, sources: ['PTO Policy'], confidence: 82, refused: false, message_id: 'm-1' },
          { follow_ups: ['How do I request time off?'] },
        ]),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const onSessionCreated = vi.fn()
    const { result } = renderHook(() => useChat({ sessionId: null, onSessionCreated }))

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(client.post).toHaveBeenCalledWith('/api/conversations', {
      title: 'How much PTO do I get?',
    })
    expect(onSessionCreated).toHaveBeenCalledWith('sess-1')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.headers).toMatchObject({ Authorization: 'Bearer test-token' })
    expect(JSON.parse(String(init.body))).toEqual({
      question: 'How much PTO do I get?',
      session_id: 'sess-1',
    })
    expect(String(init.body)).not.toContain('history')
    expect(result.current.messages).toEqual([
      { role: 'user', content: 'How much PTO do I get?' },
      {
        role: 'assistant',
        content: 'You get 15 days.',
        sources: ['PTO Policy'],
        confidence: 82,
        refused: false,
        message_id: 'm-1',
        follow_ups: ['How do I request time off?'],
      },
    ])
    expect(result.current.loading).toBe(false)
    expect(result.current.streaming).toBe(false)
  })

  it('marks a refused stream so the refusal card can render', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        sseBody([
          { chunk: 'I cannot answer that from the indexed policies.' },
          {
            done: true,
            sources: [],
            confidence: 41,
            refused: true,
            refusal_reason: 'no_match',
            message_id: 'm-ref',
          },
        ]),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('What is the boiling point of mercury?')
    })

    const assistant = result.current.messages[1]
    expect(assistant.refused).toBe(true)
    expect(assistant.refusal_reason).toBe('no_match')
    expect(assistant.sources).toEqual([])
    expect(assistant.message_id).toBe('m-ref')
  })

  it('loads a stored conversation and maps message fields', async () => {
    vi.mocked(client.get).mockResolvedValue(
      axiosData({
        messages: [
          { role: 'user', content: 'How much PTO?' },
          {
            role: 'assistant',
            content: '15 days.',
            sources: ['PTO Policy'],
            confidence: 82,
            refused: false,
            escalation_id: 'esc-1',
            message_id: 'm-1',
            follow_ups: ['How do I request it?'],
          },
          { role: 'user', content: 'Pet insurance?' },
          {
            role: 'assistant',
            content: 'No policy.',
            confidence: 79,
            refused: true,
            refusal_reason: 'not_covered',
            message_id: 'm-2',
          },
        ],
      }),
    )

    const { result } = renderHook(() =>
      useChat({ sessionId: 'sess-stored', onSessionCreated: vi.fn() }),
    )

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4)
    })
    expect(client.get).toHaveBeenCalledWith('/api/conversations/sess-stored')
    expect(result.current.messages[3]).toMatchObject({
      refused: true,
      refusal_reason: 'not_covered',
    })
    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      content: '15 days.',
      sources: ['PTO Policy'],
      confidence: 82,
      refused: false,
      escalation_id: 'esc-1',
      message_id: 'm-1',
      follow_ups: ['How do I request it?'],
    })
  })

  it('treats a missing messages array as an empty conversation', async () => {
    vi.mocked(client.get).mockResolvedValue(axiosData({}))

    const { result } = renderHook(() =>
      useChat({ sessionId: 'sess-empty', onSessionCreated: vi.fn() }),
    )

    await waitFor(() => expect(client.get).toHaveBeenCalledWith('/api/conversations/sess-empty'))
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.messages).toEqual([])
  })

  it("reports a conversation that is not this browser's", async () => {
    // Another owner's session id, or one stored before owners (#290), answers 404.
    vi.mocked(client.get).mockRejectedValue(
      new AxiosError('Not Found', '404', undefined, undefined, {
        status: 404,
      } as AxiosResponse),
    )
    const onSessionMissing = vi.fn()

    renderHook(() =>
      useChat({ sessionId: 'someone-elses', onSessionCreated: vi.fn(), onSessionMissing }),
    )

    await waitFor(() => expect(onSessionMissing).toHaveBeenCalledTimes(1))
  })

  it('does not report a conversation as missing on other load failures', async () => {
    vi.mocked(client.get).mockRejectedValue(
      new AxiosError('Server Error', '500', undefined, undefined, {
        status: 500,
      } as AxiosResponse),
    )
    const onSessionMissing = vi.fn()

    renderHook(() => useChat({ sessionId: 'sess-a', onSessionCreated: vi.fn(), onSessionMissing }))

    await waitFor(() => expect(client.get).toHaveBeenCalled())
    await act(async () => {
      await Promise.resolve()
    })
    expect(onSessionMissing).not.toHaveBeenCalled()
  })

  it('ignores a late 404 for a conversation the user already left', async () => {
    let rejectGet: (reason: unknown) => void
    vi.mocked(client.get).mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectGet = reject
      }),
    )
    const onSessionMissing = vi.fn()

    const { rerender } = renderHook(
      ({ sessionId }) => useChat({ sessionId, onSessionCreated: vi.fn(), onSessionMissing }),
      { initialProps: { sessionId: 'sess-a' as string | null } },
    )

    rerender({ sessionId: null })
    await act(async () => {
      rejectGet(
        new AxiosError('Not Found', '404', undefined, undefined, { status: 404 } as AxiosResponse),
      )
    })
    expect(onSessionMissing).not.toHaveBeenCalled()
  })

  it('clears messages when leaving a conversation and drops a late load', async () => {
    let resolveGet: (value: AxiosResponse<{ messages: { role: string; content: string }[] }>) => void
    vi.mocked(client.get).mockReturnValue(
      new Promise((resolve) => {
        resolveGet = resolve
      }),
    )

    const { result, rerender } = renderHook(
      ({ sessionId }) => useChat({ sessionId, onSessionCreated: vi.fn() }),
      { initialProps: { sessionId: 'sess-a' as string | null } },
    )

    rerender({ sessionId: null })
    await act(async () => {
      resolveGet(axiosData({ messages: [{ role: 'user', content: 'late' }] }))
    })
    expect(result.current.messages).toEqual([])
  })

  it('skips the conversation refetch after creating a session from the first message', async () => {
    vi.spyOn(client, 'post').mockResolvedValue(axiosData({ session_id: 'sess-1' }))
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          sseBody([
            { chunk: '15 days.' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      ),
    )

    const { result, rerender } = renderHook(
      ({ sessionId }) => useChat({ sessionId, onSessionCreated: vi.fn() }),
      { initialProps: { sessionId: null as string | null } },
    )

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    rerender({ sessionId: 'sess-1' })

    expect(client.get).not.toHaveBeenCalled()
    expect(result.current.messages[1]?.content).toBe('15 days.')
  })

  it('signs the user out on a 401 from the stream', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(signOut).toHaveBeenCalledTimes(1)
    expect(result.current.messages[1]?.error).toBeUndefined()
  })

  it('shows a client error bubble when the stream returns a non-OK status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 503 })))

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      content: 'Sorry, something went wrong. Please try again.',
      error: true,
    })
    expect(result.current.messages[1]?.retryable).toBeUndefined()
  })

  it('shows the provider-busy copy and Retry-After on a retryable 503', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(retryable503('3')))

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      content: PROVIDER_BUSY,
      error: true,
      retryable: true,
      retryAfter: 3,
    })
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)
  })

  it('treats a retryable mid-stream SSE error like the pre-stream 503', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          sseBody([
            { chunk: 'You get ' },
            { error: PROVIDER_BUSY, retryable: true },
          ]),
        ),
      ),
    )

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      content: PROVIDER_BUSY,
      error: true,
      retryable: true,
      retryAfter: 1,
    })
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)
  })

  it('resends the same question once without duplicating the user turn', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(retryable503('1'))
      .mockResolvedValueOnce(
        jsonResponse(
          sseBody([
            { chunk: '15 days.' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    expect(result.current.messages[1]?.retryable).toBe(true)

    await act(async () => {
      result.current.retryLastQuestion()
    })
    await waitFor(() => {
      expect(result.current.messages[1]?.content).toBe('15 days.')
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)
    expect(result.current.messages[0]?.content).toBe('How much PTO do I get?')
    const firstBody = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))
    const retryBody = JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))
    expect(firstBody).toEqual({ question: 'How much PTO do I get?', session_id: 'sess-open' })
    expect(retryBody).toEqual(firstBody)
    expect(String((fetchMock.mock.calls[1][1] as RequestInit).body)).not.toContain('history')
    expect(result.current.messages[1]?.retryable).toBeUndefined()
  })

  it('rejects a second immediate retry before loading state publishes', async () => {
    let resolveRetry!: (value: Response) => void
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(retryable503('1'))
      .mockImplementation(
        () =>
          new Promise<Response>((resolve) => {
            resolveRetry = resolve
          }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    expect(result.current.messages[1]?.retryable).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      result.current.retryLastQuestion()
      result.current.retryLastQuestion()
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)

    await act(async () => {
      resolveRetry(
        jsonResponse(
          sseBody([
            { chunk: '15 days.' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      )
    })
    await waitFor(() => {
      expect(result.current.messages[1]?.content).toBe('15 days.')
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(result.current.messages.filter((message) => message.role === 'assistant')).toHaveLength(1)
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)
    expect(result.current.loading).toBe(false)
  })

  it('releases the in-flight guard after a successful retry so a later retry still works', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(retryable503('1'))
      .mockResolvedValueOnce(
        jsonResponse(
          sseBody([
            { chunk: '15 days.' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      )
      .mockResolvedValueOnce(retryable503('1'))
      .mockResolvedValueOnce(
        jsonResponse(
          sseBody([
            { chunk: '15 days.' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-2' },
          ]),
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    await act(async () => {
      result.current.retryLastQuestion()
    })
    await waitFor(() => {
      expect(result.current.messages[1]?.message_id).toBe('m-1')
    })

    await act(async () => {
      await result.current.sendMessage('How do I request time off?')
    })
    expect(result.current.messages[3]?.retryable).toBe(true)

    await act(async () => {
      result.current.retryLastQuestion()
    })
    await waitFor(() => {
      expect(result.current.messages[3]?.message_id).toBe('m-2')
    })

    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(result.current.loading).toBe(false)
    const retryBody = JSON.parse(String((fetchMock.mock.calls[3][1] as RequestInit).body))
    expect(retryBody).toEqual({ question: 'How do I request time off?', session_id: 'sess-open' })
    expect(String((fetchMock.mock.calls[3][1] as RequestInit).body)).not.toContain('history')
  })

  it('releases the in-flight guard after a failed retry', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(retryable503('1'))
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce(
        jsonResponse(
          sseBody([
            { chunk: 'ok' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    await act(async () => {
      result.current.retryLastQuestion()
    })
    await waitFor(() => {
      expect(result.current.messages[1]?.content).toBe(
        'Sorry, something went wrong. Please try again.',
      )
    })
    expect(result.current.messages[1]?.retryable).toBeUndefined()
    expect(result.current.loading).toBe(false)

    await act(async () => {
      await result.current.sendMessage('How do I request time off?')
    })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(result.current.messages[3]?.content).toBe('ok')
    expect(result.current.loading).toBe(false)
  })

  it('does not leave a remounted hook blocked after unmount during a retry', async () => {
    let resolveRetry!: (value: Response) => void
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(retryable503('1'))
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            resolveRetry = resolve
          }),
      )
      .mockResolvedValue(
        jsonResponse(
          sseBody([
            { chunk: 'ok' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-2' },
          ]),
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    const { result, unmount } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    await act(async () => {
      result.current.retryLastQuestion()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    unmount()

    await act(async () => {
      resolveRetry(retryable503('1'))
    })

    const remounted = await mountChat('sess-open')
    await act(async () => {
      await remounted.result.current.sendMessage('How do I request time off?')
    })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(remounted.result.current.messages[1]?.content).toBe('ok')
    expect(remounted.result.current.loading).toBe(false)
  })

  it('does not offer a second retry after the one-shot resend stays busy', async () => {
    const fetchMock = vi.fn().mockResolvedValue(retryable503('1'))
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    await act(async () => {
      result.current.retryLastQuestion()
    })
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2)
    })
    await waitFor(() => {
      expect(result.current.messages[1]?.error).toBe(true)
    })

    expect(result.current.messages[1]?.retryable).toBeUndefined()
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)

    await act(async () => {
      result.current.retryLastQuestion()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('does not write a late retryable 503 into the next conversation', async () => {
    let resolveFetch!: (value: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(
        new Promise<Response>((resolve) => {
          resolveFetch = resolve
        }),
      ),
    )
    vi.mocked(client.get).mockImplementation((url: string) => {
      if (String(url).includes('sess-b')) {
        return Promise.resolve(axiosData({ messages: [{ role: 'user', content: 'other thread' }] }))
      }
      return Promise.resolve(axiosData({ messages: [] }))
    })

    const { result, rerender } = renderHook(
      ({ sessionId }) => useChat({ sessionId, onSessionCreated: vi.fn() }),
      { initialProps: { sessionId: 'sess-a' as string | null } },
    )
    await waitFor(() => expect(client.get).toHaveBeenCalledWith('/api/conversations/sess-a'))

    let sendPromise: Promise<void> = Promise.resolve()
    await act(async () => {
      sendPromise = result.current.sendMessage('How much PTO do I get?')
    })

    rerender({ sessionId: 'sess-b' })
    await waitFor(() => {
      expect(result.current.messages[0]?.content).toBe('other thread')
    })

    await act(async () => {
      resolveFetch(retryable503('2'))
      await sendPromise
    })

    expect(result.current.messages).toEqual([{ role: 'user', content: 'other thread' }])
    expect(result.current.messages.some((message) => message.retryable)).toBe(false)
  })

  it('does not apply a late retryable 503 after unmount', async () => {
    let resolveFetch!: (value: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn().mockReturnValue(
        new Promise<Response>((resolve) => {
          resolveFetch = resolve
        }),
      ),
    )

    const { result, unmount } = await mountChat('sess-open')
    const sendPromise = result.current.sendMessage('How much PTO do I get?')
    await act(async () => {
      await Promise.resolve()
    })
    unmount()

    await act(async () => {
      resolveFetch(retryable503('1'))
      await sendPromise
    })
  })

  it('drains the stream when the user leaves before headers arrive', async () => {
    vi.mocked(client.get).mockReturnValue(new Promise(() => {}))
    const encoder = new TextEncoder()
    let pulls = 0
    const stream = new ReadableStream<Uint8Array>(
      {
        pull(controller) {
          pulls += 1
          if (pulls < 3) controller.enqueue(encoder.encode('data: {"chunk":"x"}\n\n'))
          else controller.close()
        },
      },
      { highWaterMark: 0 },
    )
    let resolveFetch!: (r: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve
          }),
      ),
    )
    const { result, rerender } = renderHook(
      ({ sessionId }) => useChat({ sessionId, onSessionCreated: vi.fn() }),
      { initialProps: { sessionId: 'sess-a' as string | null } },
    )

    let sent: Promise<void> = Promise.resolve()
    await act(async () => {
      sent = result.current.sendMessage('Hello')
      await Promise.resolve()
    })
    rerender({ sessionId: 'sess-b' })
    await act(async () => {
      resolveFetch(jsonResponse(stream))
      await sent
    })

    expect(pulls).toBeGreaterThanOrEqual(3)
  })

  it('shows a client error bubble when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]?.error).toBe(true)
  })

  it('applies a stream error before any assistant token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          sseBody([{ error: 'The assistant is busy. Try again in a moment.' }]),
        ),
      ),
    )

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]).toMatchObject({
      role: 'assistant',
      content: 'The assistant is busy. Try again in a moment.',
      error: true,
    })
  })

  it('replaces a partial answer when the stream reports an error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          sseBody([
            { chunk: 'You get ' },
            { error: 'The connection dropped.' },
          ]),
        ),
      ),
    )

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]).toMatchObject({
      content: 'The connection dropped.',
      error: true,
    })
  })

  it('ignores blank, non-data, and malformed SSE lines', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: ping\n\n'))
        controller.enqueue(encoder.encode('data: \n'))
        controller.enqueue(encoder.encode('data: not-json\n'))
        controller.enqueue(encoder.encode('data: {"chun'))
        controller.enqueue(encoder.encode('k":"15 days."}\n\n'))
        controller.enqueue(
          encoder.encode(
            'data: {"done":true,"sources":[],"confidence":80,"refused":false,"message_id":"m-1"}\n\n',
          ),
        )
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(stream)))

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })

    expect(result.current.messages[1]).toMatchObject({
      content: '15 days.',
      message_id: 'm-1',
    })
  })

  it('discards remaining chunks when the user leaves mid-stream', async () => {
    const encoder = new TextEncoder()
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        controller.enqueue(encoder.encode('data: {"chunk":"Hi"}\n\n'))
        await gate
        controller.enqueue(encoder.encode('data: {"chunk":" leftover"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(stream)))
    vi.mocked(client.get).mockReturnValue(new Promise(() => {}))

    const { result, rerender } = renderHook(
      ({ sessionId }) => useChat({ sessionId, onSessionCreated: vi.fn() }),
      { initialProps: { sessionId: 'sess-a' } },
    )

    let sendPromise: Promise<void> = Promise.resolve()
    await act(async () => {
      sendPromise = result.current.sendMessage('Hello')
      await Promise.resolve()
    })
    await waitFor(() => {
      expect(result.current.messages[1]?.content).toBe('Hi')
    })

    rerender({ sessionId: 'sess-b' })
    await act(async () => {
      release()
      await sendPromise
    })

    expect(result.current.messages.some((message) => message.content.includes('leftover'))).toBe(
      false,
    )
  })

  it('does not send a second question while a stream is in flight', async () => {
    let resolveFetch!: (value: Response) => void
    const fetchMock = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = await mountChat('sess-open')

    let first: Promise<void> = Promise.resolve()
    await act(async () => {
      first = result.current.sendMessage('first')
    })
    await waitFor(() => expect(result.current.loading).toBe(true))

    await act(async () => {
      await result.current.sendMessage('second')
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveFetch(
        jsonResponse(
          sseBody([
            { chunk: 'ok' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      )
      await first
    })
    expect(result.current.messages.filter((message) => message.role === 'user')).toHaveLength(1)
  })

  it('records an escalation id on the matching message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          sseBody([
            { chunk: '15 days.' },
            { done: true, sources: [], confidence: 80, refused: false, message_id: 'm-1' },
          ]),
        ),
      ),
    )

    const { result } = await mountChat('sess-open')

    await act(async () => {
      await result.current.sendMessage('How much PTO do I get?')
    })
    await act(() => {
      result.current.markEscalated(1, 'esc-9')
    })
    expect(result.current.messages[1]?.escalation_id).toBe('esc-9')
    expect(result.current.messages[0]?.escalation_id).toBeUndefined()
  })
})
