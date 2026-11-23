"""Apply the Phase 3 release gate to a baseline/candidate experiment."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def evaluate(experiment: dict[str, object], config: dict[str, object]) -> dict[str, object]:
    thresholds = config["thresholds"]
    baseline = experiment["baseline"]
    candidate = experiment["candidate"]
    baseline_component = baseline["component"]["baseline"]
    candidate_component = candidate["component"]["baseline"]
    baseline_e2e = baseline["end_to_end"]
    candidate_e2e = candidate["end_to_end"]
    baseline_recall = float(baseline_component["recall_at_5"])
    candidate_recall = float(candidate_component["recall_at_5"])
    observed = {
        "baseline_recall_at_5": baseline_recall,
        "candidate_recall_at_5": candidate_recall,
        "recall_at_5_drop": baseline_recall - candidate_recall,
        "candidate_faithfulness": float(candidate_e2e["faithfulness"]),
        "candidate_p95_latency_ms": float(candidate_e2e["latency_ms_p95"]),
        "baseline_abstention_correctness": float(baseline_e2e["abstention_correctness"]),
        "candidate_abstention_correctness": float(candidate_e2e["abstention_correctness"]),
    }
    failures: list[str] = []
    if observed["recall_at_5_drop"] > float(thresholds["recall_at_5_max_drop"]):
        failures.append(
            f"recall@5 drop {observed['recall_at_5_drop']:.4f} exceeds {thresholds['recall_at_5_max_drop']:.4f}"
        )
    if observed["candidate_faithfulness"] < float(thresholds["faithfulness_min"]):
        failures.append(
            f"faithfulness {observed['candidate_faithfulness']:.4f} is below {thresholds['faithfulness_min']:.4f}"
        )
    if observed["candidate_p95_latency_ms"] > float(thresholds["p95_latency_max_ms"]):
        failures.append(
            f"p95 latency {observed['candidate_p95_latency_ms']:.4f}ms exceeds {thresholds['p95_latency_max_ms']:.4f}ms"
        )
    if observed["candidate_abstention_correctness"] < max(
        observed["baseline_abstention_correctness"], float(thresholds["abstention_correctness_min"])
    ):
        failures.append("abstention correctness is lower than the baseline/minimum")
    return {
        "gate": "phase3-release-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "thresholds": thresholds,
        "observed": observed,
        "failures": failures,
        "candidate_configuration": candidate["configuration"],
        "rollout_handoff": experiment.get("rollout_handoff", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the Phase 3 release gate")
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("eval/gate.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        json.loads(args.experiment.read_text(encoding="utf-8")),
        json.loads(args.config.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
