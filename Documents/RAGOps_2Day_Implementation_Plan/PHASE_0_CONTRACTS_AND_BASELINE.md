# Phase 0 — Contracts & Baseline Freeze

**Members:** Both · **Day 1, 09:00–09:30** · **Owner:** Both
**Serves:** Assignment 03 Parts A–F (all phases consume these contracts)
**Paper anchor:** 3.2.3 (guardrails), 5.1 (observability/traceability), Table 2

---

## 1. What this file is for

Before any code is written, the two members freeze the Assignment 02 baseline and agree the four schemas that every later phase depends on. This is the "contract-first" step that stops the members blocking each other.

**Output:** `docs/RAGOPS-CONTRACTS.md`, committed, plus a recorded baseline.

---

## 2. Inputs

- The running RAHBAR system from Assignment 02 (API, indexer, `k8s/base/`, `eval/run_eval.py`).
- `eval/baseline.json` and `eval/results.json` from Assignment 02.

---

## 3. Tasks

### 3.1 Freeze the Assignment 02 baseline
- [ ] Confirm the current API answers the golden set through the Ingress and `eval/run_eval.py` exits 0.
- [ ] Commit the current `eval/baseline.json` as the frozen baseline; note the commit SHA.
- [ ] Record the running collection name, embedding model and vector dimension.

### 3.2 Agree the verification report schema
Per document, per run:

| Field | Type | Example |
|---|---|---|
| `run_id` | string | `batch-b-2026-11-22` |
| `document` | string | `batch-b/doc-03.pdf` |
| `sha256` | string | `…` |
| `checks.quality` | pass/fail + reason | `fail: extracted text empty` |
| `checks.completeness` | pass/fail + reason | `fail: missing date` |
| `checks.recency` | pass/fail + reason | `fail: newer version doc-07 exists` |
| `checks.uniqueness` | pass/fail + reason | `fail: exact duplicate of doc-01` |
| `verdict` | pass/fail | `fail` |
| `quarantined` | bool | `true` |

### 3.3 Agree the trace record schema (JSON line per query)
`trace_id, timestamp, query, rewritten_query, embed_model, embed_model_version, collection, retrieved: [{chunk_id, document_id, doc_version, score}], filters, reranked_order, prompt_hash, model, parameters, response, citations, guardrail_actions, latency_per_stage, cache_hit`

### 3.4 Agree `eval/golden.jsonl`
One JSON object per line: `id, question, type (answerable|unanswerable|hard), source, page, label (human|synthetic), reviewed (bool)`

### 3.5 Agree new ConfigMap keys
`QUARANTINE_DIR, ARCHIVE_DIR, VERIFY_ENABLED, GATE_RECALL5_MAX_DROP, GATE_FAITHFULNESS_MIN, GATE_P95_MAX_MS, GATE_ABSTENTION_MIN, COVERAGE_THRESHOLD, TRACE_VOLUME`

### 3.6 Write and commit
- [ ] `docs/RAGOPS-CONTRACTS.md` contains all four schemas and the frozen baseline SHA.
- [ ] Both members state every field back to each other.

---

## 4. Files touched

| File | Change |
|---|---|
| `docs/RAGOPS-CONTRACTS.md` | Created (schemas + baseline) |
| `eval/baseline.json` | Re-committed as frozen baseline |
| `k8s/base/configmap.yaml` | New keys added (placeholders) |

---

## 5. Acceptance (sync gate G0)

- [ ] `docs/RAGOPS-CONTRACTS.md` committed.
- [ ] All four schemas present.
- [ ] Both members can state every field.
- [ ] Frozen baseline SHA recorded.

---

## 6. Handoff

- → `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md` (verification report schema, ConfigMap keys)
- → `PHASE_1_MEMBER_2_GOLDEN_SET_AND_BATCH_B.md` (`golden.jsonl` schema)
- → `PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md` (trace schema)
- → `PHASE_6_MEMBER_1_KUBERNETES.md` (ConfigMap keys)
