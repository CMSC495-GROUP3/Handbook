"""scripts/measure_question_groups.py --judge, with the OpenAI client faked."""

import json
import re
from types import SimpleNamespace

from scripts import measure_question_groups as measure


def _pair(pair_id: str, label: str, cosine: float) -> dict:
    return {
        "id": pair_id,
        "label": label,
        "a": f"{pair_id} a",
        "b": f"{pair_id} b",
        "cosine": cosine,
    }


SCORED = [
    _pair("close", "same", 0.80),
    _pair("mid", "different", 0.70),
    _pair("edge", "same", 0.62),
    _pair("low", "same", 0.50),
    _pair("above", "same", 0.90),
]


def fake_openai(monkeypatch, answer):
    """Serve chat calls with ``answer(ids in the batch)``; return the batches."""
    batches: list[list[str]] = []

    def create(*, messages, **_kwargs):
        texts = re.findall(r'^\d+\. A: (".*")$', messages[1]["content"], re.M)
        ids = [json.loads(text).removesuffix(" a") for text in texts]
        batches.append(ids)
        content = json.dumps({"same": answer(ids)})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(measure, "OpenAI", lambda: client)
    monkeypatch.setattr(measure, "QUESTION_JUDGE_MAX_PAIRS", 2)
    monkeypatch.setattr(measure, "FLOORS", [0.45, 0.60])
    return batches


def test_each_floor_is_judged_in_the_batches_the_page_would_send(monkeypatch):
    batches = fake_openai(monkeypatch, lambda ids: [True] * len(ids))

    measure.judge_floors(SCORED)

    # Closest first, two per call, and only that floor's band.
    assert batches == [["close", "mid"], ["edge", "low"], ["close", "mid"], ["edge"]]


def test_each_floor_is_scored_with_its_own_verdicts(monkeypatch):
    # A pair judged alone says "same"; with a neighbour it says "different".
    # At 0.45 "edge" shares a batch with "low", at 0.60 it is alone.
    batches = fake_openai(monkeypatch, lambda ids: [len(ids) == 1] * len(ids))

    low, default = measure.judge_floors(SCORED)

    assert len(batches) == 4
    assert (low["floor"], low["judged"], low["verdicts"]["edge"]) == (0.45, 4, False)
    assert (default["floor"], default["judged"], default["verdicts"]["edge"]) == (0.60, 3, True)
    # "above" merges on cosine alone at every floor; "edge" only where confirmed.
    assert (low["paraphrases_merged"], default["paraphrases_merged"]) == (1, 2)
    assert (low["false_merges"], default["false_merges"]) == (0, 0)


def test_an_unparsed_batch_counts_as_different(monkeypatch):
    fake_openai(monkeypatch, lambda ids: [True] * (len(ids) + 1))

    low, default = measure.judge_floors(SCORED)

    assert (low["unparsed"], default["unparsed"]) == (4, 3)
    assert (low["paraphrases_merged"], default["paraphrases_merged"]) == (1, 1)
