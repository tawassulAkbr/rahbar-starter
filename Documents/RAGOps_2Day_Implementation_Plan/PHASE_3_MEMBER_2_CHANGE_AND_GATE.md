# Phase 3 — Member 2: Change Experiment & Release Gate

**Member:** Member 2 (AI Quality, Retrieval & Evaluation) · **Day 2, 09:30–12:30**
**Serves:** Assignment 03 **Part C** (C1 one change, C2 release gate, C3 roll-out handoff)
**Paper anchor:** 4.1(d) release, 4.2.5 offline testing, 4.2.6 live testing

---

## 1. What this file is for

Choose one pipeline change, run the Part B suite on baseline and candidate, and turn the comparison into a release gate with explicit thresholds. The gate becomes the eval Job's exit status in Phase 6.

---

## 2. Inputs (from earlier phases)

- `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: baseline metrics.
- `PHASE_0_CONTRACTS_AND_BASELINE.md`: gate ConfigMap keys.

---

## 3. Tasks

### 3.1 C1 — one change (09:30–10:30)
- [ ] Choose **one** change: chunk size or overlap, embedding model, reranker, top-k, or prompt template.
- [ ] Justify it from the Day 1 numbers.
- [ ] Run the Part B suite on baseline and on candidate.
- [ ] Compare all three levels (module, component, end-to-end).

### 3.2 C2 — release gate (10:30–11:30)
- [ ] Write thresholds into a config file, e.g.:
  - recall@5 may not drop more than 2 points against baseline;
  - faithfulness at least a justified value;
  - p95 latency at most a justified value;
  - abstention correctness not lower than baseline.
- [ ] A script applies the gate and exits pass/fail.
- [ ] Show **one candidate that fails** (a deliberately bad one is fine) and **one that passes**.

### 3.3 C3 — handoff to roll-out (11:30–12:30)
- [ ] Package the candidate image and its collection name.
- [ ] Hand the gate thresholds ConfigMap to Member 1.

---

## 4. Files touched

| File | Change |
|---|---|
| `eval/change_experiment.py` | Baseline vs candidate runner |
| `eval/gate.json` (or `eval/gate.yaml`) | Thresholds |
| `eval/gate.py` | Applies thresholds, exits 0/1 |
| `eval/results/gate-pass.json`, `gate-fail.json` | Evidence |
| `k8s/base/configmap.yaml` | Gate threshold keys |

---

## 5. Acceptance (sync gate G3, Day 2 12:30)

- [ ] Baseline vs candidate tables for all three levels.
- [ ] Gate fails on the bad candidate and passes on the good one.
- [ ] Thresholds justified from the measured baseline.
- [ ] Candidate image + collection name handed to Member 1.

---

## 6. Handoff

- → `PHASE_6_MEMBER_1_KUBERNETES.md`: candidate image, thresholds, gate script.
- → `PHASE_7_MEMBER_2_REPORT.md`: release decision (release/reject with reasons).
