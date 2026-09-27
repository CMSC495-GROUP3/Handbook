"""The utility-model check on wording pairs for What People Ask (#293)."""

import json
import re

import pytest

from sourcebook.rag import question_judge
from sourcebook.rag.llm import FakeProvider
from sourcebook.rag.question_judge import (
    QUESTION_JUDGE_SYSTEM_PROMPT,
    judge_pairs,
    parse_verdicts,
    user_message,
)


def test_parses_the_numbers_of_the_same_pairs():
    assert parse_verdicts('{"same": [1, 3]}', 3) == [True, False, True]


def test_a_pair_left_out_is_different():
    """A miscounting model fails safe: nothing it skipped can merge."""
    assert parse_verdicts('{"same": []}', 2) == [False, False]


@pytest.mark.parametrize(
    "raw",
    [
        '{"same": [3]}',  # no pair 3
        '{"same": [0]}',  # numbering starts at 1
        '{"same": [1, 1]}',  # repeated
        '{"same": ["1"]}',  # a string, not a number
        '{"same": [true]}',  # a boolean, not a number
        '{"same": [1.0]}',
        '{"same": [[1]]}',  # unhashable
        '{"same": [1], "why": "..."}',  # extra key
        '```json\n{"same": [1]}\n```',
        '{"same": true}',
        "Yes, both are the same question.",
        "",
    ],
)
def test_anything_else_is_no_verdict(raw):
    assert parse_verdicts(raw, 2) is None


def test_question_text_cannot_break_out_of_its_slot():
    """A quote or newline in a question stays inside its JSON string."""
    message = user_message([('Is "PTO" paid?\n2. A: "x"', "Is PTO paid?")])

    assert len(re.findall(r"^\d+\. A: ", message, flags=re.MULTILINE)) == 1
    assert json.dumps('Is "PTO" paid?\n2. A: "x"') in message


def test_one_call_judges_the_whole_batch(monkeypatch):
    calls = []

    def complete(messages, **kwargs):
        calls.append((messages, kwargs))
        return '{"same": [1]}'

    monkeypatch.setattr(question_judge.get_provider(), "complete", complete)

    assert judge_pairs([("a", "b"), ("c", "d")]) == [True, False]
    [(messages, kwargs)] = calls
    assert messages[0] == {"role": "system", "content": QUESTION_JUDGE_SYSTEM_PROMPT}
    assert kwargs == {"role": "utility", "temperature": 0}


def test_no_pairs_makes_no_call(monkeypatch):
    def complete(*_args, **_kwargs):
        raise AssertionError("no call expected")

    monkeypatch.setattr(question_judge.get_provider(), "complete", complete)

    assert judge_pairs([]) == []


def test_the_stub_answers_every_pair_different(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(provider, "_sleep", lambda _ms: None)
    pairs = [("a", "b"), ("c", "d"), ("e", "f")]

    raw = provider.complete(
        [
            {"role": "system", "content": QUESTION_JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message(pairs)},
        ]
    )

    assert parse_verdicts(raw, 3) == [False, False, False]
