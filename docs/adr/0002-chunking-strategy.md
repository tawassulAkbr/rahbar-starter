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
