# Phase 4 — Member 2: Trace & Observability

**Member:** Member 2 (AI Quality, Retrieval & Evaluation) · **Day 1 17:30 → Day 2 12:30**
**Serves:** Assignment 03 **Part D** (D1 trace record, D2 trace tool, D3 metrics, D4 guardrail logging, D5 root cause)
**Paper anchor:** 3.2.3 guardrails, 5.1 observability, Table 2 (observability, traceability)

---

## 1. What this file is for

Make every query reconstructable: one JSON line per query with the full provenance, a tool that rebuilds the exact prompt for a trace id, metrics over a time window, and a guardrail log that catches the injected Batch B document.

---

## 2. Inputs (from earlier phases)

- `PHASE_0_CONTRACTS_AND_BASELINE.md`: trace JSON schema.
- `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`: quarantine path + injected document id.
- `PHASE_2_MEMBER_2_OFFLINE_TESTING.md`: one wrong/abstained answer + trace id.
- Existing `api/app/services/answer.py`, `api/app/routes/metrics.py`, `api/app/logjson.py`.

---

## 3. Tasks

### 3.1 D1 — trace record (Day 1 17:30 → Day 2 09:30)
- [ ] Every query writes one JSON line with: trace id, timestamp, user query, rewritten query, embedding model and version, collection name/version, retrieved chunk ids with document ids, document versions and scores, filters applied, reranked order, prompt hash (or full prompt), model and parameters, response, citations, guardrail actions, latency per stage, cache hit/miss.
- [ ] Emit to stdout (JSON lines) and to the trace volume.

### 3.2 D2 — trace tool (Day 2 09:30–10:00)
- [ ] `python scripts/trace.py <trace_id>` prints the exact context and prompt that produced the answer.

### 3.3 D3 — metrics (Day 2 10:00–10:30)
- [ ] Expose/report: top-1 retrieval similarity distribution, abstention rate, cache hit rate, p95 latency per stage, number of injection attempts flagged.
- [ ] A script summarizes the trace log over a time window.

### 3.4 D4 — guardrail logging (Day 2 10:30–11:00)
- [ ] The injection defence (or a retrieval rail) writes its action into the trace.
- [ ] Test it with the injected document from Batch B; assert the action is present.

### 3.5 D5 — root cause from the trace only (Day 2 11:00–11:30)
- [ ] Pick one wrong or abstained answer from Part B.
- [ ] Using only its trace, find the cause (which chunk, document version or filter).
- [ ] Write 5 lines in the report.

---

## 4. Files touched

| File | Change |
|---|---|
| `api/app/services/answer.py` | Emit trace record per query |
| `api/app/routes/metrics.py` | New RAGOps metrics |
| `api/app/logjson.py` | Trace line helper |
| `scripts/trace.py` | Trace tool CLI |
| `scripts/summarize_traces.py` | Window summary |
| `traces/*.jsonl` | Trace samples |

---

## 5. Acceptance (sync gate G3, Day 2 12:30)

- [ ] One full trace record captured.
- [ ] Trace tool rebuilds the prompt for a real trace id.
- [ ] Batch B injection is flagged in the trace.
- [ ] Metrics endpoint and window summary work.

---

## 6. Handoff

- → `PHASE_6_MEMBER_1_KUBERNETES.md`: trace volume mount + metrics endpoint.
- → `PHASE_7_MEMBER_2_REPORT.md`: trace sample, rebuilt prompt, root-cause note.
