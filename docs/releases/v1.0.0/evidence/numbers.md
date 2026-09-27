# Shared evidence sheet (position papers)

One table of figures for the Unit 8 individual position papers
([issue #217](https://github.com/CMSC495-GROUP3/Sourcebook/issues/217)).
Every filled cell names the artifact or GitHub search it came from. Cells
without a committed artifact use
`Pending — requires <named artifact/gate>` and do not invent a number.

**Tag status:** `v1.0.0` is not cut. The candidate is `main` at
[`7d3c779`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/7d3c7795c197c5be56b15aebc650576760fd75d1),
named on 27 September after the last code change merged
([plan on #215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215#issuecomment-5824613941)).
Final-release rows are filled as each measurement runs on it; the rest stay
Pending. The alpha and beta rows link into the tagged trees, so they do not
move when `main` does. The rest of this folder (`README.md`, `coverage.md`)
and the release pages beside it (`handoff.md`, `release-notes.md`,
`live-evaluation.md`, `live-benchmark.md`) are drafted in
[pull request #274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274) and
are not on `main` yet.

**GitHub counts:** as of **2026-09-25T19:30Z** (the review column
2026-09-25T19:57Z), to be refreshed when `v1.0.0` is tagged. They
are live search totals, not values frozen by any commit, so they will grow
until the tag. Each Source cell gives the search, scoped to
`repo:CMSC495-GROUP3/Sourcebook`. To regenerate, run the same query in the
GitHub search box, with `gh search prs` / `gh search issues`, or through the
search API, and read the total count. The earlier snapshot in
[docs/quality.md](../../../quality.md#live-pr-and-review-totals)
(2026-09-18, 122 merged pull requests) is superseded here.

## Coverage

| Figure | Value | Source |
| --- | --- | --- |
| Python coverage %, final | 93% of 2,426 statements on `7d3c779` | [coverage.md](coverage.md), from `python-coverage-7d3c779…` in [CI run 36324854066](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854066) ([issue #210](https://github.com/CMSC495-GROUP3/Sourcebook/issues/210)). Floor: `--cov-fail-under=80` in [`.github/workflows/ci.yml`](../../../../.github/workflows/ci.yml); see [quality.md § Coverage](../../../quality.md#coverage) |
| Web coverage %, final | 92.28% statements; 87.29% branches; 94% functions; 93.93% lines on `7d3c779` | [coverage.md](coverage.md), from `web-coverage-7d3c779…` in the same run. Scope is the source files listed in `web/vitest.config.ts`, not all of `web/src`. Say so wherever the figure is quoted |
| Web coverage %, pre-freeze (five files only) | 99.46% statements; 96.42% branches; 100% functions; 99.37% lines. Scope is `useChat`, `Message`, `EscalateButton`, `ThemeToggle`, and `theme.ts` | [quality.md § Coverage](../../../quality.md#what-the-suite-covers-and-what-it-does-not), measured on the head of [pull request #252](https://github.com/CMSC495-GROUP3/Sourcebook/pull/252) before it merged. `web/vitest.config.ts` has since added the escalation files, so the final figure covers a wider scope than these five. Not the release figure; cite the final row once filled |

## Pull requests, reviews, and issues (to date)

As of 2026-09-25T19:30Z (the review column 2026-09-25T19:57Z), to be
refreshed when `v1.0.0` is tagged.

| Figure | Value | Source |
| --- | ---: | --- |
| Pull requests, all states | 168 | [`is:pr`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr&type=pullrequests) |
| Merged pull requests | 144 | [`is:pr is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged&type=pullrequests). The eight per-author searches below sum to 144 |
| Merged pull requests by people (excludes Dependabot) | 124 | 144 minus [`is:pr is:merged author:app/dependabot`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3Aapp%2Fdependabot&type=pullrequests) (20) |
| Human review events, total | Pending — requires a review-event ledger from the reviews API. `reviewed-by:` counts pull requests per reviewer, not review events, and counts a pull request once per reviewer | Per-reviewer pull request counts are in the member table below |
| Closed issues | 91 | [`is:issue is:closed`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed&type=issues). The per-author searches below sum to 91 |
| Closed issues, completed | 76 | [`is:issue is:closed reason:completed`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+reason%3Acompleted&type=issues). The other 15 closed as not planned |

### Per member

| Member | Role (README) | Merged PRs authored | Others' PRs reviewed | Closed issues authored |
| --- | --- | ---: | ---: | ---: |
| [@t-shahan](https://github.com/t-shahan) | Lead Architect | [67](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3At-shahan&type=pullrequests) | [56](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3At-shahan+-author%3At-shahan&type=pullrequests) | [65](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3At-shahan&type=issues) |
| [@DanielTsang26](https://github.com/DanielTsang26) | Interface Designer | [1](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3ADanielTsang26&type=pullrequests) | [1](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3ADanielTsang26+-author%3ADanielTsang26&type=pullrequests) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3ADanielTsang26&type=issues) |
| [@threshi-art](https://github.com/threshi-art) | Integration Lead | [50](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3Athreshi-art&type=pullrequests) | [1](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3Athreshi-art+-author%3Athreshi-art&type=pullrequests) | [25](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3Athreshi-art&type=issues) |
| [@gavinwathen](https://github.com/gavinwathen) | React components, design and styling (row unconfirmed) | [1](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3Agavinwathen&type=pullrequests) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3Agavinwathen+-author%3Agavinwathen&type=pullrequests) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3Agavinwathen&type=issues) |
| [@fudgepop01](https://github.com/fudgepop01) | React components, design and styling (row unconfirmed) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3Afudgepop01&type=pullrequests) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3Afudgepop01+-author%3Afudgepop01&type=pullrequests) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3Afudgepop01&type=issues) |
| [@Lazzy-dev](https://github.com/Lazzy-dev) | Administration (EC2, S3, Atlas), locks, MongoDB | [3](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3ALazzy-dev&type=pullrequests) | [4](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3ALazzy-dev+-author%3ALazzy-dev&type=pullrequests) | [1](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3ALazzy-dev&type=issues) |
| [@RoNUO](https://github.com/RoNUO) | Corpus availability and passage index | [2](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3ARoNUO&type=pullrequests) | [2](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3ARoNUO+-author%3ARoNUO&type=pullrequests) | [0](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Aissue+is%3Aclosed+author%3ARoNUO&type=issues) |
| Dependabot (not a member) | — | [20](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged+author%3Aapp%2Fdependabot&type=pullrequests) | — | — |

How to read the columns:

- **Merged PRs authored** is `is:pr is:merged author:<login>`. It counts pull
  requests, not commits, and says nothing about their size.
- **Others' PRs reviewed** is `reviewed-by:<login> -author:<login>` over pull
  requests in any state, so it can include open drafts such as #230 and #231.
  It excludes the member's own pull requests: GitHub records a reply in a
  review thread as a review, so plain `reviewed-by:` counts self-replies too
  (on 25 September it gave 62 for @t-shahan, 6 of them their own, and 7 for
  @threshi-art, 6 of them their own). It is a count of other people's pull
  requests with at least one review from that person, not of approvals or of
  review events. Cite this column, not a plain `reviewed-by:` count.
- **Closed issues authored** is `is:issue is:closed author:<login>`. It counts
  who opened the issue, not who fixed it.
- **Role** comes from [README § Team](../../../../README.md#team) for the
  three Unit 5 roles and from [docs/team.md](../../../team.md) for the other
  four. Gavin's and Dominick's rows there are marked unconfirmed.

**Contribution statements:** each paper copies the author's row in
[docs/team.md](../../../team.md) word for word. It merged in
[#231](https://github.com/CMSC495-GROUP3/Sourcebook/pull/231) with its counts
refreshed against the candidate `7d3c779`.

## Answer quality (live evaluation)

All runs are the 20-case smoke tier: 12 answerable, 2 unanswerable, 3 prompt
injection, 3 ambiguous. The prompt-injection row is the share refused before
answer generation; whether generated prose resisted an injection is scored by
hand on each page. Twenty cases on a fictional corpus are evidence for that
sample, not a quality guarantee.

| Figure | Alpha (`v0.1.0-alpha.1`) | Beta (`v0.2.0`) | Final (`v1.0.0`) |
| --- | --- | --- | --- |
| Commit under test | `4e90382` (and `9871e3e`, the commit before #138, which scored the same) | `231e652`, [workflow run 36062704072](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36062704072) | `7d3c779`, [workflow run 36325342934](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36325342934) |
| Recall@5 (12 answerable) | 100% | 100% | 100% |
| Citation correctness (12 answerable) | 100% | 100% | 100% |
| Grounded answer rate (12 answerable) | 100% | 100% | 100% |
| Unsupported refusal handling (2 unanswerable) | 0% | 100% | 100% |
| Prompt-injection gate refusal (3 cases) | 0% | 100% | 100% |
| Full tier | Not run | Run after the tag, on `383cea5` ([run 36267109629](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36267109629)): Recall@5, citation correctness, and grounded-answer rate 95.9% (47 of 49); unsupported refusal 100% of 4; injection gate refusal 100% of 3 | On `7d3c779` ([run 36325113964](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36325113964)): Recall@5, citation correctness, and grounded-answer rate 95.9% (47 of 49), the same two misses as the beta; unsupported refusal 100% of 4; injection gate refusal 100% of 3 ([#213](https://github.com/CMSC495-GROUP3/Sourcebook/issues/213)) |
| Source | [live-evaluation.md](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/live-evaluation.md), [results JSON](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/live-evaluation-results.json); "The full tier has not been run" is in its limitations | [live-evaluation.md](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/live-evaluation.md#results-against-the-alpha), [results JSON](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/live-evaluation-results.json); full tier not run as of the tag per [handoff.md](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/handoff.md#what-this-beta-does-not-establish); the later full-tier run is in [live-evaluation.md on `main`](https://github.com/CMSC495-GROUP3/Sourcebook/blob/main/docs/releases/v0.2.0/live-evaluation.md#full-tier-run-on-2026-09-26) and `live-evaluation-full-results.json` beside it (#283) | [live-evaluation.md](../live-evaluation.md), with both results JSON files beside it |

The alpha never ran the full tier, and the beta's full-tier run came after its
tag: #283 ran it through the workflow on the tagged commit on 2026-09-26. An
earlier full-tier run happened on the host on 14 September, before #245 and #253 changed the refusal gate: all 46
answerable cases answered, and 0 of the 5 unanswerable and prompt-injection
cases refused ([comment on
#201](https://github.com/CMSC495-GROUP3/Sourcebook/issues/201#issuecomment-5658446129)).
Its results are not committed, so it is a note, not a cell value.

The alpha folder moved from `docs/alpha/` to `docs/releases/v0.1.0-alpha.1/`
after the tag. The tagged links above point at the files as tagged; the
figures are the same in both places.

## Live benchmark against the pilot

The same bounded workload each time: at most 8 requests, a burst of 3, from
one operator's laptop. It checks that the deployed path works for one user
and a small burst. It is not a load test.

| Target | Agreed | Alpha, deployed `4352966` | Beta, deployed `231e652` | Final |
| --- | --- | --- | --- | --- |
| Generated time to first token, p50 | ≤ 4.0s | 1.21s, pass | 1.21s, pass | 1.18s, pass |
| Generated total, max | ≤ 30.0s | 4.69s, pass | 4.35s, pass | 3.30s, pass |
| Cached time to first token, max | ≤ 1.5s | 0.04s, pass | 0.04s, pass | 0.10s, pass |
| Refused total, max | ≤ 3.0s | 0.31s, pass | 0.08s, pass | 0.05s, pass |
| Error rate | 0.0 | 0.00, pass | 0.00, pass | 0.00, pass |
| Requests | — | 7 (5 generated, 1 cached, 1 refused), estimated cost $0.05 | 7 (5 generated, 1 cached, 1 refused), estimated cost $0.05 | 7 (5 generated, 1 cached, 1 refused), estimated cost $0.05; run `e6615d05`, deployed `7d3c779` |
| Source | [alpha live-benchmark.md § Targets](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/live-benchmark.md#targets) | [live-benchmark.md](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/live-benchmark.md#against-the-agreed-targets), [results JSON](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/live-benchmark-results.json) | [live-benchmark.md](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/live-benchmark.md#results), [results JSON](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/live-benchmark-results.json) | [live-benchmark.md](../live-benchmark.md), [results JSON](../live-benchmark-results.json) |

The beta's and the final's refusal steps were refused at the cosine gate, so
no run times a refusal by the coverage judge. Seven requests are too few for percentiles.

## Load, Lighthouse, and the deployed pilot

| Figure | Value | Source |
| --- | --- | --- |
| Pilot load run: req/s, p50/p95 time to first token, errors, host CPU/memory | 5 / 10 / 20 concurrent: 0 errors, 1.11 / 4.44 / 8.86 req/s, first token p50 3.94 / 1.43 / 1.46 s and p95 4.09 / 1.73 / 1.68 s. 40 concurrent: 33 of 40 failed (20 OpenAI 30k TPM limit, 13 provider bound 503). API CPU peak 80%, memory 138 MiB, load 0.60 | [load-testing-pilot.md § Results](../../../load-testing-pilot.md#results), [pilot-load.json](pilot-load.json), run `3eac2646` on 2026-09-27 against code identical to `7d3c779`. Not measured at the beta: "The deployed system has not been load-tested" ([beta release notes](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/release-notes.md#what-this-beta-does-not-establish)) |
| Synthetic load figures (not the pilot) | Generated answers saturate at 14.9 req/s on the default 40-thread pool; the refusal path reaches about 700 req/s. Model faked, database in memory, chat limiter off | [docs/load-testing.md](../../../load-testing.md). Do not cite these as the deployed system's capacity |
| Lighthouse, light theme (phone and desktop) | Performance 87, 92, 89 on mobile (chat, document, sign-in) and 100 on desktop; accessibility 100; best practices 100; SEO 91 | [lighthouse.md](lighthouse.md), Lighthouse 13.5.0 on `7d3c779`, 2026-09-27. Not measured at the beta ([beta handoff](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/handoff.md#what-this-beta-does-not-establish)) |
| Lighthouse, dark theme (phone and desktop) | Performance 91, 91, 96 on mobile (chat, document, sign-in) and 100 on desktop; accessibility 100; best practices 100; SEO 91 | Same run. SEO loses 9 points on `robots-txt` only |
| Deployed uptime | Pending — requires a host uptime record or monitoring export, sanitized into this folder at the freeze | Nothing committed |
| Auto-deploys since the alpha | Pending — requires a sanitized deploy journal from the pilot host that covers the time since the alpha tag (the freeze excerpt `auto-deploy-journal.txt` is [issue #207](https://github.com/CMSC495-GROUP3/Sourcebook/issues/207)) | The deploy runs from a systemd timer on the host, not from Actions, so GitHub has no count of it. Gate text in [docs/ci-cd.md](../../../ci-cd.md) |

## Position-paper sections: where to draw from

| Paper section | Draw from (repo) | Named standards or external comparisons |
| --- | --- | --- |
| Section 1: the product and the releases | [README](../../../../README.md); the alpha [handoff](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/handoff.md) and [release notes](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.1.0-alpha.1/docs/alpha/release-notes.md); the beta [handoff](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/handoff.md) and [release notes](https://github.com/CMSC495-GROUP3/Sourcebook/blob/v0.2.0/docs/releases/v0.2.0/release-notes.md); the `v1.0.0` handoff and release notes once [#274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274) is filled and tagged | Keep claims to what a tagged or committed file shows |
| Section 2: quality and process | [docs/quality.md](../../../quality.md), with [docs/evaluation.md](../../../evaluation.md), [docs/ci-cd.md](../../../ci-cd.md), and this sheet for the figures | Compare quality.md against the **SEI CMMI** practice areas (for example Verification, Peer Review, Measurement and Analysis), or against **IEEE 730** (software quality assurance) and **IEEE 12207** (software life-cycle processes). Name the edition you cite |
| Section 3: industry context | The counts above, [README § Team](../../../../README.md#team), and [CONTRIBUTING.md](../../../../CONTRIBUTING.md) for the review and branch process | The **Stack Overflow Developer Survey**, **GitHub Octoverse**, or an **IEEE Computer Society** report. Name the year you cite |
| Contribution statement | The author's row in [docs/team.md](../../../team.md), copied as written | — |

Do not fill a Pending row from anything but the artifact it names. When that
artifact lands, replace the Pending text with the figure and point the Source
cell at the file or run.
