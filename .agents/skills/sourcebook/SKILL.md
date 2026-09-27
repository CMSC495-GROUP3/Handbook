---
name: sourcebook
description: Working in the Sourcebook repo, the policy assistant. Stack, layout, commands, code conventions, what CI enforces, and the rules that are easy to break without noticing. Read before changing anything here.
---

# Sourcebook: how to work in this repo

A retrieval-augmented question answering service over a company policy corpus.
An employee asks a question, the API retrieves passages from MongoDB Atlas
Vector Search, a grounding gate decides whether the evidence is strong enough,
and the model either answers with citations or refuses and offers to hand the
question to a person. The README explains why it is built this way. This file
is the shorter, practical version for an agent that has to change it.

If something here disagrees with CONTRIBUTING.md or the code, the code wins.
Fix this file in the same PR.

## Stack

| Layer | What | Where |
|---|---|---|
| API | FastAPI, uvicorn, slowapi rate limiting, JWT via PyJWT, bcrypt | `sourcebook/api/` |
| RAG pipeline | OpenAI embeddings and chat, LangChain text splitters, pymongo | `sourcebook/rag/` |
| Storage | MongoDB Atlas (passages, document bodies, conversations, escalations, caches, query logs), S3 for raw documents | `sourcebook/rag/mongo.py`, `sourcebook/api/db.py` |
| Web app | React 19, TypeScript (strict, no unused locals), Vite, Tailwind 4, react-router, axios | `web/` |
| Serving | Docker Compose, Nginx in front of the API, EC2 | `docker-compose.yml`, `Dockerfile`, `web/nginx.conf`, `scripts/` |
| Tests | pytest with everything external stubbed; ~240 tests, a few seconds | `tests/` |
| Lint | ruff (Python), ESLint flat config + tsc (web) | `pyproject.toml`, `web/eslint.config.js` |

Python target is 3.11 (what the Dockerfile shipped when the rules were set);
CI runs 3.11 through 3.14. Node 22 in CI, Node 26 in the image.

## Layout

```text
sourcebook/   the Python application, one package, absolute imports only
  api/              FastAPI app. main.py mounts routes/; db.py binds collection handles at import
    routes/         one file per area: auth, chat, conversations, documents, escalations, projects
    tokens.py       JWT signing and verification; auth.py, routes/deps.py, and limiter.py all use it
    analytics.py    one query_logs row per request
    notify.py       webhook delivery for escalations
  rag/              the pipeline, imported by api/ and run offline for ingestion
    config.py       every tuning knob, all env-overridable; defaults live here and nowhere else
    llm.py          LLMProvider interface; the only module that knows a vendor
    rag_chain.py    retrieval, grounding gate, prompt, generation
    cache.py        embedding and answer caches, keyed on prompt, corpus, and retrieval settings
    documents.py    source-format parsing
    embed_documents.py, seed_documents.py   offline ingestion
    evaluation.py   runs and scores smoke/full evaluation tiers
web/src/            components/{Auth,Chat,Documents,Layout}, hooks/useChat.ts, pages/, api/client.ts, config.ts
tests/              conftest.py stubs Mongo, the model, vector search, and index creation before importing main
scripts/loadtest/   fakemongo.py (partial in-memory Mongo), server.py (the stub app), run.py
scripts/            auto_deploy.sh and its systemd/ units (the EC2 host runs it on a timer), deploy.sh, audit.sh
evaluation/         smoke (20) and full-corpus labeled questions plus metric definitions
data/               sample policy corpus
requirements/       *.in inputs (base shared; api = Docker image; ingest; lint; dev = all); api, dev, ingest compile to .txt locks
pyproject.toml      ruff and pytest settings
Dockerfile          the API image; web/Dockerfile is the Nginx image
.github/            workflows (ci, security, pr-checks, evaluation), templates, Dependabot, CODEOWNERS
```

Imports are absolute: `from sourcebook.rag.config import ...`. Run
Python from the repo root as modules (`python -m sourcebook.rag.embed_documents`,
`uvicorn sourcebook.api.main:app`). Running a file by path puts the wrong
directory on `sys.path` and the package import fails. Tests and the stub get the
root on `sys.path` from `pythonpath` in `pyproject.toml` and from uvicorn.

## Set up and run

```bash
make setup        # .venv, Python deps (requirements/dev.txt), npm install
make stub         # API on :8000 with LLM_PROVIDER=fake and in-memory Mongo; password "dev"
make web          # Vite on :5173, proxies /api to :8000
make stub REFUSE=1   # every answer refuses, to see the escalation path
```

No `.env`, keys, or cloud accounts are needed for that. The stub is
`scripts/loadtest/server.py`; it patches the real app from outside. Retrieval
quality cannot be judged in stub mode because the fake embeddings are noise.

Real services need `.env` from `.env.example`, then
`python -m sourcebook.rag.seed_documents`, `... embed_documents`, and a vector index created by hand in the Atlas UI.
CONTRIBUTING.md walks through it.

## Check a change

```bash
make check    # test + lint + build; the CI workflow runs the same things
make fmt      # ruff --fix and ruff format; run before committing
make cov      # per-file coverage; CI fails under 80%
make audit    # pip-audit and npm audit; accepted advisories listed in scripts/audit.sh
```

CI on every PR: ruff check and format, pytest on four Python versions with
the 80% floor, a validity check on `evaluation/questions.json`, ESLint, tsc,
Vite build, both Docker images built and the API one import-smoked,
shellcheck, hadolint, actionlint, and a guard against committing `.env`, keys,
coverage files, or `dist/`. Branch protection requires the one check named
`CI status`. A separate Security workflow runs CodeQL, dependency audits, and
gitleaks. PR checks enforce the title format and a filled-in description.

## Conventions

### Commits, branches, PRs

- Branch names: `feat/short-name`, `fix/...`, `docs/...`, `ci/...`.
- Commit subject: `type: what changed`, lower-case, types `feat fix refactor
  docs test chore perf ci`. The body says why, and records anything a reader
  would otherwise have to rediscover (what was measured, what did not work).
- PR title follows the same rule; a check rejects anything else. The PR
  template asks how to verify the change. Fill in "What and why" or the
  description check fails.
- Docs change in the same PR as the behaviour they describe.

### Python

- `[tool.ruff]` in `pyproject.toml` is the rule set: pycodestyle, pyflakes, isort, bugbear,
  pyupgrade, simplify, ruff's own. Line length 100. E501 is off because the
  formatter wraps code. B008 is off because FastAPI's `Depends()` lives in
  default arguments.
- ruff is pinned exactly in `requirements/lint.in`. Do not run a different
  version; the formatter's output changes between releases and CI diffs it.
- Files that must set environment variables before importing the app
  (`tests/conftest.py`, `scripts/loadtest/server.py`) mark late imports with
  `# noqa: E402`. Keep the marker; ruff flags unused ones.
- Type hints on function signatures. `datetime.UTC`, not `timezone.utc`.
- New tuning knobs go in `sourcebook/rag/config.py` as `NAME = type(os.getenv("NAME", default))`.
- Vendor-specific code goes in `sourcebook/rag/llm.py` only. A new provider is a subclass
  registered in `_PROVIDERS` and selected with `LLM_PROVIDER`.
- No test-only branches in `sourcebook/`. If something cannot be
  stubbed from `tests/conftest.py`, fix the design, not the test.

### TypeScript

- `tsconfig.app.json` is strict with `noUnusedLocals` and `noUnusedParameters`.
  `npx tsc -b` must pass; the build runs it first.
- ESLint is the flat config with `typescript-eslint`, `react-hooks`
  (including the React Compiler rules, so no synchronous setState inside an
  effect), and `react-refresh`.
- Components live under `web/src/components/<Area>/`, hooks in `hooks/`
  with a `use` prefix, API calls through `web/src/api/client.ts`.
- `web/src/config.ts` mirrors `sourcebook/rag/config.py` for `APP_NAME` and
  `ESCALATION_CONTACT`. Change both.

### Tests

- Fixtures in `tests/conftest.py`: `client` (TestClient for the whole app),
  `auth` (bearer header), `retrieval` (control what vector search returns and
  count calls), `conversation` (a fresh session id).
- Assert on the HTTP response, the SSE events, or what landed in the fake
  database. Not on internals.
- `scripts/loadtest/fakemongo.py` implements only the Mongo operations the
  app uses. Add what you need there and keep it visibly partial.
- If a change alters what the assistant answers or refuses, update the smoke
  and/or full evaluation tiers (`evaluation/questions.json`,
  `evaluation/questions_full.json`) or say in the PR why not. Smoke stays at
  20 cases; full must cover every sample policy title. Tests check both.

## Rules that are easy to break

These come from CONTRIBUTING.md and the README, and each one has already
cost someone time.

- **Chat history is server-side.** The client sends only the question and a
  session id; the server reads history from the conversation record. Never
  add a history field to the request, it reopens prompt injection.
- **Refuse rather than guess.** The grounding gate is `ground_question()` in
  `rag_chain.py`: best passage score, not the mean, against
  `SIMILARITY_THRESHOLD`, and on a follow-up both the rewrite and the question
  as typed must clear it (#189). Both routes and the evaluation runner call it;
  do not reimplement the check inline. Tune the threshold from `query_logs`
  (best_score on answered versus refused rows; `raw_best_score` marks a
  follow-up blocked on its own words), never from stub mode.
- **Bump `PROMPT_VERSION`** in `config.py` whenever the answer prompt
  changes, or cached answers keep serving the old prompt.
- **Changing a `*_TTL_SECONDS`** fails at startup on an existing database
  with `IndexOptionsConflict`. Drop the index or run `collMod` first.
- **Changing the embedding model** changes vector dimensions. Re-run
  ingestion and recreate the Atlas index.
- **No gunicorn `--preload`.** `MongoClient` is not fork-safe and the
  collection handles bind at import. `uvicorn --workers N` is fine.
- **`LLM_PROVIDER=fake` refuses to start under `APP_ENV=production`.** That
  is a misconfigured deploy, not a bug.
- **`THREADPOOL_TOKENS` was measured**, not guessed. Read
  `docs/load-testing.md` before changing it, and re-measure after.
- **Never commit** `.env`, a key, a bcrypt hash, or a real policy document.
  CI greps for the file names; it cannot catch a secret pasted into code.

## Where to look

| Change | File |
|---|---|
| a tuning knob | `sourcebook/rag/config.py` |
| the answer prompt | `sourcebook/rag/rag_chain.py` `ANSWER_SYSTEM_PROMPT`, then `PROMPT_VERSION` |
| retrieval or the grounding gate | `sourcebook/rag/rag_chain.py` |
| a model vendor | `sourcebook/rag/llm.py` |
| how a source format is parsed | `sourcebook/rag/documents.py` |
| an API endpoint | `sourcebook/api/routes/<area>.py`, mounted in `sourcebook/api/main.py` |
| a collection or index | `sourcebook/api/db.py` |
| the chat UI | `web/src/components/Chat/`, state in `web/src/hooks/useChat.ts` |
| the sample corpus | `data/sample-policies/`, then re-run ingestion |
| CI behaviour | `.github/workflows/ci.yml`; lint rules in `pyproject.toml` |
| accepted vulnerability advisories | `scripts/audit.sh` |

## Debugging

- `/docs` on the API is an OpenAPI console. Log in at `POST /api/auth/login`,
  click Authorize, paste the token.
- SSE by hand: `curl -N -X POST localhost:8000/api/chat/stream -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"question":"How much PTO do I get?"}'`
- Open escalations: `GET /api/escalations?status=open`, with a token from the HR password (`hr` under `make stub`). The web UI is the HR Requests page.
- What People Ask: `GET /api/reports/gaps`, with a token from the manager password (`manager` under `make stub`, filtered to questions asked in 3+ conversations) or the HR password (unfiltered).
- API logs go to stdout; in Compose, `docker compose logs -f api`.
