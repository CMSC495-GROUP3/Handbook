import { AxiosError } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import client from '../api/client'
import type { Escalation } from '../types'
import EscalationsPage from './EscalationsPage'

function escalation(overrides: Partial<Escalation> = {}): Escalation {
  return {
    escalation_id: 'esc-1',
    status: 'open',
    reason: 'refused',
    contact: 'Human Resources',
    session_id: 'sess-1',
    message_index: 1,
    question: 'Does Meridian reimburse pet insurance?',
    answer_excerpt: 'No matching policy.',
    refused: true,
    confidence: 41,
    sources: [],
    note: null,
    resolution: null,
    created_at: '2026-09-20T12:00:00Z',
    updated_at: '2026-09-20T12:00:00Z',
    resolved_at: null,
    delivery_status: 'failed',
    delivery_attempts: 1,
    delivery_last_attempt_at: '2026-09-20T12:00:01Z',
    delivery_claimed_at: null,
    delivery_retryable: true,
    ...overrides,
  }
}

const second = escalation({ escalation_id: 'esc-2', question: 'Is there a sabbatical program?' })
const third = escalation({ escalation_id: 'esc-3', question: 'Can I carry over unused PTO?' })
const closed = escalation({
  escalation_id: 'esc-r',
  status: 'resolved',
  question: 'Who approves remote work?',
  resolution: 'Sent them the remote work policy.',
  delivery_status: 'delivered',
  delivery_retryable: false,
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((settle) => {
    resolve = settle
  })
  return { promise, resolve }
}

const listResponse = (items: Escalation[]) => ({ data: { items, total: items.length } }) as AxiosResponse

/** GET calls that fetched one request by id rather than a list. */
const byIdCalls = (get: { mock: { calls: unknown[][] } }) =>
  get.mock.calls.filter(([url]) => url !== '/api/escalations')

function axiosError(status: number, data: unknown): AxiosError {
  return new AxiosError('failed', String(status), undefined, undefined, {
    status,
    statusText: 'Error',
    data,
    headers: {},
    config: {} as InternalAxiosRequestConfig,
  })
}

interface Api {
  open?: Escalation[]
  resolved?: Escalation[]
  total?: number
  byId?: Record<string, Escalation>
}

/** Route GETs: the list by ?status, or one record by id (404 when unknown). */
function mockApi({ open = [], resolved = [], total, byId = {} }: Api) {
  return vi.spyOn(client, 'get').mockImplementation(async (url, config) => {
    if (url === '/api/escalations') {
      const params = config?.params as { status?: string } | undefined
      const items = params?.status === 'resolved' ? resolved : open
      return { data: { items, total: total ?? items.length } } as AxiosResponse
    }
    const id = url.split('/').pop() as string
    if (byId[id]) return { data: byId[id] } as AxiosResponse
    throw axiosError(404, { detail: 'Escalation not found.' })
  })
}

function Location() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

/** The browser's Back button. */
function BrowserBack() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(-1)}>Browser back</button>
}

/** The page opens with /elsewhere behind it, so Back can leave it. */
function renderPage(url = '/escalations') {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/elsewhere', url]}>
      <Routes>
        <Route path="/escalations" element={<EscalationsPage />} />
        <Route path="/elsewhere" element={null} />
      </Routes>
      <Location />
      <BrowserBack />
    </MemoryRouter>,
  )
  return user
}

const location = () => screen.getByTestId('location').textContent

/** Report the two-pane breakpoint as matched, on top of the shared stub. */
function stubTwoPane() {
  const original = window.matchMedia
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => {
    const list = original(query)
    return { ...list, matches: query.includes('1024') ? true : list.matches } as MediaQueryList
  })
}

async function openFirstRequest() {
  const user = renderPage()
  await user.click(await screen.findByRole('button', { name: /pet insurance/ }))
  return user
}

describe('EscalationsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the server total, not the length of the capped page', async () => {
    mockApi({ open: [escalation()], total: 80 })
    renderPage()
    expect(await screen.findByText('80 open')).toBeInTheDocument()
  })

  describe('one pane at a time (below lg)', () => {
    it('opens a request into the URL and goes back to the list', async () => {
      mockApi({ open: [escalation()] })
      const user = await openFirstRequest()

      expect(location()).toBe('/escalations?id=esc-1')
      expect(screen.getByRole('heading', { name: /pet insurance/ })).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'HR Requests' })).not.toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'All requests' }))
      expect(location()).toBe('/escalations')
      expect(await screen.findByRole('heading', { name: 'HR Requests' })).toBeInTheDocument()
    })

    it('opens the request a link names', async () => {
      mockApi({ open: [escalation(), second] })
      renderPage('/escalations?id=esc-2')
      expect(await screen.findByRole('heading', { name: /sabbatical/ })).toBeInTheDocument()
    })

    it('fetches a linked request that is not on the current list page', async () => {
      const get = mockApi({ open: [escalation()], byId: { 'esc-9': escalation({ escalation_id: 'esc-9', question: 'Old one?' }) } })
      renderPage('/escalations?id=esc-9')
      expect(await screen.findByRole('heading', { name: 'Old one?' })).toBeInTheDocument()
      expect(get).toHaveBeenCalledWith('/api/escalations/esc-9')
    })

    it('says so when a linked request does not exist', async () => {
      mockApi({ open: [escalation()] })
      renderPage('/escalations?id=missing')
      expect(await screen.findByText('That request was not found.')).toBeInTheDocument()
    })
  })

  describe('Back and focus below lg (#266)', () => {
    it('goes back through history from a request opened from the list', async () => {
      mockApi({ open: [escalation()] })
      const user = await openFirstRequest()

      await user.click(screen.getByRole('button', { name: 'All requests' }))
      expect(location()).toBe('/escalations')

      await user.click(screen.getByRole('button', { name: 'Browser back' }))
      expect(location()).toBe('/elsewhere')
    })

    it('pushes the list for a request opened from a link, so Back returns to it', async () => {
      mockApi({ open: [escalation(), second] })
      const user = renderPage('/escalations?id=esc-2')
      await screen.findByRole('heading', { name: /sabbatical/ })

      await user.click(screen.getByRole('button', { name: 'All requests' }))
      expect(location()).toBe('/escalations')

      await user.click(screen.getByRole('button', { name: 'Browser back' }))
      expect(location()).toBe('/escalations?id=esc-2')
    })

    it('leaves one list entry after a resolve, so Back leaves the page', async () => {
      mockApi({ open: [escalation(), second] })
      vi.spyOn(client, 'patch').mockResolvedValue({ data: escalation({ status: 'resolved' }) } as AxiosResponse)
      const user = await openFirstRequest()

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))
      await waitFor(() => expect(location()).toBe('/escalations'))

      await user.click(screen.getByRole('button', { name: 'Browser back' }))
      expect(location()).toBe('/elsewhere')
    })

    it('focuses the heading of the request it opens', async () => {
      mockApi({ open: [escalation()] })
      await openFirstRequest()

      expect(screen.getByRole('heading', { name: /pet insurance/ })).toHaveFocus()
    })

    it('focuses the row that was open when it returns to the list', async () => {
      mockApi({ open: [escalation(), second] })
      const user = renderPage()
      await user.click(await screen.findByRole('button', { name: /sabbatical/ }))

      await user.click(screen.getByRole('button', { name: 'All requests' }))

      await waitFor(() => expect(screen.getByRole('button', { name: /sabbatical/ })).toHaveFocus())
    })

    it('focuses the row that was open after the browser Back button', async () => {
      mockApi({ open: [escalation()] })
      const user = await openFirstRequest()

      await user.click(screen.getByRole('button', { name: 'Browser back' }))

      expect(location()).toBe('/escalations')
      await waitFor(() => expect(screen.getByRole('button', { name: /pet insurance/ })).toHaveFocus())
    })

    it('focuses the list heading and announces the resolve', async () => {
      mockApi({ open: [escalation(), second] })
      vi.spyOn(client, 'patch').mockResolvedValue({ data: escalation({ status: 'resolved' }) } as AxiosResponse)
      const user = await openFirstRequest()

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      await waitFor(() => expect(screen.getByRole('heading', { name: 'HR Requests' })).toHaveFocus())
      expect(screen.getByRole('status')).toHaveTextContent('Resolved: Does Meridian reimburse pet insurance?')
    })

    it('focuses the list heading after leaving a request linked from another tab', async () => {
      mockApi({ open: [escalation()], resolved: [closed], byId: { 'esc-r': closed } })
      const user = renderPage('/escalations?id=esc-r')
      await screen.findByRole('heading', { name: 'Who approves remote work?' })

      await user.click(screen.getByRole('button', { name: 'All requests' }))
      await waitFor(() => expect(screen.getByRole('heading', { name: 'HR Requests' })).toHaveFocus())

      // The row it left is on the Resolved tab. Showing it later must not pull focus.
      const tab = screen.getByRole('button', { name: 'Resolved' })
      await user.click(tab)
      expect(await screen.findByRole('button', { name: /remote work/ })).toBeInTheDocument()
      expect(tab).toHaveFocus()
    })

    it('focuses the not-found message when Back returns to a missing request', async () => {
      mockApi({ open: [escalation()] })
      const user = renderPage('/escalations?id=missing')
      await screen.findByText('That request was not found.')
      await user.click(screen.getByRole('button', { name: 'All requests' }))
      await screen.findByRole('heading', { name: 'HR Requests' })

      await user.click(screen.getByRole('button', { name: 'Browser back' }))

      await waitFor(() => expect(screen.getByText('That request was not found.')).toHaveFocus())
    })

    it('focuses the list heading when Back was pressed while a resolve was saving', async () => {
      const get = mockApi({ open: [escalation(), second] })
      const patch = deferred<AxiosResponse>()
      vi.spyOn(client, 'patch').mockReturnValue(patch.promise)
      const user = await openFirstRequest()
      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      await user.click(screen.getByRole('button', { name: 'Browser back' }))
      await waitFor(() => expect(screen.getByRole('button', { name: /pet insurance/ })).toHaveFocus())

      // The server has closed esc-1, so the refetch no longer returns it.
      get.mockImplementation(async () => listResponse([second]))
      await act(async () => patch.resolve({ data: escalation({ status: 'resolved' }) } as AxiosResponse))
      expect(location()).toBe('/escalations')
      expect(screen.queryByRole('button', { name: /pet insurance/ })).not.toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'HR Requests' })).toHaveFocus()
    })

    it('clears the announcement after a few seconds, so the next one is read', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      try {
        mockApi({ open: [escalation(), second] })
        vi.spyOn(client, 'patch').mockResolvedValue({ data: escalation({ status: 'resolved' }) } as AxiosResponse)
        const user = await openFirstRequest()
        await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
        await user.click(screen.getByRole('button', { name: 'Resolve request' }))
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Resolved:'))

        await act(async () => vi.advanceTimersByTime(5000))

        expect(screen.getByRole('status')).toBeEmptyDOMElement()
      } finally {
        vi.useRealTimers()
      }
    })

    it('announces a reopen', async () => {
      const get = mockApi({ resolved: [closed] })
      vi.spyOn(client, 'patch').mockImplementation(async () => {
        get.mockImplementation(async () => listResponse([]))
        return { data: { ...closed, status: 'open' } } as AxiosResponse
      })
      const user = renderPage('/escalations?status=resolved&id=esc-r')

      await user.click(await screen.findByRole('button', { name: 'Reopen request' }))

      await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Reopened: Who approves remote work?'))
      expect(screen.getByRole('heading', { name: 'HR Requests' })).toHaveFocus()
    })
  })

  describe('list beside the request (lg and up)', () => {
    beforeEach(stubTwoPane)

    it('opens the newest request when the URL names none', async () => {
      mockApi({ open: [escalation(), second] })
      renderPage()
      expect(await screen.findByRole('heading', { name: /pet insurance/ })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'HR Requests' })).toBeInTheDocument()
      expect(location()).toBe('/escalations?id=esc-1')
    })

    it('leaves focus on a clicked row, since both panes stay on screen', async () => {
      mockApi({ open: [escalation(), second] })
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.click(screen.getByRole('button', { name: /sabbatical/ }))

      expect(await screen.findByRole('heading', { name: /sabbatical/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sabbatical/ })).toHaveFocus()
    })

    it('focuses the list heading and announces the resolve', async () => {
      const get = mockApi({ open: [escalation(), second] })
      vi.spyOn(client, 'patch').mockImplementation(async () => {
        get.mockImplementation(async () => listResponse([second]))
        return { data: escalation({ status: 'resolved' }) } as AxiosResponse
      })
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      await waitFor(() => expect(location()).toBe('/escalations?id=esc-2'))
      expect(screen.getByRole('heading', { name: 'HR Requests' })).toHaveFocus()
      expect(screen.getByRole('status')).toHaveTextContent('Resolved: Does Meridian reimburse pet insurance?')
    })

    it('moves to the next request after a resolve, not back to the resolved one', async () => {
      const get = mockApi({ open: [escalation(), second] })
      vi.spyOn(client, 'patch').mockImplementation(async () => {
        get.mockImplementation(async () => ({ data: { items: [second], total: 1 } }) as AxiosResponse)
        return { data: escalation({ status: 'resolved' }) } as AxiosResponse
      })
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      expect(await screen.findByRole('heading', { name: /sabbatical/ })).toBeInTheDocument()
      await waitFor(() => expect(location()).toBe('/escalations?id=esc-2'))
      expect(screen.getByText('1 open')).toBeInTheDocument()
      expect(get).not.toHaveBeenCalledWith('/api/escalations/esc-1')
    })
  })

  it('switches tabs through the URL and drops the open request', async () => {
    mockApi({ open: [escalation()], resolved: [second] })
    const user = await openFirstRequest()
    await user.click(screen.getByRole('button', { name: 'All requests' }))

    await user.click(await screen.findByRole('button', { name: 'Resolved' }))

    expect(location()).toBe('/escalations?status=resolved')
    expect(screen.getByRole('button', { name: 'Resolved' })).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByRole('button', { name: /sabbatical/ })).toBeInTheDocument()
  })

  it('says so when a retried delivery fails again', async () => {
    mockApi({ open: [escalation()] })
    vi.spyOn(client, 'post').mockResolvedValue({
      data: escalation({ delivery_attempts: 2 }),
    } as AxiosResponse)
    const user = await openFirstRequest()

    await user.click(screen.getByRole('button', { name: 'Retry delivery' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Delivery was retried and failed again.')
  })

  it("shows the server's reason when a retry is refused", async () => {
    mockApi({ open: [escalation()] })
    vi.spyOn(client, 'post').mockRejectedValue(
      axiosError(409, { detail: 'Maximum delivery attempts reached.' }),
    )
    const user = await openFirstRequest()

    await user.click(screen.getByRole('button', { name: 'Retry delivery' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Maximum delivery attempts reached.')
  })

  it('labels a request with no webhook and offers no retry', async () => {
    mockApi({
      open: [
        escalation({
          delivery_status: 'not_configured',
          delivery_attempts: 0,
          delivery_last_attempt_at: null,
          delivery_retryable: false,
        }),
      ],
    })
    await openFirstRequest()

    expect(screen.getByText('No webhook configured')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Retry delivery|Send to webhook/ })).not.toBeInTheDocument()
  })

  it('explains the attempt limit instead of offering a retry that cannot send', async () => {
    mockApi({ open: [escalation({ delivery_attempts: 5, delivery_retryable: false })] })
    await openFirstRequest()

    expect(screen.getByText(/failed after 5 attempts, the most the server allows/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retry delivery' })).not.toBeInTheDocument()
  })

  it('sends a request that was filed before a webhook was configured', async () => {
    mockApi({ open: [escalation({ delivery_status: 'pending', delivery_attempts: 0 })] })
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: escalation({ delivery_status: 'delivered', delivery_attempts: 1, delivery_retryable: false }),
    } as AxiosResponse)
    const user = await openFirstRequest()

    expect(screen.getByText('This request has not been sent to the HR webhook yet.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Send to webhook' }))

    expect(post).toHaveBeenCalledWith('/api/escalations/esc-1/retry-delivery')
    expect(await screen.findByText('Delivered')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('resolves with the trimmed note and returns to the refreshed list', async () => {
    const get = mockApi({ open: [escalation()] })
    const patch = vi.spyOn(client, 'patch').mockResolvedValue({
      data: escalation({ status: 'resolved' }),
    } as AxiosResponse)
    const user = await openFirstRequest()

    await user.type(screen.getByLabelText('Resolution note'), '  Not covered; told them.  ')
    await user.click(screen.getByRole('button', { name: 'Resolve request' }))

    expect(patch).toHaveBeenCalledWith('/api/escalations/esc-1', {
      status: 'resolved',
      resolution: 'Not covered; told them.',
    })
    await waitFor(() => expect(location()).toBe('/escalations'))
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
    // The list refetch only: the resolved request is not fetched again by id.
    expect(get).not.toHaveBeenCalledWith('/api/escalations/esc-1')
  })

  it('keeps the resolution draft to the request it was typed for', async () => {
    mockApi({ open: [escalation(), second] })
    const user = await openFirstRequest()
    await user.type(screen.getByLabelText('Resolution note'), 'Half written')

    await user.click(screen.getByRole('button', { name: 'All requests' }))
    await user.click(await screen.findByRole('button', { name: /sabbatical/ }))

    expect(screen.getByLabelText('Resolution note')).toHaveValue('')
  })

  it("shows the server's reason when a reopen fails", async () => {
    mockApi({ resolved: [escalation({ status: 'resolved', resolution: 'Done.', delivery_status: 'delivered', delivery_retryable: false })] })
    vi.spyOn(client, 'patch').mockRejectedValue(axiosError(404, { detail: 'Escalation not found.' }))
    const user = renderPage('/escalations?status=resolved&id=esc-1')

    expect(await screen.findByText('Done.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reopen request' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Escalation not found.')
  })

  describe('while a resolve or its refetch is in flight', () => {
    it('keeps the resolved request out of the list until the refetch lands', async () => {
      const refetch = deferred<AxiosResponse>()
      const get = vi.spyOn(client, 'get')
        .mockResolvedValueOnce(listResponse([escalation(), second]))
        .mockReturnValueOnce(refetch.promise)
      vi.spyOn(client, 'patch').mockResolvedValue({ data: escalation({ status: 'resolved' }) } as AxiosResponse)
      const user = await openFirstRequest()

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      await waitFor(() => expect(location()).toBe('/escalations'))
      expect(screen.queryByRole('button', { name: /pet insurance/ })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /sabbatical/ })).toBeInTheDocument()
      expect(screen.getByText('1 open')).toBeInTheDocument()

      await act(async () => refetch.resolve(listResponse([second])))
      expect(screen.queryByRole('button', { name: /pet insurance/ })).not.toBeInTheDocument()
      expect(byIdCalls(get)).toHaveLength(0)
    })

    it('in two panes, does not reselect or refetch the only request after resolving it', async () => {
      stubTwoPane()
      const refetch = deferred<AxiosResponse>()
      const get = vi.spyOn(client, 'get')
        .mockResolvedValueOnce(listResponse([escalation()]))
        .mockReturnValueOnce(refetch.promise)
      vi.spyOn(client, 'patch').mockResolvedValue({ data: escalation({ status: 'resolved' }) } as AxiosResponse)
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      await waitFor(() => expect(location()).toBe('/escalations'))
      expect(screen.getByText('0 open')).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: /pet insurance/ })).not.toBeInTheDocument()

      await act(async () => refetch.resolve(listResponse([])))
      expect(location()).toBe('/escalations')
      expect(screen.getByText('Nothing to review.')).toBeInTheDocument()
      expect(byIdCalls(get)).toHaveLength(0)
    })

    it('in two panes, opens the next request before the refetch lands', async () => {
      stubTwoPane()
      const refetch = deferred<AxiosResponse>()
      vi.spyOn(client, 'get')
        .mockResolvedValueOnce(listResponse([escalation(), second]))
        .mockReturnValueOnce(refetch.promise)
      vi.spyOn(client, 'patch').mockResolvedValue({ data: escalation({ status: 'resolved' }) } as AxiosResponse)
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))

      await waitFor(() => expect(location()).toBe('/escalations?id=esc-2'))
      expect(screen.getByRole('heading', { name: /sabbatical/ })).toBeInTheDocument()
    })

    it('keeps a tab switch made while the resolve was pending', async () => {
      stubTwoPane()
      mockApi({ open: [escalation(), second], resolved: [closed] })
      const patch = deferred<AxiosResponse>()
      vi.spyOn(client, 'patch').mockReturnValue(patch.promise)
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))
      await user.click(screen.getByRole('button', { name: 'Resolved' }))
      await waitFor(() => expect(location()).toBe('/escalations?status=resolved&id=esc-r'))

      await act(async () => patch.resolve({ data: escalation({ status: 'resolved' }) } as AxiosResponse))
      expect(location()).toBe('/escalations?status=resolved&id=esc-r')
      expect(screen.getByRole('heading', { name: 'Who approves remote work?' })).toBeInTheDocument()
    })

    it('keeps a row picked while the resolve was pending, and shows that row idle', async () => {
      stubTwoPane()
      const get = mockApi({ open: [escalation(), second, third] })
      const patch = deferred<AxiosResponse>()
      vi.spyOn(client, 'patch').mockReturnValue(patch.promise)
      const user = renderPage()
      await screen.findByRole('heading', { name: /pet insurance/ })

      await user.type(screen.getByLabelText('Resolution note'), 'Told them.')
      await user.click(screen.getByRole('button', { name: 'Resolve request' }))
      await user.click(screen.getByRole('button', { name: /carry over/ }))
      expect(screen.getByRole('button', { name: 'Resolve request' })).toBeInTheDocument()
      expect(screen.queryByText('Resolving…')).not.toBeInTheDocument()

      // The server has closed esc-1, so the refetch no longer returns it.
      get.mockImplementation(async (url) =>
        url === '/api/escalations' ? listResponse([second, third]) : listResponse([]),
      )
      await act(async () => patch.resolve({ data: escalation({ status: 'resolved' }) } as AxiosResponse))
      expect(location()).toBe('/escalations?id=esc-3')
      expect(screen.queryByRole('button', { name: /pet insurance/ })).not.toBeInTheDocument()
    })
  })

  it('reopens a resolved request and returns to the resolved list', async () => {
    const get = mockApi({ resolved: [closed] })
    const patch = vi.spyOn(client, 'patch').mockImplementation(async () => {
      get.mockImplementation(async () => listResponse([]))
      return { data: { ...closed, status: 'open' } } as AxiosResponse
    })
    const user = renderPage('/escalations?status=resolved&id=esc-r')

    await user.click(await screen.findByRole('button', { name: 'Reopen request' }))

    expect(patch).toHaveBeenCalledWith('/api/escalations/esc-r', { status: 'open' })
    await waitFor(() => expect(location()).toBe('/escalations?status=resolved'))
    expect(screen.getByText('0 resolved')).toBeInTheDocument()
  })

  it('fetches a linked request by id exactly once', async () => {
    const get = mockApi({ open: [escalation()], byId: { 'esc-9': escalation({ escalation_id: 'esc-9', question: 'Old one?' }) } })
    renderPage('/escalations?id=esc-9')
    await screen.findByRole('heading', { name: 'Old one?' })
    await act(async () => {})
    expect(byIdCalls(get)).toHaveLength(1)
  })

  it('offers a retry when a linked request fails to load for a reason other than 404', async () => {
    const get = vi.spyOn(client, 'get').mockImplementation(async (url) => {
      if (url === '/api/escalations') return listResponse([escalation()])
      throw axiosError(500, { detail: 'boom' })
    })
    const user = renderPage('/escalations?id=esc-9')

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load this request.')
    expect(screen.queryByText('That request was not found.')).not.toBeInTheDocument()

    get.mockImplementation(async (url) =>
      url === '/api/escalations'
        ? listResponse([escalation()])
        : ({ data: escalation({ escalation_id: 'esc-9', question: 'Old one?' }) } as AxiosResponse),
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Old one?' })).toBeInTheDocument()
  })

  it('in two panes, re-clicking the open row keeps its draft', async () => {
    stubTwoPane()
    mockApi({ open: [escalation(), second] })
    const user = renderPage()
    await screen.findByRole('heading', { name: /pet insurance/ })
    await user.type(screen.getByLabelText('Resolution note'), 'Half written')

    await user.click(screen.getByRole('button', { name: /pet insurance/ }))

    expect(screen.getByLabelText('Resolution note')).toHaveValue('Half written')
    expect(location()).toBe('/escalations?id=esc-1')
  })

  it('in two panes, switching tabs closes the open request', async () => {
    stubTwoPane()
    mockApi({ open: [escalation()], resolved: [closed] })
    const user = renderPage()
    await screen.findByRole('heading', { name: /pet insurance/ })

    await user.click(screen.getByRole('button', { name: 'Resolved' }))

    await waitFor(() => expect(location()).toBe('/escalations?status=resolved&id=esc-r'))
    expect(screen.getByRole('heading', { name: 'Who approves remote work?' })).toBeInTheDocument()
  })

  it('offers a retry when the list fails to load', async () => {
    const get = vi.spyOn(client, 'get').mockRejectedValue(new Error('network'))
    const user = renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load HR requests.')
    get.mockResolvedValue({ data: { items: [escalation()], total: 1 } } as AxiosResponse)
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('button', { name: /pet insurance/ })).toBeInTheDocument()
  })

  it('says who the page is for when the session is not HR', async () => {
    vi.spyOn(client, 'get').mockRejectedValue(axiosError(403, { detail: 'Human Resources sign-in required.' }))
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This page is for Human Resources. Sign out and sign in with the HR password to see it.',
    )
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Filter by status' })).not.toBeInTheDocument()
  })
})
