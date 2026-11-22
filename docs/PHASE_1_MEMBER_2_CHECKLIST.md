# Phase 1 Member 2 verification checklist

This branch contains the Phase 0 contract commit plus four Member 2 commits.
`main` is not changed.

## G1 acceptance

Run from the repository root:

```text
python scripts/validate_phase1_member2.py
python -m py_compile eval/run_eval.py scripts/validate_phase1_member2.py
git diff --check
```

The validator proves:

- `eval/golden.jsonl` has at least 25 unique rows.
- There are at least 15 answerable, 5 unanswerable, and 5 hard questions.
- Every answerable/hard question has a source and positive page.
- Every unanswerable question has null source/page.
- At least 8 questions are human-labelled.
- At least 8 synthetic questions have `reviewed: true`.
- Batch B has at least 10 documents.
- The exact duplicate pair has identical SHA-256 hashes.
- The near-duplicate is textually similar but not byte-identical.
- Truncated, missing-metadata, old/new-version, corrupt, and injection fixtures exist.

## Files and handoff

| Deliverable | Location | Check |
| --- | --- | --- |
| Golden set | [`eval/golden.jsonl`](../eval/golden.jsonl) | JSONL parser and evaluator loader |
| Golden loader | [`eval/run_eval.py`](../eval/run_eval.py) | Defaults to JSONL when present; YAML remains supported |
| Batch B | [`corpus/batch-b/`](../corpus/batch-b/) | 11 documents |
| Planted-problem map | [`corpus/batch-b/MANIFEST.md`](../corpus/batch-b/MANIFEST.md) | Names every problem and expected result |
| Validation command | [`scripts/validate_phase1_member2.py`](../scripts/validate_phase1_member2.py) | Standard-library-only G1 check |

The Member 1 handoff is:

- quarantine path: the configured `QUARANTINE_DIR`; Kubernetes uses `/data/quarantine`;
- injected document ID: `batch-b-injected-instruction.md`;
- Batch B input path: `corpus/batch-b/`.

## Evaluator smoke check

The loader can be checked without an API:

```text
python -c "from pathlib import Path; import sys; sys.path.insert(0, 'eval'); from run_eval import load_golden; q=load_golden(Path('eval/golden.jsonl')); print(len(q), 'questions loaded')"
```

The full evaluator still requires a running API:

```text
python eval/run_eval.py --api <ingress-or-api-url> --golden eval/golden.jsonl
```

For the Part A handoff, run the indexer with `CORPUS_DIR=corpus/batch-b` and
inspect its verification report. Do not treat the injected instruction as an
instruction to the system; it is intentionally untrusted corpus content.
