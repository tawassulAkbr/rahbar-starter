"""Run all Phase 2 offline levels twice and write a timestamped JSON result."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from component_level import run_component_level
from e2e_level import run_e2e_level
from module_level import run_module_level
from offline_common import load_golden


def _metric_delta(first: dict[str, object], second: dict[str, object], metrics: tuple[str, ...]) -> dict[str, float | None]:
    return {
        metric: (float(second[metric]) - float(first[metric])
                 if first.get(metric) is not None and second.get(metric) is not None else None)
        for metric in metrics
    }


def run_suite(corpus_dir: Path, golden_path: Path, seed: int = 2026) -> dict[str, object]:
    golden = load_golden(golden_path)
    first = {
        "module": run_module_level(seed=seed),
        "component": run_component_level(corpus_dir, golden_path, seed=seed),
        "end_to_end": run_e2e_level(corpus_dir, golden_path, seed=seed),
    }
    second = {
        "module": run_module_level(seed=seed),
        "component": run_component_level(corpus_dir, golden_path, seed=seed),
        "end_to_end": run_e2e_level(corpus_dir, golden_path, seed=seed),
    }
    return {
        "suite": "rahbar-phase-2-offline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "golden": str(golden_path),
        "golden_questions": len(golden),
        "runs": {"run_1": first, "run_2": second},
        "stochasticity": {
            "same_seed": True,
            "metric_deltas_run_2_minus_run_1": {
                "module": _metric_delta(first["module"], second["module"], (
                    "mean_paraphrase_cosine", "mean_unrelated_cosine", "paraphrase_unrelated_gap",
                    "embedding_time_ms_per_text")),
                "component": _metric_delta(first["component"]["baseline"], second["component"]["baseline"], (
                    "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")),
                "end_to_end": _metric_delta(first["end_to_end"], second["end_to_end"], (
                    "faithfulness", "abstention_correctness", "citation_validity", "latency_ms_p50", "latency_ms_p95")),
            },
            "explanation": "The deterministic local reference harness uses a fixed fixture order and seed; timing may vary slightly on different machines.",
        },
        "summary_table": [
            {"level": "module", "metrics": first["module"]},
            {"level": "component", "metrics": first["component"]["baseline"], "noise_deltas": first["component"]["noise_test"]["deltas"]},
            {"level": "end_to_end", "metrics": {key: first["end_to_end"][key] for key in (
                "faithfulness", "abstention_correctness", "citation_validity", "latency_ms_p50", "latency_ms_p95")}},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all Phase 2 offline tests")
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    output = args.out or Path("eval/results") / f"offline-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    result = run_suite(args.corpus, args.golden, args.seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"offline suite result: {output}")
    print(json.dumps(result["summary_table"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
