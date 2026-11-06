# ADR 0001: Run indexing as a Kubernetes Job

## Status

Accepted · 2026-11-06

## Context

The API serves questions continuously, while indexing extracts documents, calls an
embedding service, and writes ChromaDB records. Running indexing during API startup
would make every replica a writer, repeat expensive work after restarts, and make
readiness depend on a long-running batch operation. Concurrent writers also make a
partial index possible.

## Decision

Run `python -m pipeline.run` in a one-shot Kubernetes Job and schedule the same
work with a weekly CronJob. The API is a read-only ChromaDB consumer. The Job uses
the shared `EMBED_MODEL`, `EMBED_DIMENSION`, Chroma collection, and Redis
invalidation configuration. `concurrencyPolicy: Forbid` prevents scheduled jobs
from overlapping.

The indexer logs each stage and exits non-zero on extraction, embedding, or storage
failure. Chroma data persists in its StatefulSet volume. Cache invalidation is
published only after a successful upsert and is logged as skipped or failed when
Redis is optional or unavailable.

## Options considered

- **Index in API startup:** rejected because three replicas would race as writers,
  restart costs would recur, and readiness would be misleading.
- **Run a long-lived indexer Deployment:** rejected because it needs additional
  leader-election and duplicate-work controls for a batch operation.
- **Job/CronJob:** selected because retries, scheduling, logs, and independent
  re-indexing are native Kubernetes concerns.

## Consequences

Re-indexing can happen without restarting the API, and failures are isolated from
question-serving processes. The trade-off is that a new index is not available
until the Job completes, and readers need a readiness check against the collection.
The current local checkout still requires a real corpus and running Chroma/Redis
services before this deployment path can be verified end to end.
