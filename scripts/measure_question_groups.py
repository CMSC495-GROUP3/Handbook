"""Measure QUESTION_GROUP_THRESHOLD against labelled question pairs (issue #287).

The What People Ask page merges two wordings into one row when their question
embeddings are within ``QUESTION_GROUP_THRESHOLD`` cosine. This script embeds
``evaluation/question_pairs.json`` with the production embedding model and
reports, for a range of thresholds, how many "same" pairs would stay apart
(missed merges) and how many "different" pairs would merge (false merges).

A false merge is the worse error: it hides a question behind a neighbour that
needs a different answer. Pick the lowest threshold with no false merges, then
check how many missed merges that leaves.

With ``--judge``, pairs from each floor in ``FLOORS`` up to
``QUESTION_GROUP_THRESHOLD`` also go to the utility model with the page's
prompt (issue #293), in batches of ``QUESTION_JUDGE_MAX_PAIRS``, closest first.
Each floor is judged separately, so its batches are the ones the page would
send at that floor. The output then scores the combined rule for each floor: a pair
merges at or above the threshold, or from the floor up when the model says it
is one question.

Needs ``OPENAI_API_KEY`` in the environment. Each unique text is embedded once,
in one request, and ``--judge`` adds one chat call per batch for each floor,
about a dozen in all, so a run costs a fraction of a cent. The output file
holds the scores only, never the key:

    OPENAI_API_KEY=... python scripts/measure_question_groups.py --judge \\
        --out evaluation/question_pairs_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sourcebook.rag.config import (  # noqa: E402
    QUESTION_GROUP_THRESHOLD,
    QUESTION_JUDGE_FLOOR,
    QUESTION_JUDGE_MAX_PAIRS,
)
from sourcebook.rag.question_judge import (  # noqa: E402
    QUESTION_JUDGE_PROMPT_VERSION,
    QUESTION_JUDGE_SYSTEM_PROMPT,
    parse_verdicts,
    user_message,
)

PAIRS = ROOT / "evaluation" / "question_pairs.json"
MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
UTILITY_MODEL = os.getenv("OPENAI_UTILITY_MODEL", "gpt-4o-mini")
THRESHOLDS = [round(0.70 + 0.01 * step, 2) for step in range(26)]
FLOORS = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def embed(texts: list[str]) -> dict[str, list[float]]:
    response = OpenAI().embeddings.create(model=MODEL, input=texts)
    ordered = sorted(response.data, key=lambda item: item.index)
    return {text: item.embedding for text, item in zip(texts, ordered, strict=True)}


def judge(scored: list[dict], floor: float) -> dict[str, bool | None]:
    """The model's verdict for every pair from ``floor`` up to the threshold,
    keyed by pair id, in the batches the page would send at that floor. A
    batch whose reply does not parse gives None for its pairs, which the
    combined rule treats as different, as the page does."""
    band = sorted(
        (p for p in scored if floor <= p["cosine"] < QUESTION_GROUP_THRESHOLD),
        key=lambda p: -p["cosine"],
    )
    client = OpenAI()
    verdicts: dict[str, bool | None] = {}
    for start in range(0, len(band), QUESTION_JUDGE_MAX_PAIRS):
        batch = band[start : start + QUESTION_JUDGE_MAX_PAIRS]
        response = client.chat.completions.create(
            model=UTILITY_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": QUESTION_JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message([(p["a"], p["b"]) for p in batch])},
            ],
        )
        parsed = parse_verdicts(response.choices[0].message.content or "", len(batch))
        for index, pair in enumerate(batch):
            verdicts[pair["id"]] = None if parsed is None else parsed[index]
    return verdicts


def combined(scored: list[dict], floor: float, verdicts: dict[str, bool | None]) -> dict:
    """Paraphrase recall and false merges of cosine plus the model at one
    floor, scored with the verdicts judged at that floor."""

    def merges(pair: dict) -> bool:
        if pair["cosine"] >= QUESTION_GROUP_THRESHOLD:
            return True
        return pair["cosine"] >= floor and verdicts.get(pair["id"]) is True

    same = [p for p in scored if p["label"] == "same"]
    false = [p["id"] for p in scored if p["label"] == "different" and merges(p)]
    return {
        "floor": floor,
        "judged": len(verdicts),
        "unparsed": sum(verdict is None for verdict in verdicts.values()),
        "paraphrases_merged": sum(merges(p) for p in same),
        "false_merges": len(false),
        "false_merge_ids": false,
        "verdicts": dict(sorted(verdicts.items())),
    }


def judge_floors(scored: list[dict]) -> list[dict]:
    """Judge and score each floor on its own. A pair near the end of one
    floor's band shares a batch with different neighbours at another floor,
    and the neighbours can change the verdict, so reusing one floor's
    verdicts for the rest would not measure what the page does."""
    return [combined(scored, floor, judge(scored, floor)) for floor in FLOORS]


def sweep(scored: list[dict]) -> list[dict]:
    rows = []
    for threshold in THRESHOLDS:
        missed = [p["id"] for p in scored if p["label"] == "same" and p["cosine"] < threshold]
        false = [p["id"] for p in scored if p["label"] == "different" and p["cosine"] >= threshold]
        rows.append(
            {
                "threshold": threshold,
                "missed_merges": len(missed),
                "false_merges": len(false),
                "false_merge_ids": false,
            }
        )
    return rows


def summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": round(ordered[0], 4),
        "median": round(ordered[len(ordered) // 2], 4),
        "max": round(ordered[-1], 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="Write the scores and sweep as JSON here.")
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Also ask the utility model about pairs below the threshold.",
    )
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2

    pairs = json.loads(PAIRS.read_text())["pairs"]
    texts = sorted({p["a"] for p in pairs} | {p["b"] for p in pairs})
    vectors = embed(texts)
    scored = [{**p, "cosine": round(cosine(vectors[p["a"]], vectors[p["b"]]), 4)} for p in pairs]

    result = {
        "model": MODEL,
        "pairs": len(scored),
        "same": summary([p["cosine"] for p in scored if p["label"] == "same"]),
        "different": summary([p["cosine"] for p in scored if p["label"] == "different"]),
        "sweep": sweep(scored),
        "scores": [
            {"id": p["id"], "label": p["label"], "cosine": p["cosine"]}
            for p in sorted(scored, key=lambda p: -p["cosine"])
        ],
    }
    if args.judge:
        result["judge"] = {
            "model": UTILITY_MODEL,
            "prompt_version": QUESTION_JUDGE_PROMPT_VERSION,
            "threshold": QUESTION_GROUP_THRESHOLD,
            "default_floor": QUESTION_JUDGE_FLOOR,
            "batch_size": QUESTION_JUDGE_MAX_PAIRS,
            "floors": judge_floors(scored),
        }
    print(f"model {MODEL}, {len(scored)} pairs")
    print(f"same:      {result['same']}")
    print(f"different: {result['different']}")
    print("threshold  missed  false")
    for row in result["sweep"]:
        print(f"{row['threshold']:.2f}       {row['missed_merges']:>3}    {row['false_merges']:>3}")
    if args.judge:
        print(f"judge {UTILITY_MODEL}, threshold {QUESTION_GROUP_THRESHOLD}")
        print("floor  judged  paraphrases merged  false merges  unparsed")
        for row in result["judge"]["floors"]:
            print(
                f"{row['floor']:.2f}   {row['judged']:>5}  {row['paraphrases_merged']:>9} of"
                f" {sum(p['label'] == 'same' for p in scored)}  {row['false_merges']:>11}"
                f"  {row['unparsed']:>8}"
            )
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
