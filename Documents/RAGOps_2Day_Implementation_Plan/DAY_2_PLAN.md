# Day 2 — Gate, Trace, Drift, Deploy, Report

**Goal by 18:00:** the candidate is gated and released (or stopped), a trace rebuilds a prompt, coverage rises after adding questions, and the report/evidence is submission-ready on the cluster.

**Working hours assumed:** 09:00–18:00, with sync gates.

---

## Schedule

| Time | Both / Sync | Member 1 | Member 2 |
|---|---|---|---|
| 09:00–09:30 | Review Day 1 results; pick the Part C change | — | — |
| 09:30–12:30 | — | **P4/P6:** trace plumbing, eval Job, threshold ConfigMap, candidate Deployment/Service (`PHASE_6_MEMBER_1_KUBERNETES.md`) | **P3:** change experiment + gate; **P4:** trace tool + guardrail test (`PHASE_3_MEMBER_2_CHANGE_AND_GATE.md`, `PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md`) |
| 12:30–13:30 | **G3:** gate fails on bad candidate, passes on good; trace tool rebuilds prompt | — | — |
| 13:30–17:00 | — | **P6:** F1–F5 deploy, rollout/undo, resources (`PHASE_6_MEMBER_1_KUBERNETES.md`) | **P5:** live queries, coverage, drift, close gap; **P7:** report (`PHASE_5_MEMBER_2_DRIFT_AND_COVERAGE.md`, `PHASE_7_MEMBER_2_REPORT.md`) |
| 17:00–18:00 | **G4:** full cluster run, evidence, report, checker | — | — |

---

## Sync gates

| Gate | Time | Entry | Exit |
|---|---|---|---|
| **G3** | 12:30 | Gate pass/fail + trace tool + injection flag | Bad candidate fails, good passes; trace tool works |
| **G4** | 17:00 | Full cluster run + evidence + report | All A03 items evidenced; checker clean; commits from both |

---

## Day 2 outputs

- [ ] Baseline vs candidate tables + gate pass/fail evidence
- [ ] Trace record + trace tool + metrics + Batch B injection flagged
- [ ] 40 live queries + coverage before/after + drift + 6 new golden questions
- [ ] `k8s/` manifests: eval Job, CronJob, ConfigMap thresholds, candidate Deployment/Service, rollout/undo
- [ ] `kubectl` evidence and Job logs committed
- [ ] Report ≤8 pages + appendix screenshots
- [ ] `python scripts/check_submission.py` clean
