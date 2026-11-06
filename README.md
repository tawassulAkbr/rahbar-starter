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
docker build -t rahbar-indexer:dev indexer/
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

The Phase 2 Member 1 indexing pipeline is implemented on
`feature/phase2-indexing-pipeline`. It includes PDF/Markdown/text/HTML extraction
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

The current verified result is 7 API tests, 15 indexer tests, and 22 total tests
passing. Unit tests use stubs and mocks, so they do not require live Ollama,
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

## 7. Automated Verification & Testing

Verify that your repository passes all mechanical rubric checks before submitting:
```bash
# Run the automated submission lint checker
python scripts/check_submission.py
```
