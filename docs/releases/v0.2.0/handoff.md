# Sourcebook beta handoff

Sourcebook answers employee policy questions from a fixed corpus of company
documents and cites the document behind every answer. When the corpus does not
cover a question, it says so and offers to hand the question to Human
Resources rather than guessing.

This page is the entry point for reviewing the Unit 6 beta. It names the
commit under review, lists what changed since the
[alpha](../v0.1.0-alpha.1/handoff.md), links the evidence behind each claim,
and states what the beta does not establish. Nothing here is called verified
without a link that shows it.

**Status: tagged.** [`v0.2.0`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.2.0) is on `383cea5`, the merge of the
release pull request, after every row in the blocker table at the end of this
page was done.

## Where to start

- **See it running.** The demo site is at <https://sourcebook.duckdns.org>. It has
  a reviewer password separate from the team's; the team supplies it through
  the course channel, not through this repository.
- **Run it yourself in about two minutes.** `git clone`, then `make setup && make
  stub`. That starts the whole app with a fake model and an in-memory database,
  so it needs no accounts, no API key, and no network.
- **Read the code.** The [README](../../../README.md) explains what the system
  does. [docs/install.md](../../install.md) is the installation guide,
  [docs/api.md](../../api.md) the API reference, [docs/ci-cd.md](../../ci-cd.md)
  the pipeline, and [docs/quality.md](../../quality.md) the review, coverage,
  and performance evidence.

## The submitted version

| Field | Value |
| --- | --- |
| Commit | `383cea5a5c2154fa4d7688e642d94299191a88a1`, the merge of PR #267 into `main` on 2026-09-24 |
| Tag and release | [`v0.2.0`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.2.0), annotated, prerelease, on that commit |
| Running at | <https://sourcebook.duckdns.org> |
| Deployed commit | `201754eb64b3d8a83d9d8da47b658ba0176a40c0`, the merge of PR #254, from `HEAD` and `refs/deployed/main` on the demo host on 2026-09-24 at 22:05 UTC. The auto-deploy recreated only the web container, at 21:52:35 UTC. The API container has run `231e652` since 21:39 UTC, and #254 changed no Python. So the benchmark at 21:49 ran entirely on `231e652`, and the browser pass from 21:53 ran the #254 web client against that same API |
| CI | [run 36065801208](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36065801208), success |
| Security | [run 36065801170](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36065801170), success |
| Code under test | `231e65224efa3ecf688af0f89b8d4d0ce924d153`, `main` after [PR #268](https://github.com/CMSC495-GROUP3/Sourcebook/pull/268), for the live evaluation below. Since then only [PR #254](https://github.com/CMSC495-GROUP3/Sourcebook/pull/254) has merged, which changes the web client and none of the Python code the evaluation runs; the release pull request adds documentation only |

## What changed since the alpha

Every blocker the alpha listed for the beta in
[#203](https://github.com/CMSC495-GROUP3/Sourcebook/issues/203) is closed.

| Area | Change | Pull requests |
| --- | --- | --- |
| Refusal card follows the model's own decline | Follow-ups are gated on the question as asked, not only the condensed rewrite (#189). A fail-closed coverage judge runs after the cosine gate clears and refuses before answer generation when the passages do not answer the question (#192) | #245, #253 |
| Provider saturation | Both chat routes answer HTTP 503 with `{"error", "retryable": true}` and `Retry-After`, and the stream sends the same as an event, instead of a generic error (#118). The web app shows the busy message with one Retry that resends the same question once (#246) | #247, #254 |
| Passage identity | Unique index on `(source, chunk_index)` with a one-time migration, deployed to the demo site (#158) | #176 |
| Knowledge-gap report | `python -m sourcebook.rag.query_log_reports` reads the query log for content gaps (#160) | #171 |
| HR queue in the app | An HR Requests page lists open and resolved escalations, resolves and reopens them, and retries webhook delivery, laid out as list and detail with the request in the URL. Delivery state is reported as it stands | #250, #263, #264 |
| Phone and source pane | Mobile drawer height fixed so the theme switch is reachable (#174); the source pane docks on narrower windows and collapses; passages render as Markdown | #234, #242, #240, #202 |
| Web tests | Vitest and React Testing Library cover the chat stream, messages, escalation button, and theme toggle (#211), and the HR queue since its pages landed. `make check` and CI run them with an 80% floor | #252, #250, #264 |
| Security | `python-jose` replaced by PyJWT to drop the `ecdsa` advisory; `session_id` sanitized at log sinks | #239, #220 |
| Evaluation workflow | The runner is admitted to the Atlas access list for the run; empty or invalid `MONGODB_DB` fails at preflight; the embedding cache is off; `commit_sha` must be a full SHA on `main` history, and results record `requested_sha` and `tested_sha` | #197, #226, #244, #258 |
| CI evidence | SHA-named Python and web coverage artifacts on green `main` runs, kept 90 days | #261 |
| Documentation | Installation guide, committed OpenAPI document and API guide, CI/CD page, quality page, evidence numbers sheet, stakeholder video script | #233, #221, #228, #232, #260, #262 |
| Package | Python package renamed from `policy_assistant` to `sourcebook`; docs moved under `docs/` | #199, #196 |

## Verification status

| Check | Status | Evidence |
| --- | --- | --- |
| Python lint and tests on 3.11 to 3.14 with the 80% floor, web lint, types, tests, and build, both Docker images, Compose validation | Passed on `d82749d` and on the release merge commit `383cea5` | [CI run 36057773007](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36057773007), [CI run 36065801208](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36065801208) |
| CodeQL, dependency audit, secret scan | Passed on `d82749d` and on the release merge commit `383cea5` | [Security run 36057772985](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36057772985), [Security run 36065801170](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36065801170) |
| Answer quality against the live system, smoke tier | Measured on `231e652`: all five scored metrics 100%, including both refusal metrics that were 0% in the alpha. All three injections resisted; one of three ambiguous questions is now refused instead of answered | [live-evaluation.md](live-evaluation.md), [run 36062704072](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36062704072), `live-evaluation-results.json` |
| Real-service latency and error rate on the demo site | Passed on 2026-09-24: all five targets met in 7 requests, no errors, no rate limiting | [live-benchmark.md](live-benchmark.md), `live-benchmark-results.json` |
| End-to-end pass through the deployed app by hand | Passed on 2026-09-24, all eleven steps, with one defect found in the refusal card's wording | [below](#end-to-end-pass-by-hand), [evidence/](evidence/README.md) |
| Knowledge-gap report run once against the demo site's query log | Run on 2026-09-24 over the 90-day window: 55 logged questions, 5 refused, no content gap asked about more than once except a test question | [below](#knowledge-gap-report), `knowledge-gap-report.txt` |

The coverage judge was measured once before it merged, on the host against
the pull request head `130c0fb`: both refusal metrics at 100% and the three
answerable metrics at 100%
([#253](https://github.com/CMSC495-GROUP3/Sourcebook/pull/253#issuecomment-5783418040)).
That was not this commit, and it was not run by the workflow, so it is the
reason to expect the smoke tier to pass, not the evidence that it did.

### End-to-end pass by hand

The alpha's pass with the same steps and expected results, plus the #189 and
#192 questions and the HR Requests page that are new in this release. The
screenshots are in [evidence/](evidence/README.md); none shows a password,
token, or session id. `ESCALATION_WEBHOOK_URL` is not set on the demo site, so
escalations are stored and nothing is delivered, and the HR Requests page says
"No webhook configured".

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-09-24, 21:53 to 21:56 |
| Tester | Taylor Shahan, with Claude Code driving Chrome through Playwright |
| Browser and version | Google Chrome 152.0.7977.77 (Playwright headless), 1440x1000 |
| Deployed commit | web `201754eb64b3d8a83d9d8da47b658ba0176a40c0` (PR #254), API `231e65224efa3ecf688af0f89b8d4d0ce924d153`; see the table at the top |

| Step | Expected | Result |
| --- | --- | --- |
| Sign in with the reviewer password | lands on the chat page; a wrong password shows "Incorrect password." | Pass. `01`, `02` |
| Ask a covered question | streamed answer with at least one cited source and a score | Pass. "How many PTO days do I get in my first year?" answered 15 days a year, 5.00 hours per pay period, at "Strong match · 76%" with three source chips. `03` |
| Open a cited source | the source pane shows the whole document | Pass. The Paid Time Off (PTO) Policy chip opened all 5 passages in the source pane, with a link to the Policy Library. `04` |
| Ask a follow-up in the same conversation | the answer uses the history; no cache badge | Pass. "Does that change after five years of service?" answered with the 3-to-5-year and 6-plus-year accrual rows. The web app no longer shows a cache badge on any answer. `05` |
| Reload the page | the conversation and its sources are restored from history | Pass. The browser reported the navigation as a reload, the conversation text after it matched the text before it exactly, and every turn came back with its score and chips. The first screenshot of this step was byte-identical to `05` and showed only the second turn, so it proved nothing. `06` was retaken at 22:04 UTC on the same conversation and the same deployed containers, scrolled to the top. By then the conversation also held the #189 turn from the next step |
| Ask an uncovered question as a follow-up (#189) | refusal card, not an answer with unrelated chips | Pass. "What is the boiling point of mercury at sea level?" inside the PTO conversation scored 59% and got the refusal card. In the alpha it scored 69% there and was answered. `07` |
| Ask an uncovered question in a new conversation | refusal card with the Ask Human Resources button | Pass. The same question, 59%, refusal card with the button. `08` |
| Ask `unanswerable_01`, "Does Meridian reimburse employee pet insurance?" (#192) | refusal card, not a prose decline with chips | Pass, with a defect. The refusal card came back with no chips. It also shows "Strong match · 79%" under the "No matching policy" heading and says "Nothing indexed came close enough to answer from." The coverage judge refused it after the cosine gate cleared, so both the badge and that sentence are wrong for this kind of refusal ([#269](https://github.com/CMSC495-GROUP3/Sourcebook/issues/269)). `09` |
| Escalate the refusal with a note | confirmation in the UI; the record appears on the HR Requests page | Pass. "Sent to Human Resources · ref 53241cfa", and the record heads the open list with the note, reason Refused, and 79%. `10`, `11`, `12` |
| Escalate the same message again | the first record comes back, not a second one | Pass. A second `POST /api/escalations` for the same message returned HTTP 200 with the same `escalation_id` |
| Resolve the request on the HR Requests page, then reopen it | the request moves between the open and resolved lists | Pass. Resolving with a note moved it to Resolved with the note shown; Reopen request moved it back, and `GET /api/escalations/{id}` read `open`. `13`, `14`. The record was resolved again afterwards so the demo site's queue holds no test request |

The untitled rows in the sidebar in these screenshots are the benchmark's
sessions from a few minutes earlier. The script creates conversations through
the API without a title.

### Knowledge-gap report

`python -m sourcebook.rag.query_log_reports --since 2026-06-26 --until
2026-09-24T21:47:31` ran once on the demo host, from the checkout's `.venv`
against the demo site's Atlas cluster. The output is `knowledge-gap-report.txt`
beside this page. The window covers the whole 90-day log retention.

- 55 questions logged: 50 answered, 5 refused.
- Content gaps: "What is the boiling point of mercury at sea level?" three
  times, which is the team's own test question, and two one-off questions
  ("How do I go about eating an elephant?" and "no"). No employee topic was
  refused more than once, so the report names no document to add.
- FAQ candidates: first-year PTO (12 times), PTO at two years of service (4),
  and the 401(k) match (2).
- Among rows with a score, answered questions run from 0.63 to 0.86 and
  refused ones from 0.58 to 0.60, on either side of the 0.62 threshold. Eight
  answered and two refused rows have no score recorded.

The log is almost all team testing, so the report shows the tool works on the
demo. It is not evidence about what real employees ask.

## Known defects and limitations

| Issue | What a demo-site user would see | Mitigation in the beta |
| --- | --- | --- |
| [#266](https://github.com/CMSC495-GROUP3/Sourcebook/issues/266) | on a phone, Back can reopen the request or policy just left, and keyboard focus falls to the top of the page when the list and detail panes switch | use the "All requests" link; on a desktop both panes show at once |
| [#142](https://github.com/CMSC495-GROUP3/Sourcebook/issues/142) | concurrent project assignment and deletion can race | a single-operator demo makes this unlikely at this volume |
| [#269](https://github.com/CMSC495-GROUP3/Sourcebook/issues/269), found in this pass | a question refused by the judge shows its cosine score as "Strong match · 79%" under "No matching policy", and the card says nothing indexed came close. Both are true only of a cosine-gate refusal | the refusal itself and the Ask Human Resources button are correct; only the badge and one sentence mislead |
| Vague questions on covered topics, from the live evaluation | "Can I expense this trip?" is refused by the coverage judge where the alpha answered in general terms. Neither version asks what the trip was | the refusal card offers Human Resources; asking a more specific question gets an answer |
| README known limitations | a shared password, a threshold set by judgement, non-atomic re-ingestion, one instance, a fictional corpus | documented in the README; none of them blocks a class demo |

## What this beta does not establish

The 10,000-user requirement still rests on the synthetic measurements in
[docs/load-testing.md](../../load-testing.md), taken with the model faked, the
database in memory, and the chat limiter off. The deployed system has not been
measured under concurrent load
([#212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212)).

Answer quality is measured on the 20-case smoke tier. The full tier has not
been run against this commit
([#213](https://github.com/CMSC495-GROUP3/Sourcebook/issues/213)).

Accessibility and web performance have not been measured
([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)).

`CustomerDataProvider` is designed and not written.

The corpus is fictional. Sourcebook has never been run against a real
company's policies.

## The tag

The tag is the claim that the beta was verified, so it waits for every row
below. The commands are the alpha's, with the version changed:

```bash
git fetch upstream
git tag -a v0.2.0 <merge commit> -m "Unit 6 beta: verified per docs/releases/v0.2.0/handoff.md"
git push upstream v0.2.0
gh release create v0.2.0 --repo CMSC495-GROUP3/Sourcebook --prerelease \
  --title "v0.2.0" --notes-file docs/releases/v0.2.0/release-notes.md
```

Rewrite relative links in the release body to absolute links into the tagged
tree. Then open the follow-up pull request that writes the tagged SHA, the tag
link, and the CI and Security run links into this page, the README, and
`docs/README.md`. That pull request closes
[#203](https://github.com/CMSC495-GROUP3/Sourcebook/issues/203).

| Blocker | State |
| --- | --- |
| Smoke-tier live evaluation on the code under test, recorded in [live-evaluation.md](live-evaluation.md) | Done: run 36062704072, results JSON saved, six manual dispositions recorded |
| Bounded benchmark against the demo site, recorded in [live-benchmark.md](live-benchmark.md) | Done: every target met |
| End-to-end pass by hand, recorded above with screenshots | Done: eleven of eleven steps pass, one defect recorded |
| Knowledge-gap report run once against the demo site's query log | Done: `knowledge-gap-report.txt` |
| Release pull request merged, with its CI and Security runs green and linked in the table at the top of this page | Done: PR #267 merged as `383cea5`; CI and Security green |
