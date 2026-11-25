"""Run all Phase 2 offline levels twice and write a timestamped JSON result."""

from __future__ import annotations

import argparse
import json
import hashlib
import random
import os
from datetime import datetime, timezone
from pathlib import Path

from component_level import run_component_level
from e2e_level import run_e2e_level
from module_level import run_module_level
from run_eval import load_golden


def _metric_delta(first: dict[str, object], second: dict[str, object], metrics: tuple[str, ...]) -> dict[str, float | None]:
    return {
        metric: (float(second[metric]) - float(first[metric])
                 if first.get(metric) is not None and second.get(metric) is not None else None)
        for metric in metrics
    }


def run_suite(corpus_dir: Path, golden_path: Path, seed: int = 2026,
              top_k: int = 5, checkpoint_dir: Path | None = None) -> dict[str, object]:
    random.seed(seed)
    golden = load_golden(golden_path)
    def run_once(number):
        random.seed(seed)
        result = {}
        stages = {
            'module': lambda: run_module_level(seed=seed),
            'component': lambda: run_component_level(corpus_dir, golden_path, seed=seed, top_k=top_k),
            'end_to_end': lambda: run_e2e_level(corpus_dir, golden_path, seed=seed, top_k=top_k),
        }
        previous = os.environ.get('EVAL_ANSWER_CHECKPOINT')
        try:
            if checkpoint_dir:
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
                os.environ['EVAL_ANSWER_CHECKPOINT'] = str(checkpoint_dir / f'answers-run-{number}.json')
            for stage, execute in stages.items():
                print(f'run={number} top_k={top_k} stage={stage}', flush=True)
                result[stage] = execute()
                if checkpoint_dir:
                    (checkpoint_dir / f'run-{number}-{stage}.json').write_text(
                        json.dumps(result[stage], indent=2), encoding='utf-8')
        finally:
            if previous is None:
                os.environ.pop('EVAL_ANSWER_CHECKPOINT', None)
            else:
                os.environ['EVAL_ANSWER_CHECKPOINT'] = previous
        return result
    first = run_once(1)
    second = run_once(2)
    return {
        "suite": "rahbar-phase-2-offline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "golden": str(golden_path),
        "golden_questions": len(golden),
        "golden_sha256": hashlib.sha256(golden_path.read_bytes()).hexdigest(),
        "configuration": {"collection": os.environ.get('CHROMA_COLLECTION', 'rahbar'),
                          "embedding_model": os.environ.get('EMBED_MODEL', 'nomic-embed-text'),
                          "generator": os.environ.get('LLM_MODEL', 'llama3.2:3b'), "top_k": top_k,
                          "temperature": float(os.environ.get('TEMPERATURE', '0.2')),
                          "max_output_tokens": int(os.environ.get('MAX_OUTPUT_TOKENS', '384')),
                          "embedding_version": first['module'].get('model_version'),
                          "cache": "disabled; direct serving answer function"},
        "runs": {"run_1": first, "run_2": second},
        "stochasticity": {
            "same_seed": True,
            "metric_deltas_run_2_minus_run_1": {
                "module": _metric_delta(first["module"], second["module"], (
                    "mean_paraphrase_cosine", "mean_unrelated_cosine", "paraphrase_unrelated_gap",
                    "embedding_time_ms_per_text", "embedding_time_ms_per_chunk", "determinism_largest_abs_difference")),
                "component": _metric_delta(first["component"]["baseline"], second["component"]["baseline"], (
                    "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")),
                "component_noise": _metric_delta(first['component']['noise_test']['metrics'], second['component']['noise_test']['metrics'],
                                                 ('recall_at_3', 'recall_at_5', 'mrr', 'ndcg_at_5')),
                "end_to_end": _metric_delta(first["end_to_end"], second["end_to_end"], (
                    "faithfulness", "abstention_correctness", "citation_validity", "latency_ms_p50", "latency_ms_p95")),
            },
            "explanation": "Serving implementation uses a fixed seed and question order; model runtime, scheduling, and warm-up can still vary latency.",
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
    parser.add_argument('--top-k', type=int, default=5)
    args = parser.parse_args()
    output = args.out or Path("eval/results") / f"offline-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    if args.top_k < 1:
        parser.error('--top-k must be positive')
    result = run_suite(args.corpus, args.golden, args.seed, args.top_k, output.with_suffix(''))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"offline suite result: {output}")
    print(json.dumps(result["summary_table"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
