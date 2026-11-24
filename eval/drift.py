"""Compare the Phase 2 suite before and after adding Batch B.

The before corpus is the committed corpus with ``corpus/batch-b`` excluded;
the after corpus is the full corpus. The script copies only the files needed
for the deterministic reference harness into a disposable repository-local directory, so the
working tree is never mutated during the comparison.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from run_offline_suite import run_suite


def run_drift(corpus: Path, golden: Path) -> dict:
    workspace = Path(".phase5-drift-work")
    if workspace.exists():
        shutil.rmtree(workspace)
    before = workspace / "before"
    before.mkdir(parents=True)
    try:
        for source in corpus.iterdir():
            if source.name == "batch-b":
                continue
            target = before / source.name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        baseline = run_suite(before, golden)
        after = run_suite(corpus, golden)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    baseline_component = baseline["summary_table"][1]["metrics"]
    after_component = after["summary_table"][1]["metrics"]
    baseline_e2e = baseline["summary_table"][2]["metrics"]
    after_e2e = after["summary_table"][2]["metrics"]
    keys = ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")
    e2e_keys = ("faithfulness", "abstention_correctness", "citation_validity")
    return {
        "suite": "rahbar-phase-5-drift",
        "golden_questions": after["golden_questions"],
        "before": {"corpus": "corpus excluding corpus/batch-b", "suite": baseline},
        "after": {"corpus": str(corpus), "suite": after},
        "metric_deltas_after_minus_before": {
            "component": {key: float(after_component[key]) - float(baseline_component[key]) for key in keys},
            "end_to_end": {key: float(after_e2e[key]) - float(baseline_e2e[key]) for key in e2e_keys},
        },
        "batch_b_change_explanation": {
            "documents_added": len(list((corpus / "batch-b").glob("*"))) - 1,
            "reason": "Batch B introduces verified policy passages and planted quality/security cases; the deterministic suite records whether retrieval and answer metrics shift.",
            "phase1_counters_reference": {
                "unchanged_embedded_chunks": 0,
                "orphan_chunks_removed": 0,
                "source": "Phase 1 lifecycle contract: unchanged ingestion embeds zero and deleted documents leave zero orphan chunks",
                "note": "These are lifecycle counters, not simulated by the dependency-free drift harness; confirm the live Job report separately.",
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_drift(args.corpus, args.golden)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["metric_deltas_after_minus_before"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
