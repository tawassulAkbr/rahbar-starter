# Kubernetes operations (Phase 6)

## Assignment 03 verified runtime (26 November 2026)

The existing real-model cluster is profile **minikube2**. Restart it using
`minikube start -p minikube2`; `minikube status` without the profile targets a
different, invalid profile. Docker exposes about 5.79Gi RAM and Ollama uses a
4Gi limit. The older 2.84Gi/6Gi blocker below is historical.

For a fresh cluster use a Docker allocation of at least 6Gi (8Gi recommended)
and start `minikube start -p minikube2 --driver=docker --cni=calico --memory=5200 --cpus=2`.
Build/load the exact image tags used by the real overlay, then initialize:

```powershell
docker build -t rahbar-api:assignment03 api
docker build -t rahbar-indexer:a03-20261126 -f indexer/Dockerfile .
docker build -t rahbar-ui:assignment03 ui
docker build -t rahbar-eval:dev -f Dockerfile.eval .
minikube image load -p minikube2 rahbar-api:assignment03 rahbar-indexer:a03-20261126 rahbar-ui:assignment03 rahbar-eval:dev
minikube addons enable metrics-server -p minikube2
kubectl apply -k k8s/overlays/minikube
kubectl rollout status deployment/ollama -n rahbar --timeout=15m
kubectl rollout status statefulset/chroma -n rahbar --timeout=5m
kubectl wait --for=condition=complete job/indexer-job -n rahbar --timeout=60m
kubectl rollout status deployment/api -n rahbar --timeout=5m
```

Part A: `python scripts/prepare_assignment03_jobs.py`, then apply
`k8s/assignment03/audit-scripts.json`, `audit.json`, `unchanged.json`.
The audit uses isolated real Chroma collections, so it can demonstrate updates,
deletion and rollback without mutating the serving corpus. Inspect Job status
and container exit code as well as logs: `kubectl logs` can exit 0 for a failed Job.
Use `batch-b.json` to ingest Batch B into the serving data lake after retaining
the before-Batch-B baseline. `seed-candidate.json` seeds the isolated candidate
collection with a separate index-state file. Never share baseline/candidate state.

Part B: `kubectl apply -f k8s/eval-job.yaml`. This runs all three levels twice
with seed 2026. Wait with `python scripts/wait_for_job.py eval-job --namespace rahbar --timeout 14400`.
CPU generation can take several minutes per question. Full result, stage
checkpoints and partial answer checkpoints are stored on the evaluation PVC;
partial files explicitly mark `evaluation_complete: false` and cannot authorize release.
Recreate a completed/failed Job to rerun it; retain its old result first.

Parts C/F: seed the candidate, apply `k8s/base/candidate-deployment.yaml`, set its
image to `rahbar-api:assignment03`, and apply `-k k8s/eval-candidate`. Use the
release thresholds in `rahbar-config`; never promote a failed/incomplete gate.
The rollout/undo and ConfigMap procedures below remain applicable. An evaluation
Job must use the same golden-set source hash as the committed dataset.

Part D/F4: `kubectl port-forward service/api 18000:8000 -n rahbar`, then open
`http://localhost:18000/metrics` and `/readyz`. Keep that command running.
Export results and traces using
`python scripts/collect_assignment03.py --out eval/results/assignment03-final`.
It also exports Job status, since successful log retrieval is not proof of success.
Run `python scripts/summarize_traces.py --path traces/assignment03-final.jsonl` and
`python scripts/trace.py TRACE_ID --path traces/assignment03-final.jsonl`.

Part E: run the root README coverage commands. For real data drift, preserve
separate collections before and after Batch B, then run `eval/drift.py` with
`--before-collection`, `--after-collection`, `--corpus corpus`,
`--golden eval/golden.jsonl`, and `--out eval/results/drift.json` inside a runtime
configured for real Chroma/Ollama (`PYTHONPATH=/workspace/api:/workspace/eval`).
The script does not ingest Batch B itself; only ingestion Jobs may write vectors.

The latest measured acceptance verdict is
[`eval/results/assignment03-final/checklist.json`](../eval/results/assignment03-final/checklist.json).
Capture actual terminal screenshots manually; generated illustrations are excluded.

These commands target Minikube from the repository root. The `dev` overlay uses
stubbed models and is for wiring checks. For real Part B evidence use the
`prod` overlay (real Ollama) and do not pass `--allow-stub`.

Current measured acceptance status, including the dev-only smoke proof and the
real-model resource blocker, is recorded in
[`docs/PHASE_6_ACCEPTANCE_STATUS.md`](../docs/PHASE_6_ACCEPTANCE_STATUS.md).
Do not treat a dev result as a candidate release decision.

The dev overlay patches both indexer templates to `--dummy` and runs one API
replica (the full base remains at three replicas). The dummy collection has the
matching `dummy-768` pin and is only for cluster wiring checks; it is not Part B
quality evidence. Redis uses an `fsGroup` on its PVC so a Minikube volume is
writable by the Redis image.

## Build, apply, and initialize

```bash
minikube start --driver=docker --cni=calico --memory=2048 --cpus=2
minikube addons enable metrics-server
minikube addons enable ingress
docker build -t rahbar-api:dev api
docker build -f indexer/Dockerfile -t rahbar-indexer:dev .
docker build -t rahbar-ui:dev ui
docker build -t rahbar-eval:dev -f Dockerfile.eval .
minikube image load rahbar-api:dev rahbar-indexer:dev rahbar-ui:dev rahbar-eval:dev
kubectl apply -k k8s/overlays/dev
kubectl rollout status statefulset/chroma -n rahbar --timeout=180s
kubectl rollout status deployment/redis -n rahbar --timeout=120s
kubectl wait --for=condition=complete job/indexer-job -n rahbar --timeout=600s
kubectl rollout status deployment/api -n rahbar --timeout=180s
kubectl rollout status deployment/ui -n rahbar --timeout=180s
```

The base resources include a data lake/quarantine/archive PVC mounted by the
indexer, the Chroma StatefulSet PVC, a trace PVC, and a results PVC. Indexer
Jobs are the only workload that writes to Chroma. The weekly CronJob uses
`concurrencyPolicy: Forbid`; trigger an immediate run with:

```bash
kubectl create job --from=cronjob/reindex reindex-manual-1 -n rahbar
kubectl logs -f job/reindex-manual-1 -n rahbar
```

## Evaluate and adjust the gate

The evaluation Job runs all three Part B levels twice: real Ollama embeddings,
Chroma retrieval with the typo noise test, and end-to-end questions through the
selected API Service. It writes the full result to the `rahbar-evaluation` PVC
and exits nonzero when a required release threshold fails. The baseline Job
refreshes its measured recall and abstention results on that PVC; the
candidate Job compares against those measurements. Threshold environment
values come from `rahbar-config`, so a change takes effect when the Job is
recreated without rebuilding its image. Each API answer is matched to its trace
on `rahbar-traces`. Faithfulness is a conservative lexical and numeric support
proxy, not semantic entailment; the result records that limitation. The dev
overlay uses stub services only for wiring checks and is not valid Part B
quality evidence.

```bash
kubectl delete job eval-job -n rahbar --ignore-not-found
kubectl apply -f k8s/eval-job.yaml
python scripts/wait_for_job.py eval-job --namespace rahbar --timeout 7200
kubectl delete pod eval-results-reader -n rahbar --ignore-not-found
kubectl apply -f k8s/base/eval-results-reader.yaml
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/eval-results-reader -n rahbar --timeout=60s
kubectl logs pod/eval-results-reader -n rahbar
```

Read results from a temporary pod mounting the PVC, or inspect the Job logs.
The initial baseline Job must pass before the candidate Job can compare with it.
To demonstrate a changed threshold, patch the ConfigMap and recreate the Job:

```bash
kubectl patch configmap rahbar-config -n rahbar --type merge \
  -p '{"data":{"GATE_RECALL5_MAX_DROP":"0.00","GATE_P95_MAX_MS":"1"}}'
kubectl delete job eval-job -n rahbar
kubectl apply -f k8s/eval-job.yaml
kubectl logs -f job/eval-job -n rahbar
```

Restore the checked-in thresholds (`GATE_RECALL5_MAX_DROP=0.05`,
`GATE_P95_MAX_MS=180000`) after the demonstration. The default
golden set is `eval/golden.jsonl`, and the immutable baseline is
`eval/baseline.json`, both copied into the evaluator image at build time.

## Candidate collection and gated rollout

The candidate uses the built `rahbar-api:dev` image with `TOP_K=4`, keeping the
Part C top-k change in configuration. It is isolated behind `api-candidate` and
uses the distinct `rahbar-candidate` collection. Seed that collection using the
indexer Job (the indexer remains the sole Chroma writer). Create the Job from
the CronJob template, set its collection before applying its pod, then wait:

```bash
kubectl create job --from=cronjob/reindex seed-candidate-1 -n rahbar --dry-run=client -o yaml > /tmp/seed-candidate.yaml
```

Edit `/tmp/seed-candidate.yaml` and add this entry under the indexer container's
`env` list (or set `env` alongside `envFrom`):

```yaml
- name: CHROMA_COLLECTION
  value: rahbar-candidate
```

Then apply and continue:

```bash
kubectl apply -f /tmp/seed-candidate.yaml
kubectl wait --for=condition=complete job/seed-candidate-1 -n rahbar --timeout=30m
kubectl apply -f k8s/base/candidate-deployment.yaml
kubectl rollout status deployment/api-candidate -n rahbar --timeout=180s
```

Run the exact same Part B gate against the candidate with the dedicated Job
manifest. It uses the same ConfigMap thresholds and result/trace volumes while
targeting only the candidate Service:

```bash
kubectl delete job eval-candidate-job -n rahbar --ignore-not-found
kubectl apply -k k8s/eval-candidate
python scripts/wait_for_job.py eval-candidate-job --namespace rahbar --timeout 7200
kubectl delete pod eval-results-reader -n rahbar --ignore-not-found
kubectl apply -f k8s/base/eval-results-reader.yaml
kubectl logs pod/eval-results-reader -n rahbar
```

Only promote after a passing measured real-model gate. Update the live Deployment to the candidate
image and collection/top-k values; its rolling update is configured with
`maxUnavailable: 0`:

```bash
kubectl set image deployment/api api=rahbar-api:dev -n rahbar
kubectl set env deployment/api -n rahbar CHROMA_COLLECTION=rahbar-candidate TOP_K=4
kubectl rollout status deployment/api -n rahbar --timeout=180s
```

To demonstrate rollback after a bad release, then verify the next trace records
the restored collection and embedding version:

```bash
kubectl rollout undo deployment/api -n rahbar
kubectl rollout status deployment/api -n rahbar --timeout=180s
kubectl logs deployment/api -n rahbar --since=10m
kubectl port-forward service/api 8000:8000 -n rahbar
```

Send a new request to `http://localhost:8000/api/ask`; trace JSONL is emitted to
pod stdout and `/data/traces/traces.jsonl` on `rahbar-traces`.

## Operations and resource observation

```bash
kubectl get all,pvc,configmap,cronjob,job -n rahbar
kubectl top pods -n rahbar
kubectl port-forward service/api 8000:8000 -n rahbar
```

Then request `http://localhost:8000/metrics`. Current API, Chroma, and indexer
requests/limits are conservative starting values; record `kubectl top` from the
demo cluster and adjust them for the report. A `ReadWriteOnce` PVC works for
the single-node Minikube demo. A multi-node production cluster needs storage
that supports the access mode required by concurrently mounted API replicas.
