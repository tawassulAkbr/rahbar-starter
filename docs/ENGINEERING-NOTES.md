# Engineering notes

These notes record the operational decisions behind the implementation. File
references are intentionally explicit so that each claim can be checked against
the manifests, services, and evaluation runner.

## 1. Indexing in API startup: what breaks with 3 replicas and one Chroma volume?

Indexing in API startup would make all three replicas attempt the same batch
write. They could race while extracting and embedding, repeat work after every
restart, and expose a partially populated collection. The API therefore remains
read-only; the one-shot worker is defined in `k8s/base/indexer-job.yaml` and the
decision is documented in `docs/adr/0001-indexer-as-job.md`.

## 2. Readiness and liveness swapped, Chroma slow for 90 seconds: what happens?

If readiness were used for liveness, Kubernetes could restart healthy API pods
while Chroma is temporarily slow. If liveness were used for readiness, traffic
could be sent to pods that cannot retrieve passages. `api/app/routes/health.py`
keeps `/healthz` dependency-free and uses `/readyz` for the Chroma collection
and embedding pin, so startup and routing fail safely.

## 3. What does a CPU-based HPA measure on a generation service, and what should scale it?

The CPU HPA measures container CPU relative to its requested CPU. That is only
a proxy for a generation service: model latency, concurrent requests, and
provider queue time may rise while CPU remains low. `k8s/base/hpa.yaml` is a
conservative CPU fallback. A better production signal would be an external
metric such as in-flight requests or provider latency, exported through a
metrics adapter and paired with a queue or concurrency limit.

## 4. The indexer's peak memory, its limit, the margin, and the exit code when it is wrong

The indexer is bounded by the memory request and limit in
`k8s/base/indexer-job.yaml`; the request is the scheduling baseline and the
limit is the OOM boundary. The actual margin must be checked from a live
`kubectl top pod -l job-name=indexer-job -n rahbar` capture in
`docs/evidence/kubectl-top-indexer.txt`, rather than guessed from a desktop
run. Exceeding the cgroup limit results in OOMKilled and normally exit code
137, which is also the failure signature used in `docs/FAILURE-ANALYSIS.md`.

## 5. recall@5 by question type: where is it worst, and why?

The evaluation runner writes `recall_at_5_by_type` in `eval/results.json`.
Exact-term questions are most sensitive to chunk boundaries and OCR noise;
version questions can also lose recall when superseded passages are filtered.
The fixture and full golden sets keep these categories separate so a strong
overall average cannot hide a regression in either one.

## 6. EMBED_MODEL changed on the API only: what does your system do?

The readiness handler compares the collection metadata with the configured
model and dimension. A mismatch returns HTTP 503 and logs the offending model,
preventing incompatible query vectors from silently producing bad results.
The guardrail is tested in `api/tests/test_member2.py` and described in
`docs/adr/0001-indexer-as-job.md`.

## 7. The failure that cost us more than an hour

The most expensive failure mode was treating the evaluation stack as if a
successful API rollout implied a usable index. The API can be live while the
indexer Job failed or the collection is empty. The fix was to make the Job
explicit, gate readiness on a non-empty collection, and make CI wait for the
Job before running the golden evaluation. The relevant workflow is
`.github/workflows/ci.yml`; the staged failure and recovery path is recorded in
`docs/FAILURE-ANALYSIS.md`.
