#!/usr/bin/env python3
"""Validate the Phase 1 Member 2 golden set and Batch B inputs.

This command uses only the Python standard library and is safe to run before
the indexer or Kubernetes cluster is available.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval" / "golden.jsonl"
BATCH = ROOT / "corpus" / "batch-b"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> int:
    if not GOLDEN.exists():
        fail(f"missing {GOLDEN}")
    rows = []
    for line_number, line in enumerate(GOLDEN.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"golden line {line_number}: {exc}")
        required = {"id", "question", "type", "source", "page", "label", "reviewed"}
        if not required <= row.keys():
            fail(f"golden line {line_number}: missing {sorted(required - row.keys())}")
        if row["type"] != "unanswerable" and (not row["source"] or not isinstance(row["page"], int) or row["page"] < 1):
            fail(f"golden line {line_number}: answerable/hard rows need source and page")
        if row["type"] == "unanswerable" and (row["source"] is not None or row["page"] is not None):
            fail(f"golden line {line_number}: unanswerable source/page must be null")
        rows.append(row)
    if len(rows) < 25 or len({row["id"] for row in rows}) != len(rows):
        fail("golden set must contain at least 25 unique rows")
    types = Counter(row["type"] for row in rows)
    if types["answerable"] < 15 or types["unanswerable"] < 5 or types["hard"] < 5:
        fail(f"golden type minimums not met: {dict(types)}")
    if sum(row["label"] == "human" for row in rows) < 8:
        fail("fewer than 8 human-labelled questions")
    if sum(row["label"] == "synthetic" and row["reviewed"] for row in rows) < 8:
        fail("fewer than 8 reviewed synthetic questions")

    documents = [path for path in BATCH.iterdir() if path.is_file() and path.name != "MANIFEST.md"]
    if len(documents) < 10:
        fail("Batch B must contain at least 10 documents")
    hashes: dict[str, list[str]] = defaultdict(list)
    for path in documents:
        hashes[hashlib.sha256(path.read_bytes()).hexdigest()].append(path.name)
    duplicate_groups = [names for names in hashes.values() if len(names) > 1]
    if not any({"batch-b-clean-policy-2026.md", "batch-b-exact-duplicate.md"} <= set(names)
               for names in duplicate_groups):
        fail("expected exact duplicate pair is missing")
    clean = (BATCH / "batch-b-clean-policy-2026.md").read_text(encoding="utf-8")
    near = (BATCH / "batch-b-near-duplicate.md").read_text(encoding="utf-8")
    if SequenceMatcher(None, clean, near).ratio() < 0.90:
        fail("near-duplicate fixture is not sufficiently similar")
    corrupt = (BATCH / "batch-b-corrupt.txt").read_bytes().decode("utf-8", errors="replace")
    if "�" not in corrupt or "\x00" not in corrupt:
        fail("corrupt fixture does not contain replacement/control characters")
    for required_file in ("batch-b-truncated.md", "batch-b-missing-metadata.md",
                          "batch-b-policy-2026.md", "batch-b-policy-2027.md",
                          "batch-b-injected-instruction.md"):
        if not (BATCH / required_file).exists():
            fail(f"missing planted-problem fixture: {required_file}")
    print(f"golden: PASS ({len(rows)} questions; types={dict(types)})")
    print(f"batch-b: PASS ({len(documents)} documents; exact_duplicate_groups={len(duplicate_groups)})")
    print("handoff: quarantine expectation is QUARANTINE_DIR; injected id is batch-b-injected-instruction.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
