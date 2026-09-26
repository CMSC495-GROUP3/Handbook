"""The coverage report behind the What People Ask page."""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from conftest import FAKE_DB, make_passages
from pymongo.errors import ExecutionTimeout

from scripts.loadtest.fakemongo import FakeCollection
from sourcebook.api.routes import reports
from sourcebook.api.routes.reports import MAX_WINDOW_DAYS

URL = "/api/reports/gaps"
# Each logged row is its own conversation unless a test passes session_id.
_SESSIONS = itertools.count(1)


@pytest.fixture(autouse=True)
def full_ttl(monkeypatch):
    """Tests below assume the default 90-day log TTL, whatever the environment sets."""
    monkeypatch.setattr(reports, "TTL_DAYS", MAX_WINDOW_DAYS)


def log(question: str, *, refused: bool, age: timedelta = timedelta(hours=1), **fields) -> None:
    """One query_logs row, shaped like analytics.log_query writes it."""
    FAKE_DB["query_logs"].insert_one(
        {
            "created_at": datetime.now(UTC) - age,
            "question_raw": question,
            "question_condensed": question,
            "question_hash": question.lower(),
            "refused": refused,
            "session_id": f"session-{next(_SESSIONS)}",
            **fields,
        }
    )


def test_requires_a_token(client):
    assert client.get(URL).status_code in (401, 403)


def test_empty_log(client, auth):
    body = client.get(URL, headers=auth).json()
    assert body["days"] == 30
    assert (body["total"], body["refused"]) == (0, 0)
    assert body["gaps"] == []
    assert body["faq"] == []


def test_refused_questions_rank_by_count(client, auth):
    for _ in range(3):
        log("Can I bring my dog?", refused=True)
    log("Is there a sabbatical?", refused=True)
    log("How much PTO do I get?", refused=False)

    body = client.get(URL, headers=auth).json()

    assert (body["total"], body["refused"]) == (5, 4)
    assert [(g["question"], g["count"], g["conversations"]) for g in body["gaps"]] == [
        ("Can I bring my dog?", 3, 3),
        ("Is there a sabbatical?", 1, 1),
    ]


def test_faq_counts_repeats_and_their_refusals(client, auth):
    log("How much PTO do I get?", refused=False)
    log("How much PTO do I get?", refused=True)
    log("Asked once", refused=False)

    faq = client.get(URL, headers=auth).json()["faq"]

    assert faq == [
        {
            "question_hash": "how much pto do i get?",
            "question": "How much PTO do I get?",
            "count": 2,
            "conversations": 2,
            "refused": 1,
        }
    ]


def test_one_conversation_repeating_itself_is_not_a_faq(client, auth):
    """Three asks from one conversation say nothing about how many people
    share the question; two conversations asking once each do."""
    for _ in range(3):
        log("Repeated by one person", refused=False, session_id="alone")
    log("Asked by two people", refused=False)
    log("Asked by two people", refused=False)

    faq = client.get(URL, headers=auth).json()["faq"]

    assert [(g["question"], g["count"], g["conversations"]) for g in faq] == [
        ("Asked by two people", 2, 2),
    ]


def test_faq_ranks_on_conversations_before_asks(client, auth):
    for _ in range(5):
        log("Many asks, few people", refused=False, session_id="one")
    log("Many asks, few people", refused=False, session_id="two")
    for _ in range(3):
        log("Fewer asks, more people", refused=False)

    faq = client.get(URL, headers=auth).json()["faq"]

    assert [(g["question"], g["count"], g["conversations"]) for g in faq] == [
        ("Fewer asks, more people", 3, 3),
        ("Many asks, few people", 6, 2),
    ]


def test_gaps_rank_on_asks_and_count_conversations(client, auth):
    """Every refusal is a gap, even one person's, so the gaps list keeps asks."""
    for _ in range(4):
        log("One person, four tries", refused=True, session_id="stuck")
    log("Two people", refused=True)
    log("Two people", refused=True)

    gaps = client.get(URL, headers=auth).json()["gaps"]

    assert [(g["question"], g["count"], g["conversations"]) for g in gaps] == [
        ("One person, four tries", 4, 1),
        ("Two people", 2, 2),
    ]


def test_rows_outside_the_window_are_left_out(client, auth):
    log("Last week", refused=True, age=timedelta(days=6))
    log("Last month", refused=True, age=timedelta(days=20))

    body = client.get(URL, params={"days": 7}, headers=auth).json()

    assert body["days"] == 7
    assert [g["question"] for g in body["gaps"]] == ["Last week"]
    assert body["total"] == 1


def test_prefers_the_condensed_question(client, auth):
    """The hash groups on the condensed rewrite, so a follow-up's raw text
    ("what about part-time?") would misname the group."""
    log(
        "what about part-time?",
        refused=True,
        question_condensed="Do part-time employees get PTO?",
    )
    log("", refused=True, question_condensed=None, question_hash="blank")

    gaps = client.get(URL, headers=auth).json()["gaps"]

    assert {g["question"] for g in gaps} == {"Do part-time employees get PTO?", None}


def test_top_caps_each_list(client, auth):
    for n in range(5):
        log(f"Question {n}", refused=True)

    gaps = client.get(URL, params={"top": 2}, headers=auth).json()["gaps"]

    assert len(gaps) == 2


def test_a_window_longer_than_the_log_ttl_is_shortened(client, auth, monkeypatch):
    """A short QUERY_LOG_TTL_SECONDS must not turn the default request into a 422."""
    monkeypatch.setattr(reports, "TTL_DAYS", 7)
    log("Inside the TTL", refused=True, age=timedelta(days=3))
    log("Past the TTL", refused=True, age=timedelta(days=20))

    response = client.get(URL, params={"days": 90}, headers=auth)

    assert response.status_code == 200
    assert response.json()["days"] == 7
    assert [g["question"] for g in response.json()["gaps"]] == ["Inside the TTL"]


@pytest.mark.parametrize(
    "params",
    [{"days": 0}, {"days": MAX_WINDOW_DAYS + 1}, {"top": 0}, {"top": 101}, {"days": "a"}],
)
def test_rejects_out_of_range_parameters(client, auth, params):
    assert client.get(URL, params=params, headers=auth).status_code == 422


def test_a_refused_chat_shows_up_as_a_gap(client, auth, retrieval, conversation):
    """End to end: the chat route logs the refusal and the report finds it."""
    retrieval.passages = make_passages(0.30)
    client.post(
        "/api/chat",
        json={"question": "Can I bring my dog to work?", "session_id": conversation},
        headers=auth,
    )

    body = client.get(URL, headers=auth).json()

    assert body["refused"] == 1
    assert [g["question"] for g in body["gaps"]] == ["Can I bring my dog to work?"]
    assert "session_id" not in body["gaps"][0]


def test_fake_aggregate_still_rejects_vector_search():
    with pytest.raises(NotImplementedError):
        FakeCollection().aggregate([{"$vectorSearch": {}}])


def test_a_slow_report_answers_503(client, auth, monkeypatch):
    calls: list[dict] = []

    def too_slow(_pipeline, **kwargs):
        calls.append(kwargs)
        raise ExecutionTimeout("operation exceeded time limit")

    monkeypatch.setattr(reports.query_logs_col, "aggregate", too_slow)

    response = client.get(URL, headers=auth)

    assert response.status_code == 503
    assert "too long" in response.json()["detail"]
    assert calls == [{"maxTimeMS": reports.QUERY_TIMEOUT_MS}]


def test_fake_sort_puts_null_first_ascending_like_mongo():
    collection = FakeCollection()
    collection.insert_many([{"k": 2}, {"k": None}, {"k": 1}])

    ascending = collection.aggregate([{"$sort": {"k": 1}}])
    descending = collection.aggregate([{"$sort": {"k": -1}}])

    assert [row["k"] for row in ascending] == [None, 1, 2]
    assert [row["k"] for row in descending] == [2, 1, None]


def test_fake_group_on_a_compound_id_then_sums_a_field_path():
    """The two-pass conversation count (#291) in the fake, including Mongo's
    rule that a missing path drops out of an object but a stored null stays."""
    collection = FakeCollection()
    collection.insert_many(
        [
            {"h": "a", "s": "x"},
            {"h": "a", "s": "x"},
            {"h": "a", "s": "y"},
            {"h": "a", "s": None},
            {"h": "a"},
            {"h": "b", "s": "x"},
        ]
    )

    first = collection.aggregate([{"$group": {"_id": {"h": "$h", "s": "$s"}, "n": {"$sum": 1}}}])
    both = collection.aggregate(
        [
            {"$group": {"_id": {"h": "$h", "s": "$s"}, "n": {"$sum": 1}}},
            {"$group": {"_id": "$_id.h", "n": {"$sum": "$n"}, "groups": {"$sum": 1}}},
        ]
    )

    assert [(row["_id"], row["n"]) for row in first] == [
        ({"h": "a", "s": "x"}, 2),
        ({"h": "a", "s": "y"}, 1),
        ({"h": "a", "s": None}, 1),
        ({"h": "a"}, 1),
        ({"h": "b", "s": "x"}, 1),
    ]
    assert list(both) == [
        {"_id": "a", "n": 5, "groups": 4},
        {"_id": "b", "n": 1, "groups": 1},
    ]


def test_fake_group_on_a_missing_dotted_path_is_null():
    collection = FakeCollection()
    collection.insert_many([{"s": "x"}, {"s": "y"}])

    rows = collection.aggregate(
        [
            {"$group": {"_id": {"h": "$h", "s": "$s"}}},
            {"$group": {"_id": "$_id.h", "n": {"$sum": 1}}},
        ]
    )

    assert list(rows) == [{"_id": None, "n": 2}]
