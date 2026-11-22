# Phase 2 — Member 2: Three-Level Offline Testing

**Member:** Member 2 (AI Quality, Retrieval & Evaluation) · **Day 1, 13:30–17:00**
**Serves:** Assignment 03 **Part B** (golden set, module, component, end-to-end, stochasticity)
**Paper anchor:** 4.2.5 offline testing, Table 1 (three levels), 4.2.5 stochasticity

---

## 1. What this file is for

Build the offline testing platform at three granularity levels — module (embedding), component (retrieval) and end-to-end (answers) — and make one command run the whole suite into a timestamped result file. This is the measurement backbone for the release gate (Phase 3) and the drift check (Phase 5).

---

## 2. Inputs (from earlier phases)

- `PHASE_0_CONTRACTS_AND_BASELINE.md`: `golden.jsonl` schema.
- `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`: verified corpus + Batch B.
- `PHASE_1_MEMBER_2_GOLDEN_SET_AND_BATCH_B.md`: golden set.
- Existing `eval/run_eval.py`, `eval/baseline.json`.

---

## 3. Tasks

### 3.1 Module level — embedding quality (13:30–14:30)
- [ ] Mean cosine similarity for ≥15 paraphrase pairs vs ≥15 unrelated pairs, and the gap.
- [ ] Embedding time per chunk.
- [ ] Determinism: embed the same text twice, report the largest difference.

### 3.2 Component level — retrieval quality (14:30–15:30)
- [ ] recall@3, recall@5, MRR, nDCG@5 on the golden set.
- [ ] Noise test: add ≥3 irrelevant documents, or add typos to queries; report how each metric changes.

### 3.3 End-to-end level — answer quality (15:30–16:15)
- [ ] Faithfulness (is the answer supported by the retrieved context).
- [ ] Abstention correctness on the unanswerable questions.
- [ ] Citation validity.
- [ ] Latency p50 and p95.
- [ ] If an LLM is the judge for faithfulness: label ≥8 answers by hand and report judge agreement.

### 3.4 Stochasticity (16:15–16:45)
- [ ] Fix random seeds.
- [ ] Run the whole suite twice; report the difference for each metric and explain remaining variation.

### 3.5 One command + timestamped result (16:45–17:00)
- [ ] `make eval` (or one script) writes `eval/results/<timestamp>.json` with a summary table.
- [ ] Commit the result file.

---

## 4. Files touched

| File | Change |
|---|---|
| `eval/module_level.py` | Paraphrase gap, embed timing, determinism |
| `eval/component_level.py` | recall@3/5, MRR, nDCG@5, noise test |
| `eval/e2e_level.py` | Faithfulness, abstention, citations, p50/p95 |
| `eval/run_eval.py` | Orchestrator: one command, timestamped output |
| `eval/results/<timestamp>.json` | Suite output |

---

## 5. Acceptance (sync gate G2, Day 1 17:00)

- [ ] All three levels report numbers from your own runs.
- [ ] Noise test shows metric deltas.
- [ ] Two seeded runs reported with per-metric deltas.
- [ ] One command produced `eval/results/<timestamp>.json`.

---

## 6. Handoff

- → `PHASE_3_MEMBER_2_CHANGE_AND_GATE.md`: baseline metrics.
- → `PHASE_5_MEMBER_2_DRIFT_AND_COVERAGE.md`: golden ids/embeddings; before/after Batch B comparison.
- → `PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md`: one wrong/abstained answer + trace id.
- → `PHASE_7_MEMBER_2_REPORT.md`: Part B results tables.
