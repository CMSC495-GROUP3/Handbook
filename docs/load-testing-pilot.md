# Load test against the deployed pilot

**Status: Pending.** The run happens on the `v1.0.0` candidate after the
Monday 28 September freeze
([plan on #215](https://github.com/CMSC495-GROUP3/Sourcebook/issues/215#issuecomment-5824613941),
issue [#212](https://github.com/CMSC495-GROUP3/Sourcebook/issues/212)). This
page holds the protocol now so the run is mechanical; every figure below stays
Pending until it is measured.

## What this measures, and what it does not

Three measurements answer different questions:

| Page | System | Load | Answers |
| --- | --- | --- | --- |
| [load-testing.md](load-testing.md) | laptop, model faked, database in memory, limiter off | up to 320 concurrent | where the thread pool saturates |
| `live-benchmark.md` in each release folder | the deployed pilot, real model | 7 or 8 requests, a burst of 3 | whether each path works for one user |
| this page | the deployed pilot, real model | a few concurrency levels, 80 requests at most | what the deployed system sustains under concurrent load |

The capacity claim for 10,000 users rests on the synthetic page's
multiplication. This run replaces that with a measured figure for the
deployed system. It does not measure 10,000 users: the pilot is one small
instance with one API worker, and a paid model makes a large run a budget
decision rather than a test.

## Mode: the real model, capped

#212 offers two modes. This run uses the real OpenAI model with a hard cap on
requests, because it measures what a pilot user waits for. The other mode, a
second Compose profile with `LLM_PROVIDER=fake`, would measure the server
without the provider, but the fake provider refuses to start with
`APP_ENV=production`, and its embeddings make every retrieval score noise.

| Setting | Value | Why |
| --- | --- | --- |
| Levels | 5, 10, 20, 40 concurrent | 75 requests in all |
| Request cap | 80 (`--max-requests`) | the script refuses to start if the levels add up to more |
| Estimated cost | about $0.75 at $0.01 a generation | an estimate, confirmed at the prompt; the request count is the hard bound. Record the actual cost from the OpenAI usage page |
| Error stop | 5 errors in a level ends the run | a failing system is not measured by more load |
| Questions | the 8 answerable questions `live_benchmark.py` uses, each virtual user in its own session | known to retrieve a policy |
| Cleanup | the script deletes the conversations it created when the run ends, however it ends | nobody else can see them, but they would stay in the database |

The cost is an estimate because each generated answer makes four provider
calls (an embedding, the coverage judge, the answer, the follow-ups),
`OPENAI_MAX_RETRIES=1` can bill a failed call twice, and a request that gets a
503 may already have paid for its embedding and judge call. The totals stay
well under $2. Set a budget limit on the OpenAI project for the window if one
is not set.

**How the columns are measured.** req/s is completed requests over the time
from the level's start to its last `done` event, the definition `run.py` uses.
The stream stays open after `done` for the follow-up suggestions, a second
model call; the report keeps the time including them as
`wall_incl_follow_ups_s`. TTFT and total are over generated answers only, and
total stops at `done`. The percentiles are nearest-rank, so at 5 and 10
requests p95 is the slowest request.

## Settings that decide the result

These pilot settings shape the numbers. Record each one as it was during the
run, in the table under Results.

- **`CHAT_RATE_LIMIT`**, default `30/minute`, is per client address. From
  one client it would cap the whole run at 30 requests a minute, so the run
  window raises it and restores it afterwards. A 429 is counted apart from
  errors.
- **`CACHE_ENABLED`**. The answer cache serves a repeated first-turn
  question without a model call. With the cache on, most of this run would
  measure cache hits, so the window turns it off and every request generates.
  That is the worst case, as in the synthetic page's Finding 1.
- **`OPENAI_MAX_CONCURRENT_REQUESTS`**, default 20, with
  `OPENAI_CAPACITY_WAIT_SECONDS` of 1. The bound covers every provider call:
  the embedding, the coverage judge, the answer, and the follow-ups. Past 20
  concurrent calls, the extra ones wait a second for a slot. Before the first
  token that is an HTTP 503 with `Retry-After` (provider busy), which the
  script lists as `HTTP 503`; a busy follow-up call only drops the
  suggestions. The 40 level is expected to show 503s. It is the provider bound
  doing its job.
- **One API worker, `THREADPOOL_TOKENS` 100, `MONGO_MAX_POOL_SIZE` 20.** The
  API container runs a single uvicorn worker unless `WEB_CONCURRENCY` is set,
  and each worker has 20 Atlas connections, which the history lookup, vector
  search, persist, and query log share. Leave these unchanged: they are what
  the pilot runs. Step 1 prints them.
- **The OpenAI account's own limits.** A request or token rate limit at
  OpenAI comes back as a 429 from OpenAI, which the SDK retries once
  (`OPENAI_MAX_RETRIES=1`). If it persists, the stream ends with "An error
  occurred while generating the response.", which the script lists apart from
  `HTTP 503`. That is OpenAI's limit, not the pilot's.

## Running it

Two people or two shells: one on the pilot host, one on a client outside it.
Pick a time when nobody else is using the pilot, and tell the team not to
merge or deploy during it.

**1. On the host, open the window.** The checkout is the one the
`auto-deploy` unit uses. The block runs in a subshell with `set -e`, so the
first failure stops it without closing your SSH session, and the sampler only
starts once everything before it worked.

```bash
cd /home/ubuntu/CMSC495-CAP && (
  set -e
  export COMPOSE_FILE=docker-compose.yml       # as auto_deploy.sh does: no stray override file
  sudo systemctl stop auto-deploy.timer        # no redeploy mid-run
  while systemctl is-active --quiet auto-deploy.service; do sleep 5; done   # let a deploy in flight finish
  git rev-parse refs/deployed/main             # record: the deployed SHA
  cp .env ~/env.before-load-test               # outside the checkout, so git never sees it
  printf '\nCHAT_RATE_LIMIT=600/minute\nCACHE_ENABLED=0\n' >> .env
  docker compose up -d api                     # recreate the API with the window settings
  until curl -fsS https://sourcebook.duckdns.org/api/health; do sleep 2; done
  docker compose exec api printenv | grep -E '^(CHAT_RATE_LIMIT|CACHE_ENABLED|OPENAI_MAX_CONCURRENT_REQUESTS|OPENAI_CAPACITY_WAIT_SECONDS|OPENAI_MAX_RETRIES|THREADPOOL_TOKENS|WEB_CONCURRENCY|MONGO_MAX_POOL_SIZE)=' || true
) && scripts/loadtest/host_stats.sh 2 > /tmp/pilot-load-host.csv
```

The `printenv` line prints no secrets. It confirms the window settings are
live and gives the values for the Results table; a setting it does not print
is at its default (`sourcebook/rag/config.py`), and no `WEB_CONCURRENCY` means
one worker. The health wait matters because Nginx keeps the old API address for
up to 10 seconds after a recreate. Leave the sampler running.

**2. On the client, run the levels.**

```bash
BENCH_PASSWORD=... ./.venv/bin/python -m scripts.loadtest.pilot_load \
  --url https://sourcebook.duckdns.org --levels 5 10 20 40 \
  --deployed-sha <sha from step 1> --client-location "<where>" \
  --setting CHAT_RATE_LIMIT=600/minute --setting CACHE_ENABLED=0 \
  --out docs/releases/v1.0.0/evidence/pilot-load.json
```

The script checks it can write `--out` before sending anything, asks for
confirmation with the request count and the estimated cost, then prints one
line per level and the results table. It rewrites the report after every
level, so a run that stops early still leaves one. When it ends, it deletes
the run's conversations and prints how many; `cleanup` in the report records
the same. It exits 1 when any level had errors, which includes the 503s
expected at 40: that is not a failed run.

**3. On the host, close the window.** Do this even if the run failed.

```bash
# Ctrl-C the sampler, then:
cd /home/ubuntu/CMSC495-CAP
export COMPOSE_FILE=docker-compose.yml
# The run's query_logs rows; <run_id> is in the report and the script's first line.
docker compose exec api python -c "from sourcebook.api.db import query_logs_col as c; print(c.delete_many({'session_id': {'\$regex': '^load-<run_id>-'}}).deleted_count)"
mv ~/env.before-load-test .env
docker compose up -d api
until curl -fsS https://sourcebook.duckdns.org/api/health; do sleep 2; done
sudo systemctl start auto-deploy.timer
```

The `query_logs` rows would otherwise skew the measured cache hit rate and the
knowledge-gap report; record the count it prints. If the script could not
delete every conversation (`failed` above 0 in `cleanup`, or it was killed
before cleaning up), the same `delete_many` on `conversations_col` removes
the rest. Ask one question in the browser to confirm the pilot answers with
the cache back on.

**4. Commit the evidence.** Commit the JSON report, then copy the host
samples to `docs/releases/v1.0.0/evidence/pilot-load-host.csv`. Neither
holds a password, token, or answer text. Check the CSV's container names
before committing it.

## Results

Pending.

| Field | Value |
| --- | --- |
| Date (UTC) | Pending |
| Deployed commit | Pending |
| Client location | Pending |
| `CHAT_RATE_LIMIT` during the run | Pending |
| `CACHE_ENABLED` during the run | Pending |
| `OPENAI_MAX_CONCURRENT_REQUESTS`, `OPENAI_CAPACITY_WAIT_SECONDS`, `OPENAI_MAX_RETRIES` | Pending |
| API workers, `THREADPOOL_TOKENS`, `MONGO_MAX_POOL_SIZE` | Pending |
| Actual OpenAI cost for the window | Pending: from the usage page |
| Cleanup | Pending: conversations deleted, `query_logs` rows deleted |
| Report | Pending: `releases/v1.0.0/evidence/pilot-load.json` |

Paste the table the script prints:

| Concurrent | Completed | Generated / cached / refused | 429 | Errors | req/s | TTFT p50 | TTFT p95 | Total p50 | Total p95 |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| 10 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| 20 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| 40 | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

Host during the run, from the sampler:

| Measure | Value |
| --- | --- |
| API container CPU, peak | Pending |
| API container memory, peak | Pending |
| 1-minute load average, peak | Pending |
| Samples | Pending: `releases/v1.0.0/evidence/pilot-load-host.csv` |

## What the result means

Pending. After the run, say in plain terms:

- the highest level with no errors, and its requests per second and TTFT p95
- where failures started and of what kind: `HTTP 503` is the pilot's provider
  bound (expected first, at 40), a generic generation error is OpenAI's own
  limit, and anything else is a finding
- how the measured requests per second compare with the synthetic page's
  83 req/s target, and what that says about the 10,000-user claim for this
  deployment
- what the release's "does not establish" section should now say
