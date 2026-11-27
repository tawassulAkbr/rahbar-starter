"""Run the Phase 3 one-change baseline/candidate experiment.

The selected change is retrieval top-k: baseline 5 versus candidate 4. The
candidate is intentionally small so the release gate can demonstrate both a
passing and a deliberately bad top-k candidate.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from component_level import run_component_level
from e2e_level import run_e2e_level
from module_level import run_module_level


def _metric_delta(baseline: dict[str, object], candidate: dict[str, object], metrics: tuple[str, ...]) -> dict[str, float | None]:
    return {
        metric: (float(candidate[metric]) - float(baseline[metric])
                 if baseline.get(metric) is not None and candidate.get(metric) is not None else None)
        for metric in metrics
    }


def _run_variant(corpus: Path, golden: Path, seed: int, top_k: int) -> dict[str, object]:
    return {
        "configuration": {
            "change": "retrieval_top_k",
            "top_k": top_k,
            "embed_model": os.environ.get("EMBED_MODEL", "nomic-embed-text"),
            "collection": os.environ.get("CHROMA_COLLECTION", "rahbar"),
        },
        "module": run_module_level(seed=seed),
        "component": run_component_level(corpus, golden, seed=seed, top_k=top_k),
        "end_to_end": run_e2e_level(corpus, golden, seed=seed, top_k=top_k),
    }


def run_change_experiment(
    corpus: Path,
    golden: Path,
    baseline_top_k: int = 5,
    candidate_top_k: int = 4,
    seed: int = 2026,
    candidate_image: str = "rahbar-api:phase3-topk4",
    collection: str = "rahbar",
) -> dict[str, object]:
    baseline = _run_variant(corpus, golden, seed, baseline_top_k)
    candidate = _run_variant(corpus, golden, seed, candidate_top_k)
    return {
        "experiment": "phase3-retrieval-top-k",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "justification": "Phase 2 measured retrieval quality and noise sensitivity; top-k=4 tests whether a smaller candidate context preserves recall while reducing candidate context size.",
        "baseline": baseline,
        "candidate": candidate,
        "comparison": {
            "module": _metric_delta(baseline["module"], candidate["module"], (
                "mean_paraphrase_cosine", "mean_unrelated_cosine", "paraphrase_unrelated_gap")),
            "component": _metric_delta(baseline["component"]["baseline"], candidate["component"]["baseline"], (
                "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")),
            "end_to_end": _metric_delta(baseline["end_to_end"], candidate["end_to_end"], (
                "faithfulness", "abstention_correctness", "citation_validity", "latency_ms_p50", "latency_ms_p95")),
        },
        "rollout_handoff": {
            "candidate_image": candidate_image,
            "collection": candidate['configuration']['collection'],
            "embed_model": candidate['configuration']['embed_model'],
            "embed_dimension": 768,
            "change": f"TOP_K={candidate_top_k}",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 3 baseline/candidate experiment")
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--baseline-top-k", type=int, default=5)
    parser.add_argument("--candidate-top-k", type=int, default=4)
    parser.add_argument("--candidate-image", default="rahbar-api:phase3-topk4")
    parser.add_argument("--collection", default="rahbar")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", type=Path, default=Path("eval/results/change-topk4.json"))
    args = parser.parse_args()
    if args.baseline_top_k <= 0 or args.candidate_top_k <= 0:
        parser.error("top-k values must be positive")
    result = run_change_experiment(
        args.corpus, args.golden, args.baseline_top_k, args.candidate_top_k,
        args.seed, args.candidate_image, args.collection,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"change experiment result: {args.out}")
    print(json.dumps(result["comparison"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
