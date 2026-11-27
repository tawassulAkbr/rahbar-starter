"""Component-level retrieval metrics and noise sensitivity evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from offline_common import Passage


def _noise_passages() -> list[Passage]:
    generic = (
        "student policy course academic semester registration university attendance warning "
        "CGPA fee withdrawal grade records FYP approval current handbook"
    )
    return [
        Passage("noise-irrelevant-01.md", "Noise", 1, generic + " cafeteria menu and dining hours", "noise-01"),
        Passage("noise-irrelevant-02.md", "Noise", 1, generic + " campus parking permits", "noise-02"),
        Passage("noise-irrelevant-03.md", "Noise", 1, generic + " sports facility bookings", "noise-03"),
    ]


def _deltas(base: dict[str, object], noisy: dict[str, object]) -> dict[str, float | None]:
    metrics = ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")
    return {
        metric: (
            float(noisy[metric]) - float(base[metric])
            if base.get(metric) is not None and noisy.get(metric) is not None else None
        )
        for metric in metrics
    }


def run_component_level(corpus_dir: Path, golden_path: Path, seed: int = 2026, top_k: int = 5) -> dict[str, object]:
    from runtime import component
    return component(golden_path, seed, top_k)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 component-level retrieval checks")
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run_component_level(args.corpus, args.golden)
    rendered = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
