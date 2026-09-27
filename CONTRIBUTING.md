# Working on this project

The [README](README.md) explains what the system is, and
[docs/architecture.md](docs/architecture.md) why it is built the way it is. This page is the practical side: getting it running, checking a change,
and getting that change merged. If something here is wrong or missing, fix it in
the same PR as the change that made it wrong.

`.agents/skills/sourcebook/SKILL.md` is the condensed version of this page
for coding agents: stack, layout, commands, conventions, and the rules that
are easy to break. Keep the two in step.

How we treat each other while doing all this, including how reviews are
worded and how stalled branches get picked up, is in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Ten minutes to a running app

No cloud accounts, API keys, or `.env` needed. This runs the real application
with a fake model and an in-memory database.

Prerequisites: Python 3.11+, Node 22+, and `make`. Docker is only needed for the
full stack.

```bash
git clone https://github.com/CMSC495-GROUP3/Sourcebook.git
cd Sourcebook
make setup          # .venv, Python deps, npm install
make stub           # terminal 1: API on :8000, fake model, in-memory Mongo
make web            # terminal 2: React on :5173 with hot reload
```

Open http://localhost:5173 and log in with the password `dev`. Log in with
`manager` to add the What People Ask page, or `hr` to add HR Requests as well.

What is fake in this mode, so you are not surprised:

- **The model.** Every answer is the same canned PTO text, and follow-up
  suggestions are canned too. Retrieval scores are fixed, so every question
  either answers or every question refuses. `make stub REFUSE=1` flips it to
  refusing, which is how you see the refusal card and the escalation button.
  `make stub REFUSE=judge` refuses through the coverage judge instead, the
  other refusal card.
- **The database.** Conversations, escalations, and caches live in memory and
  vanish when the API stops.
- **Vector search.** Replaced with canned passages. Atlas Vector Search cannot
  run locally at all.

The stub lives in `scripts/loadtest/server.py`. It patches the real app from the
outside; there is no test-only branch in application code, and there should not
be one.

## Running against the real services

Needed for anything touching retrieval quality, ingestion, or the provider.
[docs/install.md § Real services](docs/install.md#real-services) is the full
procedure; this is the short checklist.

1. `cp .env.example .env` and fill it in. The comments in that file say what
   each value is for. You need an OpenAI key, a MongoDB Atlas cluster with
   Vector Search, and an S3 bucket.
2. Generate the two secrets:
   ```bash
   openssl rand -hex 32                                   # JWT_SECRET_KEY
   .venv/bin/python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"   # APP_PASSWORD_HASH
   ```
   A bcrypt hash contains `$`. Paste it into `.env` with an editor, not `echo`.
   An optional second password goes in `APP_PASSWORD_HASH_2`, hashed the same
   way; [install.md § More passwords](docs/install.md#more-passwords) says what
   that implies before you hand one out. The HR Requests page opens only for the
   password in `HR_PASSWORD_HASH`, and What People Ask for that one or the
   manager password in `MANAGER_PASSWORD_HASH`, both hashed the same way.
3. Load the corpus, then create the vector index in the Atlas UI
   ([install.md § Load the corpus](docs/install.md#load-the-corpus) has the
   exact JSON). The driver cannot create a
   search index; this step is manual and it is the one people forget.
   ```bash
   .venv/bin/python -m sourcebook.rag.seed_documents     # documents -> S3
   .venv/bin/python -m sourcebook.rag.embed_documents    # chunk, embed, store
   ```
4. Run it either way:

   | | Command | Use when |
   |---|---|---|
   | Dev mode | `.venv/bin/uvicorn sourcebook.api.main:app --reload` plus `make web` | changing code |
   | Full stack | `make compose` | checking the Nginx proxy, the Docker build, or what a deploy will run |

   In dev mode the API is at http://localhost:8000 and the OpenAPI console at
   http://localhost:8000/docs, which is the fastest way to poke an endpoint by
   hand. In Compose the app is at http://localhost, served by Caddy in front
   of Nginx; only Caddy publishes ports.

## Checking a change

```bash
make test     # Python tests, about a second
make cov      # same, with a per-file coverage report
make lint     # ruff on Python; ESLint and tsc on the web app
make fmt      # fix what ruff can fix, then format; run before committing
make build    # production web build
make check    # Python tests, web tests (test-web / npm test), lint, build; this is what the CI workflow runs
make openapi  # rewrite docs/openapi.json from the live app; CI diffs this file
make audit    # known vulnerabilities in both dependency trees (the Security workflow)
make acceptance  # the real Caddy -> Nginx -> Uvicorn client-IP and rate-limit chain
```

`make acceptance` needs Docker Compose 2.24 or later because
`docker-compose.acceptance.yml` uses `!reset`. Older Compose fails to parse
the override. The run intentionally leaves two image tags for build-cache
reuse: `sourcebook-api:acceptance` and `sourcebook-web:acceptance`. CI's Docker
job runs the same check.

Python formatting is enforced. `make fmt` before you commit and CI will not
complain. The rules are in `pyproject.toml`; the version of ruff is pinned in
`requirements/lint.in` because the formatter's output changes between releases.

### What CI runs

Every PR and every push to `main` triggers four workflows. None needs a secret,
so they run on fork PRs too.

| Workflow | Job | What fails it |
|---|---|---|
| CI | Python lint and format | a `ruff check` finding, an unformatted file, or a lock that no longer matches its `.in` |
| CI | Python tests (3.11 through 3.14) | a failing test, or coverage under 80% on any version |
| CI | Evaluation dataset | `evaluation/questions.json` or `questions_full.json` that `load_cases` rejects |
| CI | OpenAPI document | `make openapi` rewriting `docs/openapi.json` so it no longer matches the commit |
| CI | Web lint, types, test, build | ESLint, `tsc`, `npm test`, or `vite build` |
| CI | Docker images and Compose | either image failing to build, the API image failing to import `sourcebook.api.main`, an invalid `docker-compose.yml`, or `scripts/test_proxy_chain.py` failing the live Caddy → Nginx → Uvicorn client-IP / rate-limit check |
| CI | Shell, Dockerfile, workflow lint | shellcheck on `scripts/*.sh`, hadolint on both Dockerfiles, actionlint on the workflows, or a `.env`, key, or build output that got committed |
| Security | CodeQL, dependency advisories, dependency review, leaked secrets | a new finding; the accepted-advisory list is in `scripts/audit.sh` |
| PR checks | title, description | a title not in `type: what changed` form, or an empty "What and why" |
| PR path labels | labels | nothing; it only applies area labels from the changed paths |

The Security workflow also runs every Monday, so a new advisory in an existing
dependency shows up as a failed scheduled run rather than in someone's
unrelated PR.

Branch protection on `main` should require the single check named **CI
status**, which fails unless every CI job succeeded. A job that is skipped
counts as a failure here, so a wrong `if:` or `paths:` condition on a required
job shows up as a red check rather than a silent pass. Requiring that one name
means a job added or renamed in `ci.yml` cannot quietly stop being required.

A fifth workflow, **Live evaluation**, runs the labeled question set against
the real provider and index. It costs money, so it only runs when a maintainer
starts it from the Actions tab, and it needs a repository environment named
`evaluation` holding `OPENAI_API_KEY`, `MONGODB_URI`, `MONGODB_DB`, and an
Atlas API key as `ATLAS_PUBLIC_KEY`, `ATLAS_PRIVATE_KEY`, and
`ATLAS_PROJECT_ID`, which the job uses to admit its own IP to the cluster's
access list for the length of the run. See `docs/evaluation.md` for the setup
and for what the numbers mean.

Dependabot opens one grouped PR per ecosystem on Mondays (pip, npm, GitHub
Actions, Docker base images). Review them like any other PR; CI runs on them.

### Writing tests

The suite is in `tests/`. `conftest.py` stubs every external service before the
app is imported, the same way the stub server does. Useful fixtures:

| Fixture | Gives you |
|---|---|
| `client` | a `TestClient` for the whole app |
| `auth` | a header dict with a valid bearer token |
| `retrieval` | control over what vector search returns (`retrieval.passages = make_passages(0.9, 0.7)`) and a count of calls |
| `conversation` | a fresh conversation's `session_id` |

Test the behaviour, not the implementation: assert on the HTTP response, the
SSE events, or what ended up in the fake database. Look at
`tests/test_escalations.py` for the shape of a route test and
`tests/test_chat.py::TestDroppedStream` for driving the streaming generator by
hand. That class earned its place: while the suite was being written it caught
a two-word fragment from an abandoned stream being cached as the answer for
everyone who asked the same question next.

The fake Mongo (`scripts/loadtest/fakemongo.py`) implements only the operations
the app uses. If you use a new query operator or update form, add it there, and
keep it obviously partial rather than pretending to be complete.

## Where things live

| I want to change... | Look in |
|---|---|
| a tuning knob (threshold, chunk size, TTLs, thread pool) | `sourcebook/rag/config.py`; every value is env-overridable, defaults live here |
| the answer prompt | `sourcebook/rag/rag_chain.py` `ANSWER_SYSTEM_PROMPT`, then bump `PROMPT_VERSION` in `sourcebook/rag/config.py` or cached answers keep serving the old prompt |
| the coverage-judge prompt or parser | `sourcebook/rag/rag_chain.py` `COVERAGE_SYSTEM_PROMPT` / `_parse_coverage_response`, then bump `COVERAGE_PROMPT_VERSION` in `sourcebook/rag/config.py` or cached answers and refusals keep serving the old judge |
| retrieval or the grounding gate | `sourcebook/rag/rag_chain.py` |
| the What People Ask pair check | `sourcebook/rag/question_judge.py`, then bump `QUESTION_JUDGE_PROMPT_VERSION` there and rerun `scripts/measure_question_groups.py --judge` ([evaluation.md](docs/evaluation.md#question-grouping-threshold)) |
| which model or vendor is used | `sourcebook/rag/llm.py` only. Add a subclass, register it in `_PROVIDERS`, set `LLM_PROVIDER` |
| how a source format is parsed | `sourcebook/rag/documents.py` |
| an API endpoint | `sourcebook/api/routes/`; one file per area, mounted in `sourcebook/api/main.py` |
| a MongoDB collection or index | `sourcebook/api/db.py` |
| the chat UI | `web/src/components/Chat/`, state in `web/src/hooks/useChat.ts` |
| the product name or the escalation contact | both `sourcebook/rag/config.py` and `web/src/config.ts`, mirrored; the product name is also the `<title>` in `web/index.html`, so change all three |
| the sample corpus | `data/sample-policies/`, then re-run ingestion |

### Repository layout

```text
sourcebook/   the Python application, one package, absolute imports only
  api/              FastAPI app
    main.py           app factory and lifespan; mounts routes/
    db.py             collection handles and index creation
    limiter.py        the slowapi rate limiter; routes set the limits
    tokens.py         JWT signing and verification, shared by auth, deps, and limiter
    analytics.py      one query_logs record per request, plus its per-day rollup
    logutil.py        sanitizes values before they reach a log line
    notify.py         best-effort webhook delivery for escalations
    routes/           one file per area
      auth.py           login with the shared, second, HR, or manager password; 24-hour JWT; 10 attempts a minute
      chat.py           streaming and non-streaming Q&A; enforces the grounding gate
      conversations.py  saved conversations and their citations
      projects.py       folders that group conversations
      documents.py      browse and search the indexed corpus
      escalations.py    hand a question to a person; open queue; resolve; retry delivery
      reports.py        the What People Ask report and its background refresh
      deps.py           the require_auth dependency every protected route uses
  rag/              the pipeline, imported by api/ and run offline for ingestion
    config.py         every tuning knob, env-overridable; defaults live here
    llm.py            LLMProvider interface, the only vendor-aware module
    rag_chain.py      retrieval, grounding gate, prompt, generation
    cache.py          embedding and answer caches, keyed on corpus and prompt version
    documents.py      source-format abstraction
    mongo.py          client construction and the connection-pool arithmetic
    evaluation.py     runs and scores smoke/full evaluation tiers
    question_groups.py, question_judge.py   What People Ask's grouping by meaning
    query_log_rollup.py, report_snapshots.py   per-day counts and the refreshed report windows
    query_log_reports.py   the read-only terminal report over query_logs
    seed_documents.py, embed_documents.py   offline ingestion
web/                React 19, TypeScript, Tailwind 4, Vite; served by Nginx
tests/              pytest suite; conftest.py stubs every external service
scripts/            auto_deploy.sh and the deploy and prune systemd units, deploy.sh, audit.sh, the
                    proxy-chain acceptance test, the live evaluation gate and its
                    synthetic test, purge_ownerless_conversations.py,
                    measure_question_groups.py, export_openapi.py,
                    migrate_passage_index.py, atlas_access_list.sh, the Lighthouse
                    runner in lighthouse/, and the load-test harness in loadtest/
evaluation/         smoke (20) and full-corpus labeled questions, the question-pair set
                    for What People Ask grouping, and scoring notes
data/               42 fictional sample policies
docs/               install, user-guide, architecture, api, design, evaluation, load-testing,
                    load-testing-demo, ci-cd, quality, and team pages, the README.md
                    index, the committed openapi.json, and one folder per release under releases/ with its handoff, notes,
                    measurements, and evidence
assets/brand/       the Sourcebook mark, source PNGs; web/public/ holds the served copies
requirements/       *.in are pip-compile inputs (base is shared; api is the Docker image; ingest;
                    lint; dev is everything); api, dev, and ingest compile to .txt locks
pyproject.toml      ruff and pytest settings
Makefile            setup, stub, web, test, lint, build, compose; `make` lists them
Dockerfile          the API image; web/ has its own
docker-compose.yml  caddy, web, api; docker-compose.acceptance.yml overrides it for make acceptance
Caddyfile           TLS termination and reverse proxy in front of Nginx
.env.example        every setting, with a comment on each
.github/            CI, Security, PR checks, PR path labels, and Live evaluation workflows; templates; Dependabot; CODEOWNERS
.agents/            a skill file describing this repo for coding agents
```

`sourcebook` is one package and every import is absolute
(`from sourcebook.rag.config import ...`), so run things from the repo
root as modules: `python -m sourcebook.rag.embed_documents`,
`uvicorn sourcebook.api.main:app`. Running a file by path
(`python sourcebook/rag/embed_documents.py`) puts the wrong directory on
`sys.path` and the package import fails.

## Getting a change merged

1. Branch from `main`: `feat/short-name`, `fix/short-name`, `docs/...`. If you
   do not have write access to the repo, work on a fork; `gh repo fork` sets
   one up and PRs open against `CMSC495-GROUP3/Sourcebook` the same way.
2. Commit in pieces that each make sense alone. Messages follow
   `type: what changed` with the types `feat`, `fix`, `refactor`, `docs`,
   `test`, `chore`, `perf`, `ci`. The body is for *why*, and for anything a
   reader would otherwise have to rediscover: what you measured, what you tried
   that did not work, what a future change must not break. Read
   `git log` for the house style.
3. `make check` before pushing. `make fmt` first if ruff complains.
4. Open the PR. Its title follows the same `type: what changed` rule as
   commits, because it becomes the merge commit subject; a check enforces it.
   The template asks for what a reviewer needs. One approval and green CI to
   merge. Prefer squash only when the commits are noise; otherwise keep them.
5. If the change alters setup, configuration, or behaviour someone would need
   to know about, the README, this page, or the `docs/` page that owns it
   changes in the same PR.

Never commit `.env`, a key, a hash, or a real policy document. `.gitignore`
covers `.env`; the rest is on you.

## Things that will bite you

- **Changing a TTL** (`*_TTL_SECONDS` in `config.py`) fails at startup with
  `IndexOptionsConflict` on an existing database. MongoDB will not alter a TTL
  through `create_index`; drop the index by hand or run `collMod` first.
- **Changing the embedding model** changes the vector dimensions, which are
  baked into the Atlas index. Re-run ingestion and recreate the index.
- **`typescript` stays on 6.0.x** in `web/package.json` because `typescript-eslint`
  pins its peer to `<6.1.0`, so `npm ci` refuses 7.x. Dependabot ignores the
  7.x line; lift that in `.github/dependabot.yml` once `typescript-eslint`
  supports TypeScript 7.
- **Do not deploy under gunicorn `--preload`.** `MongoClient` is not fork-safe
  and the collection handles bind at import. `uvicorn --workers N` is fine. The
  reasoning is in `sourcebook/rag/mongo.py`.
- **`LLM_PROVIDER=fake` refuses to start with `APP_ENV=production`**, on
  purpose. If a deploy fails with that error, the environment is misconfigured,
  not the code.
- **Connections per process** are `MONGO_MAX_POOL_SIZE` and the cluster limit is
  workers times that. Atlas free tier caps in the low hundreds and fails under
  load rather than at startup. Redo the arithmetic in `sourcebook/rag/mongo.py` before
  raising either number.
- **Cached answers outlive a prompt fix** unless the matching version is
  bumped. `PROMPT_VERSION` is for `ANSWER_SYSTEM_PROMPT`.
  `COVERAGE_PROMPT_VERSION` is for the coverage-judge prompt and parse
  contract. Both participate in the answer-cache key.
- **`THREADPOOL_TOKENS` is the chat throughput ceiling.** It was measured, not
  guessed; see `docs/load-testing.md` before changing it, and re-measure
  after.
- **The fake provider's embeddings are meaningless.** Never use `make stub` to
  judge retrieval quality or to tune `SIMILARITY_THRESHOLD`.

## Passage identity index migration

The `passages` collection requires a unique compound index on
`(source, chunk_index)`. Older databases may still have the same index as
non-unique and may also contain duplicate passage identities.

Do not run this migration against production without an explicit operations
decision and a current database backup/snapshot.

Before migration:

1. Stop or otherwise prevent passage ingestion/writers from changing the
   collection during the migration.
2. Confirm a current MongoDB Atlas backup/snapshot exists.
3. Check for duplicate passage identities:

   ```javascript
   db.passages.aggregate([
     {
       $group: {
         _id: { source: "$source", chunk_index: "$chunk_index" },
         count: { $sum: 1 }
       }
     },
     { $match: { count: { $gt: 1 } } }
   ])
   ```

4. Inspect the current indexes:

   ```javascript
   db.passages.getIndexes()
   ```

Run the dry run first, from the repository root:

```bash
.venv/bin/python -m scripts.migrate_passage_index --dry-run
```

It prints one line per duplicated identity, naming the record it would
keep and the `_id`s it would delete, then what it would do to the index,
and changes nothing. Read those lines before going on. Then run it for
real:

```bash
.venv/bin/python -m scripts.migrate_passage_index
```

The migration:

- prints the same per-duplicate lines before each delete, so the job log
  is the audit trail;
- keeps the record with the greatest `_id` in each group and deletes the
  rest;
- drops the legacy compound index when present, non-unique or under
  another name;
- creates `source_1_chunk_index_1` with `unique: true`;
- is safe to rerun after a successful migration.

Two things to know at cutover:

- Between the drop and the create there is a moment with no identity
  index at all. If the script dies there, rerun it; it finds no index and
  creates the unique one.
- Once the unique index exists, the previous API image fails at startup
  with `IndexOptionsConflict` (code 85), because it declares the same
  keys without `unique`. Rolling back the image is blocked from that
  point; roll back the database from the snapshot instead.

The local FakeMongo used by the test suite does not enforce MongoDB index
uniqueness. Tests therefore verify the unique index declaration, migration
behavior, duplicate reconciliation, and failure handling without pretending
that FakeMongo can reproduce MongoDB's duplicate-key enforcement.

After migration:

1. Confirm no duplicate identities remain.
2. Confirm `db.passages.getIndexes()` reports
   `source_1_chunk_index_1` with `unique: true`.
3. Re-run `scripts/embed_documents.py`. The migration keeps the greatest
   `_id` in each duplicate group, and ingestion refreshed an arbitrary one
   while duplicates existed, so the survivor can hold stale text and a
   stale embedding. Re-embedding overwrites every passage from the source.
4. Start the application and confirm normal startup succeeds.
5. Smoke-test document retrieval and the Policy Library before returning the
   deployment to normal service.

If migration fails, do not repeatedly modify the production collection by hand.
Keep passage writers stopped, inspect the reported error and current indexes,
and restore from the approved backup/snapshot if rollback is required.

Prefer a forward-only recovery. Recreate the legacy non-unique index only if an
explicit operations decision requires it; otherwise restore from the approved
backup and investigate before retrying.

## Debugging

- The OpenAPI console at `/docs` lets you call any endpoint with a token. Log in
  at `POST /api/auth/login`, click Authorize, paste the token. The committed
  document and the client walkthrough are [docs/openapi.json](docs/openapi.json)
  and [docs/api.md](docs/api.md).
- SSE by hand:
  `curl -N -X POST localhost:8000/api/chat/stream -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"question":"How much PTO do I get?"}'`
- Escalations queue: `GET /api/escalations?status=open`. Retry a failed webhook
  with `POST /api/escalations/{id}/retry-delivery`. Both need a token from the
  HR password (`hr` under `make stub`). In the web app this is the HR Requests
  page.
- Query analytics are in the `query_logs` collection: refused questions grouped
  by `question_hash` are the content gaps, and `best_score` on answered versus
  refused rows is what the threshold should be tuned against. Run a read-only
  offline report over a time window, on the EC2 host, since the cluster's IP
  access list admits that host and anywhere else waits out `--timeout`
  (default 10 s) and fails:
  `python -m sourcebook.rag.query_log_reports --since 2026-08-01`.
  `--until` defaults to now. Optional `--top` and `--min-repeat` bound the
  ranked lists. Rows expire after 90 days (`QUERY_LOG_TTL_SECONDS`), so an
  older window prints an empty report. Sample text comes from already-logged
  truncated `question_raw` / `question_condensed` when present.
- API logs go to stdout. In Compose: `docker compose logs -f api`.

## Load testing and deployment

- `make stub` in one terminal, `make loadtest` in another. Method, numbers, and
  caveats in `docs/load-testing.md`.
- The EC2 host deploys itself: a systemd timer runs `scripts/auto_deploy.sh`
  every two minutes, which fast-forwards to upstream `main` and rebuilds only
  the services whose inputs changed. `scripts/deploy.sh` starts that service
  now, over SSH, and prints its log. Both touch real infrastructure, so read
  them before running them. The host setup (Elastic IP, DuckDNS record,
  security group, `SITE_ADDRESS` in `.env`, the timer) is in
  [docs/install.md § Deployment](docs/install.md#deployment).

## Adding a Python dependency

Edit the relevant `requirements/*.in` file, never a compiled `.txt`, then
regenerate the locks and commit both:

    make lock

`make setup` installs `pip-tools`, which provides `pip-compile`. CI runs the
same command and fails if a committed lock no longer matches its `.in`. To
upgrade pinned versions on purpose, run `pip-compile --upgrade` on the file you
mean to move and commit that as its own change.
