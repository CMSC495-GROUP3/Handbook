"""Load-test server: the real application with its external services stubbed.

Run it:

    ./.venv/bin/uvicorn scripts.loadtest.server:app --port 8001
    ./.venv/bin/uvicorn scripts.loadtest.server:app --port 8001 --workers 4

## What this measures, and what it does not

It measures the **concurrency architecture** — how many simultaneous SSE
streams one process can serve, and what happens to latency past that point.
That is the property the async conversion changes, and it is reproducible on a
laptop with no cloud account.

It does **not** measure end-to-end production latency. Stubbed out:

- **The model.** `LLM_PROVIDER=fake` generates a canned answer at a configurable
  per-token delay, so a request occupies a worker for a realistic duration
  without any spend. Real OpenAI latency has a long tail this does not
  reproduce.
- **MongoDB.** Replaced with an in-memory dict plus a fixed simulated latency.
  Real Atlas round-trips vary and would themselves consume threads.
- **Atlas Vector Search.** Replaced with canned passages. `$vectorSearch` is an
  Atlas-only aggregation stage and cannot run locally at all.

The stubs live in this file rather than behind flags in `sourcebook/` so that no
test-only branch can ever be reached in production.

## Reading the gate

Fake embeddings are meaningless, so a similarity score computed from them is
noise. Rather than fake the gate, bracket it — run the whole test twice:

    SIMILARITY_THRESHOLD=0.0   every request generates      (worst case)
    SIMILARITY_THRESHOLD=1.0   every request refuses        (best case)

Real traffic sits between the two, weighted by the actual refusal rate.
"""

import os
import time

import bcrypt

# This entrypoint deliberately disables the application's rate limiter below.
# Refuse any environment that could select a real provider before mutating the
# environment or importing the production application.
if os.getenv("APP_ENV", "").strip().casefold() == "production":
    raise RuntimeError("The load-test stub cannot run with APP_ENV=production")

_inherited_provider = os.getenv("LLM_PROVIDER", "fake").strip().casefold()
if _inherited_provider != "fake":
    raise RuntimeError("The load-test stub requires LLM_PROVIDER=fake")

# Must be set before importing main, which validates them at import.
os.environ.setdefault("JWT_SECRET_KEY", "loadtest-secret-not-for-real-use")
os.environ.setdefault("MONGODB_URI", "mongodb://stubbed-never-contacted")
# main also checks that this is a bcrypt hash. `make stub` sets a real one;
# run.py logs in with password "loadtest", so the hash must match that word.
os.environ.setdefault("APP_PASSWORD_HASH", bcrypt.hashpw(b"loadtest", bcrypt.gensalt(4)).decode())
# "loadtest-hr" opens both restricted pages, and "loadtest-manager" What People
# Ask, when the stub is run without make.
os.environ.setdefault("HR_PASSWORD_HASH", bcrypt.hashpw(b"loadtest-hr", bcrypt.gensalt(4)).decode())
os.environ.setdefault(
    "MANAGER_PASSWORD_HASH", bcrypt.hashpw(b"loadtest-manager", bcrypt.gensalt(4)).decode()
)
os.environ["LLM_PROVIDER"] = "fake"
os.environ.pop("APP_ENV", None)  # FakeProvider refuses to run as production

# Simulated database round-trip. Real Atlas is slower and more variable; this
# at least stops the stub from being free.
DB_LATENCY_MS = int(os.getenv("FAKE_DB_LATENCY_MS", "15"))

# Score attached to every canned passage. Compared against SIMILARITY_THRESHOLD
# by the real, unmodified grounding gate.
PASSAGE_SCORE = float(os.getenv("FAKE_PASSAGE_SCORE", "0.78"))

CANNED_PASSAGES = [
    {
        "source": "documents/pto-policy.md",
        "doc_id": "pto-policy",
        "title": "Paid Time Off (PTO) Policy",
        "category": "Time Off & Leave",
        "effective_date": "2026-01-01",
        "chunk_index": i,
        "score": PASSAGE_SCORE - (i * 0.01),
        "text": (
            "Full-time employees accrue paid time off each pay period based on "
            "length of service. Employees with up to two years of service accrue "
            "15 days per year, rising to 20 days from year three and 25 days from "
            "year six. Accrual begins on the first day of employment and there is "
            "no waiting period before accrued time may be used. " * 2
        ),
    }
    for i in range(5)
]


def _sleep_db() -> None:
    if DB_LATENCY_MS > 0:
        time.sleep(DB_LATENCY_MS / 1000)


class LatentCollection:
    """Wraps a FakeCollection to add a simulated database round-trip.

    Without this the stub is free, which would understate how much thread-time
    a real request spends waiting on Atlas.
    """

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def timed(*args, **kwargs):
            _sleep_db()
            return attr(*args, **kwargs)

        return timed


def _fake_retrieve(query: str, k: int = 5) -> list[dict]:
    """Stand in for Atlas Vector Search, at roughly its latency."""
    _sleep_db()
    return [dict(p) for p in CANNED_PASSAGES[:k]]


# Route every collection through the in-memory fake before importing the app,
# so db.py's module-level handles bind to fakes rather than to a real cluster.
from scripts.loadtest.fakemongo import FakeDB  # noqa: E402
from sourcebook.rag import mongo  # noqa: E402

_FAKE_DB = FakeDB()
mongo.get_db = lambda: _FAKE_DB
mongo.get_collection = lambda name: LatentCollection(_FAKE_DB[name])

# The canned passages also live in the passages collection, so the Policy
# Library has one document to list under `make stub`. Retrieval never reads
# them (it is replaced below); only /api/documents does.
from sourcebook.rag.config import (  # noqa: E402
    DOCUMENT_BODIES_COLLECTION,
    PASSAGES_COLLECTION,
)

_FAKE_DB[PASSAGES_COLLECTION].insert_many(
    [{**p, "owner": "Human Resources"} for p in CANNED_PASSAGES]
)
# The same document whole, so opening it in the library renders real markdown.
_FAKE_DB[DOCUMENT_BODIES_COLLECTION].insert_one(
    {
        **{
            k: v for k, v in CANNED_PASSAGES[0].items() if k not in ("chunk_index", "score", "text")
        },
        "owner": "Human Resources",
        "body": (
            "## Accrual\n\n"
            "Full-time employees accrue paid time off each pay period based on length "
            "of service:\n\n"
            "| Years of service | Annual accrual |\n"
            "|------------------|----------------|\n"
            "| 0 through 2      | 15 days        |\n"
            "| 3 through 5      | 20 days        |\n"
            "| 6 or more        | 25 days        |\n\n"
            "Part-time employees accrue on a **prorated** basis.\n\n"
            "Accrual begins on the first day of employment and there is no waiting "
            "period before accrued time may be used.\n\n"
            "## Requesting time off\n\n"
            "Submit requests through the HR portal at least two weeks ahead for "
            "absences of three days or more."
        ),
    }
)

from sourcebook.rag import cache  # noqa: E402

cache.get_collection = mongo.get_collection

from sourcebook.api import main  # noqa: E402
from sourcebook.api.limiter import limiter  # noqa: E402
from sourcebook.rag import rag_chain  # noqa: E402


def _startup() -> None:
    """Replaces ensure_indexes in the lifespan.

    Index creation would try to reach a real cluster. This also doubles as the
    hook for resizing the thread pool, because lifespan runs inside the event
    loop and `current_default_thread_limiter()` raises outside one.
    """
    tokens = int(os.getenv("LOADTEST_THREAD_TOKENS", "0"))
    if tokens > 0:
        import anyio.to_thread

        anyio.to_thread.current_default_thread_limiter().total_tokens = tokens


# Index creation would try to reach a real cluster during startup.
main.ensure_indexes = _startup

# Vector search is the one thing the fake cannot emulate, so it is replaced
# outright, on rag_chain: ground_question there is the only caller.
rag_chain.retrieve_passages = _fake_retrieve

# The load-test client fires every request from 127.0.0.1. Leave production
# CHAT_RATE_LIMIT / REINDEX_RATE_LIMIT intact; only this synthetic stub opts out,
# the same way tests/conftest.py disables the limiter for unit tests.
limiter.enabled = False

app = main.app
