# Phase 1 — Member 1: Verification & Incremental Update

**Member:** Member 1 (Platform & Data Infrastructure) · **Day 1, 09:30–17:00**
**Serves:** Assignment 03 **Part A** (A1 verification, A2 incremental update, Batch B run)
**Paper anchor:** 4.2.1 ingestion, 4.2.2 verification, 4.2.3 updating the data lake, 4.2.4 updating retrieval sources

---

## 1. What this file is for

Add the **data-management lifecycle** to the indexer: a verification stage that runs after extraction and before chunking, a quarantine folder for failures, and an incremental update that embeds nothing when nothing changed. This is the foundation every later phase tests against.

---

## 2. Inputs (from earlier phases)

- `PHASE_0_CONTRACTS_AND_BASELINE.md`: verification report schema, ConfigMap keys, quarantine/archive paths.
- `PHASE_1_MEMBER_2_GOLDEN_SET_AND_BATCH_B.md`: Batch B (committed under `corpus/batch-b/`) arrives at sync gate G1 (Day 1 12:30).
- Existing indexer: `indexer/pipeline/run.py`, `extract.py`, `clean.py`, `chunk.py`, `embed.py`, `store.py`.

---

## 3. Tasks

### 3.1 A1 — Verification stage (09:30–12:30)
- [ ] Create `indexer/pipeline/verify.py`.
- [ ] Call it in `indexer/pipeline/run.py` **after `extract` and before `chunk`**.
- [ ] Implement the four checks per document:
  - **Quality:** empty, garbled or failed extraction.
  - **Completeness:** source, title, date/version, page count; text not truncated.
  - **Recency:** a newer version of the same document is detected.
  - **Uniqueness:** exact duplicates by hash; near-duplicates by embedding cosine similarity.
- [ ] Move failing documents to the quarantine folder on the PVC.
- [ ] Write one verification report per run to `eval/results/` using the Phase 0 schema.

### 3.2 Kubernetes for verification (parallel)
- [ ] Add the data-lake PVC, quarantine folder and archive folder so they survive pod restarts.
- [ ] Mount them into `k8s/base/indexer-job.yaml` and the reindex CronJob.
- [ ] Add the new ConfigMap keys from Phase 0.

### 3.3 A2 — Incremental update (13:30–16:00)
- [ ] Hash-based skip: re-running on an unchanged corpus embeds **0 chunks** (log and commit the counts).
- [ ] Changed document replaces **only its own chunks**.
- [ ] Deleted document leaves **no orphan chunks**; prove it with a count by document id.
- [ ] Superseded version is archived and excluded from retrieval through metadata (`superseded: true`).
- [ ] Implement restore so the rollback can be demonstrated.

### 3.4 Run Batch A and Batch B (16:00–17:00)
- [ ] Run both batches through A1 and A2.
- [ ] Commit the verification reports and the incremental counters.

---

## 4. Files touched

| File | Change |
|---|---|
| `indexer/pipeline/verify.py` | Created: four checks + quarantine + report |
| `indexer/pipeline/run.py` | Verification stage wired between extract and chunk |
| `indexer/pipeline/store.py` | Incremental delete/replace by document id; archive metadata |
| `indexer/pipeline/config.py` | New settings: quarantine/archive dirs, verify flag |
| `k8s/base/indexer-job.yaml` | PVC mounts for data lake, quarantine, archive |
| `k8s/base/reindex-cronjob.yaml` | Same mounts and arguments |
| `k8s/base/configmap.yaml` | New keys |
| `eval/results/verification-*.json` | Reports |
| `eval/results/incremental-*.json` | Embed/orphan counters |

---

## 5. Acceptance (sync gate G2, Day 1 17:00)

- [ ] Verification report for Batch B shows pass/fail per check with reasons.
- [ ] Second ingestion on an unchanged corpus shows **0 chunks embedded**.
- [ ] Orphan count by document id is 0 after a deletion.
- [ ] Superseded version archived and excluded from retrieval; restore works.
- [ ] Batch B planted problems are caught (duplicates, near-duplicate, truncated, missing metadata, newer version, injected instruction).

---

## 6. Handoff

- → `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: verified corpus + Batch B.
- → `PHASE_5_MEMBER_2_DRIFT_AND_COVERAGE.md`: per-document embed and orphan counters.
- → `PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md`: quarantine path + injected document id.
- → `PHASE_7_MEMBER_2_REPORT.md`: verification and incremental evidence.
