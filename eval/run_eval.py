#!/usr/bin/env python3
"""Score a running RAHBAR against a golden set, and gate CI on the result (section 5).

    python eval/run_eval.py --api http://<ingress>                 # your corpus
    python eval/run_eval.py --api ... --fixtures                    # CI fixtures
    python eval/run_eval.py --api ... --golden eval/fixtures/golden.fixture.yaml
    python eval/run_eval.py --api ... --update-baseline            # after a deliberate improvement

Exit code 0 when every gate passes, 1 when any fails. CI relies on that exit code.

Given: talking to the API, reading the golden set, writing results.json, the exit
code. Yours: the four functions marked STARTER-TODO. They are the evaluation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent

# The gate from section 5.4. Change these only with a reason written in docs/PIPELINE.md.
MAX_RECALL5_DROP = 0.05        # recall@5 may fall at most 5 points below the baseline
MIN_CITATION_VALIDITY = 0.95   # at least 95% of citations must match retrieved passages
REQUIRED_ABSTENTION = 1.0      # every must-abstain question must be declined


def load_golden(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions") or []
    if not questions:
        sys.exit(f"no questions in {path}")
    return questions


def ask(client: httpx.Client, api: str, question: str) -> dict:
    """POST one question and return the AskResponse as a dict (see api/app/schemas.py)."""
    response = client.post(f"{api.rstrip('/')}/api/ask", json={"question": question})
    response.raise_for_status()
    return response.json()


def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None:
    """Fraction of the relevant (source, section) pairs found in the top k retrieved.
    Return None when the question has no relevant passages (must-abstain questions)."""
    expected = {(item.get("source"), item.get("section")) for item in relevant}
    expected.discard((None, None))
    if not expected:
        return None
    actual = {(item.get("source"), item.get("section")) for item in retrieved[:k]}
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


def summarise(rows: list[dict]) -> dict:
    """Overall recall@3, recall@5, citation validity and abstention correctness, plus
    recall@5 broken down by question type. This dict becomes results.json."""
    recall3 = [recall_at_k(row["relevant"], row["response"].get("retrieved", []), 3)
               for row in rows]
    recall5 = [recall_at_k(row["relevant"], row["response"].get("retrieved", []), 5)
               for row in rows]
    citation = [citation_validity(row["response"]) for row in rows]
    abstention_rows = [row for row in rows if row["must_abstain"]]
    abstention_correct = sum(
        not row["response"].get("answered_from_context", True) for row in abstention_rows
    )

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
        "citation_validity": average(citation),
        "abstention_rate": (
            abstention_correct / len(abstention_rows) if abstention_rows else 1.0
        ),
        "recall_at_5_by_type": by_type,
    }


def gate(results: dict, baseline: dict | None) -> list[str]:
    """Return one message per failed gate (section 5.4); an empty list means pass."""
    failures: list[str] = []
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
    abstention = results.get("abstention_rate")
    if abstention != REQUIRED_ABSTENTION:
        failures.append(f"abstention rate must be 100%: {abstention}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAHBAR against a golden set.")
    parser.add_argument("--api", required=True, help="base URL, e.g. http://192.168.49.2")
    parser.add_argument("--host", help="Host header, when your Ingress rule names a host")
    parser.add_argument("--fixtures", action="store_true", help="use the CI fixture golden set")
    parser.add_argument("--golden", type=Path, help="path to a golden question set")
    parser.add_argument("--baseline", type=Path, help="path to measured baseline metrics")
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    parser.add_argument("--update-baseline", action="store_true",
                        help="write these results as the new baseline")
    args = parser.parse_args()
    if args.fixtures and args.golden:
        parser.error("--fixtures and --golden are mutually exclusive")
    if args.fixtures:
        args.golden = HERE / "fixtures" / "golden.fixture.yaml"
        args.baseline = args.baseline or HERE / "fixtures" / "baseline.json"
    else:
        args.golden = args.golden or HERE / "golden.yaml"
        args.baseline = args.baseline or HERE / "baseline.json"
    assert args.golden is not None
    assert args.baseline is not None

    questions = load_golden(args.golden)
    rows = []
    headers = {"Host": args.host} if args.host else {}
    with httpx.Client(timeout=120.0, headers=headers) as client:
        for q in questions:
            started = time.perf_counter()
            response = ask(client, args.api, q["question"])
            rows.append({
                "id": q["id"], "type": q.get("type", "ordinary"),
                "must_abstain": bool(q.get("must_abstain", False)),
                "relevant": q.get("relevant") or [],
                "expect": q.get("expect"),
                "response": response,
                "seconds": round(time.perf_counter() - started, 2),
            })
            print(f"  {q['id']:<5} {rows[-1]['seconds']:>6.2f}s  {q['question'][:60]}")

    results = summarise(rows)
    baseline = json.loads(args.baseline.read_text()) if args.baseline.exists() else None
    failures = gate(results, baseline)

    results["golden"] = str(args.golden)
    results["questions"] = len(rows)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}")
    if args.update_baseline:
        args.baseline.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"baseline updated: {args.baseline}")

    if failures:
        print("\nGATE FAILED")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("\ngate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
