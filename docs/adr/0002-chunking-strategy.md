# ADR 0002: Structure-aware overlapping chunks

## Status

Accepted · 2026-11-07

## Decision

The indexer preserves headings and page metadata while creating bounded chunks
with overlap. The overlap protects answers that cross a boundary; metadata
keeps citations traceable to the source, section, and page. Chunking is kept in
the pipeline rather than the API so every index rebuild uses the same policy.

## Consequences

Overlap increases storage and embedding work, but improves boundary recall. The
configuration and measured trade-off are recorded in `docs/PIPELINE.md`.

The offline fixture comparison measured 1.00 recall@5 for 200/25, 400/50, and
800/100. Storage amplification was 1.087, 1.087, and 1.058 respectively over
the four-document measurement set. The 400/50 option is therefore the chosen
compromise: it keeps the measured recall with fewer chunks than 200/25 and
more overlap protection than 800/100 for longer sections. These are fixture
measurements, not a substitute for production-corpus evaluation.
