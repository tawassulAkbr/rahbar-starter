# Phase 5 Member 1 evidence runbook

This directory must contain genuine outputs from the `rahbar` Kubernetes
namespace. Do not replace unavailable cluster output with guessed values or
hand-written percentages.

## Prerequisites

Start Docker Desktop and Minikube, then deploy the dev overlay and wait for the
indexer Job and API deployment:

```powershell
minikube start
minikube addons enable metrics-server
kubectl apply -k k8s/overlays/dev
kubectl wait --for=condition=complete job/indexer-job -n rahbar --timeout=300s
kubectl rollout status deployment/api -n rahbar --timeout=120s
```

## Capture runtime evidence

From the repository root on `dev`, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/capture_phase5_member1_evidence.ps1
```

The script captures `kubectl top` for the indexer and API, HPA status, and API
Service endpoints. It checks the branch before writing and fails if the cluster
is unreachable, so an empty or fabricated capture cannot look successful.

## Rollout and rollback evidence

Use an image that exists in the active cluster. The rollout demo changes the API
deployment, waits for the update, then undoes it and waits for the rollback:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/capture_phase5_member1_evidence.ps1 `
  -RunRolloutDemo -RolloutImage myregistry/rahbar-api:v2
```

This produces `rollout-status.txt` and `rollout-undo.txt`. The image name is a
parameter because a made-up image would produce a failed rollout rather than
valid evidence.

## Manual GitHub evidence

Capture genuine screenshots from the protected `main` branch settings and the
PR merge state, saving them as:

- `branch-protection.png`
- `blocked-merge.png`
- `green-merge.png`

Screenshots are intentionally not generated locally: they must show the actual
repository rules and checks.
