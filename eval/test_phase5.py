"""Focused Phase 5 checks that do not require a cluster or model service."""

from __future__ import annotations

import json
from pathlib import Path

from coverage import load_jsonl, run_coverage


ROOT = Path(__file__).resolve().parents[1]


def test_before_and_after_coverage_evidence_is_monotonic() -> None:
    golden = load_jsonl(ROOT / "eval" / "golden.jsonl")
    live = load_jsonl(ROOT / "eval" / "live_queries.jsonl")
    before = run_coverage([row for row in golden if not row["id"].startswith("phase5-")], live)
    after = run_coverage(golden, live)
    assert before["live_queries"] == 40
    assert after["coverage"] > before["coverage"]
    assert after["coverage"] >= 0.85


def test_committed_results_match_phase5_claims() -> None:
    before = json.loads((ROOT / "eval" / "results" / "coverage-before.json").read_text())
    after = json.loads((ROOT / "eval" / "results" / "coverage-after.json").read_text())
    assert before["coverage"] == 0.8
    assert after["coverage"] == 0.925
    assert before["live_queries"] == after["live_queries"] == 40
