# Lighthouse runs

`run.mjs` runs Lighthouse against a running Sourcebook for
[#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214): the sign-in
page, the chat page with one answered question, and the Policy Library with a
document open, each in the light and dark theme, at Lighthouse's mobile and
desktop presets. That is 12 runs, each scored on performance, accessibility,
best practices, and SEO.

The script signs in through the API, asks one question so the chat page has
an answer, and picks a document. Against the pilot, that is one real model
call, and it leaves a conversation titled "Lighthouse run". Before each audit it
stores the theme, and for signed-in pages the token, in the browser, and runs
Lighthouse with storage reset off so they survive. Storage reset off also keeps
the HTTP cache, so the script clears it before each audit: every run is a cold
load. If the answer to the question is not saved, the script stops rather than
audit an empty chat page.

## Running it

It needs Node 22.19 or later and a Chrome or Chromium binary.

```bash
cd scripts/lighthouse
npm ci
BASE_URL=https://sourcebook.duckdns.org \
LH_PASSWORD='<reviewer password>' \
CHROME_PATH=/path/to/chrome \
DEPLOYED_COMMIT=<the commit the pilot runs> \
node run.mjs
```

Never commit the password. Results go to `results/<timestamp>/`, which git
ignores:

- `summary.md`: the table to copy into `docs/quality.md`, under a line giving
  the date, the site, `DEPLOYED_COMMIT`, and the Lighthouse version
- `summary.json`: the same scores and details (the conversation and document
  used are printed to the console, not saved)
- one Lighthouse JSON report per run, which opens in the
  [Lighthouse viewer](https://googlechrome.github.io/lighthouse-viewer/)

To try it without the pilot, run `make stub`, build the web app
(`cd web && npm run build`), serve it with `npx vite preview` (it proxies
`/api` to the stub), and point `BASE_URL` at `http://localhost:4173` with
`LH_PASSWORD=dev`. Local scores leave out the pilot's network, TLS, and
server, so quote only the pilot run.
