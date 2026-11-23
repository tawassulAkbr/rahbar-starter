"""End-to-end answer-quality metrics for the offline reference harness."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from metrics import average, percentile, tokens
from offline_common import LexicalRetriever, load_passages
from run_eval import load_golden


def _faithful(answer: str, context: str) -> bool:
    answer_terms = tokens(answer) - {"the", "a", "an", "is", "are", "answer", "based", "on"}
    return bool(answer_terms) and len(answer_terms & tokens(context)) / len(answer_terms) >= 0.5


def run_e2e_level(corpus_dir: Path, golden_path: Path, seed: int = 2026, top_k: int = 5) -> dict[str, object]:
    from runtime import end_to_end
    return end_to_end(golden_path, seed, top_k)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 end-to-end answer checks")
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run_e2e_level(args.corpus, args.golden)
    rendered = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
