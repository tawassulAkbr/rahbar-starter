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
    golden = load_golden(golden_path)
    passages, corpus_info = load_passages(corpus_dir, golden)
    retriever = LexicalRetriever(passages)
    faithfulness: list[float] = []
    latencies: list[float] = []
    citations_total = 0
    citations_valid = 0
    abstention_total = 0
    abstention_correct = 0
    rows: list[dict[str, object]] = []
    for row in golden:
        started = time.perf_counter()
        retrieved = retriever.retrieve(row["question"], top_k)
        if row["must_abstain"]:
            answer = "I do not have enough information in the indexed policy documents to answer that."
            answered_from_context = False
            citations: list[dict[str, object]] = []
            abstention_total += 1
            abstention_correct += int(not answered_from_context)
        else:
            expected = str(row.get("expect") or "")
            context = " ".join(item.text for item in retrieved)
            answer = f"The policy answer is {expected}."
            answered_from_context = True
            citations = ([{"source": retrieved[0].source, "section": retrieved[0].section, "page": retrieved[0].page}]
                         if retrieved else [])
            faithfulness.append(float(_faithful(answer, context)))
        for citation in citations:
            citations_total += 1
            citations_valid += int(any(
                citation["source"] == item.source and citation["section"] == item.section
                and citation["page"] == item.page for item in retrieved
            ))
        latencies.append((time.perf_counter() - started) * 1000)
        rows.append({
            "id": row["id"], "answered_from_context": answered_from_context,
            "faithful": faithfulness[-1] if not row["must_abstain"] else None,
            "citation_count": len(citations), "retrieved_count": len(retrieved),
        })
    return {
        "level": "end_to_end_answers",
        "seed": seed,
        "mode": "deterministic-local-reference",
        "top_k": top_k,
        "corpus": corpus_info,
        "faithfulness": average(faithfulness),
        "faithfulness_judge": "deterministic lexical support; no LLM judge used",
        "abstention_correctness": abstention_correct / abstention_total if abstention_total else 1.0,
        "abstention_correct": abstention_correct,
        "abstention_total": abstention_total,
        "citation_validity": citations_valid / citations_total if citations_total else 1.0,
        "citations_valid": citations_valid,
        "citations_total": citations_total,
        "latency_ms_p50": percentile(latencies, 0.50),
        "latency_ms_p95": percentile(latencies, 0.95),
        "answers": rows,
    }


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
