/**
 * CoverageGapsPage, shown as "What People Ask": what employees asked that no
 * policy answered, and what they ask most. Both lists come from the query log
 * through GET /api/reports/gaps; nothing here identifies who asked.
 *
 * The copy says "not answered", as the chat's refusal card does ("Not answered
 * by any policy"), never "refused": the cause is a missing document, which HR
 * can write. The not-answered list is ochre, the refusal card's color. The
 * Asked most bars are green for answered asks with the not-answered share in
 * ochre at the end.
 *
 * ?days= picks the window (30 by default) so a link reproduces the view.
 */
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getCoverageReport } from '../api/reports'
import { READING_COLUMN, READING_GUTTER } from '../lib/layout'
import type { CoverageReport, QuestionGroup } from '../types'

const WINDOWS = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
]
const DEFAULT_DAYS = 30

/** What the last fetch returned, and for which window. */
interface ReportState {
  days: number
  report: CoverageReport | null
}

function readDays(value: string | null): number {
  const days = Number(value)
  return WINDOWS.some((option) => option.days === days) ? days : DEFAULT_DAYS
}

function plural(count: number, word: string): string {
  return `${count.toLocaleString()} ${word}${count === 1 ? '' : 's'}`
}

/** "Asked once", "Asked 12 times". */
function asked(count: number): string {
  return count === 1 ? 'Asked once' : `Asked ${count.toLocaleString()} times`
}

/** "Asked once in 1 conversation", "Asked 12 times in 7 conversations". */
function timesAsked(group: QuestionGroup): string {
  return `${asked(group.count)} in ${plural(group.conversations, 'conversation')}`
}

function QuestionText({ group }: { group: QuestionGroup }) {
  if (group.question) return <>{group.question}</>
  return <span className="text-ink-3 italic">No question text was logged</span>
}

/** The other wordings under a question, behind a disclosure. */
function OtherWordings({ group }: { group: QuestionGroup }) {
  if (group.other_wording_count === 0) return null
  const unlisted = group.other_wording_count - group.other_wordings.length
  return (
    <details className="mt-2 text-[13px] text-ink-2">
      <summary className="w-fit cursor-pointer rounded-sm text-ink-3 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        Also asked as {plural(group.other_wording_count, 'other wording')}
      </summary>
      <ul className="mt-1.5 flex flex-col gap-1 border-l border-rule pl-3">
        {group.other_wordings.map((wording, index) => (
          <li key={index} className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
            <span>{wording.question ?? <span className="italic">No question text was logged</span>}</span>
            <span className="tnum text-[12px] text-ink-3 sm:shrink-0">{asked(wording.count)}</span>
          </li>
        ))}
        {unlisted > 0 && <li className="text-ink-3">and {unlisted.toLocaleString()} more</li>}
      </ul>
    </details>
  )
}

/**
 * A bar as long as `size` is against the list's largest, so its length follows
 * the ranking. The green and ochre split is over asks: `refused` of `count`.
 */
function Bar({ size, max, count, refused }: { size: number; max: number; count: number; refused: number }) {
  const answered = count - refused
  return (
    <span aria-hidden="true" className="mt-2 flex h-1 overflow-hidden rounded-full bg-rule/60">
      <span className="flex h-full" style={{ width: `${(size / max) * 100}%` }}>
        {answered > 0 && <span className="h-full bg-accent" style={{ flexGrow: answered }} />}
        {refused > 0 && <span className="h-full bg-ochre" style={{ flexGrow: refused }} />}
      </span>
    </span>
  )
}

interface Row {
  group: QuestionGroup
  /** What the list ranks on, and so what sets the bar's length. */
  size: number
  refused: number
  meta: string
}

function RankedList({ rows, label }: { rows: Row[]; label: string }) {
  const max = Math.max(...rows.map((row) => row.size))
  return (
    <ol aria-label={label} className="mt-5 flex flex-col">
      {rows.map(({ group, size, refused, meta }, index) => (
        <li
          key={group.question_hash}
          className="grid grid-cols-[2rem_minmax(0,1fr)] border-t border-rule py-3.5 first:border-t-0 sm:grid-cols-[2.5rem_minmax(0,1fr)]"
        >
          <span className="tnum pt-px font-display text-[15px] text-ink-3">{index + 1}</span>
          <div>
            <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
              <p className="text-[15px] leading-snug text-ink">
                <QuestionText group={group} />
              </p>
              <span className="tnum text-[12.5px] text-ink-2 sm:shrink-0">{meta}</span>
            </div>
            <Bar size={size} max={max} count={group.count} refused={refused} />
            <OtherWordings group={group} />
          </div>
        </li>
      ))}
    </ol>
  )
}

function Section({
  title,
  caption,
  empty,
  rows,
}: {
  title: string
  caption: string
  empty: string
  rows: Row[]
}) {
  const id = `section-${title.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <section aria-labelledby={id} className="mt-12 first:mt-0">
      <h2 id={id} className="font-display text-[19px] font-medium tracking-tight text-ink">
        {title}
      </h2>
      <p className="mt-1 text-[13.5px] leading-normal text-ink-2">{caption}</p>
      {rows.length === 0 ? (
        <p className="mt-5 rounded-md border border-dashed border-rule-strong px-4 py-5 text-[14px] text-ink-2">
          {empty}
        </p>
      ) : (
        <RankedList rows={rows} label={title} />
      )}
    </section>
  )
}

function Summary({ report, requested }: { report: CoverageReport; requested: number }) {
  const share = report.total ? Math.round((report.refused / report.total) * 100) : 0
  return (
    <div className="border-b border-rule pb-8">
      <p className="font-display text-[34px] leading-[1.1] font-medium tracking-tight text-ink sm:text-[40px]">
        <span className="tnum text-ochre-ink">{report.refused.toLocaleString()}</span>
        <span className="text-ink-3"> of </span>
        <span className="tnum">{report.total.toLocaleString()}</span>
      </p>
      <p className="mt-2 max-w-120 text-[14.5px] leading-normal text-ink-2">
        {report.total === 0
          ? `No questions were asked in the last ${report.days} days.`
          : `questions in the last ${report.days} days had no policy to answer them (${share}%).`}
      </p>
      {report.grouping === 'exact' && (
        <p className="mt-2 max-w-120 text-[13px] leading-normal text-ink-3">
          Grouping by meaning is unavailable right now, so a question asked in other
          words has a row for each wording.
        </p>
      )}
      {report.days < requested && (
        <p className="mt-2 max-w-120 text-[13px] leading-normal text-ink-3">
          The query log keeps {plural(report.days, 'day')} of questions, so this is the longest window there is.
        </p>
      )}
    </div>
  )
}

export default function CoverageGapsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const days = readDays(searchParams.get('days'))
  const [state, setState] = useState<ReportState | null>(null)
  const [failedDays, setFailedDays] = useState<number | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    getCoverageReport(days)
      .then((report) => {
        if (cancelled) return
        setState({ days, report })
        setFailedDays(null)
      })
      .catch(() => {
        if (!cancelled) setFailedDays(days)
      })
    return () => {
      cancelled = true
    }
  }, [days, reloadKey])

  function changeWindow(next: number) {
    if (next === days) return
    const params = new URLSearchParams(searchParams)
    if (next === DEFAULT_DAYS) params.delete('days')
    else params.set('days', String(next))
    setSearchParams(params, { replace: true })
  }

  const failed = failedDays === days
  const report = state?.days === days ? state.report : null
  // The server shortens a window longer than the log's TTL; press the pill
  // for the window it ran, not the one asked for.
  const shownDays = report?.days ?? days

  let body: React.ReactNode
  if (failed) {
    body = (
      <div>
        <p role="alert" className="text-[14px] text-brick">Unable to load this report.</p>
        <button
          type="button"
          onClick={() => {
            setFailedDays(null)
            setReloadKey((key) => key + 1)
          }}
          className="mt-2 cursor-pointer text-[13px] font-medium text-accent hover:underline"
        >
          Try again
        </button>
      </div>
    )
  } else if (!report) {
    body = <p className="text-[14px] text-ink-3">Loading…</p>
  } else {
    const grouping =
      report.grouping === 'meaning'
        ? 'Near-identical wordings share a row, but a question asked in other words can still appear twice.'
        : 'Each wording has its own row.'
    body = (
      <>
        <Summary report={report} requested={days} />
        <div className="pt-10">
          <Section
            title="Not answered yet"
            caption={`Questions no policy answered, most asked first. Each one points to a policy to write or make clearer. ${grouping}`}
            empty="Every question in this window had a policy to answer it."
            rows={report.gaps.map((group) => ({
              group,
              size: group.count,
              refused: group.count,
              meta: timesAsked(group),
            }))}
          />
          <Section
            title="Asked most"
            caption={`Questions asked in at least two conversations, most conversations first. ${grouping} The ochre end of each bar is the share no policy answered.`}
            empty="No question came up in more than one conversation in this window."
            rows={report.faq.map((group) => ({
              group,
              size: group.conversations,
              refused: group.refused,
              meta: group.refused
                ? `${timesAsked(group)} · ${group.refused.toLocaleString()} not answered`
                : timesAsked(group),
            }))}
          />
        </div>
      </>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className={`flex min-h-15 shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-rule py-3 ${READING_GUTTER}`}>
        <h1 className="font-display text-[22px] leading-none font-medium tracking-tight text-ink">
          What People Ask
        </h1>
        <div className="flex gap-1.5" role="group" aria-label="Time window">
          {WINDOWS.map((option) => (
            <button
              key={option.days}
              type="button"
              onClick={() => changeWindow(option.days)}
              aria-pressed={option.days === shownDays}
              className={`h-7 cursor-pointer rounded-full border px-3 text-[12.5px] transition-colors ${
                option.days === shownDays
                  ? 'border-accent bg-accent text-paper'
                  : 'border-rule bg-paper-3 text-ink-2 hover:border-ink-3 hover:text-ink'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={`${READING_GUTTER} py-8 sm:py-10`}>
          <div className={READING_COLUMN} aria-busy={!report && !failed}>
            {body}
          </div>
        </div>
      </div>
    </div>
  )
}
