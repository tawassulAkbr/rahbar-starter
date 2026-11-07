# ADR 0003: Redis semantic cache and index generations

## Status

Accepted · 2026-11-07

## Decision

The API uses Redis as a best-effort semantic cache. Each entry stores the
normalized question, its query embedding, the complete validated `AskResponse`,
creation time, and the current `rahbar:index_generation`. A hit requires cosine
similarity at or above `CACHE_THRESHOLD` (0.92 by default), and the cached
response is returned without retrieval or LLM generation.

The indexer increments `rahbar:index_generation` only after a successful Chroma
upsert and publishes a notification as an optimization. The API checks the
generation on every lookup, so invalidation remains correct if Redis pub/sub
messages are missed. TTL is an additional bound on stale data.

Redis errors are fail-open: the API continues with normal retrieval and
generation. Abstentions, low-confidence fallbacks, failed provider responses,
and follow-up questions are never cached because they are not reusable answers.

## Consequences

This design avoids a cache flush race during re-indexing and keeps the API
stateless across replicas. It performs a bounded Redis scan per request; the
production deployment should replace that scan with a vector index when cache
volume requires it. The cache is an optimization, never a source of truth.
