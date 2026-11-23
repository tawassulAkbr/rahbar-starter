# RAHBAR architecture

RAHBAR has two deliberately separate paths:

```text
corpus + EMBED_MODEL                         question
        │                                      │
        ▼                                      ▼
  indexer Job ──writes──▶ Chroma ◀──reads── API ──▶ UI
        │                    ▲          │
        └──generation───────┘          └──Redis semantic cache
```

The indexer extracts, cleans, chunks, embeds, and stores documents. It is the
only Chroma writer and runs as a Job or weekly CronJob. The API never indexes
documents during startup; it retrieves existing chunks, calls the configured
LLM provider, validates the structured answer, and returns citations. The API
and indexer read the same `EMBED_MODEL`, `EMBED_DIMENSION`, and collection name
from the ConfigMap.

## Why Chroma is a StatefulSet

Chroma stores the indexed collection on persistent disk. A StatefulSet gives it
one stable identity and a `volumeClaimTemplates`-backed volume, so a pod restart
does not discard the index. Chroma is intentionally one replica: the indexer is
the single writer and the API replicas are readers. Scaling Chroma as a normal
Deployment would require a separately designed distributed storage and writer
coordination model; it would not make the current single-volume collection
safe.

Redis is also one replica with a PVC because it is an optimization, not the
source of truth. Redis failures are fail-open: API requests continue through
retrieval and generation. A generation counter makes cache invalidation safe
even if a pub/sub notification is missed.

## Request and deployment boundaries

- The UI reaches only the API service through the Ingress.
- The API reaches Chroma, Redis, and the configured Ollama endpoint.
- The indexer reaches Chroma, Redis invalidation, and Ollama embeddings.
- NetworkPolicy denies all other traffic; DNS is explicitly allowed.
- API, UI, Chroma, Redis, and indexer use separate non-root ServiceAccounts
  with token automount disabled because none needs Kubernetes API access.
- `/healthz` is dependency-free for liveness. `/readyz` checks Chroma,
  collection non-emptiness, embedding metadata, and Redis when configured.

## Local mode

`make dev` uses the deterministic extractive provider and local corpus retriever
so the UI can be run without Kubernetes, Ollama, or Chroma. It reads the fetched
PDF/HTML/Markdown files through `CORPUS_DIR` and is intended for transparent
local inspection; it is not used by the production overlay, which selects
Chroma and `ollama-incluster`.
