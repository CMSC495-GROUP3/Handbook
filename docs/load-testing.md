# Load test results — chat streaming throughput

Measured against the requirement *"the system must serve 10,000 concurrent
users."* All numbers reproducible with the harness in `scripts/loadtest/`.

These are synthetic. The model, MongoDB, and vector search are stubbed and the
chat limiter is off, so they measure what the thread pool can sustain, not what
a user of the deployed pilot waits. For that, see
[live-benchmark.md](releases/v0.1.0-alpha.1/live-benchmark.md), which runs
against the deployed stack with real OpenAI and Atlas on a sample far too small
for throughput, and [load-testing-pilot.md](load-testing-pilot.md), which loads
the deployed pilot at a few concurrency levels with the real model. They answer
different questions and none substitutes for the others.

## Defining the target

"10,000 concurrent users" is ambiguous. Taking it as 10,000 employees with the
app open, each asking a question every ~2 minutes:

    10,000 / 120s = 83 queries/sec

At ~2.5s per generation that is roughly 210 generations in flight at any moment.
**83 req/s is the pass mark used below.**

## Method

`scripts/loadtest/server.py` runs the real application with three things
stubbed: the model (`LLM_PROVIDER=fake`, canned answer at a configurable
per-token delay), MongoDB (in-memory dict, 15 ms simulated latency), and Atlas
Vector Search (canned passages). The stub also disables the SlowAPI limiter so
every virtual user sharing `127.0.0.1` is not capped by `CHAT_RATE_LIMIT`;
production keeps that limit. `scripts/loadtest/run.py` opens N concurrent
SSE streams and records time-to-first-token and total duration.

The grounding gate is **not** stubbed. Fake embeddings produce meaningless
similarity scores, so instead of faking the gate the test brackets it: one run
where everything generates, one where everything refuses.

Hardware: development laptop (macOS), single uvicorn worker unless stated.
Generation is ~104 tokens at 20 ms = ~2.5 s.

## Finding 1 — the ceiling is the thread pool, and it is not what it looked like

Starlette wraps a sync generator with `iterate_in_threadpool`, which calls
`next()` on it through `anyio.to_thread.run_sync`. A thread is therefore
acquired and released **per yield**, not held for the whole stream. The
constraint is aggregate thread-time: each stream needs ~2.5 s of it, so 40
threads support 40 / 2.5 ≈ 16 streams/sec.

Baseline, anyio default of 40 tokens, everything generates:

| concurrency | ok | fail | TTFB p50 | generation p50 | req/s |
|---|---|---|---|---|---|
| 10 | 10 | 0 | 0.07s | 2.55s | 3.8 |
| 20 | 20 | 0 | 0.07s | 2.58s | 7.5 |
| 40 | 40 | 0 | 0.08s | 2.59s | **14.9** |
| 80 | 80 | 0 | 0.15s | 5.23s | 14.9 |
| 160 | 160 | 0 | 0.23s | 10.46s | 14.9 |

Throughput saturates at **14.9 req/s** — within 7% of the predicted 16 — and
past that point generation time stretches linearly (2.6s → 5.2s → 10.5s as
concurrency doubles). Nothing fails; it queues. That is 18% of the 83 req/s
target.

## Finding 2 — the refusal path is 47x cheaper

Same test with `SIMILARITY_THRESHOLD=1.0`, so the grounding gate declines every
request and no generation happens:

| concurrency | ok | TTFB p50 | req/s |
|---|---|---|---|
| 10 | 10 | 0.04s | 212 |
| 40 | 40 | 0.06s | 630 |
| 160 | 160 | 0.15s | 700 |

**~700 req/s.** Refusals are nearly free because the gate runs before
generation. Real traffic sits between 15 and 700 req/s weighted by the refusal
rate, which is a strong argument for measuring that rate in production — it is
the single biggest factor in both capacity and cost.

## Finding 3 — raising the pool size moves the ceiling almost linearly

Same generation-path test, varying only the thread limiter:

| thread tokens | concurrency | generation p50 | req/s | vs. default |
|---|---|---|---|---|
| 40 (default) | 160 | 10.48s | 14.9 | 1.0x |
| 160 | 160 | 2.85s | 53.7 | 3.6x |
| 320 | 320 | 2.98s | **98.7** | 6.6x |
| 640 | 320 | 3.05s | 96.1 | 6.4x |

About **0.31 req/s per thread**. The 640-token run matches the 320-token run
because concurrency was the limit there, not threads.

Memory cost, measured at 320 concurrent streams:

| | RSS | OS threads |
|---|---|---|
| idle | 70 MB | 7 |
| under load | 103 MB | 327 |

**~105 KB of RSS per thread** — far below the 8 MB virtual stack size, because
Python threads only commit the pages they touch.

## Finding 4 — a client that hangs up on `done` lost its exchange entirely

The load harness returns as soon as it sees the `done` event, which closes the
connection. That is reasonable client behaviour: the answer is complete, so
there is nothing left to read except the follow-up suggestions.

Doing so raised `GeneratorExit` at the suspended `yield` inside `_stream`, and
every statement after that yield was skipped — `_persist`, `put_cached_answer`,
and `log_query` all lived there. The user saw a complete, correct answer that
the server had no record of: not saved to the conversation, not cached, and
absent from the analytics this system is supposed to learn from.

It surfaced as "the cache never hits under load" and was initially mistaken for
a cache bug. The bookkeeping now runs from a `finally` block, which executes
during generator close, so an abandoned stream is still recorded.

This is the same hazard that would have appeared — harder to diagnose — after an
async conversion, where a disconnect becomes task cancellation at an `await`.

## Finding 5 — cached answers are roughly an order of magnitude cheaper

Same concurrency, same questions, differing only in whether the answer cache
was warm:

| path | 80 concurrent | 160 concurrent |
|---|---|---|
| first turn, cache miss (generates) | ~15 req/s | ~36 req/s |
| first turn, cache hit | 210 req/s | 343-522 req/s |
| follow-up turn (has history, never cached) | — | ~20 req/s |

Cached responses run **6-14x** the generated path. Measured hit latency was
0.11s against 3.03s for a generation — a 29x improvement for the user.

Follow-up turns are slower than first turns even on a miss, because a turn with
history pays an extra utility model call to rewrite the question into a
standalone retrieval query. That call is skipped on first turns.

Two caveats. The spread in the cached numbers (210-522 req/s) is wide because at
these levels the harness itself becomes a factor — opening 320 sockets at once
from one Python process produced a TTFB spike that the server did not cause.
And the fake model makes a miss cheaper than reality, so the real-world ratio
between hit and miss is larger, not smaller.

The practical consequence is that **cache hit rate is the main lever on cost**.
At 83 req/s and ~$0.01 per generated query, every 10 points of hit rate is
roughly $300/hour. `query_logs.cache_hit` records the achieved rate so this can
be measured rather than assumed.

## Conclusion

**A single worker with a larger thread pool clears the 83 req/s target.** At 320
tokens it sustains 98.7 req/s with zero failures, 0.17s TTFB, and 103 MB
resident. That is a one-line configuration change, not an architecture change.

`THREADPOOL_TOKENS` now defaults to 100 (~31 req/s/worker), which with 4 workers
projects to ~124 req/s — comfortably over target with headroom for the real-world
factors below. Raise it if measurement says to.

### What this does not prove

- **Real model latency is slower and far more variable.** A p99 generation of
  20s holds thread-time for 8x as long as this test assumes, cutting throughput
  proportionally. This is the largest source of error here.
- **Real Atlas is slower than a 15 ms dict.** Every real round-trip is more
  thread-time on the same budget.
- **A dev laptop is not a t3.micro.** CPU is a real factor: at 99 req/s the
  server encodes ~10,000 SSE JSON payloads per second, all of it contending for
  the GIL. Re-measure on the target instance before trusting these numbers.
- **Cost and provider rate limits bind before compute does.** At 83 req/s and
  ~$0.01/query that is ~$3,000/hour. The binding constraint on this system is
  the budget, not the server.

### Is the async conversion still worth doing?

On this evidence, it is no longer required to hit the target, which changes the
tradeoff. Threads cost ~105 KB each and scale linearly to at least 320; the
async rewrite would touch the streaming path, the provider interface, and the
retrieval helpers, and would introduce cancellation semantics — a client
disconnect becoming task cancellation at an `await` — that are easy to get
subtly wrong.

Given the "maintainable by a team of junior developers" requirement, the
recommendation is to take the configuration change now and treat async as a
later step, justified by measurement rather than by principle. Async remains the
better answer if per-request thread-time grows a lot (slower models, slower
database) or if memory becomes the constraint.

## Reproducing

```bash
# Worst case — every request generates
./.venv/bin/uvicorn scripts.loadtest.server:app --port 8001 --log-level warning &
./.venv/bin/python scripts/loadtest/run.py --concurrency 10 20 40 80 160

# Best case — every request refuses
SIMILARITY_THRESHOLD=1.0 ./.venv/bin/uvicorn scripts.loadtest.server:app --port 8001 &
./.venv/bin/python scripts/loadtest/run.py --concurrency 10 40 80 160

# Vary the thread pool
LOADTEST_THREAD_TOKENS=320 ./.venv/bin/uvicorn scripts.loadtest.server:app --port 8001 &
./.venv/bin/python scripts/loadtest/run.py --concurrency 320
```

## Report aggregation at planned volume (issue #291)

The What People Ask report (`GET /api/reports/gaps`, #286) counts the distinct
conversations each question was asked in. The #286 pipelines collect every
`session_id` into a per-question `$addToSet` array and take its `$size`. #291
proposed a two-pass `$group` instead: first on `{question_hash, session_id}`,
then on the hash with `session_count: {$sum: 1}`, so no stage holds an array.
This section times both.

### Method

`scripts/loadtest/report_timing.py` seeds `query_logs` in a throwaway MongoDB
and runs the gaps and FAQ pipelines as the route does, with its 5,000 ms
`maxTimeMS`, five timed runs each after one warm-up run. The rows are shaped
like `analytics.log_query` writes them and carry the same three indexes as
`db.ensure_indexes`, minus the TTL. One popular question gets N asks spread
over 0.8 N conversations (UUID session ids), half of them refused, at random
times across 90 days. 100,000 more asks spread over 5,000 other questions,
each in its own conversation. The window is the full 90 days.

This ran on a **local single-node `mongo:7` container (7.0.43)** under Docker
Desktop on an Apple M3 laptop with 8 GB given to Docker. It is not Atlas: no
replica set, no network hop, a different CPU and disk, and a different memory
budget. Treat the ratios as the finding and the absolute times as local.

### Results

Median of five runs, three at 2M asks. "Timeout" means every run hit
`maxTimeMS`, which the route turns into its 503.

| Popular question | Pipeline | Before (`$addToSet`) | After (two `$group`) |
|---|---|---|---|
| 500k asks, 400k conversations | gaps | 499 ms | 2,819 ms, spilled to disk |
| 500k asks, 400k conversations | FAQ | 1,190 ms | timeout (6.3 s untimed), spilled |
| 1M asks, 800k conversations | gaps | 1,104 ms | timeout (5.5 s untimed), spilled |
| 1M asks, 800k conversations | FAQ | 2,521 ms | timeout (11.5 s untimed), spilled |
| 2M asks, 1.6M conversations | gaps | 2,290 ms | timeout (9.8 s untimed), spilled |
| 2M asks, 1.6M conversations | FAQ | timeout or `ExceededMemoryLimit` | timeout (21.8 s untimed), spilled |

"Untimed" is the `$group` time from an `executionStats` explain, which runs
without `maxTimeMS`. Where both sides finished, the ranked `_id`, `count`,
`session_count`, and `refused_count` matched.

### What this says

- **The two-pass version is 4 to 6 times slower here, and it misses the 5 s
  budget at 500k asks, where the `$addToSet` version takes 1.2 s.** Memory in
  both versions grows with distinct (question, conversation) pairs. The first
  pass keeps one group document per pair, which costs far more per pair than
  one string in an array, so it passes the 100 MB `$group` limit and spills to
  disk at a volume the array version holds in memory. Dropping the sample
  fields and `refused_count` from the first pass still took 4.1 s for the FAQ
  pipeline at 500k asks.
- **The `$addToSet` version fails differently.** One accumulator cannot spill,
  so at 1.6M conversations for one question the FAQ pipeline stopped with
  `ExceededMemoryLimit` (code 146) in one run of three and timed out in the
  other two. The route now answers that error with a 503 too, like a
  timeout.
- Neither version answers a 90-day window inside 5 s at the 7M rows a day the
  TTL comment in `sourcebook/rag/config.py` plans for. That volume needs a
  pre-aggregated count or a shorter window, not a different `$group`.
- **So the route keeps `$addToSet`.** The two-pass version was reverted before
  merge. `report_timing.py` keeps a copy of it as the "after" pipeline so the
  comparison can be rerun.

### The grouped report's session ids

#288 grouped the page by meaning after these runs. Its `wording_pipeline`
returned every session id of each wording so the route could union them
across merged wordings. With the same seed (500k asks of one question over
400k conversations, plus 100k noise), on the same local container:

| Pipeline | All asks | Refused asks only |
|---|---|---|
| Every id returned (#288 as merged) | fails: `BSONObjectTooLarge` (code 10334), a 19.5 MB result document | 604 ms, 223,564 ids in one document |
| At most 1,000 ids per wording | 1,368 ms, `session_count` 400,000 | 610 ms, `session_count` 223,564 |

A result document is capped at 16 MB, so the full list fails at roughly
370k conversations for one wording, and the route did not catch that error.
`WORDING_SESSION_SAMPLE` now returns at most 1,000 ids with the exact
`session_count`. A merged group reports the larger of the union and its
biggest wording's count: exact below the cap, a lower bound above it.

### Reproducing

```bash
docker run -d --rm --name sourcebook-report-timing -p 27099:27017 mongo:7
.venv/bin/python -m scripts.loadtest.report_timing --uri mongodb://localhost:27099
.venv/bin/python -m scripts.loadtest.report_timing --uri mongodb://localhost:27099 \
  --rows 1000000 --sessions 800000
docker stop sourcebook-report-timing
```

### The per-day rollup

The 90-day report did not fit inside 5 s at the 7M rows a day planned in
`config.py`, with either `$group` shape. At the measured rate (about 1.2 s for
600k rows) even a one-day window of 7M rows would take on the order of 14 s,
so a shorter window cannot fix it. The route now reads
`query_log_daily` instead (`sourcebook/rag/query_log_rollup.py`). Each ask
updates one document per question and UTC day as it is logged, and a
per-(question, conversation) marker makes sure each conversation counts once.
The report's cost then grows with distinct questions per day, not with asks.

What changes:

- **Asks are exact. Conversations can be lower, never higher.** A
  conversation counts on the day of its first ask of a question. If that day
  falls before the window, a later ask inside the window adds an ask but not
  a conversation.
- **Windows are whole UTC days**, today included.
- **Each ask costs up to three more writes**: one marker, or two when it is
  refused, and one upsert. The marker collection grows with distinct
  (question, conversation) pairs over 90 days, up to about the size of
  `query_logs` itself, but with small documents.
- **The terminal report is unchanged.** It still reads the raw rows. It has no
  timeout and is exact.

**Not yet measured.** No MongoDB server was reachable where this was built.
`scripts/loadtest/rollup_timing.py` seeds the rollup at planned volume and
times the route's reads with its `maxTimeMS`. Distinct questions per day is a
flag, because the pilot has not measured it:

```bash
docker run -d --rm --name sourcebook-report-timing -p 27099:27017 mongo:7
.venv/bin/python -m scripts.loadtest.rollup_timing --uri mongodb://localhost:27099
.venv/bin/python -m scripts.loadtest.rollup_timing --uri mongodb://localhost:27099 \
  --questions-per-day 200000
docker stop sourcebook-report-timing
```

To run it on Atlas, point `--uri` at a scratch cluster. The `--db` guard stops
it from dropping a real collection, but it still writes a large scratch
database.

| Distinct questions a day | Day documents (90 days) | gaps ranking | FAQ ranking | Session ids | Totals | Where |
|---|---|---|---|---|---|---|
| 50,000 | about 4.5M | pending | pending | pending | pending | local `mongo:7` |
| 200,000 | about 18M | pending | pending | pending | pending | local `mongo:7` |
| 50,000 | about 4.5M | pending | pending | pending | pending | Atlas |

If the rankings are slow because they read whole documents (each one carries
up to 1,000 session ids), the next step is a covering index on `day`,
`question_hash`, and the four counts, with sample text and ids fetched only
for the top 200.
