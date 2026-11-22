"""Rebuild the exact prompt/context captured for a trace id."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def find_trace(path: str, trace_id: str) -> dict:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("trace_id") == trace_id:
            return record
    raise SystemExit(f"trace id not found: {trace_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_id")
    parser.add_argument("--path", default="traces/traces.jsonl")
    args = parser.parse_args()
    record = find_trace(args.path, args.trace_id)
    print(json.dumps({
        "trace_id": record["trace_id"],
        "context": record.get("context", []),
        "prompt": record.get("prompt", ""),
        "prompt_hash": record.get("prompt_hash", ""),
        "response": record.get("response", {}),
        "citations": record.get("citations", []),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
