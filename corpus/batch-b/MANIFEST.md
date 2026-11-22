# Batch B planted-problem manifest

Batch B is an 11-document adversarial update set for Assignment 03 Part A.
Run the indexer with `CORPUS_DIR=corpus/batch-b`; the verification report must
record the result for every document. The expected quarantine directory is the
configured `QUARANTINE_DIR` (Kubernetes: `/data/quarantine`). The injected
document ID is `batch-b-injected-instruction.md`.

| Document | Planted condition | Expected result |
| --- | --- | --- |
| `batch-b-clean-policy-2026.md` | Clean canonical source | Pass and index |
| `batch-b-exact-duplicate.md` | Byte-for-byte duplicate of clean source | Fail uniqueness and quarantine |
| `batch-b-near-duplicate.md` | Same policy with small wording changes | Fail embedding cosine uniqueness and quarantine |
| `batch-b-truncated.md` | Explicit `[TRUNCATED]` marker | Fail completeness and quarantine |
| `batch-b-missing-metadata.md` | No `doc_version` front matter | Fail completeness and quarantine |
| `batch-b-policy-2026.md` | Older version of the Batch B policy | Fail recency and quarantine |
| `batch-b-policy-2027.md` | Newer version of the Batch B policy | Pass recency and index |
| `batch-b-injected-instruction.md` | Untrusted prompt-injection text | Pass data verification; later guardrail must treat instruction as data |
| `batch-b-records-policy.md` | Clean exact-retention fact | Pass and index |
| `batch-b-grade-improvement.md` | Multi-condition/hard question source | Pass and index |
| `batch-b-corrupt.txt` | Replacement/control characters | Fail quality and quarantine |

The exact duplicate is deliberately byte-identical to
`batch-b-clean-policy-2026.md`. The older/newer pair uses the same logical
document identity (`batch-b-policy`) and versions `2026` and `2027`.
