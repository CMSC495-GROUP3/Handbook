"""The labelled pairs behind QUESTION_GROUP_THRESHOLD, and the default they justify."""

import json
from pathlib import Path

from sourcebook.rag.config import QUESTION_GROUP_THRESHOLD

EVALUATION = Path(__file__).resolve().parent.parent / "evaluation"
PAIRS = json.loads((EVALUATION / "question_pairs.json").read_text())["pairs"]
RESULTS = json.loads((EVALUATION / "question_pairs_results.json").read_text())


def test_pairs_are_well_formed():
    assert len({p["id"] for p in PAIRS}) == len(PAIRS)
    assert {p["label"] for p in PAIRS} == {"same", "different"}
    for pair in PAIRS:
        assert pair["a"].strip() and pair["b"].strip() and pair["a"] != pair["b"]


def test_results_cover_the_committed_pairs():
    assert {s["id"] for s in RESULTS["scores"]} == {p["id"] for p in PAIRS}


def test_the_default_merges_no_measured_pair_of_different_questions():
    """Lowering the default below a measured near miss needs a new measurement."""
    different = [s["cosine"] for s in RESULTS["scores"] if s["label"] == "different"]
    assert max(different) < QUESTION_GROUP_THRESHOLD
