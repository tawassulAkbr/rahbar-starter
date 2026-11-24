# Phase 0 through Phase 2 audit

Audit branch: `feature/assignment-03-phase1-integrated`

Protected refs were not changed. At audit time:

- `origin/main`: `7afda17ea616b692cb5d1372eaa658b18dfe7050`
- `origin/dev`: `7bfb686ffb1caad4d30b1b26af045db182173451`

## Phase 0 - contracts and baseline

- [x] `docs/RAGOPS-CONTRACTS.md` exists and contains verification, trace,
  golden-set, and ConfigMap contracts.
- [x] `eval/baseline.json` is tracked with collection `rahbar`, model
  `nomic-embed-text`, dimension `768`, and top-k `5`.
- [x] Frozen baseline introducing commit is recorded in the contract.
- [x] All nine Phase 0 ConfigMap keys are present.
- [x] Base Kustomize rendering succeeds.

## Phase 1 - verification, Batch B, and incremental update

- [x] Verification runs after extraction and before chunking.
- [x] Quality, completeness, recency, and uniqueness checks exist.
- [x] Quarantine, archive, report, hash state, replacement, deletion, and
  restore code exists.
- [x] Data-lake PVC is mounted by the indexer Job and CronJob.
- [x] Batch B validator passes: 11 documents and one exact duplicate group.
- [x] Temporary Batch B dry-run detects exact/near duplicates, truncation,
  missing metadata, older version, and corrupt content.

## Phase 1 - Member 2 golden set

- [x] `eval/golden.jsonl` loads successfully.
- [x] 33 unique questions: 22 answerable, 6 unanswerable, 5 hard.
- [x] Eight human questions are marked `reviewed: true`.
- [x] Reviewed synthetic-question minimum is satisfied.
- [x] Batch B manifest and injection handoff are present.

## Phase 2 - three-level offline testing

- [x] Module evaluator: 15 paraphrase pairs, 15 unrelated pairs, cosine gap,
  timing, and determinism.
- [x] Component evaluator: recall@3, recall@5, MRR, nDCG@5, and three-document
  noise deltas.
- [x] End-to-end evaluator: faithfulness, abstention correctness, citation
  validity, p50, and p95 latency.
- [x] Same-seed suite runs twice and reports per-metric deltas.
- [x] Timestamped result is committed under `eval/results/`.
- [x] Base/CI/CD Kustomize rendering, Python compilation, and Phase 1 validator
  pass.

## Evidence still requiring external runtime state

- [ ] Live Ingress/API evaluation through Kubernetes. The local Kubernetes API
  context was unavailable during this audit.
- [ ] Full pytest completion. The local Python test process did not complete in
  this environment; install the pinned development dependencies and rerun it.
- [ ] Production-quality Phase 2 evidence using live Chroma and the real
  embedding service. The committed Phase 2 result is explicitly a deterministic
  local reference run with recorded fallback passage counts.

These are runtime/evidence limitations, not missing Phase 0-2 source artifacts.

## Recheck commands

```text
python scripts/validate_phase1_member2.py
python eval/run_offline_suite.py --corpus corpus --golden eval/golden.jsonl
python -m compileall -q eval indexer/pipeline indexer/tests scripts
python -m pytest api/tests indexer/tests -q
kubectl kustomize k8s/base
kubectl kustomize k8s/overlays/ci
kubectl kustomize k8s/overlays/cd
```
