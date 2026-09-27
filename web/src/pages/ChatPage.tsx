/**
 * ChatPage — ask a question, read the answer beside its source.
 *
 * Home (no session): one large question box, example questions, and what is
 * indexed: a strip under the examples, or, when the page is wide enough for
 * the source pane to dock, a facing page in the pane's slot so the book has
 * two pages before anything is cited. Thread (session): the Q&A column with a composer
 * for follow-ups that flows after the last answer and pins to the bottom once
 * the thread is taller than the view, and a source pane that opens when a
 * citation is clicked. The reading column is anchored to the left so the pane
 * takes the right margin and the answer never reflows; it docks when there is
 * room and slides over the thread when there is not.
 *
 * session_id lives in the URL (?session_id=uuid). When a new conversation is
 * created (first message sent), useChat calls onSessionCreated which updates the URL.
 */
import { useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Dialog, DialogBackdrop, DialogPanel } from '@headlessui/react'
import { BookOpen } from 'lucide-react'
import { APP_HEADLINE, APP_TAGLINE } from '../config'
import { useChat } from '../hooks/useChat'
import { useContainerWidth } from '../hooks/useContainerWidth'
import { useLibrarySummary } from '../hooks/useLibrarySummary'
import { READING_COLUMN, READING_GUTTER } from '../lib/layout'
import MessageList from '../components/Chat/MessageList'
import ChatInput from '../components/Chat/ChatInput'
import QuestionList from '../components/Chat/QuestionList'
import IndexedPage from '../components/Chat/IndexedPage'
import SourcePane from '../components/Documents/SourcePane'

const STARTER_PROMPTS = [
  'How many PTO days do I get in my first year?',
  'How long do I have to enroll in benefits after starting?',
  'How much does the company match on my 401(k)?',
  'What is the meal limit when travelling for work?',
]

/** Docked pane width. */
const PANE_WIDTH = 368
/** Left gutter + reading column + right gutter: the left page, as wide as the thread's when the pane is docked. */
const LEFT_PAGE_WIDTH = 48 + 720 + 24
/** Left page + pane: the room the home page's facing page needs without touching the column. */
const FACING_PAGE_MIN_WIDTH = LEFT_PAGE_WIDTH + PANE_WIDTH
/**
 * The narrowest the answer column may go to keep the pane docked. Below the
 * full 720 the column simply flexes; below this it would stop reading well, so
 * the pane slides over the thread instead. A window that is 1320 wide with
 * the sidebar open lands between the two limits, which is why the pane used
 * to turn into a dimmed dialog there while the same window docked it with
 * the sidebar collapsed.
 */
const MIN_READING_COLUMN = 560
/** Gutters + narrowest column + pane: the room the docked pane needs beside a thread. */
const DOCK_MIN_WIDTH = 48 + MIN_READING_COLUMN + 24 + PANE_WIDTH

interface HomeProps {
  onAsk: (question: string) => void
  busy: boolean
  /** Wide enough for the facing page; null until the page has been measured. */
  docked: boolean | null
  /** The conversation in the URL was not this browser's; say why the chat is empty. */
  missing: boolean
}

function Home({ onAsk, busy, docked, missing }: HomeProps) {
  const library = useLibrarySummary()

  return (
    <>
      {/* With the facing page up, the left page keeps the thread's width so the
          spine sits where the docked source pane's edge will. */}
      <div
        className={`min-h-0 overflow-y-auto ${docked ? 'shrink-0' : 'min-w-0 flex-1'}`}
        style={docked ? { width: LEFT_PAGE_WIDTH } : undefined}
      >
        <div className={`${docked ? 'pr-6 pl-12' : READING_GUTTER} pt-10 pb-16 sm:pt-[12vh] sm:pb-20`}>
          <div className={`${READING_COLUMN} flex flex-col gap-10`}>
            <header className="flex flex-col gap-2">
              <h1 className="font-display text-[32px] leading-[1.1] font-medium tracking-tight text-ink sm:text-[40px]">
                {APP_HEADLINE}
              </h1>
              <p className="max-w-130 text-[15px] leading-normal text-ink-2 sm:text-[16px]">{APP_TAGLINE}</p>
            </header>

            {missing && (
              <p role="status" className="max-w-130 text-[14px] leading-normal text-ink-2">
                That conversation isn't available in this browser. Conversations stay with
                the browser that started them, so this is a new chat.
              </p>
            )}

            <ChatInput variant="hero" onSend={onAsk} disabled={busy} />

            <QuestionList label="Try one of these" questions={STARTER_PROMPTS} onSelect={onAsk} disabled={busy} columns={2} />

            {docked === false && library.total != null && (
              <section className="flex flex-col gap-3 border-y border-rule py-4" aria-labelledby="indexed-heading">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <h2 id="indexed-heading" className="text-[14px] font-medium text-ink">
                    <span className="tnum">{library.total}</span> polic{library.total === 1 ? 'y' : 'ies'} indexed
                  </h2>
                  <Link
                    to="/documents"
                    className="inline-flex items-center gap-1.5 text-[13px] text-accent underline-offset-3 hover:text-accent-ink hover:underline"
                  >
                    <BookOpen size={14} aria-hidden="true" />
                    Browse the library
                  </Link>
                </div>
                {library.categories.length > 0 && (
                  <ul className="flex flex-wrap gap-1.5" aria-label="Categories">
                    {library.categories.map((category) => (
                      <li key={category}>
                        <Link
                          to={`/documents?category=${encodeURIComponent(category)}`}
                          className="inline-flex h-7 items-center rounded-full border border-rule bg-paper-3 px-3 text-[12.5px] text-ink-2 transition-colors hover:border-ink-3 hover:text-ink"
                        >
                          {category}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
          </div>
        </div>
      </div>

      {docked && (
        <aside className="min-w-0 flex-1 overflow-y-auto border-l border-rule" aria-labelledby="library-heading">
          <IndexedPage library={library} />
        </aside>
      )}
    </>
  )
}

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id')
  const { ref: pageRef, width: pageWidth } = useContainerWidth<HTMLDivElement>()
  // The observer's first callback sets the width; until then neither the strip
  // nor the facing page renders, so nothing jumps between them.
  const measured = pageWidth > 0
  const docked = pageWidth >= DOCK_MIN_WIDTH
  const facingPage = pageWidth >= FACING_PAGE_MIN_WIDTH

  // Says why a link opened an empty chat, until a conversation is open again.
  const [missing, setMissing] = useState(false)

  const { messages, loading, streaming, sendMessage, retryLastQuestion, markEscalated } = useChat({
    sessionId,
    onSessionCreated: (id) => {
      // Update the URL with the new session_id without re-mounting the component
      setSearchParams({ session_id: id }, { replace: true })
    },
    onSessionMissing: () => {
      // Drop the dead id so the next question starts a new conversation.
      setSearchParams({}, { replace: true })
      setMissing(true)
    },
  })

  // The open source belongs to one conversation. Switching conversations
  // closes it during the same render, the same way useChat clears messages.
  const [activeSource, setActiveSource] = useState<string | null>(null)
  const [sourceSessionId, setSourceSessionId] = useState(sessionId)
  if (sessionId !== sourceSessionId) {
    setSourceSessionId(sessionId)
    setActiveSource(null)
    if (sessionId) setMissing(false)
  }

  // The chip that opened the pane. The slide-over is a Dialog and restores
  // focus on its own; the docked pane is a plain aside, so without this a
  // keyboard user who closes it lands on body and Tabs from the top again.
  const openerRef = useRef<HTMLElement | null>(null)
  const openSource = (title: string) => {
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setActiveSource((current) => (current === title ? null : title))
  }
  const closeSource = () => {
    setActiveSource(null)
    const opener = openerRef.current
    if (docked && opener?.isConnected) opener.focus()
  }

  const hasMessages = messages.length > 0
  const busy = loading || streaming

  if (!hasMessages) {
    return (
      <div ref={pageRef} className="relative flex min-h-0 flex-1">
        <Home onAsk={sendMessage} busy={busy} docked={measured ? facingPage : null} missing={missing} />
      </div>
    )
  }

  return (
    <div ref={pageRef} className="relative flex min-h-0 flex-1">
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        {/* Narrower right gutter than the home page: the docked pane owes the column its full measure. */}
        <div className="pr-5 pl-5 sm:pr-6 sm:pl-12">
          <div className={READING_COLUMN}>
            <MessageList
              messages={messages}
              sessionId={sessionId}
              loading={loading}
              streaming={streaming}
              activeSource={activeSource}
              onOpenSource={openSource}
              onFollowUp={sendMessage}
              onEscalated={markEscalated}
              onRetry={retryLastQuestion}
            />
            {/* Flows after the thread, pins to the bottom once the thread is taller than the view. */}
            <div className="sticky bottom-0 z-10 bg-paper pb-5 before:pointer-events-none before:absolute before:inset-x-0 before:-top-6 before:h-6 before:bg-linear-to-t before:from-paper before:to-transparent">
              <ChatInput onSend={sendMessage} disabled={busy} />
            </div>
          </div>
        </div>
      </div>

      {activeSource && docked && (
        <aside className="shrink-0 border-l border-rule" style={{ width: PANE_WIDTH }}>
          <SourcePane title={activeSource} onClose={closeSource} />
        </aside>
      )}

      {/* Over the thread it is a dialog: focus moves in, Tab stays in, Escape and
          the backdrop close it, and focus returns to the chip that opened it. */}
      {activeSource && !docked && (
        <Dialog open onClose={closeSource} aria-label="Source" className="relative z-40">
          <DialogBackdrop className="fixed inset-0 bg-ink/35" />
          <DialogPanel className="fixed inset-y-0 right-0 w-full max-w-105 shadow-drawer">
            <SourcePane title={activeSource} onClose={closeSource} modal />
          </DialogPanel>
        </Dialog>
      )}
    </div>
  )
}
