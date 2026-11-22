# Phase Dependency Map — RAGOps 2-Day Plan

This document is the machine-readable companion to `README.md`. It lists every phase, its **inputs (what it needs from earlier phases)**, its **outputs (what later phases consume)**, the **owner**, the **sync gate**, and the **hard link** to the next phase. If a phase's input is missing, that phase must not start; if its output is missing, the next phase is blocked.

---

## 1. Phase inventory

| Phase | Name | A03 | Paper | Day | Owner | Output artifact |
|---|---|---|---|---|---|---|
| **P0** | Contracts & baseline freeze | — | 3.2.3, 5.1 | D1 09:00 | Both | `docs/RAGOPS-CONTRACTS.md` |
| **P1** | Verify & update data (A1, A2, Batch B) | A | 4.2.1–4.2.4 | D1 | M1 (M2 authors Batch B) | `verify.py`, verification reports, incremental counters |
| **P2** | Offline testing at three levels (B) | B | 4.2.5, Table 1 | D1 | M2 | `eval/golden.jsonl`, `eval/results/<ts>.json` |
| **P3** | Change experiment & release gate (C1, C2) | C | 4.1(d), 4.2.6 | D2 AM | M2 | baseline vs candidate tables, gate config + script |
| **P4** | Trace & observability (D1–D5) | D | 3.2.3, 5.1, Table 2 | D1 PM → D2 AM | M2 (M1 volumes) | trace record, `scripts/trace.py`, metrics, root-cause note |
| **P5** | Drift & coverage (E1–E4) | E | 4.2.7 | D2 PM | M2 | 40-query log, coverage report, +6 golden, drift delta |
| **P6** | Kubernetes (F1–F5) | F | 4.1(e)–(f), 5.1 | D2 (manifests from D1 PM) | M1 | `k8s/` manifests, jobs, rollout/undo, resources |
| **P7** | Report & submission (G) | G | — | D2 PM | M2 | PDF + appendix, contribution table, AI statement |

---

## 2. Dependency edges

Each edge is `upstream --artifact--> downstream`. The "blocked if" column tells you what breaks when the artifact is late.

| # | Upstream | Downstream | Artifact | Blocked if missing |
|---|---|---|---|---|
| E1 | P0 | P1 | Verification report schema | Report cannot be committed in a parseable format; D4/E3 cannot read it |
| E2 | P0 | P2 | `eval/golden.jsonl` schema | Suite cannot validate question types or coverage |
| E3 | P0 | P4 | Trace JSON schema | Trace tool and metrics have no fields to read |
| E4 | P0 | P6 | New ConfigMap keys | Jobs cannot be configured without a rebuild |
| E5 | P1 | P2 | Verified, deduplicated corpus | Part B measures unverified data; numbers are not defensible |
| E6 | P1 | P2 | Batch B with planted problems | No hard/injection cases; noise and guardrail tests lack data |
| E7 | P1 | P5 | Per-document embed + orphan counts | E3 drift has no before/after counters |
| E8 | P1 | P4 | Quarantine path + injected doc id | D4 guardrail log cannot point at a real injection event |
| E9 | P2 | P3 | Baseline metrics | C2 thresholds have no reference; gate is arbitrary |
| E10 | P2 | P5 | Golden question ids + embeddings | E2 nearest-golden similarity cannot be computed |
| E11 | P2 | P4 | Wrong/abstained answer + trace id | D5 root cause has no case to analyse |
| E12 | P3 | P6 | Candidate image + gate thresholds | F3 has nothing to release; F2 gate cannot run |
| E13 | P4 | P6 | Trace volume mount + metrics endpoint | F4 cannot read traces or port-forward metrics |
| E14 | P5 | P2 | 6 new golden questions | E4 coverage cannot rise; the loop back to B is broken |
| E15 | P5 | P7 | Coverage report + drift delta | Report lacks E2/E3/E4 evidence |
| E16 | P6 | P7 | `kubectl` evidence, rollout/undo, ConfigMap edit | Report lacks all Part F screenshots |
| E17 | P7 | — | Report + decision | Submission is incomplete |

---

## 3. Feedback loops (phases that link backwards)

The plan is a chain, but two loops make it a lifecycle rather than a waterfall:

1. **Coverage loop:** `P5 (E4) --6 new golden questions--> P2`. Adding questions re-runs the Part B suite, so the golden set tracks real usage (paper 4.2.7).
2. **Gate loop:** `P3 (C2) --thresholds--> P6 (F2 eval Job)`. The same gate script is the Job's exit status, so a failing gate stops the rollout automatically (paper 4.1(d), 4.2.6).
3. **Drift loop:** `P1 (A2 counters) --before/after--> P5 (E3)`. Batch B is ingested once and its effect is measured against the same counters, closing the data-management lifecycle (paper 4.2.3–4.2.4).

---

## 4. Sync gates

| Gate | Time | Entry criteria | Exit criteria | If failed |
|---|---|---|---|---|
| **G0** | D1 09:30 | A02 baseline frozen | Contracts committed; fields agreed | Stop; no code until contracts are fixed |
| **G1** | D1 12:30 | Batch B committed; report schema agreed | M1 can run A1/A2 on Batch B | M1 uses Batch A only; M2 repairs Batch B |
| **G2** | D1 17:00 | A1/A2 evidence + Part B result file | Suite exits 0; tables exist | M2 fixes metrics; M1 fixes verification; carry to D2 AM |
| **G3** | D2 12:30 | Gate pass/fail + trace tool + injection flag | Bad candidate fails, good passes | M2 adjusts thresholds; M1 holds the rollout |
| **G4** | D2 17:00 | Full cluster run + evidence + report | All A03 items evidenced; checker clean | Do not submit; fix the failing item |

---

## 5. Handoff checklist (paste into PRs/issues)

Use this when a phase hands over to the next. Every box must be ticked before the downstream member starts.

### P0 → P1/P2/P4/P6
- [ ] Trace JSON schema committed
- [ ] Verification report schema committed
- [ ] `golden.jsonl` schema committed
- [ ] ConfigMap key list committed
- [ ] Both members can state every field

### P1 → P2
- [ ] Batch A verified and indexed
- [ ] Batch B committed under `corpus/batch-b/`
- [ ] Verification reports under `eval/results/`
- [ ] Quarantine and archive paths known

### P1 → P4/P5
- [ ] Per-document embed counts committed
- [ ] Orphan count by document id committed
- [ ] Injected document id known
- [ ] Archive/restore demo recorded

### P2 → P3/P4/P5
- [ ] `eval/golden.jsonl` committed
- [ ] `eval/results/<timestamp>.json` committed
- [ ] Baseline metrics table committed
- [ ] One wrong/abstained answer + trace id noted

### P3 → P6
- [ ] Candidate image built and loaded
- [ ] Gate thresholds in config
- [ ] Gate script exits 0 and 1 as required
- [ ] Baseline vs candidate tables committed

### P4 → P6/P7
- [ ] Trace volume mounted
- [ ] Trace tool prints context + prompt
- [ ] Metrics endpoint updated
- [ ] Root-cause note written

### P5 → P7
- [ ] Coverage before/after committed
- [ ] +6 golden questions committed
- [ ] Drift delta committed
- [ ] Coverage script exit code verified

### P6 → P7
- [ ] `kubectl get all,pvc,configmap,cronjob,job` captured
- [ ] Ingestion and eval Job logs captured
- [ ] Gate-after-ConfigMap-edit captured
- [ ] `rollout status` and `rollout undo` captured
- [ ] Post-undo trace shows previous collection + embedding version
- [ ] `k8s/README.md` apply order verified on a fresh cluster
