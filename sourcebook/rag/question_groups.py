"""Group query-log questions by meaning for the What People Ask page.

``question_hash`` groups rows whose condensed question is the same text after
``cache.normalize``. That is the right key for a cache and the wrong one for a
report: "How much PTO do I get?" and "How many vacation days do I have?" are
one question to Human Resources and two hashes to the log. This module merges
hash groups whose embeddings are close (issue #287).

## The pass

Wordings are taken in count order, most asked first. Each one joins the
existing group whose leader, its first and most asked wording, it matches at
``threshold`` cosine or above, the closest leader if several do. Otherwise it
leads a new group. Comparing against the leader only, never against the other
members, stops a chain of near neighbours from drifting into one group that
covers three topics.

The order and the tie-breaks are fixed, so the same log gives the same page.
A wording with no vector (no text was logged, or the provider could not embed
it) stays in a group of its own.

This is pure Python on purpose: the API image has no numpy. The worst case at
the report's cap is 200 wordings with no two alike, about 20,000 dot products
of 1,536 dimensions, which took 0.35 s on a laptop.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from operator import mul


@dataclass(frozen=True)
class Wording:
    """One ``question_hash`` group from the log: a single wording."""

    question_hash: str | None
    question: str | None
    count: int
    refused: int
    sessions: frozenset[str | None]


@dataclass(frozen=True)
class QuestionGroup:
    """Wordings judged to be one question. ``members[0]`` is the leader."""

    members: tuple[Wording, ...]

    @property
    def leader(self) -> Wording:
        return self.members[0]

    @property
    def count(self) -> int:
        return sum(member.count for member in self.members)

    @property
    def refused(self) -> int:
        return sum(member.refused for member in self.members)

    @property
    def conversations(self) -> int:
        """Distinct sessions across every wording. A session that asked two
        wordings counts once, which is the point of grouping them. A row
        logged without a session contributes ``None``, so every such row in a
        group counts as one conversation between them; chat requests always
        log a session, so only hand-written rows hit this."""
        return len(frozenset().union(*(member.sessions for member in self.members)))


def _unit(vector: Sequence[float]) -> tuple[float, ...] | None:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return None
    return tuple(value / norm for value in vector)


def _rank(wordings: Sequence[Wording]) -> list[Wording]:
    return sorted(wordings, key=lambda w: (-w.count, w.question_hash or ""))


def exact_groups(wordings: Sequence[Wording]) -> list[QuestionGroup]:
    """One group per wording, the report's behaviour before #287."""
    return [QuestionGroup((wording,)) for wording in _rank(wordings)]


def group_by_meaning(
    wordings: Sequence[Wording],
    vectors: Mapping[str, Sequence[float]],
    threshold: float,
) -> list[QuestionGroup]:
    """Merge wordings whose question text embeds within ``threshold`` cosine.

    ``vectors`` is keyed by question text. Groups come back in the order their
    leaders were ranked; callers re-rank by whatever the list sorts on.
    """
    members: list[list[Wording]] = []
    leaders: list[tuple[float, ...] | None] = []
    for wording in _rank(wordings):
        vector = vectors.get(wording.question) if wording.question else None
        unit = _unit(vector) if vector else None
        best, best_score = None, threshold
        if unit is not None:
            for index, leader in enumerate(leaders):
                if leader is None or len(leader) != len(unit):
                    continue
                score = sum(map(mul, unit, leader))
                # Inclusive at the threshold; on a tie the earlier, more asked
                # leader keeps the wording.
                if score > best_score or (best is None and score == threshold):
                    best, best_score = index, score
        if best is None:
            members.append([wording])
            leaders.append(unit)
        else:
            members[best].append(wording)
    return [QuestionGroup(tuple(group)) for group in members]
