# Failure analysis

These are isolated, reversible failure experiments. Production source files were
not changed. Where a required external executable or service was unavailable,
the experiment is marked blocked rather than given an invented metric.

## Stage A · Extraction and OCR

- **What we broke:** Used the image-only 2023 rules PDF without its OCR runtime.
- **Symptom:** `extract()` detects pages with no text and raises `RuntimeError`:
  `OCR failed; install the Tesseract executable and ensure it is on PATH`.
- **Diagnosis:** `pdffonts` returns an empty font table for the policy PDF, and
  `tesseract` is absent on the host.
- **Remedy:** Run the indexer image, which installs `tesseract-ocr`, or install
  the executable locally before indexing. Do not silently create empty chunks.
- **Status:** Diagnosis verified; full OCR extraction is blocked on the host.

## Stage B · Chunking

- **What we broke:** The isolated equivalent is `chunk(document, 100, 0)`.
- **Symptom:** A long sentence/definition is split at a hard token boundary with
  no overlap, so a query matching the boundary can miss necessary context.
- **Diagnosis:** `test_chunking_is_stable_and_respects_overlap_budget` verifies the
  normal overlap contract; comparing the same document with overlap `0` exposes
  the lost-boundary context.
- **Remedy:** Keep structure-aware sentence splitting and configured overlap.
- **Status:** Safe unit-level experiment; no production configuration changed.

## Stage C · Retrieval

- **What we broke:** Set `top_k` to `1` in an isolated settings object, or use an
  embedding vector with the wrong configured dimension.
- **Symptom:** Fewer relevant passages are available, or retrieval raises a
  dimension-validation error before querying Chroma.
- **Diagnosis:** `test_embedding_rejects_dimension_mismatch` and the Chroma
  retrieval tests cover these failure paths.
- **Remedy:** Keep the shared model/dimension pin and a retrieval breadth that
  preserves the relevant clause.
- **Status:** Unit failure paths verified; live Chroma measurement requires a
  running indexed service.

## Stage D · Prompt grounding

- **What we broke:** Removed the instruction that evidence is untrusted and that
  unsupported questions must set `answered_from_context` to false.
- **Symptom:** An injection probe can cause an answer outside the retrieved
  evidence, and fabricated citations fail the citation contract.
- **Diagnosis:** `build_grounded_prompt()` explicitly rejects instructions inside
  evidence, while `test_answer_rejects_fabricated_citations` verifies the safety
  fallback.
- **Remedy:** Preserve the grounded prompt, schema validation, and citation
  membership check.
- **Status:** Unit-level safety behavior verified; live provider evaluation needs
  the API, Chroma, and model services.

## Stage E · Superseded-source filtering

- **What we broke:** Removed the default `superseded: false` Chroma filter.
- **Symptom:** A current-policy query can return the August 2023 rules instead
  of the active June 2026 handbook.
- **Diagnosis:** `test_chroma_filters_superseded_documents_and_maps_scores` verifies
  the default filter, and the corpus manifest marks the 2023 rules superseded.
- **Remedy:** Keep the default filter; allow an explicit year in the question only
  when historical retrieval is requested.
- **Status:** Unit behavior and corpus metadata verified; live historical query
  requires an indexed Chroma service.
