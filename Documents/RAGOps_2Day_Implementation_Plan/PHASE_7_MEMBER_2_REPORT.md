# Phase 7 — Member 2: Report & Submission

**Member:** Member 2 (AI Quality, Retrieval & Evaluation) · **Day 2, 16:00–18:00**
**Serves:** Assignment 03 **Part G** (report) and the submission checklist
**Paper anchor:** Figure 3 (stage mapping), Table 2 (five qualities)

---

## 1. What this file is for

Synthesise Phases 1–6 into the ≤8-page report and the appendix screenshots, and leave the repository submission-ready.

---

## 2. Inputs (from earlier phases)

- `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`: verification + incremental evidence.
- `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: Part B tables.
- `PHASE_3_MEMBER_2_CHANGE_AND_GATE.md`: release decision.
- `PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md`: trace sample + root cause.
- `PHASE_5_MEMBER_2_DRIFT_AND_COVERAGE.md`: coverage before/after + drift.
- `PHASE_6_MEMBER_1_KUBERNETES.md`: Part F evidence.

---

## 3. Tasks

### 3.1 Report tables
- [ ] **Figure 3 mapping table:** each stage (ingest, verify, update data lake, update retrieval sources, offline testing, live testing, check coverage) → what your pipeline does, the file that does it, what is missing.
- [ ] **Table 2 qualities table:** adaptability, monitorability, observability, traceability, reliability → what you measure, threshold, evidence.
- [ ] **Results tables A–F** and the release decision for Part C (release or reject, with reasons).

### 3.2 Short answers (a)–(f)
- [ ] (a) Which verification check caught the most Batch B problems, which did you miss, what would catch it.
- [ ] (b) Example where a module-level metric looked fine but component/end-to-end did not.
- [ ] (c) Did you archive or delete old versions, and what breaks if you delete.
- [ ] (d) Which metric you trust least, and why.
- [ ] (e) Which paper idea was hardest to apply, and what you changed.
- [ ] (f) Which Kubernetes object carries which RAGOps responsibility.

### 3.3 Contribution and AI statement
- [ ] Contribution table (what each member did).
- [ ] AI statement of 2–3 lines.

### 3.4 Appendix screenshots
- [ ] A: Batch B verification report; second ingestion showing 0 chunks embedded.
- [ ] B: evaluation summary with all three levels.
- [ ] C: release gate failing and passing.
- [ ] D: one full trace record; trace tool rebuilding the prompt.
- [ ] E: coverage output before and after adding questions.
- [ ] F: `kubectl get all,pvc,configmap,cronjob,job`; ingestion and eval Job logs; gate result after ConfigMap edit; `rollout status` + `rollout undo` + post-undo trace.

### 3.5 Repository readiness
- [ ] README gives the exact command for each part (A–F).
- [ ] `eval/results/` and `traces/` committed.
- [ ] `k8s/` manifests committed; `k8s/README.md` apply order verified.
- [ ] `python scripts/check_submission.py` clean.
- [ ] Commits from both members.

---

## 4. Files touched

| File | Change |
|---|---|
| `docs/RAGOPS-REPORT.md` (or PDF source) | Report body |
| `docs/evidence/` | Screenshots and command outputs |
| `README.md` | Commands for A–F |
| `eval/results/`, `traces/` | Committed evidence |

---

## 5. Acceptance (sync gate G4, Day 2 17:00)

- [ ] Report ≤8 pages + appendix.
- [ ] All required tables and short answers present.
- [ ] Contribution table and AI statement present.
- [ ] Repository submission-ready; checker clean.

---

## 6. Handoff

- → Submission: GitHub repository URL + report PDF.
