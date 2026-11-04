# Phase 4 — Member 1: CI/CD Pipelines & Ephemeral Cluster Testing

## Role: DevOps & Automation Architect
**Deliverables Target:** Production-ready `.github/workflows/ci.yml` and `.github/workflows/cd.yml`, multi-architecture Docker image builds, Trivy vulnerability scans, and Kind/K3d ephemeral cluster integration.

---

### Key Responsibilities & Implementation Steps

#### 1. Continuous Integration Pipeline (`.github/workflows/ci.yml`)
Triggered on: Pull Request to `main`, and push to `dev`.
Must include the following sequential/gated jobs:
- **`lint`**:
  - Run `ruff check .` and `mypy api/ indexer/`.
- **`test`**:
  - Run `pytest api/tests/ indexer/tests/ --cov=app --cov=pipeline --cov-report=term-missing`.
  - Assert overall test coverage $\ge 60\%$.
  - Uses only stub providers: 0 external network calls, 0 real LLM tokens.
- **`manifests`**:
  - Validate Kubernetes manifests: `kustomize build k8s/overlays/prod | kubeconform -strict -summary`.
  - Catch malformed YAMLs or invalid K8s API versions in 20 seconds.
- **`build`**:
  - Build images for API, Indexer, and UI locally (without pushing).
- **`scan`**:
  - Run Trivy vulnerability scan on built images:
    - Action: `aquasecurity/trivy-action`.
    - Severity: `HIGH,CRITICAL`.
    - Fail build on findings that have an available fix.
- **`e2e-eval`**:
  - Spin up an ephemeral Kubernetes cluster (`helm/kind-action` or `k3d-io/k3d-action`).
  - Load locally built container images into Kind cluster.
  - Apply manifests: `kubectl apply -k k8s/overlays/dev`.
  - Run Indexer Job using the tiny fixture corpus (`CORPUS_DIR=eval/fixtures`).
  - Wait for rollout: `kubectl rollout status deployment/api -n rahbar --timeout=120s`.
  - Run evaluation gate: `python eval/run_eval.py --api http://localhost:8000 --fixtures`.
  - Gate enforces: no recall regression > 5%, 100% abstention, $\ge 95\%$ citation validity.

#### 2. Continuous Delivery Pipeline (`.github/workflows/cd.yml`)
Triggered on: Push to `main` branch.
Must enforce:
- **`test` job**: Runs full test suite before publishing.
- **`build-push` job**:
  - `needs: [test]` (Non-negotiable! Never publish untested artifacts).
  - Authenticate to Docker Hub using GitHub Secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).
  - Tag images with explicit commit SHA: `${{ github.sha }}`. **Never use `:latest` for production release.**
- **`deploy` job**:
  - `needs: [build-push]`.
  - Deploy to ephemeral or staging cluster with `kubectl set image ...:${{ github.sha }}`.
  - Wait on `kubectl rollout status deployment/api -n rahbar`.
  - Execute live Ingress smoke test.

#### 3. Security & Governance Rules
- Workflows must have explicit least-privilege `permissions:` block.
- Credentials stored only in GitHub Secrets.
- All actions pinned to specific version tags or commit SHAs.

---

### Member 1 Acceptance Checklist (Phase 4)
- [ ] `ci.yml` passes lint, pytest ($\ge 60\%$ coverage), kubeconform, build, and Trivy scan.
- [ ] `ci.yml` creates a Kind cluster, indexes fixtures, and executes `eval/run_eval.py`.
- [ ] `cd.yml` gates `build-push` with `needs: test`.
- [ ] Docker images pushed to Docker Hub tagged with `${{ github.sha }}`.
- [ ] Deploy step waits for `kubectl rollout status`.
- [ ] PR branch protection screenshot captured showing blocked merge when gate fails.
