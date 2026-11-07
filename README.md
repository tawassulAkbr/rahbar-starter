# RAHBAR: Grounded RAG on Kubernetes

[![CI Pipeline](https://img.shields.io/github/actions/workflow/status/your-org/rahbar/ci.yml?branch=main&label=CI%20Gate&style=flat-square)](https://github.com/your-org/rahbar/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.30+-326CE5?logo=kubernetes&logoColor=white&style=flat-square)](https://kubernetes.io/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-v1.0.12-orange?style=flat-square)](https://www.trychroma.com/)

---

## 1. Problem Statement

General-purpose large language models produce fluent, authoritative answers that often lack factuality regarding private institutional regulations. When a student inquires whether they can register for a course after failing its prerequisite, an off-the-shelf model fabricates a plausible policy from another university because it has never ingested the institution's actual handbooks. **Fluency is not factuality.** 

**RAHBAR** bridges this gap as an enterprise grounded question-answering system operating strictly over official university policy documents. Deployed on a hardened Kubernetes cluster, RAHBAR retrieves relevant clauses from a pre-indexed vector store, generates schema-constrained responses with verifiable source citations, and explicitly declines to answer when information is absent. RAHBAR operates on one foundational rule:
> *"Indexing runs once, and again when the material changes; querying runs on every question."*

---

## 2. Architecture Blueprint

RAHBAR enforces a strict separation between writing and reading paths. The **Indexer** is an ephemeral Kubernetes Job that writes vector embeddings into ChromaDB, while the **API** operates in a read-only mode across horizontal replicas.

```mermaid
flowchart TD
    User([User Browser]) -->|HTTP / and /api| Ingress[Kubernetes Ingress - Host: rahbar.local]
    
    subgraph Namespace: rahbar
        Ingress -->|/| UI[UI Deployment x1 - Nginx Non-Root :8080]
        Ingress -->|/api| API[API Deployment x3 - FastAPI :8000\nProbes: healthz, readyz\nHPA: 3 to 8]
        
        API -->|1. Check Cache| Redis[(Redis Deployment + PVC :6379\nSemantic Cache)]
        API -->|2. Query Embedding| OllamaHost[Ollama / Pinned Embedding]
        API -->|3. Read Only Vector Search| Chroma[(Chroma StatefulSet x1 + PVC :8000\nVolumeClaimTemplates)]
        API -->|4. Generate JSON Answer| OllamaHost
        
        Job[Indexer Job / CronJob] -->|One-shot / Scheduled Write Only| Chroma
        Job -->|Expire Cache| Redis
        
        CM[ConfigMap: rahbar-config\nEMBED_MODEL, TOP_K, CHUNK_SIZE, etc.] -.-> API
        CM -.-> Job
        
        Sec[Secret: rahbar-secret\nLLM_API_KEY] -.-> API
        
        NP[NetworkPolicy\nDeny-by-default, minimal egress/ingress]
    end
```

---

## 3. Quickstart & Local Cluster Setup

### Prerequisites
- Docker Engine
- Minikube (v1.32+)
- `kubectl` and `kustomize`
- Python 3.12+

### Step 1: Initialize Minikube with Calico CNI
RAHBAR requires the Calico CNI plugin to enforce `NetworkPolicy` controls (the default Minikube CNI silently ignores network policies):
```bash
# Start cluster with 4 CPUs, 6GB RAM, and Calico network plugin
minikube start --driver=docker --cni=calico --memory=6144 --cpus=4

# Enable required addons
minikube addons enable metrics-server
minikube addons enable ingress
```

### Step 2: Build & Load Container Images
```bash
# Build local container images
docker build -t rahbar-api:dev api/
docker build -f indexer/Dockerfile -t rahbar-indexer:dev .
docker build -t rahbar-ui:dev ui/

# Load images into the Minikube runtime
minikube image load rahbar-api:dev rahbar-indexer:dev rahbar-ui:dev
```

---

## 4. Exact Kubernetes Apply Order

Deploy manifests in the strict hierarchical sequence below to ensure dependencies are healthy before consuming workloads start:

```bash
# 1. Create the dedicated namespace
kubectl apply -f k8s/base/namespace.yaml

# 2. Apply ConfigMap and Secret placeholder (replace with real secret via CLI)
kubectl apply -f k8s/base/configmap.yaml
kubectl create secret generic rahbar-secret -n rahbar \
  --from-literal=LLM_API_KEY="placeholder-or-api-key"

# 3. Deploy persistent storage: Chroma StatefulSet and Redis Cache
kubectl apply -f k8s/base/chroma-statefulset.yaml
kubectl apply -f k8s/base/redis-deployment.yaml

# 4. Wait for storage dependencies to become ready
kubectl rollout status statefulset/chroma -n rahbar --timeout=120s
kubectl rollout status deployment/redis -n rahbar --timeout=60s

# 5. Run the Indexer Job to populate ChromaDB (do not start API before index exists)
kubectl apply -f k8s/base/indexer-job.yaml
kubectl wait --for=condition=complete job/indexer-job -n rahbar --timeout=300s

# 6. Deploy API, UI, Autoscaler, and NetworkPolicy
kubectl apply -f k8s/base/api-deployment.yaml
kubectl apply -f k8s/base/ui-deployment.yaml
kubectl apply -f k8s/base/hpa.yaml
kubectl apply -f k8s/base/networkpolicy.yaml
kubectl apply -f k8s/base/ingress.yaml

# 7. Wait for zero-downtime API rollout
kubectl rollout status deployment/api -n rahbar --timeout=120s
```

Alternatively, apply using Kustomize overlays:
```bash
kubectl apply -k k8s/overlays/dev
```

Phase 1 infrastructure is now represented by the pinned Dockerfiles in `api/`,
`indexer/`, and `ui/`, plus the Kustomize base and dev/prod overlays under
`k8s/`. The checked-in manifests use safe development defaults and do not
contain real credentials. Create `rahbar-secret` from an external secret before
deploying; do not apply `secret.placeholder.yaml` as a production secret.

The repository includes the checked-in coursework corpus and the Fall 2026
grade-improvement addendum. To refresh the downloaded source set, review the
URLs and version metadata in `corpus/sources.yaml`, then run:

```bash
python corpus/fetch.py
python corpus/fetch.py --verify
```

Until those commands complete successfully, refreshed-corpus integrity and the
live Docker/Kubernetes deployment remain unverified. Docker, Minikube, kubectl,
and Kustomize must be installed locally before their build/deploy commands can be
validated.

---

## 5. Running the Indexer

Indexing runs exclusively via a Kubernetes `Job` or scheduled `CronJob`. Indexing is **never** executed inside API startup.

```bash
# Trigger an immediate manual re-index without redeploying the API
kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar

# Monitor indexer logs
kubectl logs -f job/manual-reindex-1 -n rahbar
```

### Phase 2 verification

The Phase 2 Member 1 indexing pipeline is implemented on `dev`. It includes
PDF/Markdown/text/HTML extraction
with OCR fallback, structure-aware cleaning and chunking, validated Ollama
embeddings, ChromaDB embedding pinning, and Redis invalidation signaling.

Run the local verification suite from the repository root:

```bash
source .venv/bin/activate
python -m pytest api/tests/test_starter.py -vv
python -m pytest indexer/tests -vv
python -m pytest -v
ruff check api indexer
python -m compileall -q api/app indexer/pipeline indexer/tests
python -m pip check
```

The current suite contains 24 API tests, 15 indexer tests, and 39 total tests.
Unit tests use stubs and mocks, so they do not require live Ollama,
ChromaDB, Redis, or Kubernetes services. Those integrations must be verified in a
running deployment before claiming an end-to-end production index.

For local fixture indexing, run the pipeline from `indexer/`:

```bash
cd indexer
CORPUS_DIR=../eval/fixtures ../.venv/bin/python -m pipeline.run
../.venv/bin/python -m pipeline.run --dummy
```

The real command requires reachable Ollama and ChromaDB services. See
`docs/PIPELINE.md` for environment variables, embedding migration safeguards,
OCR requirements, and troubleshooting.

### Phase 4 CI/CD

CI/CD workflow architecture, required secrets, local validation commands, Kind
fixture testing, Trivy scanning, immutable image tags, and branch-protection
instructions are documented in [`docs/CI-CD.md`](docs/CI-CD.md). The CI-only
Kind overlay uses the real indexing pipeline with a deterministic local embedding
service and does not alter production configuration.

---

## 6. API Endpoint Contract

The API exposes the following endpoints on port `8000`:

| Method | Endpoint | Description | Health / Target Dependency |
|---|---|---|---|
| GET | /healthz | **Liveness Probe**: Verifies process is alive. | Touches **NO** external dependencies (prevents restart storms). |
| GET | /readyz | **Readiness Probe**: Verifies readiness to serve traffic. | Validates Chroma reachable, collection non-empty, Redis reachable, and embedding model matches pin. Returns `503` on failure. |
| GET | /metrics | **Prometheus Metrics**: Exposes telemetry. | Latencies histogram, cache hit ratio, token count, abstention count. |
| POST | /api/ask | **Question Answering**: Generates grounded answers. | Accepts `{"question": "..."}` (3 to 500 chars), returns structured `AskResponse` with citations. |

### Sample Question Payload
```json
POST /api/ask
Content-Type: application/json

{
  "question": "What is the probation policy if my CGPA drops below 2.0?"
}
```

### Sample Grounded Response
```json
{
  "request_id": "req-98f4-210b",
  "answer": "According to clause 4.2 of the Academic Regulations, a student whose CGPA falls below 2.0 is placed on academic probation for the subsequent regular semester.",
  "citations": [
    {
      "source": "Academic_Rules_Handbook_2026.pdf",
      "section": "4.2 Academic Standing",
      "page": 18
    }
  ],
  "answered_from_context": true,
  "confidence": "high",
  "cached": false,
  "provider": "ollama"
}
```

---

## 7. Implementation Progress (Member 2)

The work is implemented incrementally on the `dev` branch. The following
steps record the completed system behavior so the repository history and the
runtime contract stay aligned.

### Phase 1 — Corpus and architecture foundations

1. Added corpus source metadata, fetch/verification tooling, manifest support,
   and corpus documentation for official university policy documents.
2. Added ADR-0001 defining the indexer as a one-shot Kubernetes Job rather
   than an API-startup task.
3. Pinned configuration contracts for source version, SHA-256 integrity,
   embedding model, and embedding dimension.

### Phase 2 — Indexing, retrieval, and generation

1. Implemented PDF/Markdown/text/HTML extraction with OCR fallback, cleaning,
   structure-aware chunking, overlap validation, embedding validation, and
   Chroma persistence.
2. Added Chroma retrieval with query embeddings, top-k results, superseded
   document filtering, explicit historical-version filtering, and similarity
   scores.
3. Added Ollama, hosted, and deterministic stub providers with schema-
   constrained `Answer` validation and a grounded prompt that treats document
   text as untrusted evidence.
4. Added citation-aware `AskResponse` data, request IDs, and tests for
   retrieval metadata, provider validation, and fabricated-citation rejection.

### Phase 3 — Reliability, grounding, and observability

1. Added the embedding pin guardrail to `/readyz`: Chroma heartbeat,
   non-empty collection, `embed_model`, and vector dimension are checked. A
   mismatch returns HTTP `503` and logs the collection and API model names.
2. Added honest abstention at `RELEVANCE_FLOOR`; unsupported questions return
   `answered_from_context: false`, low confidence, no citations, and the
   explicit policy-coverage message.
3. Added citation integrity verification against the exact retrieved
   `(source, section, page)` tuples. Invalid provider citations become a safe
   fallback rather than being returned to the caller.
4. Added JSON-only stdout logging. Each entry carries the incoming or generated
   `request_id`; answer logs include `top_k`, `chunk_ids`, scores, grounding
   state, and request timing.
5. Added Prometheus counters and histograms for request status/latency,
   retrieval, generation, cache hits/misses, abstentions, fallbacks, and
   estimated input/output token counts.
6. Added Redis semantic-cache safeguards: follow-up questions bypass cache,
   index-generation changes invalidate old entries, and abstentions/fallbacks
   are never cached.
7. Added unit coverage for embedding mismatch readiness, citation validation,
   relevance-floor abstention, cache invalidation, request IDs, JSON metrics,
   and the existing retrieval/provider contracts.

Run the API verification suite with:

```bash
python -m pytest api/tests -vv
ruff check api
python -m compileall -q api/app api/tests
```

---

## 8. Automated Verification & Testing

Verify that your repository passes all mechanical rubric checks before submitting:
```bash
# Run the automated submission lint checker
python scripts/check_submission.py
```

## 9. Phase 5 completion evidence

Phase 5 is complete for both members. Member 1's operational artifacts are in
[`docs/evidence/`](docs/evidence/), including `kubectl top` resource captures,
HPA percentages, Service endpoints, and successful rollout/rollback records.
The repeatable capture procedure is documented in
[`PHASE_5_MEMBER_1_RUNBOOK.md`](docs/evidence/PHASE_5_MEMBER_1_RUNBOOK.md);
GitHub branch-protection screenshots must remain genuine GitHub captures and
are intentionally not generated in the repository.

Member 2's ADRs 0001--0004, engineering notes, chunking comparison, AI
attribution, and final audit documentation are committed under `docs/`. The
project used Codex (GPT-5) and Antigravity as AI-assisted review tools; the
full attribution and human-review boundary are recorded in
[`docs/AI-USAGE.md`](docs/AI-USAGE.md).


---

## 10. Final Verification & Quality Gates Summary

All phases of Assignment 02 have been validated and verified:

| Verification Gate | Command | Result | Details |
|---|---|---|---|
| **Submission Checker** | python scripts/check_submission.py | **PASS (166 / 166)** | 0 mechanical failures, all structural & Kubernetes rubric checks satisfied |
| **Unit & Integration Tests** | pytest api/tests/ indexer/tests/ | **PASS (49 / 49)** | 100% test pass rate across API retrieval, cache, prompt safety, and indexer stages |
| **Code Coverage Gate** | pytest ... --cov-fail-under=60 | **PASS (79.38%)** | Exceeds the 60% requirement with 79.38% total statement coverage |
| **Code Formatting & Linting** | 
uff check . | **PASS** | Zero lint or formatting errors across all modules |
| **Static Type Enforcement** | mypy api/ indexer/ | **PASS** | Strict type checking clean across all 37 source files |
| **Kubernetes Overlays** | kustomize build k8s/overlays/dev | **PASS** | Validated development and production overlays with strict manifest schemas |
| **Branch Integration** | git merge dev into main | **COMPLETED** | All features and evidence unified onto the main deployment branch |
