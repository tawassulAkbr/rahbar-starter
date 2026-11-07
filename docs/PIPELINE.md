# Indexing and retrieval pipeline

## Overview
The indexer is a one-shot writer. From `indexer/` it runs
`python -m pipeline.run` as `Discover → Extract → Clean → Chunk → Embed → Store`.
The API never runs these stages. ChromaDB receives one record per chunk and Redis
receives an invalidation event only after a successful upsert.

## Extraction
PDFs are extracted one page at a time with `pdfplumber`. A page with fewer than 20
non-whitespace characters is treated as scanned and sent to Tesseract through
`pdfplumber`'s rendered image. OCR failures are surfaced as errors, rather than
silently indexing an empty page. Markdown, text, and HTML fixtures are also
supported; Markdown front matter is metadata, not document text. An edge line is
removed as a header/footer only when the exact line repeats on at least two pages.
Tables are not reconstructed by OCR, because their cells cannot be reliably
recovered without document-specific layout rules.

Supported inputs are `.pdf`, `.md`, `.txt`, `.html`, and `.htm`. Corrupt or
unreadable files raise descriptive errors; unsupported extensions are rejected.
Markdown front matter is excluded from page text, while its version and superseded
values are supplied by discovery.

## Cleaning
Whitespace is collapsed within lines, encoding artifacts (BOM, soft hyphen,
non-breaking spaces, and control characters) are removed, and adjacent wrapped
lines are joined when the continuation starts with lowercase text. Blank lines,
Markdown headings, numbered clauses, list markers, pipes, and tabs are deliberately
preserved so sections and table relationships remain visible. We do not remove
meaningful headings or merge lines around structural markers.

## Chunking
Chunking first tracks headings and numbered clauses, then paragraphs and sentences.
The configured `CHUNK_SIZE` is the target token budget and `CHUNK_OVERLAP` is copied
from the preceding chunk at word boundaries. Chunk IDs are SHA-256-derived from the
source, version, position, and text. Each chunk carries source, section, page,
version, and superseded metadata. The logger reports storage amplification as
`stored_tokens / original_tokens`; overlap intentionally makes this ratio greater
than one.

The shipped defaults are 400 tokens and 50-token overlap. The following
reproducible offline measurement uses the three committed CI Markdown fixtures
plus `corpus/raw/fee-structure-page.html` (1,722 source tokens). Recall@5 is
measured against the six fixture questions; the PDF corpus is intentionally not
included because PDF/OCR dependencies and live embeddings are not available in
the offline measurement environment.

| Size (tokens) | Overlap (tokens) | recall@5 | Chunks stored |
| --- | --- | --- | --- |
| 200 | 25 | 1.00 | 11 |
| 400 (shipped) | 50 | 1.00 | 8 |
| 800 | 100 | 1.00 | 6 |

The corresponding storage amplification values are 1.087, 1.087, and 1.058.
The 400/50 setting is retained because it preserves the measured recall while
reducing chunk count substantially versus 200/25, without the larger boundary
loss risk of 800/100 on longer policy sections. `eval/run_eval.py` remains the
authoritative service-backed evaluation harness; these offline figures do not
claim production retrieval quality.

## Embedding
Ollama `/api/embed` is called with the configured `EMBED_MODEL` in batches. The
configured `EMBED_DIMENSION` defaults to 768 and every returned vector is validated
against it. Temporary HTTP failures retry with exponential backoff. Chroma metadata
stores both values; the store refuses to reuse a collection pinned to a different
model or dimension, requiring an explicit safe re-index.

## Semantic cache
After a successful upsert, the indexer publishes `index-updated` on
`REDIS_INVALIDATION_CHANNEL` when `REDIS_URL` is configured. If Redis is not
configured or unavailable, the indexer logs that invalidation was skipped/failed;
it never reports a false success.

## Configuration
The indexer reads these environment variables through `indexer/pipeline/config.py`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CORPUS_DIR` | `/corpus` | Input directory |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `400` / `50` | Token target and overlap |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama model pin |
| `EMBED_DIMENSION` | `768` | Expected vector length (`EMBED_DIM` is an alias) |
| `EMBED_BATCH_SIZE` | `32` | Texts per Ollama request |
| `EMBED_RETRIES` / `EMBED_TIMEOUT` | `3` / `60` | Retries and request timeout |
| `OLLAMA_URL` | `http://host.minikube.internal:11434` | Ollama base URL |
| `CHROMA_HOST` / `CHROMA_PORT` | `chroma` / `8000` | ChromaDB service |
| `CHROMA_COLLECTION` | `rahbar` | Collection name |
| `REDIS_URL` | empty | Optional Redis URL |
| `REDIS_INVALIDATION_CHANNEL` | `rahbar:index-updated` | Pub/sub channel |

## Installation and operation
From the repository root:

```bash
make install
cd indexer
../.venv/bin/python -m pipeline.run --help
CORPUS_DIR=../eval/fixtures ../.venv/bin/python -m pipeline.run
../.venv/bin/python -m pipeline.run --dummy
```

The real command requires reachable Ollama and ChromaDB services. Dummy mode only
requires ChromaDB and writes deterministic placeholder vectors. Tests use fixtures
and mocks; they do not require Ollama, Redis, or ChromaDB.

## Safe re-indexing and troubleshooting
Collection metadata pins `embed_model` and `dimension`. If either configured value
differs from an existing collection, storage stops with an explicit migration error.
Create a separately named collection, index with the new pin, verify its count and
metadata, then switch readers to it. Do not delete the old collection as the first
migration step.

Common failures are `no documents found` (check `CORPUS_DIR` and extensions), OCR
errors (install the Tesseract executable in addition to Python packages), embedding
dimension mismatches (check `EMBED_MODEL` and `EMBED_DIMENSION`), and Chroma
connection errors (check host/port readiness). Redis is optional, but skipped or
failed invalidation is always logged.

## Evaluation method
The evaluation fixtures identify expected passages by source and section. Recall@k
is a hit when a retrieved passage matches an expected source/section pair within the
top k; chunk IDs are not used because chunking settings can legitimately change. No
production recall result is reported until a real corpus and service-backed
retrieval run are available.

## Phase 5 operational measurements

The captured `kubectl top` output in `docs/evidence/kubectl-top-indexer.txt`
records the indexer at 974m CPU and 35Mi memory during the recorded run. The
API capture shows three API pods at 154--157Mi, while the configured API limit
is 512Mi (`k8s/base/api-deployment.yaml`), leaving observed headroom. The
indexer limit is 1Gi (`k8s/base/indexer-job.yaml`); an actual limit breach
would be reported as `OOMKilled`/exit 137, not inferred from this single
sample. HPA evidence records `7%/70%`, and endpoint evidence records three
discovered API addresses, confirming label-driven Service discovery.
