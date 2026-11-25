"""Measure live-query coverage against the reviewed golden set.

The default threshold is 0.35 cosine similarity from the deterministic Phase 2
embedder. It is intentionally recorded in the output so the result is reproducible.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from metrics import cosine
from module_level import DeterministicEmbedder


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_coverage(golden: list[dict], live: list[dict], threshold: float = 0.35) -> dict:
    embed = DeterministicEmbedder()
    golden_text = [str(row.get("question", "")) for row in golden]
    golden_vectors = embed(golden_text)
    details = []
    for query in live:
        vector = embed([query["query"]])[0]
        scored = sorted(
            ((cosine(vector, candidate), index) for index, candidate in enumerate(golden_vectors)),
            key=lambda item: item[0], reverse=True,
        )
        score, index = scored[0]
        nearest = golden[index]
        details.append({
            "id": query["id"], "query": query["query"], "topic": query.get("topic", "unknown"),
            "nearest_golden_id": nearest["id"], "nearest_golden_question": nearest["question"],
            "similarity": round(score, 6), "covered": score >= threshold,
        })
    uncovered = [item for item in details if not item["covered"]]
    grouped = defaultdict(list)
    for item in uncovered:
        grouped[item["topic"]].append(item["id"])
    return {
        "threshold": threshold,
        "threshold_justification": "0.35 is fixed before comparison: it is a conservative cosine cutoff for the Phase 2 deterministic-hash reference and makes uncovered-topic gaps visible.",
        "live_queries": len(live),
        "covered_queries": len(details) - len(uncovered),
        "coverage": (len(details) - len(uncovered)) / len(details) if details else 0.0,
        "uncovered_count": len(uncovered),
        "uncovered_queries": uncovered,
        "uncovered_topics": dict(sorted(grouped.items())),
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--live", type=Path, default=Path("eval/live_queries.jsonl"))
    parser.add_argument("--threshold", type=float,
                        default=float(os.environ.get("COVERAGE_SIMILARITY_THRESHOLD", "0.35")))
    parser.add_argument("--exclude-id-prefix", help="exclude golden ids with this prefix for before/after comparisons")
    parser.add_argument("--fail-under", type=float,
                        default=float(os.environ.get("COVERAGE_THRESHOLD", "0.85")))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    golden = load_jsonl(args.golden)
    if args.exclude_id_prefix:
        golden = [row for row in golden if not str(row.get("id", "")).startswith(args.exclude_id_prefix)]
    result = run_coverage(golden, load_jsonl(args.live), args.threshold)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("threshold", "live_queries", "covered_queries", "coverage", "uncovered_count")}, indent=2))
    if args.fail_under is not None and result["coverage"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
