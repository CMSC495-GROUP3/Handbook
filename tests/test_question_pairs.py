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


# Different pairs one word apart that clear 0.85 on cosine alone, found by the
# pairs added for #293: HSA versus FSA (0.862), and sick versus a sick child
# (0.907). Raising the threshold past them is a separate decision; see
# docs/evaluation.md.
KNOWN_COSINE_FALSE_MERGES = {"diff_56", "diff_58"}


def test_the_default_merges_no_other_measured_pair_of_different_questions():
    """Lowering the default below a measured near miss needs a new measurement."""
    merged = {
        s["id"]
        for s in RESULTS["scores"]
        if s["label"] == "different" and s["cosine"] >= QUESTION_GROUP_THRESHOLD
    }
    assert merged == KNOWN_COSINE_FALSE_MERGES
