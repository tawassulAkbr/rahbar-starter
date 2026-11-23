# RAGOps Contracts

Status: frozen for Assignment 03 Phase 0 (G0)

These contracts are the interchange boundary between verification, indexing,
evaluation, API observability, and Kubernetes operations. Producers may add
fields only in a backwards-compatible way; consumers must tolerate unknown
fields. Field names are case-sensitive and JSON is UTF-8.

## 1. Assignment 02 baseline

The tracked baseline is [`eval/baseline.json`](../eval/baseline.json). It is
the deterministic CI/fixture baseline currently available in this worktree:

| Item | Frozen value |
| --- | --- |
| Baseline file | `eval/baseline.json` |
| Baseline introducing commit | `c108cf84fde5e26527a91304882540d8a43ef11cc` |
| Recall@3 | `1.0` |
| Recall@5 | `1.0` |
| Citation validity | `1.0` |
| Abstention rate | `1.0` |
| Collection | `rahbar` |
| Embedding model | `nomic-embed-text` |
| Vector dimension | `768` |
| Top-k | `5` |

The file is intentionally unchanged by Phase 0: its content is already
tracked and its provenance states that it is the fixture contract pending a
live Kind refresh. A live Ingress/evaluation verification was not available
when this contract was frozen because the local Kubernetes context had no
reachable API server (`localhost:8080`). The next live run must use:

```text
python eval/run_eval.py --api <ingress-url>
```

and must exit `0` before replacing this baseline with live evidence.

## 2. Verification report schema

One JSON object is emitted per document per verification run. `checks` is
required and must contain all four checks. Each check is an object with a
boolean `passed` and a human-readable `reason`; a failing reason is required.
`verdict` is `pass` only when all checks pass. `quarantined` is true when the
document is withheld from the serving index.

```json
{
  "run_id": "batch-b-2026-11-22",
  "document": "batch-b/doc-03.pdf",
  "sha256": "<64 lowercase hexadecimal characters>",
  "checks": {
    "quality": {"passed": false, "reason": "extracted text empty"},
    "completeness": {"passed": true, "reason": "required metadata present"},
    "recency": {"passed": true, "reason": "latest known version"},
    "uniqueness": {"passed": true, "reason": "no exact duplicate"}
  },
  "verdict": "fail",
  "quarantined": true
}
```

Normative types:

| Field | Type and constraint |
| --- | --- |
| `run_id` | string, non-empty, stable for the run |
| `document` | string, non-empty document path or identifier |
| `sha256` | string, lowercase 64-character SHA-256 hex digest |
| `checks.quality` | `{passed: boolean, reason: string}` |
| `checks.completeness` | `{passed: boolean, reason: string}` |
| `checks.recency` | `{passed: boolean, reason: string}` |
| `checks.uniqueness` | `{passed: boolean, reason: string}` |
| `verdict` | enum: `pass`, `fail`; must equal the aggregate checks result |
| `quarantined` | boolean; must be true for a failed verdict unless an explicit override is recorded by a later contract |

## 3. Query trace record schema

The API writes one JSON object per query (JSON Lines). Fields are retained for
reproducibility, guardrail auditing, and latency analysis.

```json
{
  "trace_id": "01J...",
  "timestamp": "2026-11-22T09:15:00Z",
  "query": "What is the attendance rule?",
  "rewritten_query": "attendance requirement",
  "embed_model": "nomic-embed-text",
  "embed_model_version": "<provider version or model digest>",
  "collection": "rahbar",
  "retrieved": [
    {"chunk_id": "chunk-001", "document_id": "doc-03", "doc_version": "2026-11", "score": 0.87}
  ],
  "filters": {},
  "reranked_order": ["chunk-001"],
  "prompt_hash": "<lowercase SHA-256 hex digest>",
  "model": "llama3.2:3b",
  "parameters": {"temperature": 0.2, "top_k": 5},
  "response": {"answer": "Students must maintain 100% attendance.", "answered_from_context": true, "confidence": "high"},
  "citations": [{"document_id": "doc-03", "page": 9}],
  "guardrail_actions": [],
  "latency_per_stage": {"rewrite_ms": 3, "embed_ms": 12, "retrieve_ms": 8, "generate_ms": 220},
  "cache_hit": false
}
```

Required fields and types: `trace_id`, `timestamp`, `query`,
`rewritten_query`, `embed_model`, `embed_model_version`, `collection`,
`prompt_hash`, `model` are strings; `response` is an object with `answer`,
`answered_from_context`, and `confidence`; `retrieved`, `reranked_order`,
`citations`, and `guardrail_actions` are arrays; `filters`, `parameters`, and
`latency_per_stage` are objects; `cache_hit` is boolean. Each `retrieved`
entry requires string `chunk_id`, `document_id`, `doc_version`, and numeric
`score`. `timestamp` is RFC 3339 UTC. `prompt_hash` is a SHA-256 digest and
`latency_per_stage` values are non-negative milliseconds.

Phase 4 adds `generation_attempts` containing each exact provider prompt,
`generation_path` distinguishing provider calls from extractive/abstention
paths, and `origin_trace_id` on cache hits. Replay follows that reference to
the generating query. Empty prompts are hashed normally and mean no provider
prompt was sent for that path. `embed_model_version` is the resolved model
digest, not an assignment label. `retrieval_ms` includes embedding and reranking;
`retrieve_ms` excludes them. These durations must not be summed together.

## 4. Evaluation golden set schema

`eval/golden.jsonl` is UTF-8 JSON Lines: exactly one object per line, no JSON
array wrapper. IDs are unique within a set.

```json
{"id":"q-001","question":"What is the attendance rule?","type":"answerable","source":"doc-03.pdf","page":9,"label":"human","reviewed":true}
```

| Field | Type and constraint |
| --- | --- |
| `id` | string, unique and non-empty |
| `question` | string, non-empty |
| `type` | enum: `answerable`, `unanswerable`, `hard` |
| `source` | string; canonical source document identifier |
| `page` | integer >= 1, or `null` when the source has no pages |
| `label` | enum: `human`, `synthetic` |
| `reviewed` | boolean; production entries require `true` before use as a gate |

For `unanswerable` questions, `source` and `page` may be null. `answerable`
and `hard` questions must identify their expected source and page when those
metadata exist.

## 5. ConfigMap contract

The following keys are reserved in `k8s/base/configmap.yaml`. Values are
strings because Kubernetes ConfigMap data is string-valued; applications
parse booleans and numbers at their boundary. The base values are conservative
placeholders until the corresponding Phase 1-6 implementation consumes them.

| Key | Placeholder | Meaning |
| --- | --- | --- |
| `QUARANTINE_DIR` | `/data/quarantine` | Failed documents, excluded from serving |
| `ARCHIVE_DIR` | `/data/archive` | Superseded/processed source documents |
| `VERIFY_ENABLED` | `"false"` | Enable verification pipeline when implemented |
| `GATE_RECALL5_MAX_DROP` | `"0.05"` | Maximum allowed recall@5 decrease |
| `GATE_FAITHFULNESS_MIN` | `"0.95"` | Minimum faithfulness score |
| `GATE_P95_MAX_MS` | `"2000"` | Maximum p95 query latency in milliseconds |
| `GATE_ABSTENTION_MIN` | `"1.0"` | Minimum required abstention correctness |
| `COVERAGE_THRESHOLD` | `"0.80"` | Minimum corpus/evaluation coverage |
| `TRACE_VOLUME` | `"1.0"` | Fraction of queries traced; `1.0` means all |

Existing embedding, retrieval, collection, and provider keys remain unchanged
in the base ConfigMap so Phase 0 does not change the Assignment 02 stub
deployment. Production overlays may pin the live embedding values.

## 6. G0 checklist and handoff

- [x] Baseline file is tracked and its introducing commit SHA is recorded.
- [x] Verification report schema is frozen.
- [x] Trace record schema is frozen.
- [x] Golden JSONL schema is frozen.
- [x] ConfigMap keys are reserved with typed placeholders.
- [ ] Live Ingress golden-set run: pending a reachable Kubernetes context.

Consumers: Phase 1 verification consumes sections 2 and 5; golden-set work
consumes section 4; trace/observability consumes section 3; Kubernetes work
consumes section 5.
