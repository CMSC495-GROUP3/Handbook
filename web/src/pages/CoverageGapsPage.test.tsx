import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AxiosError, type AxiosResponse } from 'axios'
import client from '../api/client'
import type { CoverageReport } from '../types'
import CoverageGapsPage from './CoverageGapsPage'

function report(overrides: Partial<CoverageReport> = {}): CoverageReport {
  return {
    since: '2026-08-27T00:00:00+00:00',
    until: '2026-09-26T00:00:00+00:00',
    days: 30,
    total: 412,
    refused: 37,
    gaps: [
      { question_hash: 'pet', question: 'Does the company pay for pet insurance?', count: 6, conversations: 4 },
      { question_hash: 'blank', question: null, count: 1, conversations: 1 },
    ],
    faq: [
      { question_hash: 'pto', question: 'How much PTO do I get?', count: 19, conversations: 12, refused: 2 },
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

  it('marks the page as Human Resources only', async () => {
    vi.spyOn(client, 'get').mockResolvedValue(ok(report()))
    renderPage()

    const heading = screen.getByRole('heading', { level: 1, name: 'What People Ask' })
    expect(heading.parentElement).toHaveTextContent('HR only')
    expect(screen.getByText(/Only Human Resources can open this page/)).toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Not answered yet' })).toBeInTheDocument()
  })

  it('tells a session without the HR password who the page is for', async () => {
    const forbidden = new AxiosError('Forbidden', 'ERR_BAD_REQUEST', undefined, undefined, {
      status: 403,
    } as AxiosResponse)
    vi.spyOn(client, 'get').mockRejectedValue(forbidden)
    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This page is for Human Resources. Sign out and sign in with the HR password to see it.',
    )
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Time window' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Only Human Resources can open this page/)).not.toBeInTheDocument()
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
})
