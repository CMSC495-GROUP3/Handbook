"""Model provider interface.

Vendor lock-in mitigation from the proposal: every model call in this codebase
goes through the LLMProvider interface below, so swapping OpenAI for a
self-hosted model means writing one new subclass and changing one environment
variable. No module outside this file names a vendor or a model.

Two logical roles are exposed instead of concrete model names:

    "answer"  — the grounded response shown to the user. Quality matters most.
    "utility" — cheap internal calls (query rewriting, follow-up suggestions).
                A smaller, faster model is appropriate here.

A provider maps those roles onto whatever models it actually has.
"""

import hashlib
import math
import os
import random
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from sourcebook.rag.config import (
    ESCALATION_CONTACT,
    OPENAI_CAPACITY_WAIT_SECONDS,
    OPENAI_MAX_CONCURRENT_REQUESTS,
    OPENAI_MAX_RETRIES,
    OPENAI_STREAM_DEADLINE_SECONDS,
    OPENAI_TIMEOUT_SECONDS,
)

ModelRole = Literal["answer", "utility"]

Message = dict  # {"role": "system" | "user" | "assistant", "content": str}


class ProviderBusyError(Exception):
    """The provider could not take another request within the capacity wait.

    An expected, short-lived condition, not a generation failure: the chat
    routes answer it with HTTP 503 and Retry-After so a client can try again,
    and they keep the generic error path for anything unexpected. Deliberately
    not a RuntimeError, so an `except RuntimeError` cannot swallow it by
    accident.
    """


def _reraise_transient_openai(exc: BaseException) -> None:
    """Turn OpenAI timeouts, drops, 429s, and 5xx into ``TimeoutError``.

    The coverage judge re-raises ``TimeoutError`` so a blip is not cached as
    ``refused=True``. Terminal 4xx (auth, permission, bad request) are left
    alone. Other modules never import a vendor; this helper is the only place
    those SDK types are named. No-op when openai is not installed or the error
    is something else.
    """
    try:
        import openai
    except ImportError:
        return
    if isinstance(
        exc,
        (
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        ),
    ):
        raise TimeoutError(
            "OpenAI request timed out, dropped, was rate-limited, or returned a transient 5xx"
        ) from exc


class LLMProvider(ABC):
    """The contract every provider must satisfy.

    Implement all four members to add a provider. Nothing else in the codebase
    needs to change.
    """

    name: str

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text.

        The dimensionality must match the Atlas Vector Search index. Changing
        providers therefore means re-embedding the corpus and rebuilding the
        index — see the migration note in the README.
        """

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for multiple texts in input order."""
        return [self.embed(text) for text in texts]

    @abstractmethod
    def embedding_dimensions(self) -> int:
        """Vector length this provider's embedding model produces."""

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        *,
        role: ModelRole = "utility",
        temperature: float = 0.0,
    ) -> str:
        """Return a complete response as a single string."""

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        *,
        role: ModelRole = "answer",
        temperature: float = 0.0,
    ) -> Iterator[str]:
        """Yield response text incrementally, one delta at a time."""

    # ── Cache fingerprints ────────────────────────────────────────────────────
    # Cache keys must change when the underlying model changes, or a model swap
    # would serve results produced by the previous one. These exist so that
    # cache code never has to know a model name — that stays in this file.
    #
    # Both have working defaults, so adding a provider does not require writing
    # them. Override when a provider can be configured with different models.

    def embedding_fingerprint(self) -> str:
        """Identifies the embedding model, for the embedding cache key."""
        return self.name

    def answer_fingerprint(self) -> str:
        """Identifies the answer model, for the answer cache key."""
        return self.name

    def utility_fingerprint(self) -> str:
        """Identifies the utility/coverage model, for the answer cache key."""
        return self.name


class OpenAIProvider(LLMProvider):
    """OpenAI-backed implementation — the default for the pilot."""

    name = "openai"

    # Model choice lives here and nowhere else. Overridable so the models can be
    # changed without touching code.
    ANSWER_MODEL = os.getenv("OPENAI_ANSWER_MODEL", "gpt-4o")
    UTILITY_MODEL = os.getenv("OPENAI_UTILITY_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSIONS = int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536"))

    def __init__(self) -> None:
        # Lazy: FakeProvider must import this module without openai installed
        # (Docker smoke with LLM_PROVIDER=fake). Timeout comes from the SDK, not
        # from httpx directly: openai 3.x depends on httpx2, so the api image has
        # no module named httpx and a bare import fails on the first chat.
        from openai import OpenAI, Timeout

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai. "
                "Set it in .env — see .env.example."
            )
        # read bounds idle time between streamed chunks; connect stays short so
        # a black-holed DNS or TCP handshake fails fast rather than eating a
        # THREADPOOL_TOKENS slot for the full read timeout.
        self._client = OpenAI(
            api_key=api_key,
            timeout=Timeout(
                connect=5.0,
                read=OPENAI_TIMEOUT_SECONDS,
                write=OPENAI_TIMEOUT_SECONDS,
                pool=5.0,
            ),
            max_retries=OPENAI_MAX_RETRIES,
        )
        if OPENAI_MAX_CONCURRENT_REQUESTS < 1:
            raise RuntimeError("OPENAI_MAX_CONCURRENT_REQUESTS must be at least 1")
        self._capacity = threading.BoundedSemaphore(OPENAI_MAX_CONCURRENT_REQUESTS)

    @contextmanager
    def _request_slot(self):
        """Bound provider occupancy without tying up the whole app thread pool."""
        acquired = self._capacity.acquire(timeout=OPENAI_CAPACITY_WAIT_SECONDS)
        if not acquired:
            raise ProviderBusyError("OpenAI provider is at its configured concurrency limit")
        try:
            yield
        finally:
            self._capacity.release()

    def _model_for(self, role: ModelRole) -> str:
        return self.ANSWER_MODEL if role == "answer" else self.UTILITY_MODEL

    def embedding_fingerprint(self) -> str:
        return f"{self.name}:{self.EMBEDDING_MODEL}"

    def answer_fingerprint(self) -> str:
        return f"{self.name}:{self.ANSWER_MODEL}"

    def utility_fingerprint(self) -> str:
        return f"{self.name}:{self.UTILITY_MODEL}"

    def embed(self, text: str) -> list[float]:
        with self._request_slot():
            response = self._client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text,
            )
        return response.data[0].embedding

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """One request per document's chunks. A document is a few dozen chunks,
        far below the API's 2048-input and per-request token limits; a whole
        corpus in one call would not be, so keep batches per document."""
        if not texts:
            return []

        with self._request_slot():
            response = self._client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=texts,
            )

        # Each item carries the index of its input. The docs say the list is
        # already in input order; sorting makes the upsert independent of that.
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    def embedding_dimensions(self) -> int:
        return self.EMBEDDING_DIMENSIONS

    def complete(
        self,
        messages: list[Message],
        *,
        role: ModelRole = "utility",
        temperature: float = 0.0,
    ) -> str:
        try:
            with self._request_slot():
                response = self._client.chat.completions.create(
                    model=self._model_for(role),
                    messages=messages,
                    temperature=temperature,
                )
        except ProviderBusyError:
            raise
        except Exception as exc:
            _reraise_transient_openai(exc)
            raise
        return response.choices[0].message.content or ""

    def stream(
        self,
        messages: list[Message],
        *,
        role: ModelRole = "answer",
        temperature: float = 0.0,
    ) -> Iterator[str]:
        with self._request_slot():
            stream = self._client.chat.completions.create(
                model=self._model_for(role),
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            deadline = time.monotonic() + OPENAI_STREAM_DEADLINE_SECONDS
            try:
                for chunk in stream:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("OpenAI stream exceeded its configured deadline")
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            finally:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()


class FakeProvider(LLMProvider):
    """Deterministic offline provider. No network, no API key, no cost.

    Exists so the application can be run, tested, and load-tested without
    spending money or depending on OpenAI availability. Delays are configurable
    so a fake generation takes roughly as long as a real one — which is what
    makes it useful for measuring concurrency, where the thing that matters is
    how long a request occupies a worker, not what it says.

    The embeddings are deterministic but meaningless: two texts that are
    semantically identical will not land near each other. Any similarity score
    computed from them is noise, so do not use this provider to evaluate
    retrieval quality or to tune SIMILARITY_THRESHOLD.
    """

    name = "fake"

    STREAM_DELAY_MS = int(os.getenv("FAKE_STREAM_DELAY_MS", "20"))
    UTILITY_DELAY_MS = int(os.getenv("FAKE_UTILITY_DELAY_MS", "300"))
    EMBED_DELAY_MS = int(os.getenv("FAKE_EMBED_DELAY_MS", "50"))
    DIMENSIONS = int(os.getenv("FAKE_EMBED_DIMENSIONS", "1536"))
    # FAKE_COVERED=0 makes the stub's coverage judge refuse every question.
    COVERED = os.getenv("FAKE_COVERED", "1") != "0"

    ANSWER = (
        "Based on the policy documents provided, full-time employees accrue 15 days "
        "of paid time off per year for the first two years of service, rising to 20 "
        "days from year three and 25 days from year six. Accrual begins on your first "
        "day and there is no waiting period before you may use it. You may carry a "
        "maximum of 10 unused days into the following calendar year; anything above "
        "that is forfeited on December 31. This is drawn from the Paid Time Off (PTO) "
        "Policy, effective 2026-01-01. For absences longer than five consecutive "
        f"business days you will also need approval from {ESCALATION_CONTACT}."
    )

    def __init__(self) -> None:
        if os.getenv("APP_ENV", "").lower() == "production":
            raise RuntimeError(
                "LLM_PROVIDER=fake refuses to start with APP_ENV=production. "
                "A fake provider silently answering real policy questions would be "
                "worse than an outage."
            )

    @staticmethod
    def _sleep(milliseconds: int) -> None:
        if milliseconds > 0:
            time.sleep(milliseconds / 1000)

    def embed(self, text: str) -> list[float]:
        self._sleep(self.EMBED_DELAY_MS)
        return self._vector(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """One delay for the batch: the OpenAI provider makes one request, not N."""
        if not texts:
            return []
        self._sleep(self.EMBED_DELAY_MS)
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        # Deterministic pseudo-random unit vector seeded by the text, so repeated
        # calls agree with each other and runs are reproducible.
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = random.Random(seed)
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self.DIMENSIONS)]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embedding_dimensions(self) -> int:
        return self.DIMENSIONS

    def complete(
        self,
        messages: list[Message],
        *,
        role: ModelRole = "utility",
        temperature: float = 0.0,
    ) -> str:
        if role == "answer":
            self._sleep(self.STREAM_DELAY_MS * len(self.ANSWER.split()))
            return self.ANSWER
        self._sleep(self.UTILITY_DELAY_MS)
        system = next(
            (
                str(message.get("content", ""))
                for message in messages
                if message.get("role") == "system"
            ),
            "",
        )
        # Stub mode has no real coverage judge. Identify the call by the
        # system-prompt identity, not by JSON literals in the user message, so
        # ordinary utility prompts that mention those strings still rewrite.
        if system.startswith("You are a coverage judge"):
            return '{"covered": true}' if self.COVERED else '{"covered": false}'
        # Utility calls ask for three newline-separated questions.
        return (
            "How do I request time off?\n"
            "What happens to unused days when I leave?\n"
            "Do company holidays count against my balance?"
        )

    def stream(
        self,
        messages: list[Message],
        *,
        role: ModelRole = "answer",
        temperature: float = 0.0,
    ) -> Iterator[str]:
        for index, word in enumerate(self.ANSWER.split()):
            self._sleep(self.STREAM_DELAY_MS)
            yield word if index == 0 else f" {word}"


# Register new providers here. The key is the LLM_PROVIDER environment value.
_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "fake": FakeProvider,
}

_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the configured provider, constructing it once per process.

    Construction is lazy so that importing this module never requires
    credentials — useful for tests and for tooling that only needs the config.
    """
    global _instance
    if _instance is not None:
        return _instance

    key = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    provider_cls = _PROVIDERS.get(key)
    if provider_cls is None:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER {key!r}. Available: {', '.join(sorted(_PROVIDERS))}. "
            f"To add one, subclass LLMProvider in sourcebook/rag/llm.py and register it in _PROVIDERS."
        )

    _instance = provider_cls()
    return _instance
