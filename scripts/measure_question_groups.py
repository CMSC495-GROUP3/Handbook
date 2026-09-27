"""Measure QUESTION_GROUP_THRESHOLD against labelled question pairs (issue #287).

The What People Ask page merges two wordings into one row when their question
embeddings are within ``QUESTION_GROUP_THRESHOLD`` cosine. This script embeds
``evaluation/question_pairs.json`` with the production embedding model and
reports, for a range of thresholds, how many "same" pairs would stay apart
(missed merges) and how many "different" pairs would merge (false merges).

A false merge is the worse error: it hides a question behind a neighbour that
needs a different answer. Pick the lowest threshold with no false merges, then
check how many missed merges that leaves.

Needs ``OPENAI_API_KEY`` in the environment. Each unique text is embedded once,
in one request, so a run costs a fraction of a cent. The output file holds the
scores only, never the key:

    OPENAI_API_KEY=... python scripts/measure_question_groups.py \\
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
PAIRS = ROOT / "evaluation" / "question_pairs.json"
MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
THRESHOLDS = [round(0.70 + 0.01 * step, 2) for step in range(26)]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def embed(texts: list[str]) -> dict[str, list[float]]:
    response = OpenAI().embeddings.create(model=MODEL, input=texts)
    ordered = sorted(response.data, key=lambda item: item.index)
    return {text: item.embedding for text, item in zip(texts, ordered, strict=True)}


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
    print(f"model {MODEL}, {len(scored)} pairs")
    print(f"same:      {result['same']}")
    print(f"different: {result['different']}")
    print("threshold  missed  false")
    for row in result["sweep"]:
        print(f"{row['threshold']:.2f}       {row['missed_merges']:>3}    {row['false_merges']:>3}")
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
