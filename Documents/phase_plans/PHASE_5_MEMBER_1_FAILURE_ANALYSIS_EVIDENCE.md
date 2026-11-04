# Phase 5 — Member 1: Operational Evidence Gathering & Resource Profiling

## Role: Site Reliability & Production Readiness Engineer
**Deliverables Target:** 5 Evidence artifacts in `docs/evidence/`, resource optimization justified with `kubectl top`, and rollout/rollback verification.

---

### Key Responsibilities & Implementation Steps

#### 1. Cluster Resource Profiling (`kubectl top`)
- Enable metrics server: `minikube addons enable metrics-server`.
- Run indexing Job under load:
  ```bash
  kubectl top pod -l job-name=indexer-job -n rahbar > docs/evidence/kubectl-top-indexer.txt
  ```
- Run API under query load:
  ```bash
  kubectl top pods -n rahbar > docs/evidence/kubectl-top-api.txt
  ```
- Justify container resource requests and limits in `docs/ENGINEERING-NOTES.md` and `docs/PIPELINE.md`:
  - Show peak memory of indexer Job during PDF embedding.
  - Explain the 8% CPU utilization paradox: LLM waiting is I/O-bound, so pod CPU remains low even under heavy generation load.

#### 2. Horizontal Pod Autoscaler (HPA) Verification
- Verify HPA is active and reading metrics:
  ```bash
  kubectl get hpa -n rahbar > docs/evidence/get-hpa.txt
  ```
- Ensure HPA shows actual percentages (e.g. `12%/70%`), never `<unknown>/70%`.

#### 3. Service Endpoint & Scaling Verification
- Scale API deployment:
  ```bash
  kubectl scale deployment/api --replicas=4 -n rahbar
  kubectl get endpoints api -n rahbar > docs/evidence/get-endpoints.txt
  ```
- Proves that the Service automatically discovers pods via labels without manual IP configuration.

#### 4. Rollout & Rollback Demonstration
- Trigger a rolling update:
  ```bash
  kubectl set image deployment/api api=myregistry/rahbar-api:v2 -n rahbar
  kubectl rollout status deployment/api -n rahbar > docs/evidence/rollout-status.txt
  ```
- Rollback to previous version:
  ```bash
  kubectl rollout undo deployment/api -n rahbar
  kubectl rollout status deployment/api -n rahbar > docs/evidence/rollout-undo.txt
  ```

#### 5. GitHub Branch Protection Evidence
- Place screenshots or evidence in `docs/evidence/`:
  - `docs/evidence/branch-protection.png` (showing protected `main` branch rules, required PR, required CI checks).
  - `docs/evidence/blocked-merge.png` (showing greyed-out merge button when eval gate fails).
  - `docs/evidence/green-merge.png` (showing successful green checks allowing merge).

---

### Member 1 Acceptance Checklist (Phase 5)
- [ ] At least 5 evidence files saved in `docs/evidence/`.
- [ ] `kubectl top` outputs recorded and committed.
- [ ] `kubectl get hpa` and `kubectl get endpoints` output saved.
- [ ] Rollout update and rollback demonstrated and documented.
- [ ] Branch protection and blocked merge evidence verified.
