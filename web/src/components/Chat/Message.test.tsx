import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { AxiosResponse } from 'axios'
import client from '../../api/client'
import Message from './Message'
import type { ChatMessage } from '../../hooks/useChat'

function renderMessage(message: ChatMessage, overrides: Record<string, unknown> = {}) {
  return render(
    <MemoryRouter>
      <Message
        message={message}
        index={1}
        sessionId="sess-1"
        isLast
        isStreaming={false}
        activeSource={null}
        onOpenSource={vi.fn()}
        onFollowUp={vi.fn()}
        onEscalated={vi.fn()}
        {...overrides}
      />
    </MemoryRouter>,
  )
}

describe('Message', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('renders a user question', () => {
    renderMessage({ role: 'user', content: 'How much PTO do I get?' }, { index: 0 })
    expect(screen.getByText('Question')).toBeInTheDocument()
    expect(screen.getByText('How much PTO do I get?')).toBeInTheDocument()
  })

  it('shows the refusal card and Ask Human Resources action', async () => {
    const user = userEvent.setup()
    renderMessage({
      role: 'assistant',
      content: 'I cannot answer that from the indexed policies.',
      refused: true,
      confidence: 41,
      message_id: 'm-ref',
    })

    expect(screen.getByText('No matching policy')).toBeInTheDocument()
    expect(screen.getByText('I cannot answer that from the indexed policies.')).toBeInTheDocument()
    expect(
      screen.getByText(/Nothing indexed came close enough to answer from/),
    ).toBeInTheDocument()

    const indexed = screen.getByRole('link', { name: 'See what is indexed' })
    expect(indexed).toHaveAttribute('href', '/documents')

    await user.click(screen.getByRole('button', { name: 'Ask Human Resources' }))
    expect(screen.getByRole('heading', { name: 'Send to Human Resources' })).toBeInTheDocument()
  })

  it('keeps the no-match wording and score for a similarity refusal', () => {
    renderMessage({
      role: 'assistant',
      content: 'I cannot answer that from the indexed policies.',
      refused: true,
      refusal_reason: 'no_match',
      confidence: 59,
      message_id: 'm-ref',
    })

    expect(screen.getByText('No matching policy')).toBeInTheDocument()
    expect(screen.getByText(/Nothing indexed came close enough/)).toBeInTheDocument()
    expect(screen.getByText('Partial match')).toBeInTheDocument()
  })

  // Issue #269: the judge refuses questions that cleared the similarity
  // threshold, so "nothing came close" and a "Strong match" meter are both wrong.
  it('says related policies do not answer it when the coverage judge refused', () => {
    renderMessage({
      role: 'assistant',
      content: 'I cannot answer that from the indexed policies.',
      refused: true,
      refusal_reason: 'not_covered',
      confidence: 79,
      message_id: 'm-judge',
    })

    expect(screen.getByText('Not answered by any policy')).toBeInTheDocument()
    expect(
      screen.getByText(/Some policies mention related topics, but none of them answers this question as asked/),
    ).toBeInTheDocument()
    // A vague question on a covered topic lands here too, so the card says
    // what to do next.
    expect(screen.getByText(/ask the full question again with them/)).toBeInTheDocument()
    expect(screen.queryByText('No matching policy')).not.toBeInTheDocument()
    expect(screen.queryByText(/Nothing indexed came close/)).not.toBeInTheDocument()
    expect(screen.queryByText('Strong match')).not.toBeInTheDocument()
    expect(screen.queryByText(/79%/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask Human Resources' })).toBeInTheDocument()
  })

  it('forwards a refusal escalation id to the parent', async () => {
    const user = userEvent.setup()
    const onEscalated = vi.fn()
    vi.spyOn(client, 'post').mockResolvedValue({
      data: { escalation_id: 'esc-ref' },
    } as AxiosResponse)
    renderMessage(
      {
        role: 'assistant',
        content: 'I cannot answer that from the indexed policies.',
        refused: true,
        message_id: 'm-ref',
      },
      { onEscalated },
    )
    await user.click(screen.getByRole('button', { name: 'Ask Human Resources' }))
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(onEscalated).toHaveBeenCalledWith(1, 'esc-ref')
  })

  it('renders an answer with sources, follow-ups, and the quiet escalate link', () => {
    const onFollowUp = vi.fn()
    const onOpenSource = vi.fn()
    renderMessage(
      {
        role: 'assistant',
        content: 'Employees receive **15 days** of PTO.',
        sources: ['PTO Policy'],
        confidence: 82,
        follow_ups: ['How do I request time off?'],
        message_id: 'm-1',
      },
      { onFollowUp, onOpenSource },
    )

    expect(screen.getByText('15 days', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PTO Policy' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ask Human Resources/ })).toBeInTheDocument()
    expect(screen.getByText('How do I request time off?')).toBeInTheDocument()
  })

  it('forwards an unhelpful-answer escalation id to the parent', async () => {
    const user = userEvent.setup()
    const onEscalated = vi.fn()
    vi.spyOn(client, 'post').mockResolvedValue({
      data: { escalation_id: 'esc-ans' },
    } as AxiosResponse)
    renderMessage(
      {
        role: 'assistant',
        content: 'Employees receive 15 days of PTO.',
        message_id: 'm-1',
      },
      { onEscalated },
    )
    await user.click(screen.getByRole('button', { name: /Ask Human Resources/ }))
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(onEscalated).toHaveBeenCalledWith(1, 'esc-ans')
  })

  it('hides metadata while tokens are still arriving', () => {
    renderMessage(
      { role: 'assistant', content: 'Employees receive' },
      { isStreaming: true },
    )
    expect(screen.queryByRole('button', { name: /Ask Human Resources/ })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Sources')).not.toBeInTheDocument()
  })

  it('does not offer escalation on a client-only error bubble', () => {
    renderMessage({
      role: 'assistant',
      content: 'Sorry, something went wrong. Please try again.',
      error: true,
    })
    expect(screen.queryByRole('button', { name: /Ask Human Resources/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Retry/ })).not.toBeInTheDocument()
  })

  it('shows Retry for an eligible provider-busy error when it is last', () => {
    const onRetry = vi.fn()
    renderMessage(
      {
        role: 'assistant',
        content: 'The assistant is answering as many questions as it can right now. Please try again in a moment.',
        error: true,
        retryable: true,
        retryAfter: 0,
      },
      { isLast: true, onRetry },
    )
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('suppresses Retry for an eligible provider-busy error when it is not last', () => {
    const onRetry = vi.fn()
    renderMessage(
      {
        role: 'assistant',
        content: 'The assistant is answering as many questions as it can right now. Please try again in a moment.',
        error: true,
        retryable: true,
        retryAfter: 0,
      },
      { isLast: false, onRetry },
    )
    expect(screen.queryByRole('button', { name: /Retry/ })).not.toBeInTheDocument()
  })

  it('does not offer Retry on ordinary errors even when last', () => {
    renderMessage(
      {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        error: true,
      },
      { isLast: true, onRetry: vi.fn() },
    )
    expect(screen.queryByRole('button', { name: /Retry/ })).not.toBeInTheDocument()
  })

  it('holds the retry control until Retry-After elapses', async () => {
    vi.useFakeTimers()
    const onRetry = vi.fn()
    renderMessage(
      {
        role: 'assistant',
        content: 'The assistant is answering as many questions as it can right now. Please try again in a moment.',
        error: true,
        retryable: true,
        retryAfter: 2,
      },
      { onRetry },
    )

    expect(screen.getByRole('button', { name: 'Retry in 2s' })).toBeDisabled()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(screen.getByRole('button', { name: 'Retry in 1s' })).toBeDisabled()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    const retry = screen.getByRole('button', { name: 'Retry' })
    expect(retry).toBeEnabled()
    retry.click()
    expect(onRetry).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })
})
