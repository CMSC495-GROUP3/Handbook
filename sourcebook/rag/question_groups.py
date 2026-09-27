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

Cosine alone cannot tell a paraphrase from a near neighbour: on the labelled
pairs they overlap from 0.47 to 0.83 (docs/evaluation.md). So a second rule
covers the band below ``threshold`` (issue #293). A pair scoring at or above
``floor`` but below ``threshold`` matches only if it is in ``same``, the pairs
the utility model confirmed as one question. ``candidate_pairs`` lists the
pairs in that band for the caller to judge.

The order and the tie-breaks are fixed, so the same log and the same verdicts
give the same page. A wording with no vector (no text was logged, or the
provider could not embed it) stays in a group of its own.

This is pure Python on purpose: the API image has no numpy. The worst case at
the report's cap is 200 wordings with no two alike, about 20,000 dot products
of 1,536 dimensions, which took 0.35 s on a laptop.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
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
    # Exact distinct sessions. ``sessions`` may be a sample of them (#291).
    session_count: int = 0


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
        log a session, so only hand-written rows hit this.

        The route reads ``sessions`` only for wordings at or under
        ``ROLLUP_SESSION_SAMPLE`` conversations (#291), so past that the union
        undercounts. Each wording's exact
        ``session_count`` is then the floor: exact below the cap, a lower
        bound above it."""
        union = len(frozenset().union(*(member.sessions for member in self.members)))
        return max(union, *(member.session_count for member in self.members))


def _unit(vector: Sequence[float]) -> tuple[float, ...] | None:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return None
    return tuple(value / norm for value in vector)


def _units(
    ranked: Sequence[Wording], vectors: Mapping[str, Sequence[float]]
) -> list[tuple[float, ...] | None]:
    """Each wording's unit vector, or None when it has no usable one."""
    units = []
    for wording in ranked:
        vector = vectors.get(wording.question) if wording.question else None
        units.append(_unit(vector) if vector else None)
    return units


def _cosine(a: tuple[float, ...] | None, b: tuple[float, ...] | None) -> float | None:
    if a is None or b is None or len(a) != len(b):
        return None
    return sum(map(mul, a, b))


def pair_key(a: str, b: str) -> tuple[str, str]:
    """One key per unordered pair of question texts."""
    return (a, b) if a <= b else (b, a)


def _rank(wordings: Sequence[Wording]) -> list[Wording]:
    return sorted(wordings, key=lambda w: (-w.count, w.question_hash or ""))


def exact_groups(wordings: Sequence[Wording]) -> list[QuestionGroup]:
    """One group per wording, the report's behaviour before #287."""
    return [QuestionGroup((wording,)) for wording in _rank(wordings)]


def candidate_pairs(
    wordings: Sequence[Wording],
    vectors: Mapping[str, Sequence[float]],
    floor: float,
    threshold: float,
) -> dict[tuple[str, str], float]:
    """Every pair of texts scoring at or above ``floor`` and below ``threshold``.

    Keyed by ``pair_key``, valued by cosine. This checks every pair, not only
    pairs with a leader, because who leads depends on the verdicts. At the
    report's cap of 200 wordings that is 19,900 dot products.
    """
    ranked = [w for w in _rank(wordings) if w.question]
    units = _units(ranked, vectors)
    pairs: dict[tuple[str, str], float] = {}
    for i, first in enumerate(ranked):
        for j in range(i + 1, len(ranked)):
            score = _cosine(units[i], units[j])
            if score is not None and floor <= score < threshold:
                pairs[pair_key(first.question, ranked[j].question)] = score
    return pairs


def group_by_meaning(
    wordings: Sequence[Wording],
    vectors: Mapping[str, Sequence[float]],
    threshold: float,
    *,
    floor: float | None = None,
    same: Collection[tuple[str, str]] = (),
) -> list[QuestionGroup]:
    """Merge wordings whose question text embeds within ``threshold`` cosine,
    or within ``floor`` when ``same`` holds the pair.

    ``vectors`` is keyed by question text and ``same`` by ``pair_key``. Groups
    come back in the order their leaders were ranked; callers re-rank by
    whatever the list sorts on.
    """

    def matches(score: float, a: str, b: str) -> bool:
        if score >= threshold:
            return True
        return floor is not None and score >= floor and pair_key(a, b) in same

    ranked = _rank(wordings)
    units = _units(ranked, vectors)
    members: list[list[Wording]] = []
    leaders: list[int] = []
    for position, wording in enumerate(ranked):
        best, best_score = None, -math.inf
        for index, leader in enumerate(leaders):
            score = _cosine(units[position], units[leader])
            if score is None or not matches(
                score, wording.question or "", ranked[leader].question or ""
            ):
                continue
            # The closest leader wins; on a tie the earlier, more asked one
            # keeps the wording.
            if score > best_score:
                best, best_score = index, score
        if best is None:
            members.append([wording])
            leaders.append(position)
        else:
            members[best].append(wording)
    return [QuestionGroup(tuple(group)) for group in members]
