# Phase 4 completion checklist

**Historical checklist:** see [the Phase 0–4 re-audit](PHASE_0_TO_4_REAUDIT.md)
for prompt, cache provenance, versioning and guardrail corrections.

- [x] Every normal query emits one JSON trace line to stdout and `TRACE_DIR/traces.jsonl`.
- [x] Cache-hit queries also emit a trace with `cache_hit: true`.
- [x] Trace fields include query rewrite, embedding model/version, collection, retrieved
  chunk/document/version/score, filters, reranking, prompt hash, prompt/context, model,
  parameters, response, citations, guardrail actions, stage latency, and cache state.
- [x] `scripts/trace.py <trace_id>` prints the captured context and exact prompt.
- [x] Prometheus exposes top-1 similarity, abstention, cache-hit, injection, and existing
  latency metrics.
- [x] `scripts/summarize_traces.py` supports a time window and reports the required rates,
  distributions, p95 stage latency, and injection count.
- [x] Batch B injection is detected as untrusted data and logged in the trace.
- [x] A trace-only root-cause note is committed.
- [x] Kubernetes ConfigMap, PVC, mount, and read-only-root-filesystem compatibility are present.

Verification commands:

```text
python scripts/trace.py phase4-injection-sample --path traces/phase4-sample.jsonl
python scripts/summarize_traces.py --path traces/phase4-sample.jsonl
kubectl kustomize k8s/base
python -m compileall -q api scripts
python -m pytest api/tests/test_tracing.py -q
```
