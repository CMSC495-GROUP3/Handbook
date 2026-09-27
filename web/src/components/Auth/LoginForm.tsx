import axios from 'axios'
import { useState } from 'react'
import { AlertCircle, BookOpen, LifeBuoy, Quote } from 'lucide-react'
import client, { browserId, TOKEN_KEY } from '../../api/client'
import { ESCALATION_CONTACT } from '../../config'
import { BrandMark, Wordmark } from '../Layout/Brand'
import ThemeToggle from '../Layout/ThemeToggle'

interface Props {
  onSuccess: () => void
}

// Only a 401 means the password was wrong. A rate limit or a server-side
// configuration error must not be reported as one, or a locked-out admin
// would keep retrying a password that was never the problem.
function loginErrorMessage(err: unknown): string {
  const status = axios.isAxiosError(err) ? err.response?.status : undefined
  if (status === 401) return 'Incorrect password.'
  if (status === 429) return 'Too many attempts. Wait a minute and try again.'
  return 'Sign-in is unavailable right now. Try again in a moment.'
}

const PROMISES = [
  { icon: Quote, text: 'Every answer names the policy documents it came from.' },
  { icon: BookOpen, text: 'Answers come only from the indexed library, which you can read in full.' },
  { icon: LifeBuoy, text: `When nothing matches, it says so and hands you to ${ESCALATION_CONTACT}.` },
]

export default function LoginForm({ onSuccess }: Props) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await client.post('/api/auth/login', { password, client_id: browserId() })
      localStorage.setItem(TOKEN_KEY, res.data.access_token)
      onSuccess()
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative grid min-h-svh w-full grid-cols-1 bg-paper md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <ThemeToggle className="absolute top-3 right-3" />
      {/* The left page: what this is. It is set on the 24px grid of the ruled
          background: every line-height, gap, and top padding is a multiple of
          24px, and the small `top` nudges drop each face's baseline onto the
          rule that runs 21px into its slot. The footer is pinned to the
          bottom, so on desktop the bottom padding is 48px plus whatever the
          viewport height leaves over after whole 24px slots, which keeps the
          footer's slot on the grid. */}
      <section className="ruled flex flex-col border-b border-rule bg-paper-2 px-6 py-6 md:border-r md:border-b-0 md:px-12 md:pt-12 md:pb-[calc(3rem+mod(100svh,24px))] lg:px-16">
        <div className="relative top-[10px] flex h-12 items-center gap-3">
          <BrandMark size={36} />
          <Wordmark className="text-[24px] leading-none" />
        </div>
        <div className="mt-12 flex flex-col gap-12 md:mt-24">
          <div className="flex flex-col gap-6">
            <h1 className="relative top-[11px] font-display text-[34px] leading-12 font-medium tracking-tight text-ink md:top-[9px] md:text-[44px]">
              The policy, with its source.
            </h1>
            <p className="max-w-110 text-[15px] leading-6 text-ink-2 md:text-[16px]">
              Ask about company policy in plain words. Sourcebook answers from the indexed policy documents and shows you where each answer came from.
            </p>
          </div>
          <ul className="hidden flex-col md:flex">
            {PROMISES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-[14px] leading-6 text-ink">
                <Icon size={16} strokeWidth={1.75} aria-hidden="true" className="mt-1 shrink-0 text-accent" />
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-auto hidden pt-6 text-[12.5px] leading-6 text-ink-3 md:block">Internal tool. Ask {ESCALATION_CONTACT} for the password.</p>
      </section>

      {/* The right page: the form. */}
      <section className="flex items-center justify-center px-6 py-12 md:px-12">
        <form onSubmit={handleSubmit} className="flex w-full max-w-90 flex-col gap-6" noValidate>
          <div className="flex flex-col gap-1.5">
            <h2 className="font-display text-[28px] leading-none font-medium tracking-tight text-ink">Sign in</h2>
            <p className="text-[14px] text-ink-2">Enter the shared password to continue.</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-[12.5px] font-medium text-ink-2">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              autoFocus
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? 'password-error' : undefined}
              className="h-11 w-full rounded-md border border-rule-strong bg-paper-3 px-3.5 text-[16px] text-ink transition-colors placeholder:text-ink-3 focus:border-accent focus:ring-3 focus:ring-accent-soft focus:outline-none sm:text-[15px]"
            />
          </div>
          {/* Always rendered so the form does not jump when an error appears. */}
          <p id="password-error" role="alert" className="-mt-2 flex min-h-5 items-center gap-1.5 text-[13px] text-brick">
            {error && (
              <>
                <AlertCircle size={14} aria-hidden="true" />
                {error}
              </>
            )}
          </p>
          <button
            type="submit"
            disabled={loading || !password}
            className="h-11 cursor-pointer rounded-md bg-accent text-[14.5px] font-medium text-paper transition-colors hover:bg-accent-ink disabled:cursor-not-allowed disabled:bg-rule disabled:text-ink-3"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="text-[12.5px] text-ink-3 md:hidden">Internal tool. Ask {ESCALATION_CONTACT} for the password.</p>
        </form>
      </section>
    </main>
  )
}
