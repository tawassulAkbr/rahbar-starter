# Phase 1 — Member 2: Golden Set & Batch B

**Member:** Member 2 (AI Quality, Retrieval & Evaluation) · **Day 1, 09:30–12:30**
**Serves:** Assignment 03 **Part B** (golden set) and **Part A** (Batch B input)
**Paper anchor:** 4.2.5 offline testing, Table 1 (test data per level)

---

## 1. What this file is for

Produce the two data inputs the rest of the plan depends on: the **golden set** that Part B measures against, and **Batch B** — the second corpus with planted problems that Part A must catch.

---

## 2. Inputs (from earlier phases)

- `PHASE_0_CONTRACTS_AND_BASELINE.md`: `eval/golden.jsonl` schema.
- Existing `eval/golden.yaml` and `eval/run_eval.py` from Assignment 02.

---

## 3. Tasks

### 3.1 Golden set `eval/golden.jsonl` (09:30–11:00)
- [ ] At least **25 questions**:
  - ≥15 answerable, each with ground-truth document **and page**.
  - ≥5 unanswerable (correct behaviour is to abstain).
  - ≥5 hard (paraphrased, or needing more than one chunk, or from Batch B).
- [ ] At least **8 questions written by hand** by the group.
- [ ] Label every question `human` or `synthetic`.
- [ ] At least **8 synthetic questions reviewed by hand** (`reviewed: true`).
- [ ] Keep the Assignment 02 categories (ordinary, version, exact, abstain, injection).

### 3.2 Batch B `corpus/batch-b/` (11:00–12:30)
At least **10 documents** with planted problems:
- [ ] ≥2 exact duplicates.
- [ ] 1 near-duplicate.
- [ ] 1 truncated or corrupt file.
- [ ] 1 with missing metadata.
- [ ] 1 newer version of an existing document.
- [ ] 1 containing an injected instruction.
- [ ] A `MANIFEST.md` or `_index.json` describing each planted problem.

### 3.3 Handoff
- [ ] Commit Batch B under `corpus/batch-b/`.
- [ ] Tell Member 1 the quarantine path expectation and the injected document id.

---

## 4. Files touched

| File | Change |
|---|---|
| `eval/golden.jsonl` | Created (≥25 questions, labels, review flags) |
| `corpus/batch-b/*` | ≥10 documents with planted problems |
| `corpus/batch-b/MANIFEST.md` | Planted-problem map |
| `eval/run_eval.py` | Read `golden.jsonl` in addition to `golden.yaml` |

---

## 5. Acceptance (sync gate G1, Day 1 12:30)

- [ ] `eval/golden.jsonl` valid against the Phase 0 schema and the Part B minimums.
- [ ] Batch B committed; each planted problem identified in its manifest.
- [ ] Member 1 can run A1/A2 on Batch B.

---

## 6. Handoff

- → `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`: Batch B.
- → `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: golden set.
- → `PHASE_5_MEMBER_2_DRIFT_AND_COVERAGE.md`: golden question ids and embeddings.
