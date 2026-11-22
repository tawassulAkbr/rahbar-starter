# Phase 6 — Member 1: Run It on Kubernetes

**Member:** Member 1 (Platform & Data Infrastructure) · **Day 1 17:30 → Day 2 17:00**
**Serves:** Assignment 03 **Part F** (F1 deploy, F2 Jobs, F3 controlled release, F4 observability, F5 resources)
**Paper anchor:** 4.1(e) deployment, 4.1(f) operate/monitor, 5.1 reliability

---

## 1. What this file is for

Deploy the whole RAGOps layer on Kubernetes: the API and vector store, the data lake/quarantine/archive on PVCs, ingestion+verification and evaluation as Jobs, thresholds as a ConfigMap, and a controlled release with rollback.

---

## 2. Inputs (from earlier phases)

- `PHASE_0_CONTRACTS_AND_BASELINE.md`: ConfigMap keys, trace volume.
- `PHASE_3_MEMBER_2_CHANGE_AND_GATE.md`: candidate image, gate thresholds, gate script.
- `PHASE_4_MEMBER_2_TRACE_AND_OBSERVABILITY.md`: trace volume mount + metrics endpoint.
- `PHASE_1_MEMBER_1_VERIFY_AND_UPDATE.md`: data lake/quarantine/archive PVCs.

---

## 3. Tasks

### 3.1 F1 — deploy (Day 2 13:30–14:15)
- [ ] API as a Deployment; vector store as a StatefulSet (or Deployment + PVC); a Service exposes the API.
- [ ] Data lake, quarantine folder and archived versions on a PVC that survives pod restarts.

### 3.2 F2 — Jobs (Day 2 14:15–15:00)
- [ ] Ingestion with verification runs as a Kubernetes Job; a CronJob re-runs it on a schedule.
- [ ] The only writer to the vector store is that Job.
- [ ] The Part B suite runs as a Job (`kubectl apply -f k8s/eval-job.yaml`), writes its result file to a volume, and exits failing when the release gate fails.
- [ ] Gate thresholds are a ConfigMap; show that changing a threshold changes the outcome **without rebuilding the image**.

### 3.3 F3 — controlled release (Day 2 15:00–15:45)
- [ ] Candidate runs as a second Deployment with its own Service and its own collection name.
- [ ] Run the Part B suite Job against it.
- [ ] If the gate passes, release to the live Deployment with a rolling update (`maxUnavailable: 0`), watched with `kubectl rollout status`.
- [ ] Show a candidate stopped by the gate and never rolled out.
- [ ] Show a bad release reversed with `kubectl rollout undo`.
- [ ] After the undo, a new trace must show the previous collection and embedding version.

### 3.4 F4 — observability on the cluster (Day 2 15:45–16:15)
- [ ] Trace records go to stdout as JSON lines, readable with `kubectl logs`.
- [ ] Traces also written to a volume for the report scripts.
- [ ] Metrics endpoint reachable with `kubectl port-forward`.

### 3.5 F5 — resources (Day 2 16:15–16:45)
- [ ] Set requests and limits for the API, the vector store and the Jobs from `kubectl top` measurements.
- [ ] Copy the numbers into the report.
- [ ] Write `k8s/README.md` with the apply order and extra commands.

---

## 4. Files touched

| File | Change |
|---|---|
| `k8s/base/api-deployment.yaml` | Resources, trace volume, metrics |
| `k8s/base/chroma-statefulset.yaml` | Resources |
| `k8s/base/data-lake-pvc.yaml` | New PVC for lake/quarantine/archive |
| `k8s/base/indexer-job.yaml` | Verification + mounts |
| `k8s/base/reindex-cronjob.yaml` | Schedule + mounts |
| `k8s/eval-job.yaml` | Part B suite as a Job |
| `k8s/candidate-deployment.yaml` | Second Deployment + Service + collection |
| `k8s/base/configmap.yaml` | Gate thresholds + RAGOps keys |
| `k8s/README.md` | Apply order |
| `docs/evidence/` | kubectl output, logs, rollout/undo |

---

## 5. Acceptance (sync gate G4, Day 2 17:00)

- [ ] `kubectl get all,pvc,configmap,cronjob,job` captured for the namespace.
- [ ] Logs of a completed ingestion Job and a completed evaluation Job captured.
- [ ] Gate result changes after a ConfigMap edit (no rebuild).
- [ ] `kubectl rollout status` and `kubectl rollout undo` captured; post-undo trace shows previous collection + embedding version.
- [ ] Resources justified from `kubectl top`.
- [ ] Fresh cluster reaches a working pipeline by applying `k8s/`.

---

## 6. Handoff

- → `PHASE_7_MEMBER_2_REPORT.md`: all Part F evidence and the release decision input.
