# Phase 5 — Member 2: Architectural Decision Records, Engineering Notes & Final Audit

## Role: Principal AI Architect & Documentation Lead
**Deliverables Target:** 4 Completed ADRs (`docs/adr/`), `docs/ENGINEERING-NOTES.md` (all 7 questions answered with code references), `docs/AI-USAGE.md`, `README.md`, and final run of `check_submission.py`.

---

### Key Responsibilities & Implementation Steps

#### 1. Architectural Decision Records (4 ADRs Required)
- `docs/adr/0001-indexer-as-job.md`:
  - Context, decision, consequences: Indexer as a Kubernetes Job instead of API startup hook.
- `docs/adr/0002-chunking-strategy.md`:
  - Evaluation of 3 chunking configurations (e.g. 200/25, 400/50, 800/100).
  - Measurement table of recall@5 and storage amplification. Justification for shipped settings.
- `docs/adr/0003-cache-store.md`:
  - Trade-off analysis between Redis vs secondary Chroma collection for semantic cache. Defend chosen solution.
- `docs/adr/0004-llm-provider-and-data-governance.md`:
  - Local Ollama vs Hosted LLM API. Data privacy, credential isolation via K8s Secret, and mitigation of prompt injection.

#### 2. Comprehensive Engineering Notes (`docs/ENGINEERING-NOTES.md`)
Must answer all seven specific questions with explicit file names and line numbers ($\ge 2000$ characters):
1. **Indexing in API startup**: Details on Chroma PVC file lock collisions, volume corruption across 3 replicas, pointing to `k8s/base/indexer-job.yaml` and `api/app/main.py`.
2. **Readiness vs Liveness swap**: Cascading failure analysis when Chroma is slow for 90 seconds. Liveness restarts healthy pods into a crash loop, killing the cluster.
3. **CPU-based HPA vs I/O-bound generation**: Explaining that pod CPU stays low while waiting for Ollama/hosted LLM. Signal that should scale is request queue depth or concurrent active in-flight requests.
4. **Indexer peak memory & OOMKill**: Memory profile from `kubectl top pod`, memory limit margin, and exit code 137 when exceeded.
5. **recall@5 by question type**: Analysis of exact-term recall degradation vs definitional recall; motivation for BM25/hybrid search.
6. **EMBED_MODEL mismatch demonstration**: Pod stuck at `0/1 READY` with 503 log line showing model conflict.
7. **The failure that cost > 1 hour**: Honest incident post-mortem with exact debug commands and resolution.

#### 3. AI Usage & Attribution (`docs/AI-USAGE.md`)
- Document all AI tools used (e.g. Claude, Gemini, ChatGPT, Copilot).
- Specify what they generated, what human architectural review modified, and lessons learned.

#### 4. Portfolio-Ready `README.md` ($\ge 2000$ characters)
- Mermaid architecture diagram.
- CI/CD build badges.
- Step-by-step Minikube cluster startup commands.
- Exact Kubernetes manifest apply order (`kubectl apply -k ...`).
- API documentation table (Endpoints, methods, schemas).
- How to execute the indexer Job and CronJob.

#### 5. Pre-Submission Quality Gate Verification
- Run submission checker:
  ```bash
  python scripts/check_submission.py
  ```
- Ensure:
  - 0 Failures across all 15 audit suites.
  - Zero starter placeholder markers left in the entire repository.
  - No secrets or keys in git history.
  - Balanced git commit distribution between Member 1 and Member 2.

---

### Member 2 Acceptance Checklist (Phase 5)
- [ ] ADRs 0001, 0002, 0003, and 0004 written and committed.
- [ ] `docs/ENGINEERING-NOTES.md` answers all 7 questions with line numbers and $\ge 2000$ characters.
- [ ] `docs/PIPELINE.md` includes the 3-configuration chunking comparison table.
- [ ] `docs/AI-USAGE.md` provides full, transparent attribution.
- [ ] `README.md` is complete, beautifully formatted, and exceeds 2000 characters.
- [ ] `python scripts/check_submission.py` outputs clean green (0 failures).
