# Sourcebook v1.0.0 handoff

Sourcebook answers employee policy questions from a fixed corpus of company
documents and cites the document behind every answer. When the corpus does not
cover a question, it says so and offers to hand the question to Human
Resources rather than guessing.

This page is the entry point for reviewing the Unit 8 final release. It names
the commit under review, lists what changed since the
[beta](../v0.2.0/handoff.md), links the evidence behind each claim, and states
what the release does not establish. Nothing here is called verified without a
link that shows it.

**Status: draft, no candidate yet.** The plan on
[#215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215#issuecomment-5824613941)
freezes code on Monday 28 September. `main` at that point is the candidate,
and every Pending cell below is measured on it. Until the blocker table at the
end of this page is clear, treat every Pending cell as unmeasured.

## Where to start

- **Graders:** start at [portfolio.md](portfolio.md). It has one row per
  item in the assignment, each linking to its evidence.
- **See it running.** The pilot is at <https://sourcebook.duckdns.org>. The
  reviewer password comes through the course channel, not this repository.
- **Run it yourself.** [docs/install.md](../../install.md), or `git clone`
  then `make setup && make stub`: fake model, in-memory database, no accounts.
- **Read the code.** The [README](../../../README.md), the
  [API guide](../../api.md), the [CI/CD page](../../ci-cd.md), and the
  [quality page](../../quality.md).

## The submitted version

| Field | Value |
| --- | --- |
| Commit | Pending: the merge commit of the release pull request that fills this folder |
| Tag and release | Pending: `v1.0.0`, annotated, a full release (not a prerelease), on that commit |
| Running at | <https://sourcebook.duckdns.org> |
| Deployed commit | Pending: read `HEAD` and `refs/deployed/main` on the pilot host and record them with the time checked |
| CI | Pending: the push-to-`main` run on the merge commit |
| Security | Pending: the push-to-`main` run on the merge commit |
| Code under test | Pending: `main` at the Monday 28 September freeze. The release pull request adds documentation only, so its merge commit runs the same code |

## What changed since the beta

Pending until the freeze. So far:

| Area | Change | Pull requests |
| --- | --- | --- |
| Refusal card | The card says which check refused. A question refused by the coverage judge no longer shows "Strong match" under "No matching policy" or claims nothing indexed came close ([#269](https://github.com/CMSC495-GROUP3/Sourcebook/issues/269)) | #271 |
| Projects | Assigning a conversation to a project and deleting that project no longer race: on a replica set, which Atlas clusters like the pilot's are, both run in MongoDB transactions, and the assignment writes to the project so it conflicts with a concurrent delete ([#142](https://github.com/CMSC495-GROUP3/Sourcebook/issues/142)). The in-memory stub has no transactions and keeps the old sequential behavior. The move-to-project menu stays open when the pointer leaves the row | #279, #272 |
| HR Requests and Policy Library on a phone | Back from the list leaves the page instead of reopening the item just left, and a resolve leaves one list entry. Focus moves to the item's heading when it opens, back to its row when you return, and to the list heading after a resolve or reopen, which is announced to screen readers ([#266](https://github.com/CMSC495-GROUP3/Sourcebook/issues/266)) | #277 |
| README | Release, pilot site, and Ruff badges | #273 |
| Refusal card for vague questions | When related policies don't answer a question as asked, the card says to ask the full question again with the details it depends on, such as dates, location, or the kind of leave or expense. The coverage judge is unchanged | #281 |
| Sign-in page and Lighthouse | The sign-in page has a main landmark and a meta description. `scripts/lighthouse/` runs Lighthouse on the three pages in both themes at phone and desktop widths ([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)) | #280 |
| Compression on the pilot | Nginx gzips responses that come through Caddy. Before, Caddy's `Via` header made Nginx skip gzip, so the pilot served its 674 KB JavaScript bundle uncompressed. The chat stream stays uncompressed and unbuffered | #282 |
| What People Ask | A page for Human Resources that ranks the questions no policy answered and the questions asked in more than one conversation, over 7, 30, or 90 days, from `GET /api/reports/gaps`. Wordings whose embeddings are within `QUESTION_GROUP_THRESHOLD` cosine (0.85) share a row ([#287](https://github.com/CMSC495-GROUP3/Sourcebook/issues/287)); the threshold is measured in [docs/evaluation.md](../../evaluation.md#question-grouping-threshold). The "Asked most" caption names the bar colors in plain words ([#294](https://github.com/CMSC495-GROUP3/Sourcebook/issues/294)) | #286, #288, #297 |
| HR password | `HR_PASSWORD_HASH` is a third password. HR Requests, What People Ask, and their routes return 403 to any other session, and the sidebar hides both links. Filing an escalation from the chat still needs only the shared password. On the pilot the HR hash equals the second one, so the reviewer password opens both pages ([#290](https://github.com/CMSC495-GROUP3/Sourcebook/issues/290)) | #295 |
| What People Ask at volume | The grouped report returns at most 1,000 session ids per wording with an exact count beside them, so one question asked in 400,000 conversations no longer exceeds MongoDB's 16 MB document limit. A window over Mongo's memory limit gets 503 and "Try a shorter window." instead of 500. Timings from a local `mongo:7`, not Atlas, are in [docs/load-testing.md](../../load-testing.md) ([#291](https://github.com/CMSC495-GROUP3/Sourcebook/issues/291)) | #296 |
| Sample policies | The injury policy's incident-reporting window now matches the Workplace Health and Safety Policy: report no later than 24 hours after the incident, instead of by the end of the shift. The pilot was re-ingested on 2026-09-26, so the corpus version differs from the beta's | #284 |
| Documentation | User guide ([#206](https://github.com/CMSC495-GROUP3/Sourcebook/issues/206)) and team page ([#209](https://github.com/CMSC495-GROUP3/Sourcebook/issues/209)) pending; [portfolio page](portfolio.md) in this folder; pilot load-run page; README and quality page corrected where the beta made their status claims stale | Pending: #259, #231; #274, #278, #285 |

## Verification status

| Check | Status | Evidence |
| --- | --- | --- |
| Python lint and tests on 3.11 to 3.14 with the 80% floor, web lint, types, tests, and build, both Docker images, Compose validation | Pending on the release merge commit | none yet |
| CodeQL, dependency audit, secret scan | Pending on the release merge commit | none yet |
| Coverage, Python and web, for the tagged commit ([#210](https://github.com/CMSC495-GROUP3/Sourcebook/issues/210)) | Pending: copy from the candidate's `python-coverage-<sha>` and `web-coverage-<sha>` artifacts | [evidence/coverage.md](evidence/coverage.md) |
| Answer quality, smoke tier | Pending | [live-evaluation.md](live-evaluation.md) |
| Answer quality, full tier, against the beta's run as the before ([#213](https://github.com/CMSC495-GROUP3/Sourcebook/issues/213)) | Pending | [live-evaluation.md](live-evaluation.md) |
| Real-service latency and error rate on the pilot | Pending | [live-benchmark.md](live-benchmark.md) |
| Load run against the deployed pilot ([#212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212)) | Pending | [docs/load-testing-pilot.md](../../load-testing-pilot.md), Pending |
| Lighthouse, both themes, phone and desktop ([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)) | Pending: run `scripts/lighthouse` (#280) against the pilot on the candidate | [docs/quality.md](../../quality.md), Pending |
| End-to-end pass by hand | Pending | [below](#end-to-end-pass-by-hand) |
| What People Ask on the pilot's query log, 30-day window, signed in with the HR password | Pending: record the headline counts and a sanitized screenshot. Question text can identify who asked, so crop or blur it | none yet |
| Screenshots of green CI, Security, and auto-deploy runs ([#207](https://github.com/CMSC495-GROUP3/Sourcebook/issues/207)) | Pending | [evidence/](evidence/README.md) |

### End-to-end pass by hand

Pending. Repeat the beta's pass with the same steps and expected results, and
add steps for the #271, #277, and #295 fixes and the What People Ask page.
Sign in with the reviewer password, which on the pilot is also the HR
password, and switch to the shared employee password only for the step that
says so. Save sanitized screenshots to [evidence/](evidence/README.md): no
password, token, or session id visible.

| Field | Value |
| --- | --- |
| Date (UTC) | Pending |
| Tester | Pending |
| Browser and version | Pending |
| Deployed commit | Pending |

| Step | Expected | Result |
| --- | --- | --- |
| Sign in with the reviewer password | lands on the chat page with HR Requests and What People Ask in the sidebar; a wrong password shows "Incorrect password." | Pending |
| Ask a covered question | streamed answer with at least one cited source and a score | Pending |
| Open a cited source | the source pane shows the whole document | Pending |
| Ask a follow-up in the same conversation | the answer uses the history; no cache badge | Pending |
| Reload the page | the conversation and its sources are restored from history | Pending |
| Ask an uncovered question in a new conversation | refusal card with the Ask Human Resources button | Pending |
| Ask an uncovered question as a follow-up (#189) | refusal card, not an answer with unrelated chips | Pending |
| Ask `unanswerable_01`, "Does Meridian reimburse employee pet insurance?" (#192, #269) | refusal card that says the coverage check refused it, without "Strong match" under "No matching policy" | Pending |
| Escalate the refusal with a note | confirmation in the UI; the record appears on the HR Requests page | Pending |
| Escalate the same message again | the first record comes back, not a second one | Pending |
| Resolve the request on the HR Requests page, then reopen it | the request moves between the open and resolved lists | Pending |
| Open What People Ask and switch between 7, 30, and 90 days (#286, #288) | the headline counts questions and the share no policy answered; both lists load; the URL carries `?days=` | Pending |
| Sign out, sign in with the shared employee password, then open `/gaps` (#290) | no HR links in the sidebar; the page says it is for Human Resources instead of loading the report | Pending |
| At 390px wide, keyboard only: open a request on the HR Requests page, choose "All requests", then press Back (#266) | focus lands on the request's heading, then on its row; Back leaves the page instead of reopening the request | Pending |

## Known defects and limitations

Carried from the beta unless fixed before the freeze. Update at the freeze.

| Issue | What a pilot user would see | Mitigation |
| --- | --- | --- |
| Vague questions on covered topics | "Can I expense this trip?" is refused where the alpha answered in general terms ([beta evaluation](../v0.2.0/live-evaluation.md#manual-review)) | the refusal card now says to ask the full question again with the details it depends on (#281); or use Ask Human Resources |
| Conversations are not scoped to their owner | anyone with a password can list and open every conversation through `GET /api/conversations`, including the question text the HR pages show (README [Known limitations](../../../README.md#known-limitations)) | a pilot with a few reviewers; draft PR #299 scopes conversations to the browser that made them, and would move this row to the changes above if it merges before the freeze. Its deploy signs everyone out, and conversations from before it have no owner, so the app can no longer reach them; their retention is item 3 of [#300](https://github.com/CMSC495-GROUP3/Sourcebook/issues/300) |
| Any signed-in session can rebuild the document index | `POST /api/documents/reindex` needs only the shared password, and a rebuild bumps the corpus version, which empties the answer cache | the route is rate-limited; who may call it is item 5 of [#300](https://github.com/CMSC495-GROUP3/Sourcebook/issues/300) |
| What People Ask merges few paraphrases | at 0.85 cosine it merged 4 of 40 labelled paraphrases and none of 40 different questions ([measurement](../../evaluation.md#question-grouping-threshold)), so "Asked most" undercounts a question asked in different words | the caption says so; draft PR #298 ([#293](https://github.com/CMSC495-GROUP3/Sourcebook/issues/293)) confirms candidate pairs with the utility model |
| README known limitations | shared passwords plus an HR password, a threshold set by judgement, non-atomic re-ingestion, one instance, a fictional corpus | documented in the README |

## What this release does not establish

Pending: rewrite at the freeze from what was measured. Start from the beta's
list: load (#212), full-tier quality (#213), accessibility and web performance
(#214), `CustomerDataProvider` not written, a fictional corpus, one instance
with no failover. Add the What People Ask report at volume: #296 timed it on
a local `mongo:7`, not Atlas, and neither query shape answers a 90-day window
within the route's 5 s limit at the 7M rows a day planned in `config.py`
([#291](https://github.com/CMSC495-GROUP3/Sourcebook/issues/291)). Remove
only the items the measurements above actually settle.

## The tag

The tag is the claim that the release was verified, so it waits for every row
below. `v1.0.0` is the final release, so it is not marked prerelease:

```bash
git fetch upstream
git tag -a v1.0.0 <merge commit> -m "Unit 8 final: verified per docs/releases/v1.0.0/handoff.md"
git push upstream v1.0.0
gh release create v1.0.0 --repo CMSC495-GROUP3/Sourcebook \
  --title "v1.0.0" --notes-file docs/releases/v1.0.0/release-notes.md
```

Rewrite relative links in the release body to absolute links into the tagged
tree. Then open the follow-up pull request that writes the tagged SHA, the tag
link, the CI and Security run links, and the video link into this page, the
README, `docs/README.md`, and `portfolio.md`. That pull request closes
[#215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215) and
[#201](https://github.com/CMSC495-GROUP3/Sourcebook/issues/201).

| Blocker | State |
| --- | --- |
| Code frozen on `main`; the candidate commit named in the table at the top of this page | Pending: Monday 28 September |
| Smoke and full tier on the candidate, recorded in [live-evaluation.md](live-evaluation.md) | Pending |
| Bounded benchmark against the pilot, recorded in [live-benchmark.md](live-benchmark.md) | Pending |
| End-to-end pass by hand, recorded above with screenshots | Pending |
| Coverage for the candidate in [evidence/coverage.md](evidence/coverage.md) | Pending |
| Load run and Lighthouse, or recorded as not measured | Pending |
| `docs/user-guide.md` and `docs/team.md` on `main` | Pending: #259, #231 |
| Release pull request merged, with its CI and Security runs green and linked in the table at the top of this page | Pending |
