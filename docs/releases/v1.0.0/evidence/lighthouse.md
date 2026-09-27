# Lighthouse on the v1.0.0 candidate

`scripts/lighthouse/run.mjs` ([#280](https://github.com/CMSC495-GROUP3/Sourcebook/pull/280))
against the pilot at <https://sourcebook.duckdns.org> running
[`7d3c779`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/7d3c7795c197c5be56b15aebc650576760fd75d1),
on 2026-09-27 at 14:33 UTC, with Lighthouse 13.5.0 and Google Chrome
153.0.8010.53 on a Mac laptop. It covers the three pages
([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)), both themes,
and Lighthouse's mobile and desktop presets: 12 cold loads. The scores are in
[lighthouse-summary.json](lighthouse-summary.json); the full per-run reports
stayed in the runner's git-ignored `results/` folder.

| Page | Theme | Width | Performance | Accessibility | Best practices | SEO |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| sign-in | light | mobile | 89 | 100 | 100 | 91 |
| chat | light | mobile | 87 | 100 | 100 | 91 |
| document | light | mobile | 92 | 100 | 100 | 91 |
| sign-in | light | desktop | 100 | 100 | 100 | 91 |
| chat | light | desktop | 100 | 100 | 100 | 91 |
| document | light | desktop | 100 | 100 | 100 | 91 |
| sign-in | dark | mobile | 96 | 100 | 100 | 91 |
| chat | dark | mobile | 91 | 100 | 100 | 91 |
| document | dark | mobile | 91 | 100 | 100 | 91 |
| sign-in | dark | desktop | 100 | 100 | 100 | 91 |
| chat | dark | desktop | 100 | 100 | 100 | 91 |
| document | dark | desktop | 100 | 100 | 100 | 91 |

- **Accessibility and best practices** are 100 on every run.
- **Performance** is 100 on desktop and 87 to 96 on the mobile preset, which
  throttles the network and CPU. A practice run before
  [#282](https://github.com/CMSC495-GROUP3/Sourcebook/pull/282) scored 66 to
  74 on mobile, when the pilot served its JavaScript bundle uncompressed.
- **SEO** is 91 everywhere for one reason: the pilot has no valid
  `robots.txt`, so the `robots-txt` audit fails. Every other SEO audit passes.
  A pilot behind a password is not meant to be indexed, and no code changes
  after the freeze, so this stays.

One run is one sample. Mobile performance moves by several points between
runs on the same commit, so quote the range, not a single score.
