# Phase 3 — Member 1: Redis Semantic Cache & Kubernetes Reliability Architecture

## Role: Platform Architect & Systems Performance Engineer
**Deliverables Target:** Semantic Cache in Redis, Cache Invalidation Mechanism, Kubernetes NetworkPolicies, HPA, Probes tuning, and Graceful Shutdown configuration.

---

### Key Responsibilities & Implementation Steps

#### 1. Semantic Cache Implementation (`api/app/services/cache.py`)
- Deploy Redis as a persistent semantic cache store.
- Cache Entry structure:
  - Query text, Query vector embedding, Full cached `AskResponse`, timestamp.
- On incoming question:
  - Check if query vector has cosine similarity $\ge \text{CACHE\_THRESHOLD}$ (e.g. 0.92) with any cached entry in Redis.
  - If similarity $\ge$ threshold $\rightarrow$ return cached response with header `X-Cache: HIT` and JSON field `"cached": true`.
- Implement **Never-Cache Rules**:
  - Do NOT cache follow-up questions.
  - Do NOT cache queries where `answered_from_context == False` (abstentions).
  - Do NOT cache out-of-scope queries or failed/fallback answers.

#### 2. Cache Invalidation on Re-Index
- When indexer finishes or creates a new index generation:
  - Indexer issues a flush signal or increments a generation ID in Redis (`SET rahbar:index_generation <gen_id>`).
  - API verifies generation ID or drops cache entries older than the re-index timestamp.
  - Document this design choice in `docs/adr/0003-cache-store.md`.

#### 3. Kubernetes Probes & Reliability Hardening
- Audit and test probe behaviors:
  - `/healthz`: Pure process check. Returns 200 immediately. **Must NEVER touch Redis, Chroma, or Ollama.**
  - `/readyz`: Deep readiness check:
    - Verifies Chroma HTTP heartbeat (`GET /api/v2/heartbeat`).
    - Verifies collection exists and is **non-empty** (`collection.count() > 0`).
    - Verifies Redis connection (`PING`).
    - Verifies Embedding Pin (collaborating with Member 2).
    - If any check fails, immediately returns HTTP 503 with exact error breakdown in JSON body.
- Rolling Update & Graceful Termination:
  - Configure `maxSurge: 1`, `maxUnavailable: 0` in `k8s/base/api-deployment.yaml`.
  - Add `lifecycle.preStop.exec.command: ["/bin/sh", "-c", "sleep 5"]`.
  - Set `terminationGracePeriodSeconds: 30` so in-flight requests finish cleanly before pod termination.

#### 4. Calico NetworkPolicy Hardening
- Ensure default-deny ingress/egress is enforced.
- Verify through cluster tests that:
  - The UI pod can reach `api:8000`, but UI pod **CANNOT** reach `chroma:8000` or `redis:6379`.
  - The API pod can reach `chroma:8000`, `redis:6379`, and DNS (`kube-dns:53`).
  - Indexer Job can reach `chroma:8000`, `redis:6379`, and DNS.

---

### Member 1 Acceptance Checklist (Phase 3)
- [ ] Redis semantic cache hits on semantically identical questions and skips LLM generation.
- [ ] Never-cache rules prevent caching abstentions and fallbacks.
- [ ] Re-indexing invalidates or expires old cache keys.
- [ ] Liveness probe touches zero external dependencies.
- [ ] Readiness probe returns 503 if Chroma is down, Chroma is empty, or Redis is down.
- [ ] Zero-downtime rolling update tested and verified (`maxUnavailable: 0`).
- [ ] NetworkPolicy prevents UI pod from curling Chroma directly.
