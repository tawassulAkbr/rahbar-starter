"""Focused Phase 5 checks that do not require a cluster or model service."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("phase5_coverage", ROOT / "eval" / "coverage.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
load_jsonl = _MODULE.load_jsonl
run_coverage = _MODULE.run_coverage


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
