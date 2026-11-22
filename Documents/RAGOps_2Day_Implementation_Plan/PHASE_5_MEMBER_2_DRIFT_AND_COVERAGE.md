# Phase 5 — Member 2: Drift & Coverage

**Member:** Member 2 (AI Quality, Retrieval & Evaluation) · **Day 2, 13:30–16:00**
**Serves:** Assignment 03 **Part E** (E1 live log, E2 coverage, E3 drift, E4 close the gap)
**Paper anchor:** 4.2.7 coverage checking, 4.2.5 offline testing (triggered by data shift)

---

## 1. What this file is for

Check that the test data still matches real usage: build a live query log, measure coverage against the golden set, ingest Batch B and measure drift, then close the gap by adding golden questions.

---

## 2. Inputs (from earlier phases)

- `PHASE_1_MEMBER_2_GOLDEN_SET_AND_BATCH_B.md`: golden question ids and embeddings.
- `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`: per-document embed and orphan counters.
- `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: Part B suite and baseline.

---

## 3. Tasks

### 3.1 E1 — live query log (13:30–14:00)
- [ ] Create ≥40 queries as if from users: ≈28 in the golden domain, ≥12 from an uncovered topic.
- [ ] Commit as `eval/live_queries.jsonl`.

### 3.2 E2 — query coverage (14:00–14:45)
- [ ] For each live query, find the most similar golden question.
- [ ] Report the share above a similarity threshold you choose and justify (the paper's example flags a gap below 85%).
- [ ] List the uncovered queries and group them into topics.

### 3.3 E3 — data drift (14:45–15:15)
- [ ] Ingest Batch B.
- [ ] Re-run the Part B suite.
- [ ] Report what changed and why (compare against the Phase 1 counters).

### 3.4 E4 — close the gap (15:15–16:00)
- [ ] Add ≥6 new golden questions from the uncovered topics.
- [ ] Re-run and show coverage rises.
- [ ] A script returns a non-zero exit code when coverage falls below your threshold.

---

## 4. Files touched

| File | Change |
|---|---|
| `eval/live_queries.jsonl` | 40 live queries |
| `eval/coverage.py` | Nearest-golden similarity, share, topics, exit code |
| `eval/drift.py` | Batch B re-run comparison |
| `eval/golden.jsonl` | +6 new questions |
| `eval/results/coverage-before.json`, `coverage-after.json` | Evidence |
| `eval/results/drift.json` | Evidence |

---

## 5. Acceptance (sync gate G4, Day 2 17:00)

- [ ] 40 live queries committed.
- [ ] Coverage before/after committed; threshold justified.
- [ ] Uncovered queries grouped by topic.
- [ ] Coverage rises after adding ≥6 questions; script exits non-zero below threshold.

---

## 6. Handoff

- → `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: 6 new golden questions (loop back).
- → `PHASE_7_MEMBER_2_REPORT.md`: coverage before/after and drift results.
