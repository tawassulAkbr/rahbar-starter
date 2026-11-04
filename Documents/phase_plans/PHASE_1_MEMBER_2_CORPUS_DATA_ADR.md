# Phase 1 — Member 2: Corpus Curation, Integrity Hashing & ADR-0001

## Role: Lead AI Data Architect & Governance Specialist
**Ownership:** Member 2 focuses purely on data curation, document verification (all 7 required properties), `corpus/MANIFEST.md`, `docs/CORPUS.md`, and `docs/adr/0001-indexer-as-job.md`. (Zero Docker responsibilities).

---

### Key Responsibilities & Implementation Steps

#### 1. Corpus Acquisition & Verification (All 7 Mandatory Properties)
Use `corpus/fetch.py` and inspect documents from the FAST-NUCES website (`nu.edu.pk`):
- Ensure the corpus meets all 7 properties required by Section 2:
  1. **Scale**: At least 6 documents, total page count $> 40$ pages.
  2. **Two Versions of One Policy**: E.g. Undergraduate Academic Rules Aug 2023 vs Academic Rules Handbook Jun 2026.
  3. **Scanned, Image-Only PDF**: Document with no text layer (e.g. Faculty Entrepreneurship Policy). Verify with `pdffonts` (an empty font list confirms a scan).
  4. **Tables with Real Information**: Document containing complex tabular data (e.g. Fee Structure per credit hour, Grading tables).
  5. **Long Definitions**: Document where multi-paragraph definitions would be severed by naive chunkers (e.g. Student Handbook Generative AI policy).
  6. **Deliberately Absent Topic**: Exclude a plausible topic on purpose (e.g., Hostel Allotment/Transport rules, where the handbook only mentions hostels exist).
  7. **Exact-Term Content**: Precise clause numbers (`4.2`, `1.21`), course codes (`CS4032`), and CGPA probation thresholds.

- Run `corpus/fetch.py` to download documents to local `corpus/raw/` (gitignored).
- Verify checksums: `python corpus/fetch.py --verify`.
- Generate `corpus/MANIFEST.md` containing every public URL and its verified SHA-256 hash.

---

#### 2. Document Corpus Mapping in `docs/CORPUS.md`
Fill out `docs/CORPUS.md` completely without leaving any placeholders:
- Detail the chosen source, number of documents, total page count.
- Fill the matrix table connecting each of the 7 properties to its exact document title, section, and the specific RAG failure mode it exposes (A through E).

---

#### 3. Architectural Decision Record: ADR-0001 (`docs/adr/0001-indexer-as-job.md`)
Author the first and most critical ADR of the system in your own words:
- **Title**: `ADR 0001: Decoupling Indexing as an Ephemeral Kubernetes Job`
- **Context**:
  - What happens when 3 API replicas run indexing on startup?
  - PVC locking collisions across concurrent writers.
  - Pod readiness probe timeouts and OOMKills leading to rolling restart storms.
  - Inability to re-index changed policy documents without a complete redeployment of the API.
- **Decision**:
  - Indexing is strictly isolated into an ephemeral Kubernetes `Job` (manual trigger) and `CronJob` (weekly schedule).
  - API operates in a strict read-only mode over the Chroma vector store.
- **Consequences**:
  - Clean separation of concerns (one writer, multiple readers).
  - Re-indexing can be triggered independently with zero downtime (`kubectl create job --from=cronjob/reindex ...`).
  - API readiness probe can reliably check for a non-empty index before accepting traffic.

---

### Member 2 Acceptance Checklist (Phase 1)
- [ ] At least 6 documents ($>40$ pages total) identified and verified.
- [ ] All 7 failure-mode properties mapped to real university documents.
- [ ] `pdffonts` run to confirm scanned PDF has no text layer.
- [ ] `corpus/MANIFEST.md` generated with URLs and SHA-256 hashes and committed.
- [ ] `docs/CORPUS.md` fully completed with all tables populated.
- [ ] `docs/adr/0001-indexer-as-job.md` authored with comprehensive engineering rationale.
- [ ] No Docker tasks touched (all containerization handed off to Member 1).
