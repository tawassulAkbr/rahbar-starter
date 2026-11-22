# Day 1 — Verify, Update, and Test

**Goal by 18:00:** a verified corpus with Batch B planted problems caught, incremental update proven, and the full Part B suite running twice with a timestamped result file.

**Working hours assumed:** 09:00–18:00, with sync gates.

---

## Schedule

| Time | Both / Sync | Member 1 | Member 2 |
|---|---|---|---|
| 09:00–09:30 | **G0:** freeze baseline, agree contracts (`PHASE_0_CONTRACTS_AND_BASELINE.md`) | — | — |
| 09:30–12:30 | — | **P1:** verification stage + quarantine PVC (`PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`) | **P1:** golden set + Batch B (`PHASE_1_MEMBER_2_GOLDEN_SET_AND_BATCH_B.md`) |
| 12:30–13:30 | **G1:** Batch B handed over; report schema agreed | — | — |
| 13:30–17:00 | — | **P1:** incremental update (A2) + run Batch A/B + evidence | **P2:** module + component + end-to-end suites + stochasticity (`PHASE_2_MEMBER_2_OFFLINE_TESTING.md`) |
| 17:00–17:30 | **G2:** A1/A2 evidence + Part B result file | — | — |
| 17:30–18:00 | — | Start trace volume + `k8s/eval-job.yaml` skeleton (`PHASE_6_MEMBER_1_KUBERNETES.md`) | Start trace record writer (`PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md`) |

---

## Sync gates

| Gate | Time | Entry | Exit |
|---|---|---|---|
| **G0** | 09:30 | A02 baseline frozen | `docs/RAGOPS-CONTRACTS.md` committed; fields agreed |
| **G1** | 12:30 | Batch B committed; report schema agreed | M1 can run A1/A2 on Batch B |
| **G2** | 17:00 | A1/A2 evidence + Part B result | Suite exits 0; tables exist; evidence committed |

---

## Day 1 outputs

- [ ] `docs/RAGOPS-CONTRACTS.md`
- [ ] `indexer/pipeline/verify.py` + wired into `run.py`
- [ ] `eval/golden.jsonl` (≥25 questions)
- [ ] `corpus/batch-b/` (≥10 documents, planted problems)
- [ ] Verification reports + incremental counters
- [ ] `eval/results/<timestamp>.json` (module, component, end-to-end, two seeded runs)
- [ ] Trace volume + eval Job skeleton started
