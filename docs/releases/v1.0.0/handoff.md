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

**Status: draft, candidate named.** The candidate is `main` at
[`7d3c779`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/7d3c7795c197c5be56b15aebc650576760fd75d1),
the merge of #303, named on Sunday 27 September. The plan on
[#215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215#issuecomment-5824613941)
froze code on Monday 28 September; the last code change landed a day early, so
measurement starts then. Documentation can still merge. A code change after
this point makes a new candidate and repeats every measurement. Until the
blocker table at the end of this page is clear, treat every Pending cell as
unmeasured.

## Where to start

- **Graders:** start at [portfolio.md](portfolio.md). It has one row per
  item in the assignment, each linking to its evidence.
- **See it running.** The pilot is at <https://sourcebook.duckdns.org>. Two
  passwords come through the course channel, never this repository: the
  reviewer password, which opens What People Ask as a manager sees it, and
  the HR password, which also opens HR Requests and the unfiltered report.
  See [Passwords on the pilot](#passwords-on-the-pilot).
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
| Deployed commit | `7d3c779` in both `HEAD` and `refs/deployed/main` on the pilot host, checked 2026-09-27 14:10 UTC. Re-check when the tag is cut |
| CI | Pending: the push-to-`main` run on the merge commit |
| Security | Pending: the push-to-`main` run on the merge commit |
| Code under test | [`7d3c779`](https://github.com/CMSC495-GROUP3/Sourcebook/commit/7d3c7795c197c5be56b15aebc650576760fd75d1), the candidate. CI run [36324854066](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854066) and Security run [36324854241](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854241) are green on it. The release pull request adds documentation only, so its merge commit runs the same code |

## Passwords on the pilot

The pilot has four password slots, and a session can do what the password it
signed in with allows. No password is written anywhere in this repository.

| Password | Who has it | Opens |
| --- | --- | --- |
| Shared employee (`APP_PASSWORD_HASH`) | the team | the chat, the Policy Library, projects, and escalating a question |
| Reviewer (`APP_PASSWORD_HASH_2`, also set as `MANAGER_PASSWORD_HASH`) | the grader, through the course channel | everything the employee password opens, plus What People Ask as a manager sees it: only questions asked in at least 3 separate conversations |
| HR (`HR_PASSWORD_HASH`) | the grader and the team's HR tester, through the course channel | everything above, HR Requests, the unfiltered What People Ask, and rebuilding the document index |

Conversations do not follow the password. Each browser keeps its own id, and a
session sees only the conversations started in that browser, whichever
password it signed in with (#299). The deploy of #299 signed everyone out
once.

## What changed since the beta

Every code change on the candidate:

| Area | Change | Pull requests |
| --- | --- | --- |
| Refusal card | The card says which check refused. A question refused by the coverage judge no longer shows "Strong match" under "No matching policy" or claims nothing indexed came close ([#269](https://github.com/CMSC495-GROUP3/Sourcebook/issues/269)) | #271 |
| Projects | Assigning a conversation to a project and deleting that project no longer race: on a replica set, which Atlas clusters like the pilot's are, both run in MongoDB transactions, and the assignment writes to the project so it conflicts with a concurrent delete ([#142](https://github.com/CMSC495-GROUP3/Sourcebook/issues/142)). The in-memory stub has no transactions and keeps the old sequential behavior. The move-to-project menu stays open when the pointer leaves the row | #279, #272 |
| HR Requests and Policy Library on a phone | Back from the list leaves the page instead of reopening the item just left, and a resolve leaves one list entry. Focus moves to the item's heading when it opens, back to its row when you return, and to the list heading after a resolve or reopen, which is announced to screen readers ([#266](https://github.com/CMSC495-GROUP3/Sourcebook/issues/266)) | #277 |
| README | Release, pilot site, and Ruff badges | #273 |
| Refusal card for vague questions | When related policies don't answer a question as asked, the card says to ask the full question again with the details it depends on, such as dates, location, or the kind of leave or expense. The coverage judge is unchanged | #281 |
| Sign-in page and Lighthouse | The sign-in page has a main landmark and a meta description. `scripts/lighthouse/` runs Lighthouse on the three pages in both themes at phone and desktop widths ([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)) | #280 |
| Compression on the pilot | Nginx gzips responses that come through Caddy. Before, Caddy's `Via` header made Nginx skip gzip, so the pilot served its 674 KB JavaScript bundle uncompressed. The chat stream stays uncompressed and unbuffered | #282 |
| What People Ask | A page that ranks the questions no policy answered and the questions asked in more than one conversation, over 7, 30, or 90 days, from `GET /api/reports/gaps`. Wordings whose embeddings are within `QUESTION_GROUP_THRESHOLD` cosine share a row ([#287](https://github.com/CMSC495-GROUP3/Sourcebook/issues/287)). The "Asked most" caption names the bar colors in plain words ([#294](https://github.com/CMSC495-GROUP3/Sourcebook/issues/294)) | #286, #288, #297 |
| What People Ask: the question judge | Pairs of wordings from 0.70 cosine up to the threshold go to the utility model, which lists the pairs that are one question. At most 50 pairs per page load, closest first; the rest wait for a later load, and the page says how many. If the call fails or its reply doesn't parse, nothing below the threshold merges and the page says rewordings aren't being checked. The threshold rose from 0.85 to 0.91, because two different questions one word apart cleared 0.85 on cosine alone. On 120 labelled pairs the combined rule merged 16 to 18 of 60 paraphrases and 0 or 1 of 60 different questions in three runs; the measurement is in [docs/evaluation.md](../../evaluation.md#the-model-check-below-the-threshold) ([#293](https://github.com/CMSC495-GROUP3/Sourcebook/issues/293)) | #298, #303 |
| What People Ask for managers | A fourth password, `MANAGER_PASSWORD_HASH`, opens What People Ask and nothing else HR-only. A manager's report lists only wordings asked in at least `MANAGER_MIN_CONVERSATIONS` separate conversations (3), filtered in the query before the candidate cap, so a question typed once can't point a manager at the person who typed it. On the pilot the reviewer password is the manager password | #302 |
| Conversations belong to the browser that started them | The token's `sub` is a per-browser owner id that the web app keeps in local storage and sends at login. Every conversation, project, chat, and escalation route filters on it; another browser's session id or project id answers 404. A link to a conversation from another browser opens a new chat with a notice. Tokens issued before this were rejected, so everyone signed in once more. Conversations from before it had no owner; `scripts/purge_ownerless_conversations.py` removed them from the pilot on 2026-09-27 (5 conversations and 1 project, exported first). Escalation records were kept ([#290](https://github.com/CMSC495-GROUP3/Sourcebook/issues/290) item 4) | #299, #301, #303 |
| Report and reindex limits | Each provider call on What People Ask has an 8 s timeout and no retry (`REPORT_PROVIDER_TIMEOUT_SECONDS`), so a stalled provider costs a page load about 16 s instead of about 60. `POST /api/documents/reindex` needs the HR password, since a rebuild empties the answer cache. The redundant `conversations.updated_at` index is dropped at startup ([#300](https://github.com/CMSC495-GROUP3/Sourcebook/issues/300)) | #301 |
| HR password | `HR_PASSWORD_HASH` is a third password. HR Requests and its routes return 403 to any other session, and the sidebar hides the link. Filing an escalation from the chat still needs only the shared password. On the pilot the HR password has been its own since 2026-09-27; before that it was the reviewer password ([#290](https://github.com/CMSC495-GROUP3/Sourcebook/issues/290)) | #295 |
| What People Ask at volume | The grouped report returns at most 1,000 session ids per wording with an exact count beside them, so one question asked in 400,000 conversations no longer exceeds MongoDB's 16 MB document limit. A window over Mongo's memory limit gets 503 and "Try a shorter window." instead of 500. Timings from a local `mongo:7`, not Atlas, are in [docs/load-testing.md](../../load-testing.md) ([#291](https://github.com/CMSC495-GROUP3/Sourcebook/issues/291)) | #296 |
| Sample policies | The injury policy's incident-reporting window now matches the Workplace Health and Safety Policy: report no later than 24 hours after the incident, instead of by the end of the shift. The pilot was re-ingested on 2026-09-26, so the corpus version differs from the beta's | #284 |
| Documentation | User guide ([#206](https://github.com/CMSC495-GROUP3/Sourcebook/issues/206)) and team page ([#209](https://github.com/CMSC495-GROUP3/Sourcebook/issues/209)) pending; [portfolio page](portfolio.md) in this folder; pilot load-run page; README and quality page corrected where the beta made their status claims stale | Pending: #259, #231; #274, #278, #285 |

## Verification status

| Check | Status | Evidence |
| --- | --- | --- |
| Python lint and tests on 3.11 to 3.14 with the 80% floor, web lint, types, tests, and build, both Docker images, Compose validation | Pending on the release merge commit | none yet |
| CodeQL, dependency audit, secret scan | Pending on the release merge commit | none yet |
| Coverage, Python and web, for the tagged commit ([#210](https://github.com/CMSC495-GROUP3/Sourcebook/issues/210)) | Done on `7d3c779`: Python 93% of 2,426 statements; web 92.28% statements, 87.29% branches, 94% functions, 93.93% lines on the files `web/vitest.config.ts` lists | [evidence/coverage.md](evidence/coverage.md), from CI run [36324854066](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36324854066) |
| Answer quality, smoke tier | Done on `7d3c779`: 100% on all five metrics, the same as the beta | [live-evaluation.md](live-evaluation.md), run [36325342934](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36325342934) |
| Answer quality, full tier, against the beta's run as the before ([#213](https://github.com/CMSC495-GROUP3/Sourcebook/issues/213)) | Done on `7d3c779`: 95.9% (47 of 49) on the three answer metrics and 100% on both refusal metrics, the same as the beta, with the same two cases citing a sibling policy | [live-evaluation.md](live-evaluation.md), run [36325113964](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/36325113964) |
| Real-service latency and error rate on the pilot | Done on `7d3c779`: all five targets pass, 0 errors in 7 requests | [live-benchmark.md](live-benchmark.md), run `e6615d05` |
| Load run against the deployed pilot ([#212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212)) | Pending | [docs/load-testing-pilot.md](../../load-testing-pilot.md), Pending |
| Lighthouse, both themes, phone and desktop ([#214](https://github.com/CMSC495-GROUP3/Sourcebook/issues/214)) | Pending: run `scripts/lighthouse` (#280) against the pilot on the candidate | [docs/quality.md](../../quality.md), Pending |
| End-to-end pass by hand | Done on `7d3c779`: 18 of 18 steps pass | [below](#end-to-end-pass-by-hand), screenshots in [evidence/](evidence/README.md) |
| What People Ask on the pilot's query log, 30-day window, signed in with the HR password and with the reviewer password | Done: 15 of 87 questions unanswered (17%), `grouping` `meaning`, nothing left unjudged; the reviewer sees the same headline with only rows from at least 3 conversations | [evidence/16](evidence/16-what-people-ask-hr.png) and [evidence/19](evidence/19-what-people-ask-reviewer.png), question text blurred |
| Screenshots of green CI, Security, and auto-deploy runs ([#207](https://github.com/CMSC495-GROUP3/Sourcebook/issues/207)) | Pending | [evidence/](evidence/README.md) |

### End-to-end pass by hand

Done on 2026-09-27 against the pilot running `7d3c779`. The beta's steps and
expected results, plus steps for the #271, #277, #295, #299, and #302 changes
and the What People Ask page. Signed in with the HR password, switching to the
reviewer password, the employee password, or a second browser only for the
steps that say so. Driven by a Playwright script from Taylor's session; every
result below was read from the page, and the screenshots are in
[evidence/](evidence/README.md). Save sanitized screenshots to [evidence/](evidence/README.md): no
password, token, or session id visible.

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-09-27, 14:22 to 14:40 |
| Tester | Claude, from Taylor's session, with Playwright |
| Browser and version | Google Chrome 153.0.8010.53 at 1440x1000; 390x844 for the phone step |
| Deployed commit | `7d3c779` |

| Step | Expected | Result |
| --- | --- | --- |
| Sign in with the HR password | lands on the chat page with HR Requests and What People Ask in the sidebar; a wrong password shows "Incorrect password." | Pass. HR Requests and What People Ask in the sidebar; a wrong password shows "Incorrect password." (`01`, `02`) |
| Ask a covered question | streamed answer with at least one cited source and a score | Pass. Two cited sources at "Strong match · 75%" (`03`) |
| Open a cited source | the source pane shows the whole document | Pass (`04`) |
| Ask a follow-up in the same conversation | the answer uses the history; no cache badge | Pass. Answered with sources, no cache badge (`05`) |
| Reload the page | the conversation and its sources are restored from history | Pass. Both answers and their sources restored (`06`) |
| Ask an uncovered question in a new conversation | refusal card with the Ask Human Resources button | Pass (`08`) |
| Ask an uncovered question as a follow-up (#189) | refusal card, not an answer with unrelated chips | Pass (`07`) |
| Ask `unanswerable_01`, "Does Meridian reimburse employee pet insurance?" (#192, #269) | refusal card that says the coverage check refused it, without "Strong match" under "No matching policy" | Pass. "Not answered by any policy" with the related-policies line from #281; no "Strong match" and no "Nothing indexed came close" (`09`) |
| Escalate the refusal with a note | confirmation in the UI; the record appears on the HR Requests page | Pass. "Sent to Human Resources · ref 48d08505"; the request heads the HR Requests open list (`10`, `11`, `13`) |
| Escalate the same message again | the first record comes back, not a second one | Pass. After a reload the message still shows "Sent · ref 48d08505" and offers no second button (`12`). Filing one message twice through the API returned the same `escalation_id` both times, and that test record was resolved |
| Resolve the request on the HR Requests page, then reopen it | the request moves between the open and resolved lists | Pass. Moved to Resolved with its note, then back to Open; left resolved afterwards (`13`, `14`, `15`) |
| Open What People Ask and switch between 7, 30, and 90 days (#286, #288, #298) | the headline counts questions and the share no policy answered; both lists load; the URL carries `?days=` except for the 30-day default; the captions say wordings of one question share a row | Pass. 15 of 87 questions in the last 30 days had no policy (17%); both lists load; `?days=7` and `?days=90` in the URL, and no parameter for the 30-day default; the captions say wordings of one question share a row. Question text blurred (`16`) |
| Sign out, then sign in again with the HR password (#299) | the conversations from this browser are still in the sidebar | Pass (`17`) |
| In a private window, sign in with the HR password, then open a `/chat?session_id=` link copied from the first window (#299) | an empty sidebar; the link opens a new chat with "That conversation isn't available in this browser" | Pass. Empty sidebar; the link became `/chat` with the notice (`18`) |
| Sign out, sign in with the reviewer password, and open What People Ask (#302) | only What People Ask in the sidebar, not HR Requests; the page says it shows only questions asked in at least 3 separate conversations | Pass. No HR Requests link; the page says "you see only questions asked in at least 3 separate conversations". Question text blurred (`19`) |
| Open `/escalations` with the reviewer password (#290, #299) | the page says it is for Human Resources, with no list and no retry | Pass (`20`) |
| Sign out, sign in with the shared employee password, then open `/gaps` (#290, #302) | no HR Requests or What People Ask links in the sidebar; the page says it is for managers and Human Resources instead of loading the report | Pass. Neither link in the sidebar; "This page is for managers and Human Resources." (`21`) |
| At 390px wide, keyboard only: open a request on the HR Requests page, choose "All requests", then press Back (#266) | focus lands on the request's heading, then on its row; Back leaves the page instead of reopening the request | Pass. Focus on the request's heading (H2), then on its row; Back left the page for `/chat` (`22`) |

## Known defects and limitations

Carried from the beta unless fixed before the freeze. Update at the freeze.

| Issue | What a pilot user would see | Mitigation |
| --- | --- | --- |
| Vague questions on covered topics | "Can I expense this trip?" is refused where the alpha answered in general terms ([beta evaluation](../v0.2.0/live-evaluation.md#manual-review)) | the refusal card now says to ask the full question again with the details it depends on (#281); or use Ask Human Resources |
| Conversations belong to a browser, not a person | there is no per-user sign-in, so clearing site data or switching browsers or devices starts an empty history, and anyone who copies the browser's owner id and knows a password can read that browser's conversations (README [Known limitations](../../../README.md#known-limitations)) | a pilot with a few reviewers; the owner id sits in local storage next to the token it would take to use it |
| What People Ask still misses paraphrases | with the question judge, 16 to 18 of 60 labelled paraphrases merged and 0 or 1 of 60 different questions; #293's target of half with none was not met. When the judge call fails, only case and punctuation changes merge (3 of 60) ([measurement](../../evaluation.md#the-model-check-below-the-threshold)) | the captions say a question asked in other words can still appear twice, and a failed check says so on the page |
| README known limitations | shared passwords, a threshold set by judgement, non-atomic re-ingestion, one instance, a fictional corpus | documented in the README |

## What this release does not establish

Pending: rewrite at the freeze from what was measured. Start from the beta's
list: load (#212), full-tier quality (#213), accessibility and web performance
(#214), `CustomerDataProvider` not written, a fictional corpus, one instance
with no failover. Add the question judge: its numbers come from 120 pairs
written by the team on the sample policies, not from real employees'
questions, and `gpt-4o-mini`'s verdicts varied between runs. Add the What
People Ask report at volume: #296 timed it on
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
| Code frozen on `main`; the candidate commit named in the table at the top of this page | Done: `7d3c779`, named 27 September |
| Smoke and full tier on the candidate, recorded in [live-evaluation.md](live-evaluation.md) | Done |
| Bounded benchmark against the pilot, recorded in [live-benchmark.md](live-benchmark.md) | Done |
| End-to-end pass by hand, recorded above with screenshots | Done |
| Coverage for the candidate in [evidence/coverage.md](evidence/coverage.md) | Done |
| Load run and Lighthouse, or recorded as not measured | Pending |
| `docs/user-guide.md` and `docs/team.md` on `main` | Pending: #259, #231 |
| Release pull request merged, with its CI and Security runs green and linked in the table at the top of this page | Pending |
