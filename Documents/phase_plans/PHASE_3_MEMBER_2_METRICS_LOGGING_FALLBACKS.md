# Phase 3 — Member 2: Embedding Pin Guardrail, Observability & Grounding Checks

## Role: AI Reliability & Observability Engineer
**Deliverables Target:** In-code Embedding Pin Guardrail, Citation Matching Verifier, Honest Abstention Logic, Structured JSON Logging, and Prometheus Metrics.

---

### Key Responsibilities & Implementation Steps

#### 1. In-Code Embedding Pin Guardrail
- Section 4.4 Requirement:
  - Both indexer and API read `EMBED_MODEL` from the same ConfigMap.
  - When the indexer writes to Chroma, it records `embed_model` and `dimension` in collection metadata.
  - At startup and in `/readyz`:
    - The API fetches collection metadata from Chroma.
    - Compares `collection.metadata["embed_model"]` with its local `settings.embed_model`.
    - If there is a mismatch:
      - Log a clear error: `f"Embedding model mismatch! Collection built with {coll_model}, but API configured with {api_model}"`.
      - `/readyz` fails with HTTP 503, preventing the pod from entering the Service endpoint pool!
    - This turns a silent failure (corrupted vector search) into a hard, detectable readiness failure.

#### 2. Citation Integrity Verification
- Grounding verification in `services/answer.py`:
  - Extract all citations from the generated `Answer.citations`.
  - For each citation (`source`, `section`, `page`), compare against the retrieved passages list for that exact request.
  - If a citation refers to a chunk/source that was **NOT** retrieved $\rightarrow$ flag citation as invalid and scrub/correct it.
  - Prevents the -10 mark automatic deduction for hallucinated citations.

#### 3. Honest Abstention Logic (Relevance Floor)
- Check similarity scores of retrieved passages against `RELEVANCE_FLOOR` (e.g. 0.60):
  - If no retrieved chunk clears the relevance floor, or if retrieved chunks do not answer the question:
    - Return `answered_from_context: false`.
    - Friendly message: *"The provided university policy documents do not cover this topic."*
    - Confidence: `"low"`.
    - Empty citations: `[]`.
- Write dedicated test asserting honest abstention for deliberately omitted topics.

#### 4. Observability: JSON Logging & Prometheus Metrics
- **JSON Structured Logging (`api/app/logjson.py`)**:
  - Log to stdout only, never to a local file.
  - Every log entry must include `request_id` (from `X-Request-ID` or generated uuid4).
  - Include retrieval telemetry: `top_k`, `chunk_ids`, `scores`, `answered_from_context`, `latency_ms`.
- **Prometheus Metrics (`/metrics`)**:
  - Expose in Prometheus text format:
    - `request_count_total{route, status}`
    - `request_latency_seconds{route}` (Histogram)
    - `retrieval_latency_seconds`
    - `generation_latency_seconds`
    - `cache_hits_total`, `cache_misses_total`
    - `abstention_count_total`
    - `fallback_count_total`
    - `tokens_in_total`, `tokens_out_total`

---

### Member 2 Acceptance Checklist (Phase 3)
- [ ] Embedding pin mismatch causes `/readyz` to return 503 and logs clear conflict.
- [ ] Citation verifier guarantees 100% of returned citations correspond to retrieved chunks.
- [ ] Relevance floor triggers honest abstention with `answered_from_context: false`.
- [ ] JSON logs print to stdout with `request_id`, scores, and chunk ids.
- [ ] `/metrics` exposes Prometheus counters and histograms for all required metrics.
- [ ] Unit tests written for embedding pin check, citation verifier, and relevance floor.
