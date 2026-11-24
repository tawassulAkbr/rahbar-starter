# Phase 5 Member 2 completion checklist

Phase 5 is implemented on `feature/assignment-03-phase1-integrated`.

- [x] `eval/live_queries.jsonl` contains 40 user-like queries: 28 in covered policy/document
  domains and 12+ in uncovered topics.
- [x] `eval/coverage.py` finds the nearest golden question with deterministic cosine similarity,
  records the threshold, lists uncovered queries, groups topics, and supports `--fail-under`.
- [x] Before evidence is committed: 32/40 covered = 0.80, below the 0.85 warning level.
- [x] Six reviewed golden questions were added from uncovered topics.
- [x] After evidence is committed: 38/40 covered = 0.95, demonstrating the gap was reduced.
- [x] `eval/drift.py` reruns the dependency-free Phase 2 suite before Batch B and with Batch B,
  then reports component and end-to-end deltas.
- [x] `eval/results/drift.json` records the Batch B comparison and the Phase1 lifecycle counter
  reference. Live Kubernetes counters remain a deployment-time check, not simulated evidence.
- [x] `eval/results/offline-phase5-after.json` reruns the complete Phase 2 suite against the
  expanded golden set and Batch B corpus.

## Verification commands

```text
python scripts/validate_phase1_member2.py
python eval/coverage.py --golden eval/golden.jsonl --live eval/live_queries.jsonl --threshold 0.35 --fail-under 0.85 --out eval/results/coverage-after.json
python eval/drift.py --corpus corpus --golden eval/golden.jsonl --out eval/results/drift.json
python eval/run_offline_suite.py --corpus corpus --golden eval/golden.jsonl --out eval/results/offline-phase5-after.json
```

The threshold is fixed at `0.35` for the deterministic-hash reference embedder and is stored
in every coverage result. A production run should repeat coverage with the pinned live embedding
service before changing the threshold.
