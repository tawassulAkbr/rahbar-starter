"""Compare two real collections indexed before and after ingesting Batch B.

The serving suite reads Chroma, so copying local corpus files cannot change
the evaluated data. Seed distinct collections using ingestion Jobs first.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from run_offline_suite import run_suite


def run_drift(corpus: Path, golden: Path, before_collection: str, after_collection: str) -> dict:
    if not before_collection or not after_collection or before_collection == after_collection:
        raise ValueError("Drift requires distinct before/after collections seeded by ingestion Jobs")
    original = os.environ.get("CHROMA_COLLECTION")
    try:
        os.environ["CHROMA_COLLECTION"] = before_collection
        baseline = run_suite(corpus, golden)
        os.environ["CHROMA_COLLECTION"] = after_collection
        after = run_suite(corpus, golden)
    finally:
        if original is None:
            os.environ.pop("CHROMA_COLLECTION", None)
        else:
            os.environ["CHROMA_COLLECTION"] = original
    baseline_component = baseline["summary_table"][1]["metrics"]
    after_component = after["summary_table"][1]["metrics"]
    baseline_e2e = baseline["summary_table"][2]["metrics"]
    after_e2e = after["summary_table"][2]["metrics"]
    keys = ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")
    e2e_keys = ("faithfulness", "abstention_correctness", "citation_validity")
    return {
        "suite": "rahbar-phase-5-drift",
        "golden_questions": after["golden_questions"],
        "before": {"collection": before_collection, "suite": baseline},
        "after": {"collection": after_collection, "suite": after},
        "metric_deltas_after_minus_before": {
            "component": {key: float(after_component[key]) - float(baseline_component[key]) for key in keys},
            "end_to_end": {key: float(after_e2e[key]) - float(baseline_e2e[key]) for key in e2e_keys},
        },
        "batch_b_change_explanation": {
            "documents_added": len(list((corpus / "batch-b").glob("*"))) - 1,
            "reason": "The real serving suite compares independently indexed pre-Batch-B and post-Batch-B collections. Consult ingestion reports for measured lifecycle counters.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--before-collection", required=True)
    parser.add_argument("--after-collection", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_drift(args.corpus, args.golden, args.before_collection, args.after_collection)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["metric_deltas_after_minus_before"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
