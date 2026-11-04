# Phase 1 — Member 1: Containerization (ALL Docker) & Kubernetes Infrastructure

## Role: Lead DevOps, Containerization & Platform Engineer
**Ownership:** Member 1 exclusively owns ALL Dockerfiles, `.dockerignore` files, image building, container hardening, and Kubernetes manifests.

---

### Key Responsibilities & Implementation Steps

#### 1. Containerization & Dockerfiles (Exclusively Member 1)
Build lightweight, hardened, multi-stage production images adhering strictly to section 4.7 and section 10:

- **`api/Dockerfile`**:
  - Base: Pinned `python:3.12-slim` (e.g. `python:3.12.7-slim`).
  - Create dedicated non-root system user:
    ```dockerfile
    FROM python:3.12.7-slim
    WORKDIR /app
    RUN groupadd -r appgroup && useradd -r -g appgroup -u 10001 appuser
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY app/ ./app
    USER appuser
    EXPOSE 8000
    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ```

- **`indexer/Dockerfile`**:
  - Base: Pinned `python:3.12-slim`.
  - Install tesseract OCR runtime:
    ```dockerfile
    FROM python:3.12.7-slim
    WORKDIR /indexer
    RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        && rm -rf /var/lib/apt/lists/*
    RUN groupadd -r indexergroup && useradd -r -g indexergroup -u 10002 indexeruser
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY pipeline/ ./pipeline
    USER indexeruser
    CMD ["python", "-m", "pipeline.run"]
    ```

- **`ui/Dockerfile`**:
  - Multi-stage build ensuring no Node/build tools exist in the final production layer:
    ```dockerfile
    FROM alpine:3.20 AS builder
    WORKDIR /src
    COPY index.html nginx.conf ./

    FROM nginxinc/nginx-unprivileged:1.27-alpine
    COPY --from=builder /src/nginx.conf /etc/nginx/nginx.conf
    COPY --from=builder /src/index.html /usr/share/nginx/html/index.html
    EXPOSE 8080
    USER 101
    CMD ["nginx", "-g", "daemon off;"]
    ```

- **`.dockerignore` files**:
  - Create in root, `api/`, `indexer/`, and `ui/`.
  - Must exclude: `.git`, `__pycache__`, `*.pyc`, `.venv`, `venv`, `corpus/raw/`, `docs/`, `eval/fixtures/`.

- **Local Image Build & Minikube Ingestion**:
  ```bash
  docker build -t rahbar-api:dev api/
  docker build -t rahbar-indexer:dev indexer/
  docker build -t rahbar-ui:dev ui/
  minikube image load rahbar-api:dev rahbar-indexer:dev rahbar-ui:dev
  ```

---

#### 2. Kubernetes Cluster Setup & Base Manifests (`k8s/base/`)
Initialize Minikube with Calico CNI:
```bash
minikube start --driver=docker --cni=calico --memory=6144 --cpus=4
minikube addons enable metrics-server
minikube addons enable ingress
```

Create all required manifests with strict enterprise constraints:
- `namespace.yaml`:
  - Dedicated namespace: `rahbar`. Never use `default`.
- `configmap.yaml`:
  - Keys: `EMBED_MODEL: "dummy-768"` (for Phase 1 stubs), `TOP_K: "5"`, `CHUNK_SIZE: "400"`, `CHUNK_OVERLAP: "50"`, `RETRIEVER: "stub"`, `LLM_PROVIDER: "stub"`, `CHROMA_HOST: "chroma"`, `CHROMA_PORT: "8000"`, `CHROMA_COLLECTION: "rahbar"`, `TEMPERATURE: "0.2"`, `RELEVANCE_FLOOR: "0.6"`, `CACHE_THRESHOLD: "0.92"`.
- `secret.placeholder.yaml`:
  - Contains dummy `REPLACE_ME`. Excluded from `kustomization.yaml`! Real secrets created via CLI:
  ```bash
  kubectl create secret generic rahbar-secret -n rahbar --from-literal=LLM_API_KEY="dummy"
  ```
- `chroma-statefulset.yaml`:
  - Kind: `StatefulSet` with `replicas: 1`
  - `volumeClaimTemplates` with PVC for `/data` (10Gi).
  - ClusterIP Service `chroma` on port 8000. Never NodePort or LoadBalancer.
- `redis-deployment.yaml`:
  - Kind: `Deployment` with `replicas: 1`, attached PVC for persistence `/data`.
  - ClusterIP Service `redis` on port 6379.
- `api-deployment.yaml`:
  - `replicas: 3`
  - `image: rahbar-api:dev`, `imagePullPolicy: IfNotPresent`
  - `strategy.rollingUpdate`: `maxSurge: 1`, `maxUnavailable: 0`
  - Probes:
    - `startupProbe`: httpGet `/healthz` on 8000, `failureThreshold: 30`, `periodSeconds: 2`
    - `livenessProbe`: httpGet `/healthz` on 8000, `failureThreshold: 3`, `periodSeconds: 20`
    - `readinessProbe`: httpGet `/readyz` on 8000, `failureThreshold: 3`, `periodSeconds: 10`
  - Lifecycle: `preStop: exec: command: ["/bin/sh", "-c", "sleep 5"]`, `terminationGracePeriodSeconds: 30`
  - Resources: `requests: {cpu: "100m", memory: "256Mi"}`, `limits: {cpu: "500m", memory: "512Mi"}`
  - SecurityContext: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities: {drop: ["ALL"]}`, `automountServiceAccountToken: false`.
  - ClusterIP Service `api` on port 8000.
- `ui-deployment.yaml`:
  - `image: rahbar-ui:dev`, `imagePullPolicy: IfNotPresent`
  - Serving nginx chat UI on port 8080.
  - Mount `emptyDir` at `/tmp` for nginx temporary files.
  - ClusterIP Service `ui` on port 8080.
- `ingress.yaml`:
  - Host: `rahbar.local`
  - Paths: `/api` -> `api:8000`, `/` -> `ui:8080`.
- `hpa.yaml`:
  - Scale target: `Deployment/api`, `minReplicas: 3`, `maxReplicas: 8`, target CPU: 70%.
- `networkpolicy.yaml`:
  - Deny-by-default for namespace `rahbar` (`podSelector: {}`).
  - Allow UI ingress from Ingress controller.
  - Allow API ingress from UI and Ingress.
  - Allow Chroma ingress from API and Indexer Job only! (UI cannot touch Chroma).
  - Allow Redis ingress from API only.
  - Allow API/Indexer egress to `kube-dns` on UDP/TCP port 53.
  - Allow API/Indexer egress to `host.minikube.internal:11434` for Ollama.
- `indexer-job.yaml` & `reindex-cronjob.yaml`:
  - One-shot Job with `restartPolicy: OnFailure`, `backoffLimit: 3`.
  - Runs dummy indexer: `python -m pipeline.run --dummy`.
  - Weekly CronJob: `schedule: "0 0 * * 0"`.

---

#### 3. Kustomize Setup (`k8s/overlays/dev` and `prod`)
- Set up `k8s/base/kustomization.yaml` referencing all manifests (except secret placeholder).
- Set up `k8s/overlays/dev/kustomization.yaml` and `k8s/overlays/prod/kustomization.yaml`.
- Verify with `kustomize build k8s/overlays/prod | kubeconform -strict`.

---

### Member 1 Acceptance Checklist (Phase 1)
- [ ] All 3 Dockerfiles authored, pinned, with non-root USER (`runAsNonRoot: true` verified).
- [ ] UI Dockerfile is verified multi-stage (no Node in final image).
- [ ] `.dockerignore` files created in root and subdirectories.
- [ ] Local container images built and loaded into Minikube (`minikube image load`).
- [ ] Minikube running with Calico and Ingress enabled.
- [ ] All manifests cleanly build through Kustomize.
- [ ] Applying manifests deploys Redis, Chroma, 3 API pods, and UI into `rahbar` namespace.
- [ ] Indexer Job completes successfully in `--dummy` mode, writing 3 dummy chunks into Chroma.
- [ ] Ingress routes `curl http://rahbar.local/healthz` to API returning `{"status": "alive"}`.
- [ ] Verified zero occurrences of secrets in committed manifests.
