"""The coverage report behind the What People Ask page."""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from conftest import FAKE_DB, make_passages
from pymongo.errors import ExecutionTimeout, OperationFailure

from scripts.loadtest.fakemongo import FakeCollection
from sourcebook.api.routes import reports
from sourcebook.api.routes.reports import MAX_WINDOW_DAYS
from sourcebook.rag import query_log_reports
from sourcebook.rag.config import MANAGER_MIN_CONVERSATIONS

URL = "/api/reports/gaps"
# Each logged row is its own conversation unless a test passes session_id.
_SESSIONS = itertools.count(1)


@pytest.fixture(autouse=True)
def empty_vector_memo():
    """The route memoizes vectors per process; tests below swap them per test."""
    reports._vector_memo.clear()
    reports._verdict_memo.clear()
    yield
    reports._vector_memo.clear()
    reports._verdict_memo.clear()


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


def test_an_employee_token_is_forbidden(client, auth):
    """The shared password opens the chat, not the report on everyone's questions."""
    response = client.get(URL, headers=auth)
    assert response.status_code == 403
    assert response.json()["detail"] == "Manager or Human Resources sign-in required."


def test_forbidden_without_an_hr_or_manager_password_configured(client, auth, monkeypatch):
    """With only APP_PASSWORD_HASH set, nobody can open the report."""
    monkeypatch.delenv("HR_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("MANAGER_PASSWORD_HASH", raising=False)
    assert client.get(URL, headers=auth).status_code == 403


def test_empty_log(client, hr_auth):
    body = client.get(URL, headers=hr_auth).json()
    assert body["days"] == 30
    assert body["min_conversations"] is None
    assert (body["total"], body["refused"]) == (0, 0)
    assert body["gaps"] == []
    assert body["faq"] == []


def test_refused_questions_rank_by_count(client, hr_auth):
    for _ in range(3):
        log("Can I bring my dog?", refused=True)
    log("Is there a sabbatical?", refused=True)
    log("How much PTO do I get?", refused=False)

    body = client.get(URL, headers=hr_auth).json()

    assert (body["total"], body["refused"]) == (5, 4)
    assert [(g["question"], g["count"], g["conversations"]) for g in body["gaps"]] == [
        ("Can I bring my dog?", 3, 3),
        ("Is there a sabbatical?", 1, 1),
    ]


def test_faq_counts_repeats_and_their_refusals(client, hr_auth):
    log("How much PTO do I get?", refused=False)
    log("How much PTO do I get?", refused=True)
    log("Asked once", refused=False)

    faq = client.get(URL, headers=hr_auth).json()["faq"]

    assert faq == [
        {
            "question_hash": "how much pto do i get?",
            "question": "How much PTO do I get?",
            "count": 2,
            "conversations": 2,
            "other_wordings": [],
            "other_wording_count": 0,
            "refused": 1,
        }
    ]


def test_one_conversation_repeating_itself_is_not_a_faq(client, hr_auth):
    """Three asks from one conversation say nothing about how many people
    share the question; two conversations asking once each do."""
    for _ in range(3):
        log("Repeated by one person", refused=False, session_id="alone")
    log("Asked by two people", refused=False)
    log("Asked by two people", refused=False)

    faq = client.get(URL, headers=hr_auth).json()["faq"]

    assert [(g["question"], g["count"], g["conversations"]) for g in faq] == [
        ("Asked by two people", 2, 2),
    ]


def test_faq_ranks_on_conversations_before_asks(client, hr_auth):
    for _ in range(5):
        log("Many asks, few people", refused=False, session_id="one")
    log("Many asks, few people", refused=False, session_id="two")
    for _ in range(3):
        log("Fewer asks, more people", refused=False)

    faq = client.get(URL, headers=hr_auth).json()["faq"]

    assert [(g["question"], g["count"], g["conversations"]) for g in faq] == [
        ("Fewer asks, more people", 3, 3),
        ("Many asks, few people", 6, 2),
    ]


def test_gaps_rank_on_asks_and_count_conversations(client, hr_auth):
    """Every refusal is a gap, even one person's, so the gaps list keeps asks."""
    for _ in range(4):
        log("One person, four tries", refused=True, session_id="stuck")
    log("Two people", refused=True)
    log("Two people", refused=True)

    gaps = client.get(URL, headers=hr_auth).json()["gaps"]

    assert [(g["question"], g["count"], g["conversations"]) for g in gaps] == [
        ("One person, four tries", 4, 1),
        ("Two people", 2, 2),
    ]


def test_rows_outside_the_window_are_left_out(client, hr_auth):
    log("Last week", refused=True, age=timedelta(days=6))
    log("Last month", refused=True, age=timedelta(days=20))

    body = client.get(URL, params={"days": 7}, headers=hr_auth).json()

    assert body["days"] == 7
    assert [g["question"] for g in body["gaps"]] == ["Last week"]
    assert body["total"] == 1


def test_prefers_the_condensed_question(client, hr_auth):
    """The hash groups on the condensed rewrite, so a follow-up's raw text
    ("what about part-time?") would misname the group."""
    log(
        "what about part-time?",
        refused=True,
        question_condensed="Do part-time employees get PTO?",
    )
    log("", refused=True, question_condensed=None, question_hash="blank")

    gaps = client.get(URL, headers=hr_auth).json()["gaps"]

    assert {g["question"] for g in gaps} == {"Do part-time employees get PTO?", None}


def test_top_caps_each_list(client, hr_auth):
    for n in range(5):
        log(f"Question {n}", refused=True)

    gaps = client.get(URL, params={"top": 2}, headers=hr_auth).json()["gaps"]

    assert len(gaps) == 2


def test_a_window_longer_than_the_log_ttl_is_shortened(client, hr_auth, monkeypatch):
    """A short QUERY_LOG_TTL_SECONDS must not turn the default request into a 422."""
    monkeypatch.setattr(reports, "TTL_DAYS", 7)
    log("Inside the TTL", refused=True, age=timedelta(days=3))
    log("Past the TTL", refused=True, age=timedelta(days=20))

    response = client.get(URL, params={"days": 90}, headers=hr_auth)

    assert response.status_code == 200
    assert response.json()["days"] == 7
    assert [g["question"] for g in response.json()["gaps"]] == ["Inside the TTL"]


@pytest.mark.parametrize(
    "params",
    [{"days": 0}, {"days": MAX_WINDOW_DAYS + 1}, {"top": 0}, {"top": 101}, {"days": "a"}],
)
def test_rejects_out_of_range_parameters(client, hr_auth, params):
    assert client.get(URL, params=params, headers=hr_auth).status_code == 422


def test_a_refused_chat_shows_up_as_a_gap(client, auth, hr_auth, retrieval, conversation):
    """End to end: the chat route logs the refusal and the report finds it."""
    retrieval.passages = make_passages(0.30)
    client.post(
        "/api/chat",
        json={"question": "Can I bring my dog to work?", "session_id": conversation},
        headers=auth,
    )

    body = client.get(URL, headers=hr_auth).json()

    assert body["refused"] == 1
    assert [g["question"] for g in body["gaps"]] == ["Can I bring my dog to work?"]
    assert "session_id" not in body["gaps"][0]


def test_fake_aggregate_still_rejects_vector_search():
    with pytest.raises(NotImplementedError):
        FakeCollection().aggregate([{"$vectorSearch": {}}])


def test_a_slow_report_answers_503(client, hr_auth, monkeypatch):
    calls: list[dict] = []

    def too_slow(_pipeline, **kwargs):
        calls.append(kwargs)
        raise ExecutionTimeout("operation exceeded time limit")

    monkeypatch.setattr(reports.query_logs_col, "aggregate", too_slow)

    response = client.get(URL, headers=hr_auth)

    assert response.status_code == 503
    assert "too long" in response.json()["detail"]
    assert calls == [{"maxTimeMS": reports.QUERY_TIMEOUT_MS}]


def test_a_report_over_the_memory_limit_answers_503(client, hr_auth, monkeypatch):
    """$addToSet cannot spill, so one very common question can hit code 146 (#291)."""

    def too_big(_pipeline, **_kwargs):
        raise OperationFailure("$group exceeded memory limit", code=146)

    monkeypatch.setattr(reports.query_logs_col, "aggregate", too_big)

    response = client.get(URL, headers=hr_auth)

    assert response.status_code == 503
    assert "shorter window" in response.json()["detail"]


def test_other_mongo_failures_are_not_reported_as_slow(client, hr_auth, monkeypatch):
    def unauthorized(_pipeline, **_kwargs):
        raise OperationFailure("not authorized", code=13)

    monkeypatch.setattr(reports.query_logs_col, "aggregate", unauthorized)

    with pytest.raises(OperationFailure):
        client.get(URL, headers=hr_auth)


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


# ── Grouping by meaning (#287) ────────────────────────────────────────────────

PTO = [1.0, 0.0, 0.0]
PTO_REPHRASED = [0.95, 0.312, 0.0]  # cosine 0.95 with PTO
PTO_CARRYOVER = [0.8, 0.0, 0.6]  # cosine 0.80: close, but a different question
PARKING = [0.0, 1.0, 0.0]


def vectors(monkeypatch, table: dict[str, list[float]]) -> list[list[str]]:
    """Serve `table` through the provider; return the batches it was asked for."""
    calls: list[list[str]] = []

    def embed_many(texts, **_kwargs):
        calls.append(list(texts))
        return [table[text] for text in texts]

    monkeypatch.setattr(reports.get_provider(), "embed_many", embed_many)
    return calls


def test_rephrasings_share_a_row_with_summed_counts(client, hr_auth, monkeypatch):
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "How many vacation days do I have?": PTO_REPHRASED},
    )
    log("How much PTO do I get?", refused=True, session_id="a")
    log("How much PTO do I get?", refused=True, session_id="b")
    log("How many vacation days do I have?", refused=True, session_id="c")
    log("How many vacation days do I have?", refused=False, session_id="a")

    body = client.get(URL, headers=hr_auth).json()

    assert body["grouping"] == "meaning"
    [row] = body["faq"]
    # Tied at two asks each, so the hash order picks the leader.
    assert row["question"] == "How many vacation days do I have?"
    assert (row["count"], row["refused"], row["conversations"]) == (4, 3, 3)
    assert row["other_wordings"] == [{"question": "How much PTO do I get?", "count": 2}]
    assert row["other_wording_count"] == 1
    [gap] = body["gaps"]
    assert (gap["question"], gap["count"]) == ("How much PTO do I get?", 3)


def test_two_single_asks_in_other_words_reach_asked_most(client, hr_auth, monkeypatch):
    """Neither wording repeats on its own; together they are asked twice."""
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "How many vacation days do I have?": PTO_REPHRASED},
    )
    log("How much PTO do I get?", refused=False, session_id="a")
    log("How many vacation days do I have?", refused=False, session_id="b")

    faq = client.get(URL, headers=hr_auth).json()["faq"]

    assert [(row["count"], row["other_wording_count"]) for row in faq] == [(2, 1)]


def test_a_near_miss_below_the_threshold_stays_apart(client, hr_auth, monkeypatch):
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "Does unused PTO carry over?": PTO_CARRYOVER},
    )
    log("How much PTO do I get?", refused=True)
    log("Does unused PTO carry over?", refused=True)

    gaps = client.get(URL, headers=hr_auth).json()["gaps"]

    assert sorted(g["question"] for g in gaps) == [
        "Does unused PTO carry over?",
        "How much PTO do I get?",
    ]


def test_cached_vectors_are_used_and_nothing_is_written(client, hr_auth, monkeypatch):
    from sourcebook.rag import cache

    cache.put_cached_embedding("How much PTO do I get?", PTO)
    calls = vectors(monkeypatch, {"Where do I park?": PARKING})
    log("How much PTO do I get?", refused=True)
    log("Where do I park?", refused=True)
    before = FAKE_DB["embedding_cache"].count_documents({})

    client.get(URL, headers=hr_auth)

    assert calls == [["Where do I park?"]]
    assert FAKE_DB["embedding_cache"].count_documents({}) == before


def test_a_provider_failure_falls_back_to_exact_wording(client, hr_auth, monkeypatch):
    from sourcebook.rag.llm import ProviderBusyError

    def busy(_texts, **_kwargs):
        raise ProviderBusyError("busy")

    monkeypatch.setattr(reports.get_provider(), "embed_many", busy)
    log("How much PTO do I get?", refused=True)
    log("How many vacation days do I have?", refused=True)

    response = client.get(URL, headers=hr_auth)

    assert response.status_code == 200
    assert response.json()["grouping"] == "exact"
    assert len(response.json()["gaps"]) == 2


def test_a_repeat_load_makes_no_provider_call(client, hr_auth, monkeypatch):
    calls = vectors(monkeypatch, {"Where do I park?": PARKING, "How much PTO do I get?": PTO})
    log("Where do I park?", refused=True)
    log("How much PTO do I get?", refused=True)

    client.get(URL, headers=hr_auth)
    client.get(URL, headers=hr_auth)

    assert calls == [["How much PTO do I get?", "Where do I park?"]]


def test_asked_most_candidates_are_picked_by_conversations(client, hr_auth, monkeypatch):
    """One person asking five times must not take the only slot from a
    question asked once each in three conversations."""
    monkeypatch.setattr(reports, "CANDIDATE_LIMIT", 1)
    vectors(monkeypatch, {"Repeated by one": PTO, "Asked by three": PARKING})
    for _ in range(5):
        log("Repeated by one", refused=False, session_id="solo")
    for session in ("a", "b", "c"):
        log("Asked by three", refused=False, session_id=session)

    faq = client.get(URL, headers=hr_auth).json()["faq"]

    assert [row["question"] for row in faq] == ["Asked by three"]


def test_the_vector_memo_evicts_the_least_recently_used(monkeypatch):
    monkeypatch.setattr(reports, "VECTOR_MEMO_SIZE", 2)
    reports._remember({"a": PTO, "b": PARKING})
    reports._recall(["a"])  # "a" is now the most recently used
    reports._remember({"c": PTO_REPHRASED})

    assert set(reports._recall(["a", "b", "c"])) == {"a", "c"}


def test_cache_disabled_turns_the_vector_memo_off(client, hr_auth, monkeypatch):
    monkeypatch.setattr(reports, "CACHE_ENABLED", False)
    calls = vectors(monkeypatch, {"Where do I park?": PARKING})
    log("Where do I park?", refused=True)

    client.get(URL, headers=hr_auth)
    client.get(URL, headers=hr_auth)

    assert calls == [["Where do I park?"], ["Where do I park?"]]
    assert len(reports._vector_memo) == 0


# ── The utility-model check on the band below the threshold (#293) ───────────

PTO_REWORDED = [0.7, 0.714, 0.0]  # cosine 0.70 with PTO: in the judged band
SEVERANCE_LAID_OFF = [0.0, 0.0, 1.0]
SEVERANCE_RESIGN = [0.0, 0.6, 0.8]  # cosine 0.80 with SEVERANCE_LAID_OFF


def verdicts(monkeypatch, *, same: set[frozenset[str]] = frozenset(), reply=None):
    """Answer the question judge; return the pairs it was asked about, per call."""
    import json
    import re

    calls: list[list[tuple[str, str]]] = []

    def complete(messages, **_kwargs):
        texts = re.findall(r'^\s*\d+\. A: (".*")\n\s+B: (".*")$', messages[1]["content"], re.M)
        pairs = [(json.loads(a), json.loads(b)) for a, b in texts]
        calls.append(pairs)
        if reply is not None:
            return reply(pairs)
        return json.dumps(
            {"same": [n for n, pair in enumerate(pairs, start=1) if frozenset(pair) in same]}
        )

    monkeypatch.setattr(reports.get_provider(), "complete", complete)
    return calls


def test_a_rewording_the_model_confirms_shares_a_row(client, hr_auth, monkeypatch):
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "What is my annual paid time off allowance?": PTO_REWORDED},
    )
    calls = verdicts(
        monkeypatch,
        same={frozenset({"How much PTO do I get?", "What is my annual paid time off allowance?"})},
    )
    log("How much PTO do I get?", refused=True)
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)

    body = client.get(URL, headers=hr_auth).json()

    assert body["grouping"] == "meaning"
    [gap] = body["gaps"]
    assert (gap["question"], gap["count"], gap["other_wording_count"]) == (
        "How much PTO do I get?",
        3,
        1,
    )
    # Both lists hold the same pair, and it is judged once.
    assert len(calls) == 1 and len(calls[0]) == 1


def test_both_provider_calls_get_the_report_timeout(client, hr_auth, monkeypatch):
    # A slow provider costs the page a few seconds, not the chat timeouts (#300).
    seen: dict[str, dict] = {}

    def embed_many(texts, **kwargs):
        seen["embed"] = kwargs
        return [
            {
                "How much PTO do I get?": PTO,
                "What is my annual paid time off allowance?": PTO_REWORDED,
            }[text]
            for text in texts
        ]

    def complete(messages, **kwargs):
        seen["judge"] = kwargs
        return '{"same": [1]}'

    monkeypatch.setattr(reports.get_provider(), "embed_many", embed_many)
    monkeypatch.setattr(reports.get_provider(), "complete", complete)
    monkeypatch.setattr(reports, "REPORT_PROVIDER_TIMEOUT_SECONDS", 3.5)
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)

    assert client.get(URL, headers=hr_auth).json()["grouping"] == "meaning"
    assert seen["embed"] == {"timeout": 3.5}
    assert seen["judge"]["timeout"] == 3.5


def test_a_pair_the_model_calls_different_stays_apart(client, hr_auth, monkeypatch):
    vectors(
        monkeypatch,
        {
            "Do I get severance if I'm laid off?": SEVERANCE_LAID_OFF,
            "Do I get severance if I resign?": SEVERANCE_RESIGN,
        },
    )
    calls = verdicts(monkeypatch)
    log("Do I get severance if I'm laid off?", refused=True)
    log("Do I get severance if I resign?", refused=True)

    body = client.get(URL, headers=hr_auth).json()

    assert body["grouping"] == "meaning"
    assert len(body["gaps"]) == 2
    assert calls == [[("Do I get severance if I resign?", "Do I get severance if I'm laid off?")]]


def test_a_pair_below_the_floor_is_never_sent(client, hr_auth, monkeypatch):
    vectors(monkeypatch, {"How much PTO do I get?": PTO, "Where do I park?": PARKING})
    calls = verdicts(monkeypatch)
    log("How much PTO do I get?", refused=True)
    log("Where do I park?", refused=True)

    body = client.get(URL, headers=hr_auth).json()

    assert (body["grouping"], len(body["gaps"]), calls) == ("meaning", 2, [])


def test_a_judge_failure_falls_back_to_cosine_and_says_so(client, hr_auth, monkeypatch):
    from sourcebook.rag.llm import ProviderBusyError

    def busy(*_args, **_kwargs):
        raise ProviderBusyError("busy")

    vectors(
        monkeypatch,
        {
            "How much PTO do I get?": PTO,
            "How much PTO do I get": PTO_REPHRASED,
            "What is my annual paid time off allowance?": PTO_REWORDED,
        },
    )
    monkeypatch.setattr(reports.get_provider(), "complete", busy)
    log("How much PTO do I get?", refused=True)
    log("How much PTO do I get?", refused=True)
    log("How much PTO do I get", refused=True)
    log("What is my annual paid time off allowance?", refused=True)

    response = client.get(URL, headers=hr_auth)

    assert response.status_code == 200
    assert response.json()["grouping"] == "cosine"
    # The pairs the failed call was asked about still have no verdict: the
    # rewording with each spelling of the PTO question (0.70 and 0.89).
    assert response.json()["unjudged"] == 2
    # Cosine still merges what clears the threshold on its own.
    assert [g["count"] for g in response.json()["gaps"]] == [3, 1]


def test_a_reply_that_does_not_parse_falls_back_to_cosine(client, hr_auth, monkeypatch):
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "What is my annual paid time off allowance?": PTO_REWORDED},
    )
    verdicts(monkeypatch, reply=lambda _pairs: '{"same": true}')
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)

    body = client.get(URL, headers=hr_auth).json()

    assert (body["grouping"], len(body["gaps"])) == ("cosine", 2)
    # A failed reply is not remembered, so the next load asks again.
    assert len(reports._verdict_memo) == 0


def test_a_repeat_load_reuses_verdicts(client, hr_auth, monkeypatch):
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "What is my annual paid time off allowance?": PTO_REWORDED},
    )
    calls = verdicts(
        monkeypatch,
        same={frozenset({"How much PTO do I get?", "What is my annual paid time off allowance?"})},
    )
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)

    first = client.get(URL, headers=hr_auth).json()
    second = client.get(URL, headers=hr_auth).json()

    assert len(calls) == 1
    assert first["gaps"] == second["gaps"] and len(second["gaps"]) == 1


def test_only_the_closest_pairs_go_in_one_call(client, hr_auth, monkeypatch):
    monkeypatch.setattr(reports, "QUESTION_JUDGE_MAX_PAIRS", 1)
    vectors(
        monkeypatch,
        {
            "How much PTO do I get?": PTO,
            "What is my annual paid time off allowance?": PTO_REWORDED,  # 0.70 with PTO
            "Does unused PTO carry over?": PTO_CARRYOVER,  # 0.80 with PTO
        },
    )
    calls = verdicts(monkeypatch)
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)
    log("Does unused PTO carry over?", refused=True)

    first = client.get(URL, headers=hr_auth).json()
    second = client.get(URL, headers=hr_auth).json()

    assert [len(batch) for batch in calls] == [1, 1]
    assert calls[0] == [("Does unused PTO carry over?", "How much PTO do I get?")]
    assert calls[1] != calls[0]
    # The page can say a pair is still waiting (#300), until a later load judges it.
    assert (first["grouping"], first["unjudged"]) == ("meaning", 1)
    assert (second["grouping"], second["unjudged"]) == ("meaning", 0)


def test_a_zero_pair_cap_turns_the_judge_off(client, hr_auth, monkeypatch):
    monkeypatch.setattr(reports, "QUESTION_JUDGE_MAX_PAIRS", 0)
    vectors(
        monkeypatch,
        {"How much PTO do I get?": PTO, "What is my annual paid time off allowance?": PTO_REWORDED},
    )
    calls = verdicts(monkeypatch)
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)

    body = client.get(URL, headers=hr_auth).json()

    assert (body["grouping"], len(body["gaps"]), calls) == ("cosine", 2, [])
    assert body["unjudged"] == 0


def test_wording_pipeline_returns_a_capped_sample_of_session_ids(monkeypatch):
    """A popular wording's full id list would pass the 16 MB result document
    limit at about 370k conversations (#291). The count stays exact."""
    monkeypatch.setattr(query_log_reports, "WORDING_SESSION_SAMPLE", 2)
    now = datetime.now(UTC)
    collection = FakeCollection()
    collection.insert_many(
        [
            {"created_at": now, "question_hash": "pto", "refused": False, "session_id": s}
            for s in ("a", "b", "c", "d")
        ]
    )

    [row] = collection.aggregate(
        query_log_reports.wording_pipeline(
            now - timedelta(days=1), now + timedelta(days=1), 10, refused_only=False
        )
    )

    assert row["session_count"] == 4
    assert len(row["sessions"]) == 2


def test_a_wording_past_the_sample_cap_reports_its_exact_conversations(
    client, hr_auth, monkeypatch
):
    monkeypatch.setattr(query_log_reports, "WORDING_SESSION_SAMPLE", 2)
    vectors(monkeypatch, {"Where do I park?": PARKING})
    for session in ("a", "b", "c"):
        log("Where do I park?", refused=False, session_id=session)

    [row] = client.get(URL, headers=hr_auth).json()["faq"]

    assert row["conversations"] == 3


def test_a_failed_judge_merges_nothing_below_the_threshold(client, hr_auth, monkeypatch):
    # A pair confirmed on an earlier load must not merge on a load whose call
    # fails, or the page would say "cosine" while showing a band merge (#300).
    from sourcebook.rag.llm import ProviderBusyError

    vectors(
        monkeypatch,
        {
            "How much PTO do I get?": PTO,
            "What is my annual paid time off allowance?": PTO_REWORDED,
            "Does unused PTO carry over?": PTO_CARRYOVER,
        },
    )
    verdicts(
        monkeypatch,
        same={frozenset({"How much PTO do I get?", "What is my annual paid time off allowance?"})},
    )
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)
    first = client.get(URL, headers=hr_auth).json()
    assert (first["grouping"], len(first["gaps"])) == ("meaning", 1)

    def busy(*_args, **_kwargs):
        raise ProviderBusyError("busy")

    monkeypatch.setattr(reports.get_provider(), "complete", busy)
    log("Does unused PTO carry over?", refused=True)  # a new pair, so the judge is called
    second = client.get(URL, headers=hr_auth).json()

    assert (second["grouping"], len(second["gaps"])) == ("cosine", 3)


def test_with_the_memo_off_no_pairs_are_promised_to_a_later_load(client, hr_auth, monkeypatch):
    # Without the memo every load judges the same closest pairs, so reloading
    # never reaches the rest and the page must not say it will.
    monkeypatch.setattr(reports, "CACHE_ENABLED", False)
    monkeypatch.setattr(reports, "QUESTION_JUDGE_MAX_PAIRS", 1)
    vectors(
        monkeypatch,
        {
            "How much PTO do I get?": PTO,
            "What is my annual paid time off allowance?": PTO_REWORDED,
            "Does unused PTO carry over?": PTO_CARRYOVER,
        },
    )
    calls = verdicts(monkeypatch)
    log("How much PTO do I get?", refused=True)
    log("What is my annual paid time off allowance?", refused=True)
    log("Does unused PTO carry over?", refused=True)

    first = client.get(URL, headers=hr_auth).json()
    second = client.get(URL, headers=hr_auth).json()

    assert calls[0] == calls[1]
    assert (first["unjudged"], second["unjudged"]) == (0, 0)


# ── What a manager sees ───────────────────────────────────────────────────────


def _ask(question: str, conversations: int, *, refused: bool) -> None:
    for _ in range(conversations):
        log(question, refused=refused)


def test_the_default_manager_threshold_is_three():
    assert MANAGER_MIN_CONVERSATIONS == 3


def test_a_manager_sees_only_questions_asked_in_enough_conversations(client, manager_auth):
    _ask("How do I enroll in benefits?", 3, refused=False)
    _ask("Can I bring my dog?", 3, refused=True)
    _ask("Where do I find my W-2?", 2, refused=False)
    _ask("How do I report my manager for harassment?", 1, refused=True)

    body = client.get(URL, headers=manager_auth).json()

    assert body["min_conversations"] == 3
    # Totals count every row: a number names nobody.
    assert (body["total"], body["refused"]) == (9, 4)
    assert [g["question"] for g in body["gaps"]] == ["Can I bring my dog?"]
    assert [g["question"] for g in body["faq"]] == [
        "Can I bring my dog?",
        "How do I enroll in benefits?",
    ]


def test_hr_sees_every_wording(client, hr_auth):
    _ask("Where do I find my W-2?", 2, refused=False)
    _ask("How do I report my manager for harassment?", 1, refused=True)

    body = client.get(URL, headers=hr_auth).json()

    assert body["min_conversations"] is None
    assert [g["question"] for g in body["gaps"]] == ["How do I report my manager for harassment?"]
    assert [g["question"] for g in body["faq"]] == ["Where do I find my W-2?"]


def test_one_conversation_repeating_itself_does_not_reach_a_manager(client, manager_auth):
    """The threshold counts conversations, not asks."""
    for _ in range(5):
        log("Asked five times by one person", refused=True, session_id="alone")

    body = client.get(URL, headers=manager_auth).json()

    assert body["gaps"] == []
    assert body["faq"] == []


def test_a_rare_wording_never_rides_along_under_a_common_one(
    client, hr_auth, manager_auth, monkeypatch
):
    """Filtering happens before grouping, so a one-off rewording that merges
    into a common question for HR is not listed under it for a manager."""
    rare = "How much PTO do I get as a new hire in the Denver office?"
    vectors(monkeypatch, {"How much PTO do I get?": PTO, rare: PTO_REPHRASED})
    _ask("How much PTO do I get?", 3, refused=False)
    _ask(rare, 1, refused=False)

    [hr_row] = client.get(URL, headers=hr_auth).json()["faq"]
    [manager_row] = client.get(URL, headers=manager_auth).json()["faq"]

    assert hr_row["other_wordings"] == [{"question": rare, "count": 1}]
    assert (manager_row["question"], manager_row["count"]) == ("How much PTO do I get?", 3)
    assert manager_row["other_wordings"] == []


def test_single_conversation_wordings_do_not_crowd_a_manager_out_of_the_cap(
    client, manager_auth, monkeypatch
):
    """Refused candidates are capped by asks. One person's heavy repeats must
    not fill the cap ahead of a question asked in several conversations."""
    monkeypatch.setattr(reports, "CANDIDATE_LIMIT", 2)
    for question in ("Repeat one", "Repeat two"):
        for _ in range(5):
            log(question, refused=True, session_id=f"alone-{question}")
    _ask("Can I bring my dog?", 3, refused=True)

    gaps = client.get(URL, headers=manager_auth).json()["gaps"]

    assert [(g["question"], g["conversations"]) for g in gaps] == [("Can I bring my dog?", 3)]


def test_the_manager_threshold_is_configurable(client, manager_auth, monkeypatch):
    monkeypatch.setattr(reports, "MANAGER_MIN_CONVERSATIONS", 2)
    _ask("Where do I find my W-2?", 2, refused=False)

    body = client.get(URL, headers=manager_auth).json()

    assert body["min_conversations"] == 2
    assert [g["question"] for g in body["faq"]] == ["Where do I find my W-2?"]
