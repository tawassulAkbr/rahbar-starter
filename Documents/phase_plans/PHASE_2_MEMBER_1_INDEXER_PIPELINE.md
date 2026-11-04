# Phase 2 — Member 1: Five-Stage Indexing Pipeline & ChromaDB Store

## Role: Data Pipeline & Vector Storage Specialist
**Deliverables Target:** Complete implementation of `indexer/pipeline/{extract,clean,chunk,embed,store}.py`, supporting OCR, structure-aware chunking, embedding model pinning, and ChromaDB persistence.

---

### Key Responsibilities & Implementation Steps

#### 1. Stage 1: Extraction (`extract.py`)
- Ingest PDFs from `CORPUS_DIR` (or Markdown fixtures for CI).
- Use `pdfplumber` (or `pypdf`/`fitz`) to extract text page-by-page.
- Check if extracted text is empty or below threshold:
  - If no text layer found (scanned PDF), invoke `pytesseract.image_to_string`.
- Strip repeating running headers and footers while preserving chapter headings, section boundaries, and tables.
- Return structured extracted documents with page numbers and metadata.

#### 2. Stage 2: Cleaning (`clean.py`)
- Normalize whitespace, fix broken line wraps, and clean PDF encoding artifacts.
- Preserve markdown headings (`#`, `##`, numbered clauses `1.21`, `4.2`).
- Preserve table delimiters (`|`, tabulations) so tabular relationships remain intact.
- Document in `docs/PIPELINE.md` what rules were applied and what was deliberately retained.

#### 3. Stage 3: Structure-Aware Chunking (`chunk.py`)
- Implement hierarchical structure-aware chunking:
  - First split by major headings/sections (`clause`, `section`, `###`).
  - Next split by paragraphs.
  - Finally split by sentences if chunk exceeds target size (`CHUNK_SIZE`).
- Apply sliding window overlap (`CHUNK_OVERLAP`) across sentence boundaries.
- Attach required metadata to every chunk:
  - `source`: document filename.
  - `section`: nearest section title or clause number.
  - `page`: original page number.
  - `doc_version`: policy year or version string (e.g. `"2023"`, `"2026"`).
  - `superseded`: boolean (`True` if repealed/superseded by a newer document, else `False`).
- Compute and log storage amplification: `(stored_tokens / original_tokens)`.

#### 4. Stage 4: Embedding (`embed.py`)
- Connect to embedding service (e.g., Ollama `/api/embeddings` or hosted endpoint) using `EMBED_MODEL` (e.g. `nomic-embed-text`).
- Embed chunks in batches with backoff and retry.
- Validate embedding dimension matches expected dimension (e.g. 768 for nomic-embed-text).

#### 5. Stage 5: Vector Store (`store.py`)
- Connect to ChromaDB server using `chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)`.
- Create or get collection `settings.chroma_collection`.
- **CRITICAL EMBEDDING PIN RECORDING:**
  - Store model name and vector dimension in collection metadata:
    ```python
    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={
            "embed_model": settings.embed_model,
            "dimension": dimension,
            "created_at": datetime.utcnow().isoformat()
        }
    )
    ```
- Upsert chunks: `ids=[c.chunk_id]`, `documents=[c.text]`, `embeddings=[c.vector]`, `metadatas=[c.metadata]`.
- Trigger cache invalidation signal to Redis when re-indexing finishes.

---

### Member 1 Acceptance Checklist (Phase 2)
- [ ] `extract.py` extracts text and successfully OCRs the scanned PDF.
- [ ] `clean.py` preserves tables and section headings.
- [ ] `chunk.py` implements structure-aware splitting with overlap and correct metadata schema.
- [ ] `embed.py` generates vectors using `EMBED_MODEL`.
- [ ] `store.py` stores chunks in ChromaDB and writes `embed_model` into collection metadata.
- [ ] Running `python -m pipeline.run` on test corpus completes without error.
- [ ] Chunks in Chroma carry `source`, `section`, `page`, `doc_version`, and `superseded`.
