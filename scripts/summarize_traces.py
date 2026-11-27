"""Summarize Phase 4 JSONL traces over an optional UTC time window."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from statistics import mean


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, round((len(values) - 1) * p))
    return values[index]


def summarize(path: str, since: str | None = None, until: str | None = None) -> dict:
    start = datetime.fromisoformat(since) if since else None
    end = datetime.fromisoformat(until) if until else None
    rows = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        timestamp = datetime.fromisoformat(row["timestamp"])
        if start and timestamp < start or end and timestamp > end:
            continue
        rows.append(row)
    total = len(rows)
    top1 = [float(r["retrieved"][0]["score"]) for r in rows if r.get("retrieved")]
    latency: dict[str, list[float]] = {}
    for row in rows:
        for stage, value in row.get("latency_per_stage", {}).items():
            latency.setdefault(stage, []).append(float(value))
    return {
        "count": total,
        "top1_similarity": {"count": len(top1), "mean": mean(top1) if top1 else 0.0,
                             "p50": percentile(top1, .5), "p95": percentile(top1, .95)},
        "abstention_rate": sum(not r.get("response", {}).get("answered_from_context", True) for r in rows) / total if total else 0.0,
        "cache_hit_rate": sum(bool(r.get("cache_hit")) for r in rows) / total if total else 0.0,
        "p95_latency_per_stage_ms": {stage: percentile(values, .95) for stage, values in latency.items()},
        "injection_attempts_flagged": sum(len(r.get("guardrail_actions") or []) for r in rows),
        "trace_ids": [r["trace_id"] for r in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="traces/traces.jsonl")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = summarize(args.path, args.since, args.until)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
