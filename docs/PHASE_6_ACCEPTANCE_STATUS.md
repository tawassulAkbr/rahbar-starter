# Phase 6 acceptance status

Captured 2026-11-25 against the available Minikube cluster.

## Verified in the dev cluster

- The `api` Service responded to `/api/ask` with HTTP 200 through a port-forward.
- `/metrics` responded with HTTP 200 and exposed the `rahbar_requests_total` counter.
- Trace `abd81aa6a92d448abebd2f4ef6807b28` appeared in API logs and on the mounted
  `rahbar-traces` volume.
- The full API, indexer, and evaluation pytest suite passed: 79 tests.
- The gate rejected the exploratory top-k=4 artifact because it uses deterministic-hash
  embeddings and the reference harness. The release decision is `NOT_AUTHORIZED`.
- The unapproved dev candidate Deployment was scaled to zero after the gate rejection.

The HTTP, metrics, and trace evidence is in
[`phase6-dev-smoke-20261125.json`](../eval/results/phase6-dev-smoke-20261125.json).
It is wiring evidence only: this cluster uses `provider=stub` and `embed_model=dummy-768`.

## Real-model release acceptance

Not completed on this host. Docker reports 3,052,404,736 bytes of total memory and the
Minikube node has 2,911 MiB. The existing node has no Ollama Deployment; the production
manifest requests 2 GiB for Ollama and permits 6 GiB, alongside Chroma, the API, the
control plane, and the evaluation Job. The prior dev evaluation jobs failed their quality
gate (recall@5 0.5185 and abstention correctness 0.5) and cannot be used as real-model
measurements.

The release gate remains closed until the same cluster revision completes all of the
following with `nomic-embed-text` and `llama3.2:3b` against separate baseline and candidate
collections:

1. Baseline and candidate module, Chroma component, and serving API evaluations, each twice.
2. A passing measured top-k=4 gate; the reference-harness PASS artifact is rejected.
3. Candidate stop or promotion according to that gate, recorded rollback, and a post-rollback
   trace showing the restored active collection and embedding version.

Use [`k8s/README.md`](../k8s/README.md) from a node with enough memory to run the production
Ollama model and evaluation workload concurrently. Keep `eval/release-handoff.json` marked
pending until those results exist. Do not promote from the dev smoke evidence.
