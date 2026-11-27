"""Run the complete Part B suite against a deployed Kubernetes API.

The module and retrieval checks use the same configured Ollama/Chroma runtime
as the API. End-to-end questions go through the target Service so traces and
latencies represent the deployed API. The first run establishes a measured
baseline on the shared results volume; later runs and candidate Jobs compare
against it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from component_level import run_component_level
from module_level import run_module_level


def run_suite(api: str, golden: Path, baseline: Path, trace_path: Path,
              out: Path, seed: int = 2026, *, bootstrap_baseline: bool = False) -> dict[str, object]:
    out.parent.mkdir(parents=True, exist_ok=True)
    golden_rows = [json.loads(line) for line in golden.read_text(encoding="utf-8").splitlines() if line.strip()]
    runs: list[dict[str, object]] = []
    for run_number in (1, 2):
        print(f"Part B run {run_number}/2: module embeddings", flush=True)
        module = run_module_level(seed=seed)
        print(f"Part B run {run_number}/2: component retrieval", flush=True)
        component = run_component_level(Path("/data/corpus"), golden, seed=seed,
                                        top_k=int(os.environ.get("TOP_K", "5")))
        out.with_name(f'{out.stem}-levels-run-{run_number}.json').write_text(
            json.dumps({'module': module, 'component': component}, indent=2) + '\n',
            encoding='utf-8')

        answer_out = out.with_name(f"{out.stem}-answers-run-{run_number}.json")
        command = [sys.executable, '-u', str(Path(__file__).with_name("run_eval.py")),
                   "--api", api, "--golden", str(golden), "--baseline", str(baseline),
                   "--trace-path", str(trace_path), "--out", str(answer_out),
                   # The provider can try twice. Include retrieval and HTTP
                   # overhead instead of timing out at the retry boundary.
                   "--request-timeout", os.environ.get(
                       "EVAL_REQUEST_TIMEOUT",
                       str(max(600, 2 * float(os.environ.get('EMBED_TIMEOUT', '300')) + 120)))]
        if bootstrap_baseline and not baseline.exists():
            command.append("--update-baseline")
        completed = subprocess.run(command, check=False)
        if not answer_out.exists():
            raise RuntimeError(f"end-to-end evaluator exited {completed.returncode} without writing {answer_out}")
        answers = json.loads(answer_out.read_text(encoding="utf-8"))
        runs.append({"run": run_number, "module": module, "component": component,
                     "end_to_end": answers, "gate_exit_code": completed.returncode})

    first, second = runs
    metric_names = ("mean_paraphrase_cosine", "mean_unrelated_cosine", "paraphrase_unrelated_gap",
                    "embedding_time_ms_per_chunk", "determinism_largest_abs_difference", "recall_at_3", "recall_at_5", "mrr",
                    "ndcg_at_5", "faithfulness", "abstention_rate", "citation_validity",
                    "latency_ms_p50", "latency_ms_p95")
    def value(run: dict[str, object], name: str) -> object:
        if name in run["module"]:
            return run["module"].get(name)
        if name in run["component"]["baseline"]:
            return run["component"]["baseline"].get(name)
        return run["end_to_end"].get(name)

    deltas = {}
    for name in metric_names:
        left, right = value(first, name), value(second, name)
        deltas[name] = (float(right) - float(left)
                        if isinstance(left, (int, float)) and isinstance(right, (int, float)) else None)

    summary = {
        "module": first["module"],
        "component": first["component"]["baseline"],
        "component_noise": first["component"]["noise_test"],
        "end_to_end": {key: first["end_to_end"].get(key) for key in
                       ("faithfulness", "abstention_rate", "citation_validity", "latency_ms_p50", "latency_ms_p95")},
    }
    result: dict[str, object] = {
        "suite": "rahbar-assignment-03-part-b-kubernetes",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "golden": str(golden),
        "golden_questions": len(golden_rows),
        "configuration": {"collection": os.environ.get("CHROMA_COLLECTION", "rahbar"),
                          "embed_model": os.environ.get("EMBED_MODEL", "nomic-embed-text"),
                          "generator": os.environ.get("LLM_MODEL", "llama3.2:3b"),
                          "top_k": int(os.environ.get("TOP_K", "5"))},
        "runs": runs,
        "stochasticity": {"same_seed": True, "metric_deltas_run_2_minus_run_1": deltas},
        "summary_table": summary,
        "gate_status": "PASS" if all(run["gate_exit_code"] == 0 for run in runs) else "FAIL",
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all Assignment 03 Part B levels against a Kubernetes API")
    parser.add_argument("--api", required=True)
    parser.add_argument("--golden", type=Path, default=Path("/workspace/eval/golden.jsonl"))
    parser.add_argument("--baseline", type=Path, default=Path("/results/part-b-baseline.json"))
    parser.add_argument("--trace-path", type=Path, default=Path("/data/traces/traces.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("/results/eval-results.json"))
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--bootstrap-baseline", action="store_true",
                        help="replace an earlier measured baseline before this baseline Job")
    args = parser.parse_args()
    settings = get_settings()
    if settings.retriever != "chroma" or settings.llm_provider == "stub":
        print("Part B Kubernetes evaluation requires Chroma and a real LLM provider; "
              "the dev stub overlay is wiring-only.", file=sys.stderr)
        return 2
    if args.bootstrap_baseline:
        args.baseline.unlink(missing_ok=True)
    result = run_suite(args.api, args.golden, args.baseline, args.trace_path, args.out, args.seed,
                       bootstrap_baseline=args.bootstrap_baseline)
    print(json.dumps({"gate_status": result["gate_status"], "summary_table": result["summary_table"]}, indent=2))
    return 0 if result["gate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
