"""The grouping pass behind the What People Ask page (#287)."""

from sourcebook.rag.question_groups import (
    Wording,
    candidate_pairs,
    exact_groups,
    group_by_meaning,
    pair_key,
)


def wording(key: str, count: int, *, refused: int = 0, sessions=()) -> Wording:
    return Wording(key, key, count, refused, frozenset(sessions or {key}))


def test_members_join_the_closest_leader_at_or_above_the_threshold():
    words = [wording("pto", 5), wording("vacation", 2), wording("parking", 3)]
    vectors = {"pto": [1, 0], "vacation": [0.9, 0.1], "parking": [0, 1]}

    groups = group_by_meaning(words, vectors, 0.9)

    assert [[m.question for m in g.members] for g in groups] == [
        ["pto", "vacation"],
        ["parking"],
    ]


def test_the_threshold_is_inclusive():
    words = [wording("a", 2), wording("b", 1)]

    [group] = group_by_meaning(words, {"a": [1, 0], "b": [0.6, 0.8]}, 0.6)

    assert len(group.members) == 2


def test_comparing_to_the_leader_only_stops_chains():
    """b is close to a and c is close to b, but c is not close to a."""
    words = [wording("a", 3), wording("b", 2), wording("c", 1)]
    vectors = {"a": [1, 0], "b": [0.94, 0.34], "c": [0.77, 0.64]}

    groups = group_by_meaning(words, vectors, 0.9)

    assert [[m.question for m in g.members] for g in groups] == [["a", "b"], ["c"]]


def test_the_more_asked_leader_wins_a_tie():
    words = [wording("first", 5), wording("second", 4), wording("between", 1)]
    vectors = {"first": [1, 0], "second": [0, 1], "between": [1, 1]}

    groups = group_by_meaning(words, vectors, 0.7)

    assert [m.question for m in groups[0].members] == ["first", "between"]


def test_counts_sum_and_conversations_union():
    words = [
        wording("pto", 3, refused=1, sessions={"s1", "s2"}),
        wording("vacation", 2, refused=2, sessions={"s2", "s3"}),
    ]

    [group] = group_by_meaning(words, {"pto": [1, 0], "vacation": [1, 0]}, 0.9)

    assert (group.count, group.refused, group.conversations) == (5, 3, 3)


def test_a_wording_without_a_vector_or_text_stands_alone():
    words = [wording("pto", 3), wording("unembedded", 2), Wording("blank", None, 1, 0, frozenset())]

    groups = group_by_meaning(words, {"pto": [1, 0]}, 0.5)

    assert len(groups) == 3


def test_a_zero_vector_does_not_divide_by_zero():
    groups = group_by_meaning([wording("a", 1), wording("b", 1)], {"a": [0, 0], "b": [0, 0]}, 0.5)

    assert len(groups) == 2


def test_order_is_most_asked_first_and_stable():
    words = [wording("b", 1), wording("a", 1), wording("c", 4)]

    assert [g.leader.question for g in exact_groups(words)] == ["c", "a", "b"]


def test_fake_provider_embeds_a_batch_with_one_delay(monkeypatch):
    from sourcebook.rag import llm

    provider = llm.FakeProvider()
    sleeps: list[int] = []
    monkeypatch.setattr(provider, "_sleep", sleeps.append)

    batch = provider.embed_many(["a", "b", "c"])

    assert len(sleeps) == 1
    assert batch == [provider._vector(text) for text in ("a", "b", "c")]


def test_a_capped_member_keeps_its_exact_count_as_a_floor():
    """wording_pipeline returns a sample of session ids past its cap (#291),
    so the union can undercount. The largest exact member count is a floor."""
    words = [
        Wording("pto", "pto", 9, 0, frozenset({"s1", "s2"}), session_count=6),
        Wording("vacation", "vacation", 1, 0, frozenset({"s9"}), session_count=1),
    ]

    [group] = group_by_meaning(words, {"pto": [1, 0], "vacation": [1, 0]}, 0.9)

    assert group.conversations == 6


# ── The judged band (#293) ────────────────────────────────────────────────────


def test_a_judged_pair_in_the_band_merges():
    words = [wording("pto", 2), wording("vacation", 1)]
    vectors = {"pto": [1, 0], "vacation": [0.7, 0.714]}  # cosine 0.70

    [group] = group_by_meaning(words, vectors, 0.85, floor=0.6, same={pair_key("vacation", "pto")})

    assert [m.question for m in group.members] == ["pto", "vacation"]


def test_an_unjudged_pair_in_the_band_stays_apart():
    words = [wording("pto", 2), wording("carryover", 1)]
    vectors = {"pto": [1, 0], "carryover": [0.7, 0.714]}

    assert len(group_by_meaning(words, vectors, 0.85, floor=0.6, same=set())) == 2


def test_a_pair_below_the_floor_never_merges_even_if_judged_same():
    words = [wording("a", 2), wording("b", 1)]
    vectors = {"a": [1, 0], "b": [0.5, 0.866]}  # cosine 0.50

    groups = group_by_meaning(words, vectors, 0.85, floor=0.6, same={pair_key("a", "b")})

    assert len(groups) == 2


def test_a_judged_member_joins_its_closest_matching_leader():
    """The member x is judged the same as both leaders and is closer to "second"."""
    words = [wording("first", 5), wording("second", 4), wording("x", 1)]
    vectors = {"first": [1, 0], "second": [0, 1], "x": [0.6, 0.8]}
    same = {pair_key("first", "x"), pair_key("second", "x")}

    groups = group_by_meaning(words, vectors, 0.85, floor=0.55, same=same)

    assert [[m.question for m in g.members] for g in groups] == [["first"], ["second", "x"]]


def test_candidate_pairs_are_the_band_only():
    words = [wording("a", 3), wording("b", 2), wording("c", 1), wording("far", 1)]
    vectors = {
        "a": [1, 0, 0],
        "b": [0.9, 0.436, 0],  # 0.90 with a: over the threshold, not a candidate
        "c": [0.7, 0, 0.714],  # 0.70 with a, 0.63 with b
        "far": [0, 0, 1],  # 0.71 with c, 0 with a and b
    }

    pairs = candidate_pairs(words, vectors, 0.6, 0.85)

    assert set(pairs) == {pair_key("a", "c"), pair_key("b", "c"), pair_key("c", "far")}
    assert round(pairs[pair_key("a", "c")], 2) == 0.70
