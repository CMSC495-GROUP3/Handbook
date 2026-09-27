// Lighthouse against a running Sourcebook: three pages, two themes, two widths.
//
// Pages: the sign-in page, the chat page showing one answered question, and
// the Policy Library with one document open. Themes: the stored light and dark
// choice, which wins over the system preference (web/src/lib/theme.ts).
// Widths: Lighthouse's mobile preset (a phone) and its desktop preset.
//
// The script signs in through the API once, asks one question so the chat page
// has an answer (on the pilot that is one real model call), and picks a
// document. Before each audit it writes the theme, and for signed-in pages the
// token, into localStorage, and runs Lighthouse with storage reset off so they
// survive. Storage reset off also keeps the HTTP cache, so the script clears
// that itself: every audit is a cold load. Scores are the four Lighthouse
// categories, 0 to 100, or "error" when a category could not be scored.
//
//   BASE_URL      the site, e.g. https://sourcebook.duckdns.org (required)
//   LH_PASSWORD   the sign-in password (required; never commit it)
//   CHROME_PATH   Chrome or Chromium binary (required)
//   OUT_DIR       where results go (default: ./results/<timestamp>)
//   QUESTION      the question to ask (default: a covered PTO question)
//   DEPLOYED_COMMIT  the commit the site runs, recorded in the summaries
//
// Writes summary.json, summary.md, and one Lighthouse JSON report per run.
// The conversation and document used are printed, not written.

import fs from 'node:fs/promises'
import path from 'node:path'
import lighthouse from 'lighthouse'
import desktopConfig from 'lighthouse/core/config/desktop-config.js'
import puppeteer from 'puppeteer-core'

const TOKEN_KEY = 'sourcebook_token' // web/src/config.ts
const THEME_KEY = 'theme' // web/src/lib/theme.ts
const CATEGORIES = ['performance', 'accessibility', 'best-practices', 'seo']

function required(name) {
  const value = process.env[name]
  if (!value) {
    console.error(`${name} is required`)
    process.exit(2)
  }
  return value
}

const baseUrl = required('BASE_URL').replace(/\/+$/, '')
const password = required('LH_PASSWORD')
const chromePath = required('CHROME_PATH')
const question =
  process.env.QUESTION ??
  'How many PTO days do full time employees with two years of service receive each year?'
const deployedCommit = process.env.DEPLOYED_COMMIT ?? null
const outDir =
  process.env.OUT_DIR ?? path.join('results', new Date().toISOString().replace(/[:.]/g, '-'))

async function api(method, route, token, body) {
  const response = await fetch(`${baseUrl}${route}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    throw new Error(`${method} ${route} answered ${response.status}`)
  }
  return response.json()
}

async function setUp() {
  const { access_token: token } = await api('POST', '/api/auth/login', null, { password })
  const conversation = await api('POST', '/api/conversations', token, { title: 'Lighthouse run' })
  const sessionId = conversation.session_id
  // /api/chat answers 200 even when generation fails, but only a saved answer
  // carries a message_id. Without one the chat page would be audited empty.
  const answer = await api('POST', '/api/chat', token, { question, session_id: sessionId })
  if (!answer.message_id) {
    throw new Error(`the chat answer was not saved: ${answer.answer}`)
  }
  const documents = await api('GET', '/api/documents?limit=1', token)
  const source = documents.items?.[0]?.source
  const pages = [
    { name: 'sign-in', url: `${baseUrl}/`, signedIn: false },
    { name: 'chat', url: `${baseUrl}/chat?session_id=${encodeURIComponent(sessionId)}`, signedIn: true },
    {
      name: 'document',
      url: source
        ? `${baseUrl}/documents?source=${encodeURIComponent(source)}`
        : `${baseUrl}/documents`,
      signedIn: true,
    },
  ]
  return { token, sessionId, pages, source }
}

async function prepareStorage(browser, token, theme, signedIn) {
  const page = await browser.newPage()
  await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' })
  await page.evaluate(
    ({ tokenKey, themeKey, token, theme, signedIn }) => {
      localStorage.clear()
      localStorage.setItem(themeKey, theme)
      if (signedIn) localStorage.setItem(tokenKey, token)
    },
    { tokenKey: TOKEN_KEY, themeKey: THEME_KEY, token, theme, signedIn },
  )
  // disableStorageReset leaves the HTTP cache alone too, and this page and
  // earlier audits have just cached the bundles and fonts.
  const cdp = await page.createCDPSession()
  await cdp.send('Network.clearBrowserCache')
  await cdp.detach()
  await page.close()
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const { token, sessionId, pages, source } = await setUp()

  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--remote-debugging-port=9222', '--no-sandbox'],
  })
  const port = 9222
  const results = []
  let lighthouseVersion = null

  try {
    for (const theme of ['light', 'dark']) {
      for (const width of ['mobile', 'desktop']) {
        for (const target of pages) {
          await prepareStorage(browser, token, theme, target.signedIn)
          const flags = { port, output: 'json', logLevel: 'error', disableStorageReset: true }
          const config = width === 'desktop' ? desktopConfig : undefined
          const run = await lighthouse(target.url, flags, config)
          const lhr = run.lhr
          lighthouseVersion = lhr.lighthouseVersion
          const scores = Object.fromEntries(
            CATEGORIES.map((id) => {
              const score = lhr.categories[id]?.score
              return [id, typeof score === 'number' ? Math.round(score * 100) : 'error']
            }),
          )
          const file = `${target.name}-${theme}-${width}.json`
          await fs.writeFile(path.join(outDir, file), run.report)
          results.push({ page: target.name, theme, width, scores, report: file })
          console.log(`${target.name} ${theme} ${width}: ${CATEGORIES.map((c) => `${c} ${scores[c]}`).join(', ')}`)
        }
      }
    }
  } finally {
    await browser.close()
  }

  const summary = {
    date: new Date().toISOString(),
    base_url: baseUrl,
    deployed_commit: deployedCommit,
    lighthouse_version: lighthouseVersion,
    results,
  }
  await fs.writeFile(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2) + '\n')

  const header = '| Page | Theme | Width | Performance | Accessibility | Best practices | SEO |\n| --- | --- | --- | ---: | ---: | ---: | ---: |'
  const rows = results.map(
    (r) =>
      `| ${r.page} | ${r.theme} | ${r.width} | ${r.scores.performance} | ${r.scores.accessibility} | ${r.scores['best-practices']} | ${r.scores.seo} |`,
  )
  const heading = `Run ${summary.date} against ${baseUrl} at commit ${deployedCommit ?? '(not given)'}, Lighthouse ${lighthouseVersion}.`
  await fs.writeFile(path.join(outDir, 'summary.md'), [heading, '', header, ...rows].join('\n') + '\n')
  // The conversation and document come from the API, so they go to the
  // console, not into summary.json.
  console.log(`Conversation ${sessionId}, document ${source ?? '(none)'}`)
  console.log(`Wrote ${results.length} runs to ${outDir}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
