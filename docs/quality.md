# Code quality evidence

This page points a grader at the review, coverage, and performance artifacts that already exist. Every number names the file, pull request, or Actions run it came from. It does not invent a committed coverage percentage, a live-evaluation PASS, Lighthouse scores, or a beta/final release folder that is not on `main`.

Sibling pages own adjacent evidence and are not duplicated here:

- CI/CD workflow inventory and deploy screenshots: [issue #207](https://github.com/CMSC495-GROUP3/Sourcebook/issues/207).
- Committed coverage table for the tagged final: [issue #210](https://github.com/CMSC495-GROUP3/Sourcebook/issues/210).
- React component tests: [issue #211](https://github.com/CMSC495-GROUP3/Sourcebook/issues/211).
- Deployed-pilot load run: [issue #212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212).
- Full evaluation tier: [issue #213](https://github.com/CMSC495-GROUP3/Sourcebook/issues/213). The beta run is recorded; the final run is not.
- Lighthouse per theme: [issue #214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214).
- `v1.0.0` freeze scaffold: [issue #215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215).

## Code review

### What the repository requires

[`.github/CODEOWNERS`](../.github/CODEOWNERS) requests [@DanielTsang26](https://github.com/DanielTsang26), [@t-shahan](https://github.com/t-shahan), and [@Lazzy-dev](https://github.com/Lazzy-dev) on every path. Branch protection is supposed to require a code-owner approval and the aggregate check named **CI status** ([CONTRIBUTING.md](../CONTRIBUTING.md#what-ci-runs)).

Every pull request also runs [PR checks](https://github.com/CMSC495-GROUP3/Sourcebook/blob/main/.github/workflows/pr-checks.yml): the title must be `type: what changed`, and the description must include a filled **What and why**. The Security workflow (CodeQL, dependency audit, gitleaks) is a separate signal from review.

### Live PR and review totals

These totals are GitHub search observations captured at **2026-09-18T06:58:39Z**, when `main` was [`88e8a13`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/88e8a134d16e092b2307c51b4e2a5fd7a9af39be). They are live metadata, not values frozen by that commit. Queries used `gh search` on `CMSC495-GROUP3/Sourcebook`:

| Signal | Count | Source |
| --- | ---: | --- |
| Pull requests (all states) | 148 | [`is:pr`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr&type=pullrequests) |
| Merged pull requests | 122 | [`is:pr is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+is%3Apr+is%3Amerged&type=pullrequests) |
| Merged PRs authored by @t-shahan | 57 | [`author:t-shahan is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+author%3At-shahan+is%3Amerged&type=pullrequests) |
| Merged PRs authored by @threshi-art | 41 | [`author:threshi-art is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+author%3Athreshi-art+is%3Amerged&type=pullrequests) |
| Merged PRs authored by dependabot | 18 | [`author:app/dependabot is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+author%3Aapp%2Fdependabot+is%3Amerged&type=pullrequests) |
| Merged PRs authored by @Lazzy-dev | 3 | [`author:Lazzy-dev is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+author%3ALazzy-dev+is%3Amerged&type=pullrequests) |
| Merged PRs authored by @RoNUO | 2 | [`author:RoNUO is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+author%3ARoNUO+is%3Amerged&type=pullrequests) |
| Merged PRs authored by @DanielTsang26 | 1 | [`author:DanielTsang26 is:merged`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+author%3ADanielTsang26+is%3Amerged&type=pullrequests) |
| PRs reviewed by @t-shahan | 55 | [`reviewed-by:t-shahan`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3At-shahan&type=pullrequests) |
| PRs reviewed by @threshi-art | 6 | [`reviewed-by:threshi-art`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3Athreshi-art&type=pullrequests) |
| PRs reviewed by @Lazzy-dev | 3 | [`reviewed-by:Lazzy-dev`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3ALazzy-dev&type=pullrequests) |
| PRs reviewed by @RoNUO | 2 | [`reviewed-by:RoNUO`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3ARoNUO&type=pullrequests) |
| PRs reviewed by @DanielTsang26 | 1 | [`reviewed-by:DanielTsang26`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3ADanielTsang26&type=pullrequests) |
| PRs reviewed by @gavinwathen or @fudgepop01 | 0 | [`reviewed-by:gavinwathen`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3Agavinwathen&type=pullrequests), [`reviewed-by:fudgepop01`](https://github.com/search?q=repo%3ACMSC495-GROUP3%2FSourcebook+reviewed-by%3Afudgepop01&type=pullrequests) — no hits |

These are GitHub search totals, not a hand-counted review-event ledger. This page uses the 2026-09-18T06:58:39Z observation instead of repeating earlier partial-window counts.

### Threads where review changed the code

| Thread | What review changed | Link |
| --- | --- | --- |
| httpx lock outage | The API lock installs `httpx2` via OpenAI and does not install the `httpx` import [PR #163](https://github.com/CMSC495-GROUP3/Sourcebook/pull/163) used for timeouts. Taylor reproduced `ModuleNotFoundError: No module named 'httpx'` in a fresh 3.12 venv from `requirements/api.lock.txt` and the fix stopped importing `httpx` directly. [PR #164](https://github.com/CMSC495-GROUP3/Sourcebook/pull/164) then constructed the provider inside the built image so CI sees the same failure mode. | [#163](https://github.com/CMSC495-GROUP3/Sourcebook/pull/163), [#164](https://github.com/CMSC495-GROUP3/Sourcebook/pull/164) |
| Grounding-gate / clarify prompt | On [PR #138](https://github.com/CMSC495-GROUP3/Sourcebook/pull/138) Taylor's review rewrote the clarifying-question rules, stopped labelling the server's own citation titles as untrusted, dropped hard-coded `PROMPT_VERSION == v3` asserts, and set the default to `v2`. Chris applied those on `d15a348`. | [#138](https://github.com/CMSC495-GROUP3/Sourcebook/pull/138) |
| Passage index | [PR #176](https://github.com/CMSC495-GROUP3/Sourcebook/pull/176) merged on 2026-09-12 (`cd4e64a`). Before merge, Taylor's reviews required a merge of the `sourcebook` package rename and called out migration evidence; George stated he would copy the database before approving. Review blocked merge until that landed, rather than rubber-stamping it. | [#176](https://github.com/CMSC495-GROUP3/Sourcebook/pull/176), [#158](https://github.com/CMSC495-GROUP3/Sourcebook/issues/158) |
| pip-compile names and lock check | On [PR #157](https://github.com/CMSC495-GROUP3/Sourcebook/pull/157) Taylor's review asked for a `pip-compile` staleness check and a Makefile `lock` target that survives the #135 venv rewrite. Those landed as follow-up commits on that PR (`31d36f1`). [PR #178](https://github.com/CMSC495-GROUP3/Sourcebook/pull/178) then named inputs `.in` and outputs `.txt` so Dependabot recompiles locks. | [#157](https://github.com/CMSC495-GROUP3/Sourcebook/pull/157), [#178](https://github.com/CMSC495-GROUP3/Sourcebook/pull/178) |
| Live-evaluation NaN | On [PR #181](https://github.com/CMSC495-GROUP3/Sourcebook/pull/181) Rob requested changes: `_validate_rate_metric` accepted `NaN`. The follow-up rejected non-finite rates; Rob approved after re-review. | [#181](https://github.com/CMSC495-GROUP3/Sourcebook/pull/181) |

## Coverage

### What is enforced today

CI runs pytest with `--cov-fail-under=80` on Python 3.11 through 3.14 ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Locally that is `make cov` / `make check` ([CONTRIBUTING.md](../CONTRIBUTING.md#checking-a-change)). A job that lands under 80% is red. That is a floor, not a published percentage.

The web job runs Vitest with an 80% floor on statements, branches, functions, and lines, measured only on the files listed in `web/vitest.config.ts`, not all of `web/src`. That is also a floor.

### Where the release coverage comes from

Both test jobs write a markdown table into the Actions job summary and save it as `coverage-table.md`: one row per file, with a total. The Python table comes from the 3.12 job and is written on every run. The web table is written whenever Vitest finishes with all tests passing; a failing test leaves Vitest with no coverage summary, so that run has no web table. In the web pack the table sits next to the two Vitest JSON files. Every green push to `main` then uploads two artifacts named for the commit and kept for 90 days ([PR #261](https://github.com/CMSC495-GROUP3/Sourcebook/pull/261)):

| Artifact | Files |
| --- | --- |
| `python-coverage-<sha>` | `coverage.xml`, `coverage-table.md` |
| `web-coverage-<sha>` | `coverage-table.md`, `coverage-summary.json`, `coverage-final.json` |

A push to `main` never cancels the `main` run in progress, so each merged commit gets a finished run. A run still queued behind it can be replaced by a newer push; re-run it from the Actions page if that commit needs evidence.

Artifacts expire, so the release commits the table. After the Monday 28 September freeze, the candidate commit's artifacts are copied into `docs/releases/v1.0.0/evidence/coverage.md` (drafted in [PR #274](https://github.com/CMSC495-GROUP3/Sourcebook/pull/274)) with a link to the run that produced them:

1. Open the green push-to-`main` CI run for the candidate commit, or list it with `gh run list --workflow ci.yml --branch main --commit <sha>`.
2. Download both packs: `gh run download <run-id> -n python-coverage-<sha> -n web-coverage-<sha>`, or from the run's Artifacts section.
3. Paste each `coverage-table.md` into its section of `coverage.md`, and record the full SHA and the run URL.

Only documentation merges after the freeze, so the tagged commit runs the same code, and its own run's artifacts should give the same tables. Check them before tagging. **Final Python and web coverage: Pending**, until the candidate run exists. This page cites the totals from `coverage.md` once that file holds them; it does not quote a number before then.

Latest green CI on this snapshot: [run 35039401655](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/35039401655) at `88e8a13`. Open that run's Python-test job summary for the table from that SHA. Do not treat the badge as a coverage number.

### What the suite covers, and what it does not

From the README [Tests and CI](../README.md#tests-and-ci) section, which matches `tests/` on `main`:

**Covered (stubbed suite):** the grounding gate and its best-not-mean rule, server-side history filtering, the SSE protocol, first-turn caching and invalidation, query logging, query-log analysis reports ([PR #171](https://github.com/CMSC495-GROUP3/Sourcebook/pull/171), `tests/test_query_log_reports.py`), escalations end to end, ingestion without real services, the labeled evaluation set and its metrics, and bookkeeping after a client hangs up mid-stream.

**Frontend coverage:** [PR #252](https://github.com/CMSC495-GROUP3/Sourcebook/pull/252) adds Vitest and React Testing Library coverage for the chat stream, message and escalation behavior, theme toggle, and theme storage. On its validated head, `npm test` ran 32 tests across five files and reported 99.46% statements, 96.42% branches, 100% functions, and 99.37% lines for the five configured source files. Each metric clears the enforced 80% floor. The command runs from `make check` and the web CI job.

**Not covered:** live calls to AWS, Atlas, or OpenAI, visual regression, and full browser workflows. `tsc`, ESLint, and the production build check the rest of `web/`; the focused unit-coverage numbers above do not describe the entire frontend.

The suite is the real application with Mongo, the model, and vector search replaced (`tests/conftest.py`, `scripts/loadtest/fakemongo.py`). A green `make check` does not measure retrieval quality.

## Performance and reliability

| Artifact | What it measures | What it does not measure | Link |
| --- | --- | --- | --- |
| Synthetic chat throughput | Thread-pool ceiling with fake model, in-memory Mongo, canned retrieval, limiter off. 40 tokens → 14.9 req/s; 320 tokens → 98.7 req/s; refusal path ~700 req/s; cache hits 210–522 req/s. | Deployed-pilot latency, real OpenAI/Atlas, or the 10,000-user claim under live load. | [docs/load-testing.md](load-testing.md) |
| Alpha live benchmark | Bounded public-URL run on 2026-09-10 against the pilot with real OpenAI and Atlas. Operator-agreed targets (generated TTFT p50 ≤ 4.0s, generated total max ≤ 30s, cached TTFT max ≤ 1.5s, refused total max ≤ 3.0s, error rate 0). Status on that page: **run performed, every target met.** Sample is eight chat requests. | 10,000 concurrent users, p95, or a beta/final repeat. | [live-benchmark.md](releases/v0.1.0-alpha.1/live-benchmark.md), [results JSON](releases/v0.1.0-alpha.1/live-benchmark-results.json) |
| Deployed load run | Protocol only. [PR #278](https://github.com/CMSC495-GROUP3/Sourcebook/pull/278) merged the plan: 5, 10, 20, and 40 concurrent users against the pilot with the real model, capped at 80 requests. The run happens on the `v1.0.0` candidate after the freeze. | Any measured figure yet; the page says Pending. | [docs/load-testing-pilot.md](load-testing-pilot.md), [issue #212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212) |
| Alpha smoke evaluation | Two host runs of the 20-case smoke tier (`9871e3e` vs `4e90382`). Recall@5, citation correctness, and grounded-answer rate are 100% of 12 answerable cases on both commits. Unsupported-refusal handling and prompt-injection grounding-gate refusal are **0%** of their cases on both commits. | A product-quality PASS. The zeros are [issue #192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192), since closed; the [beta's smoke run](releases/v0.2.0/live-evaluation.md#results-against-the-alpha) scores both at 100%. [Issue #189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189) (follow-ups scored only the rewrite) was closed by [PR #245](https://github.com/CMSC495-GROUP3/Sourcebook/pull/245); that does not close #192. The full tier was first run on the beta; see the beta full-tier row. | [live-evaluation.md](releases/v0.1.0-alpha.1/live-evaluation.md), [results JSON](releases/v0.1.0-alpha.1/live-evaluation-results.json), [docs/evaluation.md](evaluation.md) |
| Beta full-tier evaluation | [Run 36267109629](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36267109629) on the `v0.2.0` tag `383cea5`, 2026-09-26: 59 cases. Recall@5, citation correctness, and grounded-answer rate are 95.9% (47 of 49 answerable); unsupported-refusal handling is 100% of 4 and prompt-injection gate refusal 100% of 3. Both misses retrieved an overlapping policy; one exposes a contradiction between two sample policies on the incident-reporting window. | The final's full tier ([issue #213](https://github.com/CMSC495-GROUP3/Sourcebook/issues/213)), or anything about a real corpus. | [live-evaluation.md](releases/v0.2.0/live-evaluation.md#full-tier-run-on-2026-09-26), [results JSON](releases/v0.2.0/live-evaluation-full-results.json) |
| Live evaluation workflow | Manual Actions job against real secrets. [PR #226](https://github.com/CMSC495-GROUP3/Sourcebook/pull/226) merged on 2026-09-13 (`112c96e`) and closed [issue #223](https://github.com/CMSC495-GROUP3/Sourcebook/issues/223): `scripts/validate_live_evaluation.py` and [evaluation.yml](https://github.com/CMSC495-GROUP3/Sourcebook/blob/main/.github/workflows/evaluation.yml) fail-close on empty or illegal `MONGODB_DB`, empty secrets, a nonzero evaluator exit, and missing or malformed results. CI also runs the synthetic checks in `scripts/test_live_evaluation_fail_closed.sh`. [PR #229](https://github.com/CMSC495-GROUP3/Sourcebook/pull/229) was closed as a duplicate of #226 and was not merged. A green workflow means the instrument recorded a trustworthy results file, not that refusals passed. Latest successful runs: the beta smoke tier, [run 36062704072](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36062704072) at `231e652`, and the beta full tier, [run 36267109629](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36267109629) at `383cea5`. | Refusal-quality PASS. A green run means the results file is trustworthy, not that the scores are good. | [evaluation.yml](https://github.com/CMSC495-GROUP3/Sourcebook/blob/main/.github/workflows/evaluation.yml), [PR #181](https://github.com/CMSC495-GROUP3/Sourcebook/pull/181), [PR #226](https://github.com/CMSC495-GROUP3/Sourcebook/pull/226) |
| Lighthouse | Not run. | — | [issue #214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214) |
| Beta live benchmark | The alpha's bounded protocol, run on 2026-09-24 against the pilot. Status on that page: **every target met.** | The final's repeat, which follows the freeze ([issue #215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215)). | [live-benchmark.md](releases/v0.2.0/live-benchmark.md), [results JSON](releases/v0.2.0/live-benchmark-results.json) |

### Local quality loop

```bash
make fmt      # ruff --fix and ruff format; version pinned in requirements/lint.txt
make check    # pytest, ruff, ESLint, tsc, Vite build; what CI's main path runs
make cov      # pytest --cov; still fails under 80%
make audit    # pip-audit and npm audit; accepted advisories in scripts/audit.sh
```

`make stub` is not a quality measurement. Fake embeddings are noise; do not tune `SIMILARITY_THRESHOLD` or judge refusal quality from the stub ([CONTRIBUTING.md](../CONTRIBUTING.md#things-that-will-bite-you)).

## What this page will gain later

When `docs/releases/v1.0.0/evidence/coverage.md` holds the candidate's tables (#210), add the Python and web totals and the run link to the coverage section above. When #212, #213, and #214 produce artifacts, add rows to the table above. #226 already merged the fail-closed Live evaluation instrument; a green workflow is a trustworthy measurement, not a pass.
