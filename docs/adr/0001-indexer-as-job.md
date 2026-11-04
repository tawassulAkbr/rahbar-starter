# ADR 0001: Decoupling the Indexer as an Ephemeral Kubernetes Job

## Status
Accepted — November 2026

## Context
When designing a grounded RAG service with multiple horizontally scaled API replicas, the initial intuitive instinct might be to trigger document chunking and vector indexing during API application startup (such as inside a FastAPI `@app.on_event("startup")` hook or lifespan context manager).

However, in our production target architecture on Kubernetes with 3 API replicas sharing a persistent ChromaDB volume, this naive approach causes catastrophic distributed systems failures:
1. **Concurrent Writer Collisions & Split-Brain Corruption**: With three API pods mounting the same underlying Chroma volume (`ReadWriteOnce` or shared block storage), three simultaneous processes race to parse, embed, and write documents. Chroma’s underlying SQLite / DuckDB persistence engines do not support multi-writer concurrency. The resulting index suffers race-induced corruption or partial writes that no single document actually produced.
2. **Expensive Re-Indexing on Routine Pod Restarts**: Any transient cluster lifecycle event—a rolling update, an OOMKill, a node drain, or a transient probe blip—causes newly spawned pods to re-parse all PDFs, execute optical character recognition, and make expensive embedding calls all over again, consuming unnecessary compute and memory.
3. **The Readiness Probe Dilemma (False Readiness vs. Restart Storms)**: If an API pod marks itself ready before the index is built, it enters the Service endpoints and serves empty or ungrounded answers to students. Conversely, if readiness waits for complete document extraction and vectorization (which can take several minutes), Kubernetes liveness or readiness probes will exceed their failure thresholds and kill the booting pod halfway through. A rolling update would terminate three working pods and replace them with three pods trapped in an unready initialization loop.
4. **Tight Coupling & Inability to Re-Index Without Redeploy**: When campus rules change, updating the vector index requires redeploying or rebuilding the API container images—an anti-pattern where data changes force operational code rebuilds.

## Decision
We decouple indexing entirely from the API lifecycle and establish a strict **One-Writer, Multiple-Readers** architecture:
- **Write Path**: Indexing is performed solely by an ephemeral, one-shot Kubernetes `Job` (`indexer-job`) and a scheduled weekly `CronJob` (`reindex`). The indexer extracts text with OCR, cleans, chunks with overlap, computes vector embeddings, stores them in ChromaDB, records the embedding model pin in collection metadata, and exits.
- **Read Path**: The API deployment runs across 3 replicas strictly in read-only mode against the Chroma HTTP endpoint.
- **Guardrail & Readiness Check**: The API `/readyz` probe performs a deep check verifying that the Chroma collection exists, is non-empty (`count() > 0`), and has an embedding model metadata tag matching the API's configured `EMBED_MODEL`. If the index does not exist, the API returns HTTP 503 and is withheld from routing traffic until the indexer Job completes.
- **Independent Re-Indexing**: Re-indexing becomes a single zero-downtime command without touching running API pods:
  ```bash
  kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
  ```

## Options Considered

### Option A: Indexing inside API Startup Hooks (`lifespan`)
- **Pros**: Zero additional Kubernetes manifests needed.
- **Cons**: High write-concurrency conflicts across replicas, massive CPU/memory spikes during rolling updates, and complete violation of the single-responsibility principle. Ruled out as fundamentally flawed for clustered workloads.

### Option B: InitContainer on the API Pod
- **Pros**: Guarantees indexing completes before the API container boots.
- **Cons**: Every newly scheduled API replica pod executes the InitContainer, creating identical concurrent write races on the Chroma PVC when scaling horizontally from 3 to 8 pods under HPA. Ruled out.

### Option C: Standalone One-Shot Kubernetes Job / CronJob (Chosen)
- **Pros**: Guarantees exactly one writer at any given time, separates batch CPU/memory limits from latency-sensitive serving limits, permits instant zero-downtime manual re-indexing, and preserves honest readiness semantics.
- **Cons**: Requires explicit orchestration of Job completion before directing live queries to the API.

## Consequences

### Positive Consequences
- **Index Data Integrity**: Only one batch process writes to ChromaDB, eliminating lock contention and corrupted vector stores.
- **Fast Zero-Downtime Rollouts**: Rolling updates to the API take seconds because new pods only establish a read client and immediately pass the readiness check.
- **Independent Resource Optimization**: The Indexer Job can be allocated dedicated resource limits (1000m CPU, 1024Mi memory) for OCR and batch vectorization, while API pods maintain lightweight requests (100m CPU, 256Mi memory).
- **Zero-Downtime Updates**: Document updates can be ingested at any time by triggering a manual Job run while the existing API replicas continue serving from the active index.

### Challenges & Mitigations
- **Cache Invalidation**: When the indexer Job finishes populating a new index, any existing answers cached in the Redis semantic cache could become stale. We mitigate this by having the indexer signal cache invalidation upon completion.
- **Orchestration Order**: In initial deployments, the Indexer Job must be executed before expecting API pods to transition to `1/1 READY`. This is codified in our apply order in `README.md`.
