#!/usr/bin/env python3
"""Score a running RAHBAR against a golden set, and gate CI on the result (section 5).

    python eval/run_eval.py --api http://<ingress>                 # your corpus
    python eval/run_eval.py --api ... --fixtures                    # CI fixtures
    python eval/run_eval.py --api ... --golden eval/fixtures/golden.fixture.yaml
    python eval/run_eval.py --api ... --update-baseline            # after a deliberate improvement

Exit code 0 when every gate passes, 1 when any fails. CI relies on that exit code.

Given: talking to the API, reading the golden set, writing results.json, the exit
code. The evaluation logic is implemented below and is covered by the API and
fixture test suites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent

# The gate from section 5.4. Change these only with a reason written in docs/PIPELINE.md.
MAX_RECALL5_DROP = float(os.environ.get("GATE_RECALL5_MAX_DROP", "0.05"))
MIN_CITATION_VALIDITY = float(os.environ.get("GATE_CITATION_MIN", "0.95"))
MIN_FAITHFULNESS = float(os.environ.get("GATE_FAITHFULNESS_MIN", "0.90"))
MAX_P95_LATENCY_MS = float(os.environ.get("GATE_P95_MAX_MS", "180000"))
REQUIRED_ABSTENTION = float(os.environ.get("GATE_ABSTENTION_MIN", "1.0"))


def load_golden(path: Path, *, fixture: bool = False) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        questions = _load_jsonl_golden(path)
    else:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        questions = data.get("questions") or []
    if not questions:
        sys.exit(f"no questions in {path}")
    # The production golden set follows section 5.1's 15-question contract.
    # CI deliberately uses a smaller six-question fixture corpus so the Kind
    # smoke test stays fast; it still exercises every evaluator question type.
    minimum_questions = 6 if fixture else 15
    required_types = (
        {"ordinary": 1, "version": 2, "exact": 1, "abstain": 1, "injection": 1}
        if fixture
        else {"ordinary": 8, "version": 2, "exact": 2, "abstain": 2, "injection": 1}
    )
    counts = {kind: sum(q.get("type") == kind for q in questions) for kind in required_types}
    missing = [f"{kind}>={minimum}" for kind, minimum in required_types.items()
               if counts[kind] < minimum]
    if len(questions) < minimum_questions or missing:
        sys.exit(f"golden set must contain at least {minimum_questions} questions with {missing}")
    ids = [q.get("id") for q in questions]
    if any(not question_id for question_id in ids) or len(set(ids)) != len(ids):
        sys.exit("golden question ids must be present and unique")
    for question in questions:
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            sys.exit(f"question {question.get('id')} has no question text")
        if question.get("must_abstain", False) and question.get("relevant"):
            sys.exit(f"abstention question {question['id']} cannot have relevant passages")
    return questions


def _load_jsonl_golden(path: Path) -> list[dict]:
    """Load the Assignment 03 JSONL contract and normalize it for the evaluator."""
    allowed_types = {"answerable", "unanswerable", "hard"}
    allowed_labels = {"human", "synthetic"}
    allowed_categories = {"ordinary", "version", "exact", "abstain", "injection"}
    questions: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.exit(f"invalid JSONL golden line {line_number}: {exc}")
        if not isinstance(item, dict):
            sys.exit(f"golden line {line_number} must be a JSON object")
        missing = [field for field in ("id", "question", "type", "source", "page", "label", "reviewed")
                   if field not in item]
        if missing:
            sys.exit(f"golden line {line_number} is missing fields: {missing}")
        if item["type"] not in allowed_types:
            sys.exit(f"golden line {line_number} has invalid type: {item['type']}")
        if item["label"] not in allowed_labels or not isinstance(item["reviewed"], bool):
            sys.exit(f"golden line {line_number} has invalid label/reviewed fields")
        if item["type"] != "unanswerable" and (not isinstance(item["source"], str) or not isinstance(item["page"], int) or item["page"] < 1):
            sys.exit(f"golden line {line_number} needs a source and positive page")
        if item["type"] == "unanswerable" and (item["source"] is not None or item["page"] is not None):
            sys.exit(f"golden line {line_number} unanswerable entries must have null source/page")
        category = item.get("category")
        if category is not None and category not in allowed_categories:
            sys.exit(f"golden line {line_number} has invalid category: {category}")
        normalized_type = category or {
            "answerable": "ordinary", "unanswerable": "abstain", "hard": "ordinary"
        }[item["type"]]
        relevant = [] if item["type"] == "unanswerable" else [{
            "source": item["source"], "page": item["page"],
            "section": item.get("section", "Unsectioned"),
        }]
        questions.append({
            **item,
            "original_type": item["type"],
            "type": normalized_type,
            "relevant": relevant,
            "must_abstain": item["type"] == "unanswerable",
        })
    ids = [question["id"] for question in questions]
    if len(questions) < 25 or len(set(ids)) != len(ids):
        sys.exit("JSONL golden set must contain at least 25 unique questions")
    counts = {kind: sum(question.get("type") == kind for question in questions)
              for kind in ("ordinary", "version", "exact", "abstain", "injection")}
    if counts["abstain"] < 5:
        sys.exit("JSONL golden set requires at least 5 unanswerable questions")
    if sum(question.get("source") is not None for question in questions if not question["must_abstain"]) < 15:
        sys.exit("JSONL golden set requires at least 15 answerable questions with sources")
    hard_count = sum(question.get("original_type") == "hard" for question in questions)
    if hard_count < 5:
        sys.exit("JSONL golden set requires at least 5 hard questions")
    if sum(question["label"] == "human" for question in questions) < 8:
        sys.exit("JSONL golden set requires at least 8 human-written questions")
    if sum(question["label"] == "synthetic" and question["reviewed"] for question in questions) < 8:
        sys.exit("JSONL golden set requires at least 8 reviewed synthetic questions")
    return questions


def ask(client: httpx.Client, api: str, question: str) -> dict:
    """POST one question and return the AskResponse as a dict (see api/app/schemas.py)."""
    response = client.post(f"{api.rstrip('/')}/api/ask", json={"question": question})
    response.raise_for_status()
    return response.json()


def validate_production_response(response: dict, question_id: str) -> None:
    """Prevent a full-corpus report from being generated by the offline stub."""
    if response.get("provider") == "stub":
        raise RuntimeError(
            f"{question_id}: full-corpus evaluation received provider=stub; "
            "configure a real LLM provider before recording production evidence"
        )
    retrieved = response.get("retrieved") or []
    if any(item.get("source") == "stub-handbook.pdf" for item in retrieved):
        raise RuntimeError(
            f"{question_id}: full-corpus evaluation received stub retrieval passages; "
            "set RETRIEVER=chroma and index the real corpus first"
        )


def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None:
    """Fraction of the relevant (source, section) pairs found in the top k retrieved.
    Return None when the question has no relevant passages (must-abstain questions)."""
    # Golden files may identify a passage by chunk_id or by its stable source /
    # section metadata. Use the same identity scheme for both sides. The old
    # implementation always preferred a returned chunk_id, which made a valid
    # source/section golden entry score zero whenever chunking was enabled.
    by_chunk = bool(relevant) and all(item.get("chunk_id") is not None for item in relevant)

    def key(item: dict) -> tuple[object, ...]:
        if by_chunk:
            return (item.get("chunk_id"),)
        return (item.get("source"), item.get("section"))

    expected = {key(item) for item in relevant}
    expected.discard((None, None))
    if not expected:
        return None
    actual = {key(item) for item in retrieved[:k]}
    return len(expected & actual) / len(expected)


def citation_validity(response: dict) -> float | None:
    """Fraction of the response's citations that match a passage in response['retrieved'].
    Return None when there are no citations."""
    citations = response.get("citations") or []
    retrieved = response.get("retrieved") or []
    if not citations:
        return None
    allowed = {
        (item.get("source"), item.get("section"), item.get("page"))
        for item in retrieved
    }
    valid = sum(
        (item.get("source"), item.get("section"), item.get("page")) in allowed
        for item in citations
    )
    return valid / len(citations)


def trace_for_id(path: Path, trace_id: str) -> dict | None:
    """Find the trace emitted for a request; traces hold the exact retrieved context."""
    if not trace_id or not path.is_file():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate a partially written final line
        if record.get("trace_id") == trace_id:
            return record
    return None


def faithfulness(response: dict, trace: dict | None) -> float | None:
    """Conservative lexical support proxy, with numeric claims required verbatim.

    This is not a semantic entailment judge. Missing trace evidence scores zero.
    """
    if not response.get("answered_from_context"):
        return None  # Abstention correctness is measured separately.
    if trace is None:
        return 0.0
    answer = response.get("answer", "")
    context = " ".join(trace.get("context") or [])
    def words(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.lower()))
    answer_terms = words(answer) - {"the", "a", "an", "is", "are", "was", "were", "of", "to", "and", "in", "on", "for", "from", "with", "based"}
    if not answer_terms:
        return 0.0
    overlap = len(answer_terms & words(context)) / len(answer_terms)
    number_pattern = r"\b\d+(?:\.\d+)?\s*(?:%|percent)?"
    def normalize_number(value: str) -> str:
        return re.sub(r"\s*(?:%|percent)$", "", value.strip(), flags=re.I)
    numbers = {normalize_number(value) for value in re.findall(number_pattern, answer, re.I)}
    context_numbers = {normalize_number(value) for value in re.findall(number_pattern, context, re.I)}
    return float(overlap >= 0.8 and numbers <= context_numbers)


def abstention_correctness(
    results: list[dict], golden_data: list[dict] | None = None
) -> dict[str, int | float]:
    """Measure false `answered_from_context` for every golden abstention question."""
    if golden_data is None:
        rows = results
    else:
        golden_by_id = {row["id"]: row for row in golden_data}
        rows = [
            {
                "must_abstain": bool(golden_by_id.get(row.get("id"), {}).get("must_abstain")),
                "response": row.get("response", row),
            }
            for row in results
        ]
    abstentions = [row for row in rows if row["must_abstain"]]
    correct = sum(not row["response"].get("answered_from_context", True)
                  for row in abstentions)
    total = len(abstentions)
    return {
        "correct": correct,
        "incorrect": total - correct,
        "total": total,
        "rate": correct / total if total else 1.0,
    }


def summarise(rows: list[dict]) -> dict:
    """Overall recall@3, recall@5, citation validity and abstention correctness, plus
    recall@5 broken down by question type. This dict becomes results.json."""
    recall3 = [recall_at_k(row["relevant"], row["response"].get("retrieved", []), 3)
               for row in rows]
    recall5 = [recall_at_k(row["relevant"], row["response"].get("retrieved", []), 5)
               for row in rows]
    citation = [citation_validity(row["response"]) for row in rows]
    abstention = abstention_correctness(rows)
    ranked = []
    for row in rows:
        relevant = row["relevant"]
        retrieved = row["response"].get("retrieved", [])
        expected = {(item.get("source"), item.get("section")) for item in relevant}
        rank = next((index for index, item in enumerate(retrieved, 1)
                     if (item.get("source"), item.get("section")) in expected), None)
        if expected:
            ranked.append((rank, len(retrieved)))
    mrr = sum((1 / rank if rank else 0) for rank, _ in ranked) / len(ranked) if ranked else 0.0
    ndcg5 = sum((1 / math.log2(rank + 1) if rank and rank <= 5 else 0)
                for rank, _ in ranked) / len(ranked) if ranked else 0.0

    def average(values: list[float | None]) -> float | None:
        usable = [value for value in values if value is not None]
        return sum(usable) / len(usable) if usable else None

    by_type: dict[str, float | None] = {}
    for question_type in sorted({row["type"] for row in rows}):
        by_type[question_type] = average([
            recall_at_k(row["relevant"], row["response"].get("retrieved", []), 5)
            for row in rows if row["type"] == question_type
        ])
    return {
        "recall_at_3": average(recall3),
        "recall_at_5": average(recall5),
        "mrr": mrr,
        "ndcg_at_5": ndcg5,
        "citation_validity": average(citation),
        "faithfulness": average([row["faithfulness"] for row in rows]),
        "latency_ms_p50": _percentile([row["seconds"] * 1000 for row in rows], 0.50),
        "latency_ms_p95": _percentile([row["seconds"] * 1000 for row in rows], 0.95),
        "abstention_rate": abstention["rate"],
        "abstention_correct": abstention["correct"],
        "abstention_incorrect": abstention["incorrect"],
        "abstention_total": abstention["total"],
        "recall_at_5_by_type": by_type,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, round((len(values) - 1) * percentile))
    return values[index]


def gate(results: dict, baseline: dict | None, *, require_context_faithfulness: bool = True) -> list[str]:
    """Return one message per failed gate (section 5.4); an empty list means pass."""
    failures: list[str] = []
    required = ("recall_at_3", "recall_at_5", "citation_validity", "latency_ms_p95", "abstention_rate")
    if require_context_faithfulness:
        required += ("faithfulness",)
    for metric in required:
        value = results.get(metric)
        if value is None or not isinstance(value, (int, float)):
            failures.append(f"required metric is missing or invalid: {metric}")
    current_recall = results.get("recall_at_5")
    if baseline is None or baseline.get("recall_at_5") is None:
        failures.append("baseline recall_at_5 is required before the regression gate can run")
    elif current_recall is None or current_recall < baseline["recall_at_5"] - MAX_RECALL5_DROP:
        failures.append(
            f"recall@5 regressed beyond {MAX_RECALL5_DROP:.0%}: "
            f"baseline={baseline['recall_at_5']}, current={current_recall}"
        )
    citation = results.get("citation_validity")
    if citation is None or citation < MIN_CITATION_VALIDITY:
        failures.append(f"citation validity is below {MIN_CITATION_VALIDITY:.0%}: {citation}")
    measured_faithfulness = results.get("faithfulness")
    if require_context_faithfulness and (measured_faithfulness is None or measured_faithfulness < MIN_FAITHFULNESS):
        failures.append(f"faithfulness is below {MIN_FAITHFULNESS:.0%}: {measured_faithfulness}")
    latency = results.get("latency_ms_p95")
    if latency is None or latency > MAX_P95_LATENCY_MS:
        failures.append(f"p95 latency exceeds {MAX_P95_LATENCY_MS:.0f}ms: {latency}")
    abstention = results.get("abstention_rate")
    required_abstention = max(REQUIRED_ABSTENTION, float((baseline or {}).get("abstention_rate", 0.0)))
    if abstention is None or abstention < required_abstention:
        failures.append(f"abstention correctness is below baseline/minimum {required_abstention:.0%}: {abstention}")
    return failures


def _dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAHBAR against a golden set.")
    parser.add_argument("--api", required=True, help="base URL, e.g. http://192.168.49.2")
    parser.add_argument("--request-timeout", type=float, default=120.0,
                        help="per-question HTTP timeout in seconds (default: 120)")
    parser.add_argument("--host", help="Host header, when your Ingress rule names a host")
    parser.add_argument("--fixtures", action="store_true", help="use the CI fixture golden set")
    parser.add_argument(
        "--allow-stub", action="store_true",
        help="allow a deterministic local stub for offline smoke evaluation; never use for production evidence",
    )
    parser.add_argument("--golden", type=Path, help="path to a golden question set")
    parser.add_argument("--baseline", type=Path, help="path to measured baseline metrics")
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    parser.add_argument("--trace-path", type=Path,
                        default=Path(os.environ.get("TRACE_DIR", "traces")) / "traces.jsonl",
                        help="JSONL trace file used to measure faithfulness against captured context")
    parser.add_argument("--update-baseline", action="store_true",
                        help="write these results as the new baseline")
    args = parser.parse_args()
    if args.fixtures and args.golden:
        parser.error("--fixtures and --golden are mutually exclusive")
    if args.fixtures:
        args.golden = HERE / "fixtures" / "golden.fixture.yaml"
        args.baseline = args.baseline or HERE / "fixtures" / "baseline.json"
    else:
        args.golden = args.golden or (HERE / "golden.jsonl" if (HERE / "golden.jsonl").exists()
                                      else HERE / "golden.yaml")
        args.baseline = args.baseline or HERE / "baseline.json"
    assert args.golden is not None
    assert args.baseline is not None

    questions = load_golden(args.golden, fixture=args.fixtures)
    rows = []
    headers = {"Host": args.host} if args.host else {}
    try:
        with httpx.Client(timeout=args.request_timeout, headers=headers) as client:
            for q in questions:
                started = time.perf_counter()
                response = ask(client, args.api, q["question"])
                if not args.fixtures and not args.allow_stub:
                    validate_production_response(response, q["id"])
                trace = trace_for_id(args.trace_path, response.get("trace_id", ""))
                rows.append({
                    "id": q["id"], "type": q.get("type", "ordinary"),
                    "must_abstain": bool(q.get("must_abstain", False)),
                    "relevant": q.get("relevant") or [],
                    "expect": q.get("expect"),
                    "response": response,
                    "faithfulness": faithfulness(response, trace),
                    "trace_found": trace is not None,
                    "seconds": round(time.perf_counter() - started, 2),
                })
                # Keep completed answers if a later request or the pod fails.
                # A partial checkpoint is never a completed evaluation result.
                checkpoint = args.out.with_suffix('.partial.json')
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                checkpoint.write_text(json.dumps({
                    'evaluation_complete': False, 'completed_questions': len(rows),
                    'expected_questions': len(questions), 'rows': rows,
                }, indent=2), encoding='utf-8')
                print(f"  {q['id']:<5} {rows[-1]['seconds']:>6.2f}s  {q['question'][:60]}")
    except httpx.HTTPError as exc:
        sys.exit(f"evaluation unavailable: could not reach API at {args.api}: {exc}")

    results = summarise(rows)
    baseline = json.loads(args.baseline.read_text()) if args.baseline.exists() else None
    failures = gate(results, baseline, require_context_faithfulness=not args.fixtures)
    # A baseline update is how the first genuine baseline is established. It
    # still enforces citation and abstention quality, but has no prior recall
    # value to regress against on that first run.
    if args.update_baseline and baseline is None:
        failures = [failure for failure in failures
                    if not failure.startswith("baseline recall_at_5 is required")]

    results["generated_at"] = datetime.now(timezone.utc).isoformat()
    results['evaluation_complete'] = True
    results["dataset_sha256"] = _dataset_sha256(args.golden)
    results["golden"] = str(args.golden)
    results["questions"] = len(rows)
    results["configuration"] = {
        "embed_model": os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        "embed_dimension": int(os.environ.get("EMBED_DIMENSION", "768")),
        "collection": os.environ.get("CHROMA_COLLECTION", "rahbar"),
        "top_k": int(os.environ.get("TOP_K", "5")),
    }
    if args.allow_stub:
        results["evaluation_mode"] = "offline-stub-smoke"
    results["rows"] = rows
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}")
    if args.update_baseline and not failures:
        args.baseline.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"baseline updated: {args.baseline}")
    elif args.update_baseline and failures:
        print("baseline not updated because the evaluation gate failed")

    if failures:
        print("\nGATE FAILED")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("\ngate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
