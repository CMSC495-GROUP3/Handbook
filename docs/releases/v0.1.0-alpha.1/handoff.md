# Sourcebook alpha handoff

Sourcebook answers employee policy questions from a fixed corpus of company
documents and cites the document behind every answer. When the corpus does not
cover a question, it says so and offers to hand the question to Human
Resources rather than guessing.

This page is the entry point for reviewing the Unit 5 alpha. It names the
commit under review, maps the scope the team agreed in its project pitch and
its Unit 3 design specification onto what shipped, links the evidence behind
each claim, and states what the alpha does not establish. Nothing here is
called verified without a link that shows it.

## Where to start

- **See it running.** The demo site is at <https://sourcebook.duckdns.org>. It has
  a reviewer password separate from the team's; the team supplies it through
  the course channel, not through this repository. The README's Configure
  section explains how the second password works.
- **Run it yourself in about two minutes.** `git clone`, then `make setup && make
  stub`. That starts the whole app with a fake model and an in-memory database,
  so it needs no accounts, no API key, and no network.
- **Read the code.** The [README](../../../README.md) explains what the system
  does and walks one question through retrieval, the grounding gate, and
  streaming. [CONTRIBUTING.md](../../../CONTRIBUTING.md) covers the development
  setup.

Unit 5 roles are in the [README's Team section](../../../README.md#team): Taylor
as Lead Architect, Daniel as Interface Designer, Chris as Integration Lead,
with Gavin, Dominick, George, and Robert on the React app, administration, and
the corpus.

## The submitted version

| Field | Value |
| --- | --- |
| Commit | `d7199f57e3eb600e646d4202de43c97f2c5cc770`, the merge of PR #191 into `main` on 2026-09-11 |
| Tag and release | [`v0.1.0-alpha.1`](https://github.com/CMSC495-GROUP3/Sourcebook/releases/tag/v0.1.0-alpha.1), annotated, prerelease, on that commit |
| Running at | <https://sourcebook.duckdns.org> |
| Deployed commit | the same, per `refs/deployed/main` on the demo host, checked 2026-09-11 00:20 UTC. The demo site follows `main`, so it moves on from here; the evidence below records the commit each check ran against |
| CI | [run 34545903866](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/34545903866), success |
| Security | [run 34545903887](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/34545903887), success |
| Proposed tag | `v0.1.0-alpha.1`, annotated, marked prerelease |

The tag is not cut yet. The verification status section says what has been
checked on this commit and what has not. The tag goes on the commit that
clears the remaining items, and this table is updated to match it.

## What shipped, against the agreed scope

The table below reconciles the candidate against the two planning documents
from earlier units, neither of which lives in this repository. The project
pitch states the problem, the stack, and the risks the team promised to
mitigate. The Unit 3 design specification of 2026-08-30 fixes the interface
contracts and the architecture. Where the candidate departs from the
specification, the departure is in the next section rather than missing from
this one.

| Requirement | Implemented | Evidence | Limitation |
| --- | --- | --- | --- |
| Plain-language questions answered from the policy corpus with the source cited | Yes | README "How a question is answered"; `tests/test_chat.py`, `tests/test_rag_chain.py`; evaluation metric "citation correctness" | Measured on the 20-case smoke tier on 2026-09-11, see [live-evaluation.md](live-evaluation.md); never on a real corpus |
| Refuse when the corpus does not support an answer | Yes | grounding gate in `sourcebook/rag/rag_chain.py`; evaluation "unsupported refusal handling" | `SIMILARITY_THRESHOLD` is set at 0.62 by judgement, not tuned against a real corpus. [#192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192): uncovered questions near HR topics clear the gate, and the model's prose declines instead of the refusal card |
| Escalate a refusal or unhelpful answer to Human Resources | Employee side yes; handler side through the API | `sourcebook/api/routes/escalations.py`, `tests/test_escalations.py`; webhook delivery and retry from #99 / PR #113 | Until [PR #188](https://github.com/CMSC495-GROUP3/Sourcebook/pull/188) an escalation filed after a failed generation could name the wrong exchange (#84). The specification's Figure 3 has the Human Resources agent read the open queue through `GET /api/escalations?status=open` and `PATCH` it resolved, reached from a Slack or Teams webhook, so API-only handling is the designed path. #159 proposes an in-app queue beyond it |
| Learn from the query log (content gaps, FAQ ranking, threshold tuning) | Logging yes; reports not in this commit | `sourcebook/api/analytics.py`, `tests/test_analytics.py` | The specification asks for a weekly human-read knowledge-gap report over `query_logs`. That report is in draft as PR #171 and did not make this commit, so #160 stands as a gap against the specification |
| Policy Library renders whole documents | Yes | PR #167, `web/src/components/Documents` | none known |
| Conversation history, projects, reload | Yes | `tests/test_conversations.py`, PRs #126, #133 | #142: project assignment and deletion are not transactional |
| Shared-password sign-in with a second reviewer password | Yes | PRs #75 (for #74), #110, #154; `tests/test_auth.py`, `tests/test_tokens.py` | A shared credential by design for the demo site, with no per-user accounts |
| Rate limits and provider bounds so a stalled provider cannot take the site down | Yes | PRs #112, #144; `tests/test_provider_timeout.py`, `tests/test_proxy_headers.py` | #118: saturation reports as a generic error rather than a retryable one |
| Serve 10,000 concurrent users, which the design specification reads as about 100 requests per second | Synthetic evidence only | `docs/load-testing.md`: 98.7 requests per second on one worker at `THREADPOOL_TOKENS=320`, zero failures, 0.17s time to first byte, with the model faked | The measurement is 1.3% under the 100 figure, not over it. Four workers at the shipped default project to about 124 requests per second, and that is arithmetic rather than a measurement. The real-service run described in [live-benchmark.md](live-benchmark.md) is deliberately small and cannot settle any of this |
| Model call behind one interface, so a self-hosted model can replace the vendor (pitch risk: lock-in) | Yes | `LLMProvider` in `sourcebook/rag/llm.py`, with `OpenAIProvider` and `FakeProvider` registered in `_PROVIDERS` and chosen by `LLM_PROVIDER`; `tests/test_provider_timeout.py` | One real vendor is implemented. The fake exists for tests and refuses to start in production, so the swap is unproven against a second real provider |
| Customer record lookup behind one interface, shown to be workable rather than integrated | Not yet | `CustomerDataProvider` in section 2 of the design specification and grey in its Figure 1 | The requirement is a demonstration, so the alpha implements the contract with a simulated provider rather than reading a real customer system. Not written yet, and not tracked by an issue |
| Passages, metadata, and embeddings in one database rather than a vector store beside a document store (pitch) | Yes | `sourcebook/rag/mongo.py`, the index setup in `sourcebook/api/db.py`, `tests/test_indexes.py`; Atlas Vector Search index `vector_index` | The Atlas free tier caps the demo corpus at 512 MB, which the pitch names as a risk |
| Deployed demo with TLS and automatic deploys | Yes | README "Deployment" and "Checking a deploy"; `scripts/auto_deploy.sh`, `tests/test_auto_deploy.py` | One instance, no redundancy, a free DuckDNS name |
| Redesigned web app, responsive, keyboard-usable | Redesign shipped in PR #161 and its follow-ups | milestone "refactor: new UI/UX" | #51 responsive pass, #52 keyboard pass, #174 theme switch on a phone, #53 deployment verification, all open |

## Where the implementation differs from the Unit 3 design specification

The specification was written on 2026-08-30 and this commit is eleven days of
work past it. Nothing below breaks a contract the React app or the tests rely
on, but anyone reading the two side by side will find these, so the team names
them here.

| Item | Design specification | This commit | Why it changed |
| --- | --- | --- | --- |
| Edge | Figure 1 has one edge component: Nginx serves the app and proxies `/api` with buffering off | Caddy terminates TLS for `SITE_ADDRESS` and forwards to Nginx, which still serves the app and proxies `/api`. Only Caddy publishes ports | TLS with a Let's Encrypt certificate for the DuckDNS name arrived with the demo host, after the specification was written. No contract changed. Figure 1 is stale |
| Endpoint contract | Section 2.1 lists login, chat, chat/stream, conversations (list, create, get), documents, and escalations (create, list, patch) | Also `GET /api/health` and `/api/config`, `PATCH` and `DELETE /api/conversations/{id}`, `GET /api/documents/categories`, `/body`, and `/passages`, `POST /api/documents/reindex`, `GET /api/escalations/{id}`, `POST /api/escalations/{id}/retry-delivery`, and the whole `/api/projects` resource | Every addition is additive, and Figure 1 already names projects among the route files. Section 2.1 needs the extra rows |
| Rate limits | Login 10 a minute per IP, escalation 5 | The same two, plus `CHAT_RATE_LIMIT` at 30 a minute per address per worker and `REINDEX_RATE_LIMIT` at 2 a minute | The chat cap is the binding ceiling for interactive use and is missing from section 2 of the specification |
| Throughput target | "the 10,000-user target, which we read as about 100 requests per second" | README and `docs/load-testing.md` derive 83 requests per second from 10,000 employees each asking one question in a 120-second peak, and use that as their pass mark | Two readings of one requirement, from the same 10,000 employees. The team states the specification's figure of about 100 requests per second. `docs/load-testing.md` keeps 83 as its internal pass mark because that is what its own arithmetic gives, so the two documents differ on the target and agree on the measurement. Both rest on synthetic runs with the model faked |
| `CustomerDataProvider` | A planned interface, drawn grey in Figure 1, with `get_customer(id)` returning three fields and raising `PermissionError` for another owner's id | Not built. Nothing in `sourcebook/` reads a customer database | The specification draws it grey because the requirement is to show the interface is workable, not to integrate a real customer system. The alpha satisfies it with a simulated provider behind the contract, the way `FakeProvider` already stands behind `LLMProvider`. That code is not written yet |
| Module paths | `src/llm.py`, `src/rag_chain.py`, `src/mongo.py` | `sourcebook/rag/llm.py`, `sourcebook/rag/rag_chain.py`, `sourcebook/rag/mongo.py`, `sourcebook/api/db.py` | The package layout refactor landed after the specification. The modules and their jobs are unchanged and only the paths moved. Figure 1 needs relabelling |

Checked against the specification and unchanged: the grounding threshold at
0.62, retrieval at k=5, the 20-turn history cap, the streaming event names and
payloads, the escalation record shape with its unique `(session_id,
message_index)` index, and the error and validation table in section 2.5.

## Verification status

| Check | Status on this commit | Evidence |
| --- | --- | --- |
| Python lint, tests on 3.11 to 3.14 with an 80% coverage floor, web lint and types and build, both Docker images, Compose validation, the proxy-chain acceptance script | Passed | [CI run 34534962223](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/34534962223) |
| CodeQL, dependency audit, secret scan | Passed | [Security run 34534962098](https://github.com/CMSC495-GROUP3/Sourcebook/actions/runs/34534962098) |
| Answer quality against the live system | Measured on the smoke tier, on `4e90382` and on the pre-#138 baseline; one defect found | [live-evaluation.md](live-evaluation.md): retrieval, citation, and grounded answers 100% of 12 on both commits; the grounding gate stopped none of the five refusal cases, now [#192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192) |
| Real-service latency and error rate on the demo site | Passed, on a sample of seven | [live-benchmark.md](live-benchmark.md): all five agreed targets met on `4352966`, 1.21s median time to first token, no errors, no rate limiting |
| End-to-end pass through the deployed app by hand | Passed, with one defect found | [below](#end-to-end-pass-by-hand): all eight steps pass on `4e90382`; the uncovered-question step surfaced [#189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189) |
| Escalation after a failed generation | Fixed in [PR #188](https://github.com/CMSC495-GROUP3/Sourcebook/pull/188) | `tests/test_escalations.py` covers the id path and the legacy index path. The browser pass ran before that merge, so its two escalation steps exercised the old path |

The dependency review job runs only on pull requests, so a push to `main`
skips it. It last ran on the pull request that produced this commit.

### Answer quality

The measurement was taken on 2026-09-11 and is written up in
[live-evaluation.md](live-evaluation.md), with every answer and score in
`live-evaluation-results.json` beside it. The gate on #137 asked for three
things, and each was done with the real provider and the demo site's Atlas index,
exit-code verified, on both `4e90382` (tip `main`, prompt `v2`) and the
pre-#138 baseline `9871e3ed2faa798cc21d237b421c7ac68963a9a2` (prompt `v1`):

- The 20-case smoke tier on both commits. Recall@5, citation correctness, and
  grounded answer rate are 100% of 12 answerable cases on both. Unsupported
  refusal handling and the prompt-injection gate refusal rate are 0% on both:
  the five cases the grounding gate was expected to stop all scored between
  62 and 79 against a threshold of 62 and were sent to the model, which then
  declined in prose every time. The answers are safe; the refusal card and its
  escalation button are missing. That is [#192](https://github.com/CMSC495-GROUP3/Sourcebook/issues/192), and it is the same mechanism
  as #189.
- The three ambiguous cases in the set and three questions asked by hand, on
  the PTO amount, parental-leave eligibility, and working from home, on both
  commits, with a disposition for each. The `v2` prompt is judged equal or
  better on all six and asks for the missing employee fact in three of them
  where `v1` pointed to Human Resources in general. No regression was found.
  Neither prompt asks the one missing fact for "Can I expense this trip?".

Two earlier workflow runs, from 2026-09-06 and 2026-09-07, predate the
fail-closed repair in PR #181 and produced no results file; they are not
evidence of anything. The repaired workflow was not used for this measurement
either, because its `evaluation` environment holds `MONGODB_URI` but not
`MONGODB_DB`, so its secrets gate refuses to start. Setting that one secret is
what it takes for the workflow to replace the by-hand procedure the page
describes.

A green workflow badge is not evidence of answer quality and the team does not
present it as such. Twenty cases on a fictional corpus, run once, are evidence
that retrieval and citation work on that corpus and that the gate does not
separate covered from uncovered questions near HR topics; they are not a
quality guarantee.

### Real-service performance

PR #186 merged the benchmark protocol and its harness on 2026-09-10. The
protocol is in [live-benchmark.md](live-benchmark.md) and the script is
`scripts/loadtest/live_benchmark.py`. It logs in once and sends a scripted
workload over the public address, through Caddy and Nginx to the API, with
real OpenAI and Atlas and the rate limits left on. It is capped at eight chat
requests and stops after two errors, so a full run costs under ten cents.

The operator agreed the targets unchanged and ran the workload on 2026-09-10
against deployed commit `4352966`. Seven chat requests, five generated, one
served from the cache, one refused. Every request took the path its step
expected. Median time to first token on the generated path was 1.21s against a
4.0s target, the slowest generation completed in 4.69s against 30.0s, the
cache hit answered in 0.04s, the refusal in 0.31s, and there were no errors
and no rate limiting. All five targets pass. Results, the settings in force,
and the limitations are in [live-benchmark.md](live-benchmark.md), with the
sanitized JSON in `live-benchmark-results.json`. This closes #183.

This is a bounded check that the deployed path works for one user and a burst
of three on a given day. It says nothing about 10,000 concurrent users, and a
passing run does not narrow the gap in the table above.

### End-to-end pass by hand

One pass through the deployed app gets recorded here. It reuses the
deployment verification from #53 and the responsive and keyboard work from #51
and #52 rather than repeating them. Before the escalation step,
`ESCALATION_WEBHOOK_URL` points at a controlled test destination or is left
unset.

`ESCALATION_WEBHOOK_URL` is not set in the host's `.env`, so the escalation
step stored its record and attempted no delivery. Both escalation records
below read `delivery_status: pending` with zero attempts, which corroborates
that from the API side.

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-09-11, 00:10 to 00:40 |
| Tester | Taylor Shahan, driving Chromium with Playwright |
| Browser and version | Chromium 153.0.8010.12 (Playwright headless), 1440x1000 |
| Deployed commit | `4e903828621d30deec838302b005b037e623a9e0` |
| Screenshots or logs | `docs/releases/v0.1.0-alpha.1/evidence/`, sanitized: no password, no token, no real policy |

| Step | Expected | Result |
| --- | --- | --- |
| Sign in with the reviewer password | lands on the chat page; a wrong password shows "Incorrect password." | Pass. The wrong password showed "Incorrect password." and stayed on the form; the correct one landed on the chat page. `01`, `02` |
| Ask a covered question | streamed answer with at least one cited source and a score | Pass. "How many PTO days do full time employees with two years of service receive each year?" answered "15 PTO days each year" and named the Accrual section, with "Strong match · 75%" and two chips, Paid Time Off (PTO) Policy and Sick and Safe Leave Policy. `03` |
| Open a cited source | Policy Library shows the whole document | Pass. The Paid Time Off (PTO) Policy chip opened the document body including the Accrual section, and the chat input stayed available. `04` |
| Ask a follow-up in the same conversation | the answer uses the history; no cache badge | Pass. "Does that change after five years of service?" was answered against the history, and no cache badge appeared. `05` |
| Reload the page | the conversation and its sources are restored from history | Pass. Both questions and the source chips came back after a reload. `06` |
| Ask an uncovered question | refusal card with the Ask Human Resources button | Pass in a new conversation: "What is the boiling point of mercury at sea level?" gave the refusal card at "Partial match · 59%" with the Ask Human Resources button. `07`. Asked instead as a follow-up inside the PTO conversation it scored 69%, cleared the gate, and was answered rather than refused. That is [#189](https://github.com/CMSC495-GROUP3/Sourcebook/issues/189), opened from this pass. `10` |
| Escalate the refusal with a note | confirmation in the UI; the record appears at `GET /api/escalations?status=open`; the webhook arrives at the test destination if one is configured | Pass. The form took the note, the UI showed "Sent to Human Resources · ref 9e19a751", and `GET /api/escalations?status=open&session_id=...` returned one record with `reason: refused`, `refused: true`, and the note stored. No webhook is configured, so delivery stayed `pending` with zero attempts. `08`, `09` |
| Escalate the same message again | the first record comes back, not a second one | Pass. A second create on the same message returned HTTP 200 with the same `escalation_id` and the original note, not the new one, and the session still had exactly one record |

### The passage index migration

PR #176 adds a unique index on `(source, chunk_index)` for passages and a
one-time migration to reconcile duplicates. It is not in this commit. The
passages collection keeps its non-unique index, so nothing at the database
level stops a duplicate passage identity from being written, and re-ingestion
relies on upserting by `(source, chunk_index)` to avoid it.

That pull request needs a database snapshot and a maintenance window, because
the migration deletes duplicate records and the application refuses to start
against a database still carrying the old index. The steps ship with it in
CONTRIBUTING.md. Tracked as #158.

## Known defects and limitations

| Issue | What a demo-site user would see | Mitigation in the alpha |
| --- | --- | --- |
| #189 | an uncovered question asked as a follow-up can clear the grounding gate, so it is answered with a decline that cites unrelated policies instead of the refusal card | ask an uncovered question in a new conversation, where the gate scores it correctly |
| #192 | an uncovered question on an HR-adjacent topic, or a prompt injection, clears the grounding gate even as a first question; the model declines in prose, but the refusal card and its button do not appear | the answer text says the policies do not cover it; "Not what you needed?" under the answer still files the escalation |
| #118 | provider saturation reads as a generic error, so the user does not know it is worth retrying | `OPENAI_MAX_CONCURRENT_REQUESTS` bounds the damage; retry by hand |
| #142 | concurrent project assignment and deletion can race | a single-operator demo makes this unlikely at this volume |
| #158 | nothing at the database level prevents duplicate passage identities | ingestion upserts by `(source, chunk_index)`; PR #176 adds the constraint |
| #159 | Human Resources has no in-app queue | the handler works the queue through the API or a webhook-fed channel |
| #160 | no report over the query log yet | query the collection directly, or run the draft report from PR #171 by hand |
| #174, #51, #52 | phone and keyboard usability gaps | review the demo site in a desktop browser |
| README known limitations | a shared password, an untuned threshold, non-atomic re-ingestion, one instance, regex document search, a fictional corpus | documented in the README; none of them blocks a class demo |

## What this alpha does not establish

The 10,000-user requirement rests on synthetic measurements taken on a
development laptop with the model faked, the database in memory, and the chat
limiter off. Reading that requirement as about 100 requests per second, the
best measured figure is 98.7 on a single worker, which is just under the
target rather than over it. Four workers at the shipped `THREADPOOL_TOKENS`
default project to about 124 requests per second, but that number is
multiplication, not a run. `docs/load-testing.md` gives the method and
the raw tables, and lists what its own harness cannot capture: real model
latency is slower and more variable, real Atlas is slower than a 15 ms
dictionary, and a development laptop is not the t3.micro the demo site runs on.
None of this measures the deployed system under load, and the bounded run in
[live-benchmark.md](live-benchmark.md) is too small to become one.

Answer quality is measured on a 20-case smoke tier and three questions asked
by hand, on one day, with the clarification judgements made by one reader.
That is evidence for the sample corpus, not a guarantee. The full tier has not
been run, and the smoke tier's refusal cases show the gate does not separate
covered from uncovered questions near HR topics (#192).

`CustomerDataProvider` is designed and not written. When the simulated
provider lands it will show that the contract holds, not that Sourcebook can
read a real customer system.

The corpus is fictional. Sourcebook has never been run against a real company's
policies, so the retrieval threshold, the refusal rate, and the citation
accuracy would all have to be revisited before anyone used it for real.

## Release notes for the prerelease

Sourcebook v0.1.0-alpha.1 is the first tagged version of the policy assistant.
It answers employee questions from a policy corpus and cites the document each
answer came from. When the corpus does not cover a question it says so and
lets the employee hand the question to Human Resources.

In this release: streaming answers with citations and a retrieval score; a
grounding gate that refuses rather than guesses; escalation with webhook
delivery and retry; conversation history with projects; a Policy Library that
renders whole documents; shared-password sign-in with a second password for
reviewers; rate limits and provider timeouts; a query log for later analysis;
and a Docker Compose deployment behind Caddy that redeploys itself when `main`
moves.

The demo site runs at <https://sourcebook.duckdns.org> on a single instance and
stays up while the course runs. The reviewer password comes from the team
through the course channel.

Known defects, limitations, and the checks the team has not run carry over
from the tables above.

The release body itself is [release-notes.md](release-notes.md), which repeats
the defects with their impact and mitigation inline rather than pointing back
here, because a release page is read on its own.

## The tag, and reproducing this version later

The demo host follows `main`, so it moves past the tag. The tag does not. To
see the submitted version:

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
git checkout v0.1.0-alpha.1
make setup && make stub        # fake model, in-memory database, no accounts
```

With a `.env` holding real credentials, `docker compose up --build` at that
checkout runs the full stack instead. The commit deployed on the demo site at any
moment is `refs/deployed/main` on the host, which the README's "Automatic
deploys" section explains. The demo site is expected to move past the tag; the
tag, not the demo site, is the submitted version. If the demo site ever has to be
shown at the tagged version, the operator stops the auto-deploy timer,
because it refuses a checkout that is not on `main` and would otherwise
fast-forward it back, checks out the tag in the host checkout, runs
`docker compose build api web && docker compose up -d`, records the date
here, and re-enables the timer afterwards. `scripts/deploy.sh` cannot do
this: it only triggers the auto-deploy, which deploys `origin/main`.

The tag itself is annotated, so it carries its date and tagger, and the
release is marked prerelease so nobody mistakes it for production:

```bash
git fetch upstream
git checkout <the verified commit>
git tag -a v0.1.0-alpha.1 -m "Unit 5 alpha: verified per docs/releases/v0.1.0-alpha.1/handoff.md"
git push upstream v0.1.0-alpha.1
gh release create v0.1.0-alpha.1 --repo CMSC495-GROUP3/Sourcebook --prerelease \
  --title "v0.1.0-alpha.1" --notes-file docs/releases/v0.1.0-alpha.1/release-notes.md
```

`docs/releases/v0.1.0-alpha.1/release-notes.md` is written and is the release body, so the
release page and the repository say the same thing. Two things are filled in
at tag time and are deliberately not guessed now: the commit, and the
`Tagged commit:` line at the top of that file.

Before running the commands above, all of these must be true. The tag is the
claim that the alpha was verified, so cutting it early is the one mistake this
page exists to prevent.

| Blocker | State |
| --- | --- |
| Answer quality measured against the live system, per the gate on [#137](https://github.com/CMSC495-GROUP3/Sourcebook/issues/137) | Done on 2026-09-11, see [live-evaluation.md](live-evaluation.md). The dispositions in it are one reader's and the issue closes when the owners accept them |
| [PR #188](https://github.com/CMSC495-GROUP3/Sourcebook/pull/188) merged, or #84 accepted as a shipped defect | Merged before this page, which describes #84 as fixed |
| [PR #190](https://github.com/CMSC495-GROUP3/Sourcebook/pull/190) merged, so the browser pass is on `main` | Merged; the pass is recorded above |
| A commit chosen on `main` after those merges, with its CI and Security runs green and linked in the table at the top of this page | `d7199f5`, linked at the top |

The tag was cut on 2026-09-11 and is linked in the table at the top of this
page and in the README's Documentation table.
