import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import type { AxiosResponse } from 'axios'
import client from '../api/client'
import type { CoverageReport, QuestionGroup } from '../types'
import CoverageGapsPage from './CoverageGapsPage'

function group(fields: Pick<QuestionGroup, 'question_hash' | 'question' | 'count'> & Partial<QuestionGroup>): QuestionGroup {
  return { conversations: fields.count, other_wordings: [], other_wording_count: 0, ...fields }
}

function report(overrides: Partial<CoverageReport> = {}): CoverageReport {
  return {
    since: '2026-08-27T00:00:00+00:00',
    until: '2026-09-26T00:00:00+00:00',
    days: 30,
    grouping: 'meaning',
    total: 412,
    refused: 37,
    gaps: [
      group({ question_hash: 'pet', question: 'Does the company pay for pet insurance?', count: 6, conversations: 4 }),
      group({ question_hash: 'blank', question: null, count: 1, conversations: 1 }),
    ],
    faq: [
      { ...group({ question_hash: 'pto', question: 'How much PTO do I get?', count: 19, conversations: 12 }), refused: 2 },
    ],
    ...overrides,
  }
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="search">{location.search}</output>
}

function renderPage(url = '/gaps') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route
          path="/gaps"
          element={
            <>
              <CoverageGapsPage />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

const ok = (data: CoverageReport) => ({ data }) as AxiosResponse

describe('CoverageGapsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the refused share and both ranked lists', async () => {
    vi.spyOn(client, 'get').mockResolvedValue(ok(report()))
    renderPage()

    expect(await screen.findByText(/had no policy to answer them \(9%\)/)).toBeInTheDocument()

    const gaps = screen.getByRole('list', { name: 'Not answered yet' })
    const gapRows = within(gaps).getAllByRole('listitem')
    expect(gapRows).toHaveLength(2)
    expect(gapRows[0]).toHaveTextContent('Does the company pay for pet insurance?')
    expect(gapRows[0]).toHaveTextContent('Asked 6 times in 4 conversations')
    expect(gapRows[1]).toHaveTextContent('No question text was logged')
    expect(gapRows[1]).toHaveTextContent('Asked once in 1 conversation')

    const faq = screen.getByRole('list', { name: 'Asked most' })
    expect(faq).toHaveTextContent('Asked 19 times in 12 conversations · 2 not answered')
  })

  it('asks for 30 days by default and switches window through the URL', async () => {
    const get = vi.spyOn(client, 'get').mockImplementation((_url, config) =>
      Promise.resolve(ok(report({ days: (config?.params as { days: number }).days }))),
    )
    renderPage()
    await screen.findByText(/last 30 days/)
    expect(get).toHaveBeenLastCalledWith('/api/reports/gaps', { params: { days: 30 } })

    await userEvent.click(screen.getByRole('button', { name: '7 days' }))

    expect(await screen.findByText(/last 7 days/)).toBeInTheDocument()
    expect(get).toHaveBeenLastCalledWith('/api/reports/gaps', { params: { days: 7 } })
    expect(screen.getByTestId('search')).toHaveTextContent('?days=7')
    expect(screen.getByRole('button', { name: '7 days' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('ignores a ?days= value that is not one of the windows', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue(ok(report()))
    renderPage('/gaps?days=365')
    await screen.findByText(/last 30 days/)
    expect(get).toHaveBeenCalledWith('/api/reports/gaps', { params: { days: 30 } })
  })

  it('presses the window the server ran when it shortened the request', async () => {
    vi.spyOn(client, 'get').mockResolvedValue(ok(report({ days: 7 })))
    renderPage('/gaps?days=90')

    expect(await screen.findByText(/keeps 7 days of questions/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '7 days' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '90 days' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('says so when the lists are empty', async () => {
    vi.spyOn(client, 'get').mockResolvedValue(ok(report({ total: 0, refused: 0, gaps: [], faq: [] })))
    renderPage()

    expect(await screen.findByText('No questions were asked in the last 30 days.')).toBeInTheDocument()
    expect(screen.getByText('Every question in this window had a policy to answer it.')).toBeInTheDocument()
    expect(screen.getByText('No question came up in more than one conversation in this window.')).toBeInTheDocument()
  })

  it('offers a retry after a failed load', async () => {
    const get = vi
      .spyOn(client, 'get')
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue(ok(report()))
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load this report.')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Not answered yet' })).toBeInTheDocument()
    expect(get).toHaveBeenCalledTimes(2)
  })
  it('lists the other wordings of a grouped question behind a disclosure', async () => {
    const grouped = group({
      question_hash: 'pto',
      question: 'How much PTO do I get?',
      count: 9,
      other_wordings: [
        { question: 'How many vacation days do I have?', count: 3 },
        { question: 'what is my pto balance', count: 1 },
      ],
      other_wording_count: 4,
    })
    vi.spyOn(client, 'get').mockResolvedValue(ok(report({ gaps: [grouped], faq: [] })))
    renderPage()

    const summary = await screen.findByText('Also asked as 4 other wordings')
    expect(screen.getByText('How many vacation days do I have?')).not.toBeVisible()

    await userEvent.click(summary)

    expect(screen.getByText('How many vacation days do I have?')).toBeVisible()
    expect(screen.getByText('and 2 more')).toBeInTheDocument()
  })

  it('says so when grouping fell back to exact wording', async () => {
    vi.spyOn(client, 'get').mockResolvedValue(ok(report({ grouping: 'exact' })))
    renderPage()

    expect(await screen.findByText(/Grouping by meaning is unavailable/)).toBeInTheDocument()
    // The captions must not promise merged wordings while grouping is off.
    expect(screen.queryByText(/Near-identical wordings share a row/)).not.toBeInTheDocument()
    expect(screen.getAllByText(/Each wording has its own row/)).toHaveLength(2)
  })
})
