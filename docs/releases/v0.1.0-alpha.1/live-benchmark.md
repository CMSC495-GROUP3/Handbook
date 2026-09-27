# Alpha performance benchmark against the real services

Unit 5 asks whether the demo site meets minimum acceptable performance. The
existing [load-test results](../../load-testing.md) answer a
different question. They ran on a laptop with a fake model, an in-memory
database, canned retrieval, and the chat limiter switched off, and they measure
what the thread pool can sustain. This page covers the deployed demo site with
OpenAI, Atlas, Caddy, Nginx, rate limits, and provider bounds all on, on a
sample small enough to stay within a few cents. Tracking issue:
[#183](https://github.com/CMSC495-GROUP3/Sourcebook/issues/183).

Status on 2026-09-10: **run performed, every target met.** The operator
agreed the targets, then ran the workload against the deployed demo site. The
numbers, the settings in force, and the limitations are in
[Results](#results) below, and the sanitized JSON sits beside this page in
`live-benchmark-results.json`.

## What the run does

`scripts/loadtest/live_benchmark.py` logs in once, then sends a scripted
workload over the public address, through Caddy and Nginx to the API, the
same path a user's browser takes. Each request records the path the server
reports in its `done` event next to the path the step expected, so the
results say which code path ran rather than assuming it.

| Step | Question | Expected path | What it checks |
| --- | --- | --- | --- |
| cache probe | a pool question that turns out to be warm | cached | recorded as a probe, not a failure; the run moves to the next pool question |
| uncached answer | the first pool question the cache does not hold | generated | retrieval, grounding gate, model streaming, follow-up call |
| cached repeat | the identical text in a new session | cached | the answer cache serves a first-turn repeat without a model call |
| follow-up | "Does that change after five years of service?" in the first session | generated | the history path, which pays an extra condense call and skips the cache |
| refusal | a question no policy covers | refused | the grounding gate declines before any model call |
| burst 1..N | N distinct pool questions at once | generated | a small concurrent load with the limiter on; 429s are counted on their own |

The question pool is eight answerable cases from `evaluation/questions.json`,
sent exactly as written. Nothing is appended to the text, because the server
embeds the question as sent and a tag would move the grounding score. Instead
the uncached step walks the pool until the server reports a generation; a
question asked in the last `ANSWER_CACHE_TTL_SECONDS` (24 hours by default)
comes back cached, which costs no model call and is recorded as a probe. If
every pool question is warm, the run records that, skips the repeat and
follow-up steps, and still runs the refusal and the burst; wait for the TTL
or extend the pool. The burst draws from the questions the probe did not
touch.

The client holds every stream open through the follow-up event. Hanging up at
`done` is a legitimate client behaviour, but it exercises the
generator-close path that load-testing.md finding 4 describes rather than the
ordinary one, and this run is about the ordinary one.

## Caps and stop conditions

These are the defaults in the script. The operator can lower them; raising
them needs a reason recorded here.

| Control | Default | Why |
| --- | --- | --- |
| `--max-requests` | 8 | hard cap on chat requests, probes included; later steps are dropped to fit |
| `--burst` | 3 | concurrent questions after the sequential steps, from the unused pool |
| `--max-errors` | 2 | stop the sequential steps and skip the burst once this many errors occur |
| `--pause` | 2.0s | gap between sequential requests, so one client stays under `CHAT_RATE_LIMIT` (30/minute) |
| `--cost-per-generation` | $0.01 | the README's estimate; used only for the cost line |

A default run with a cold cache is seven chat requests, up to the cap of
eight when a probe hits a warm question. Five of them generate, at roughly a
cent each, so a full run is under ten cents. The login route's limit is
10/minute and the script logs in once. Production settings are not changed
for the run; if the burst trips the limiter, the 429s are the result.

## Targets

The deployment operator agreed these before the run, unchanged from the set
PR #186 proposed. They describe what a demo-site user should find acceptable, not
the 10,000-user requirement, which a run this size cannot address.

| Target | Limit | Reasoning |
| --- | --- | --- |
| `generated_ttft_p50_s` | 4.0s | median time to first token on the generated path; retrieval plus the provider's first token |
| `generated_total_max_s` | 30.0s | slowest completed generation; the provider timeout is 30s and the stream deadline 90s |
| `cached_ttft_max_s` | 1.5s | a cache hit makes no model call |
| `refused_total_max_s` | 3.0s | a refusal is an embedding call and a vector search, nothing else |
| `error_rate_max` | 0.0 | no failed answers in a run this small; rate limiting is excluded from this rate |

Agreed on: 2026-09-10, before the run. Agreed by: Taylor Shahan, deployment
operator. Amendments: _none_; the table above is the agreed set.

A sample of eight cannot support a p95, so the script reports p50 and max
only, with the sample size beside each. Treat a single slow request as a
finding to investigate, not as a percentile.

## Running it

From any machine with the repository's virtualenv. The client's network adds
to every number, so record where it ran.

```bash
BENCH_PASSWORD='the demo password' ./.venv/bin/python scripts/loadtest/live_benchmark.py \
  --url https://sourcebook.duckdns.org \
  --deployed-sha "$(ssh ubuntu@sourcebook.duckdns.org git -C CMSC495-CAP rev-parse refs/deployed/main)" \
  --client-location 'home, Maryland' \
  --out docs/releases/v0.1.0-alpha.1/live-benchmark-results.json
```

Without `--yes` the script says how many chat requests it may send and asks
before the first one, and before it logs in. Without `BENCH_PASSWORD` it prompts, so the password
never lands in shell history. Answer text is not written to the JSON unless
`--keep-answers` is given; the committed results must be the sanitized form.

The script prints two markdown tables at the end. Paste them into the
results section below, together with the fields listed there.

To read the requests from the server side afterwards, the query log has one
row per request, keyed by session ids that all start with `bench-<run id>`.
`docs/releases/v0.1.0-alpha.1/handoff.md` links the query-log report work in #160 / PR #171.
Container logs are thinner than this page first claimed: `docker logs
cmsc495-cap-api-1` prints Uvicorn access lines only, so it confirms the
request count, the status codes, and the client address, and it does not name
the session or the path taken. Take the path from the `done` event the script
records, and from the query log once #160 lands.

## Results

Run on 2026-09-10 at 22:20 UTC, run id `e8aa8cde`, by Taylor Shahan as
deployment operator. The client was a macOS 26.6.2 arm64 laptop on a home
network in Maryland, Python 3.13.2, reaching the public address over the
open internet. The sanitized report is
[live-benchmark-results.json](live-benchmark-results.json) beside this page;
it carries no answer text.

Deployed commit: `435296607ec1b95a4b989c3c421d0cb246c0ffaa`, the merge of
[#181](https://github.com/CMSC495-GROUP3/Sourcebook/pull/181), read from
`refs/deployed/main` on the host at run time. The API container had restarted
14 minutes earlier, so the first pool question generated instead of probing a
warm cache.

Settings in force. Confirmed on 2026-09-11 by listing the variable names set
in the host's `.env`: it sets twelve, all of them credentials, connection
strings, the provider choice, and the site address. None of the values below
appears there, so the `sourcebook/rag/config.py` defaults applied.

| Setting | Value |
| --- | --- |
| `THREADPOOL_TOKENS` | 100 |
| `CHAT_RATE_LIMIT` | 30/minute |
| `OPENAI_TIMEOUT_SECONDS` | 30 |
| `OPENAI_MAX_CONCURRENT_REQUESTS` | 20 |
| `OPENAI_STREAM_DEADLINE_SECONDS` | 90 |
| `SIMILARITY_THRESHOLD` | 0.62 |
| `ANSWER_CACHE_TTL_SECONDS` | 86400 |
| answer model | `gpt-4o` |
| utility model | `gpt-4o-mini` |
| embedding model | `text-embedding-3-small` |

### Per-step results

| Step | Expected | Observed | HTTP | TTFT | Complete | Follow-ups | Sources | Confidence | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uncached answer | generated | generated | 200 | 4.17s | 4.69s | 5.61s | 2 | 75 |  |
| cached repeat | cached | cached | 200 | 0.04s | 0.04s | 0.04s | 2 | 75 |  |
| follow-up | generated | generated | 200 | 2.06s | 2.72s | 3.79s | 2 | 77 |  |
| refusal | refused | refused | 200 | 0.31s | 0.31s | n/a | 0 | 59 |  |
| burst 1 | generated | generated | 200 | 1.21s | 1.62s | 2.92s | 3 | 75 |  |
| burst 2 | generated | generated | 200 | 1.07s | 1.55s | 2.35s | 2 | 74 |  |
| burst 3 | generated | generated | 200 | 1.16s | 1.55s | 3.55s | 3 | 78 |  |

Every request took the path its step expected, so there are no mismatches to
explain. No cache probe was needed. The refusal question, "What is the boiling
point of mercury at sea level?", was declined by the grounding gate at
confidence 59 with no sources, which is the behaviour the step was written to
check.

Uvicorn access logs on the host show one `POST /api/auth/login` and seven
`POST /api/chat/stream`, all 200, from a single client address, which matches
the client's own count.

### Against the agreed targets

| Target | Limit | Observed | Sample | Result |
| --- | --- | --- | --- | --- |
| `generated_ttft_p50_s` | 4.0s | 1.21s | n=5 | pass |
| `generated_total_max_s` | 30.0s | 4.69s | n=5 | pass |
| `cached_ttft_max_s` | 1.5s | 0.04s | n=1 | pass |
| `refused_total_max_s` | 3.0s | 0.31s | n=1 | pass |
| `error_rate_max` | 0.0 | 0.00 | n=7 | pass |

All five pass, so there is no failure to link and no new defect to open.
[#118](https://github.com/CMSC495-GROUP3/Sourcebook/issues/118) stays open on
its own merits; this run produced no provider-busy response, which is an
absence of evidence at this size rather than evidence the message never fires.

- Requests: 7 (5 generated, 1 cached, 1 refused).
- Rate limited (HTTP 429): 0.
- Errors, excluding rate limits: 0.

Estimated cost: $0.05, from five generations at the README's $0.01 estimate.
The measured cost from the provider's usage page is not recorded; the operator
did not read it for the run window, and at this size the estimate and the
measurement would differ by less than a cent.

### Limitations

- Seven requests. The p50 rests on five generations, and the cached and
  refused figures each rest on one. These are single observations with a
  label, not percentiles.
- One client, one network location, one operating system, one point in time
  on 2026-09-10.
- The burst was three concurrent requests. It shows the limiter did not fire
  at that level and says nothing about the level where it would.
- The first generation was the slowest at 4.17s to first token, against 1.07s
  to 1.21s for the burst that followed. A cold container, a cold embedding
  cache, or provider variance would each explain that, and one run cannot
  separate them.
- Costs, latencies, and provider behaviour all move with OpenAI's load. A
  rerun on another day will not reproduce these numbers exactly.

## What this does and does not establish

A passing run shows that the deployed path works end to end for a single
user and a burst of three, within the agreed limits, on that day. It says
nothing about 10,000 concurrent users. That claim rests on the synthetic
measurements in load-testing.md plus the caveats listed there, and a demo-site run of
this size does not change it either way. The handoff page records the
original requirement, the synthetic evidence, this run, and the gap between
them without redefining the requirement.
