# Assignment 03: P0–P3 evidence and acceptance

This checklist is checked against the repository copies of
[Assignment 03](../Documents/Assignment_03.md) and
[the RAGOps paper](../Documents/RAGOps%20Operating%20and%20Managing%20Retrieval%20Augmented%20Generation%20Pipelinei.md).
The assignment's concrete counts and deliverables take precedence over the
paper's illustrative metrics. Completion requires measured artifacts; an
implementation or a historical reference-harness PASS is not sufficient.

| Phase / requirement | Paper connection | Implementation / evidence | Acceptance condition |
| --- | --- | --- | --- |
| P0: schemas and measured baseline | 3.2; 5.1 traceability | `docs/RAGOPS-CONTRACTS.md`; `baseline-freeze.json` | Freeze the real configuration, golden hash and result hash; retain fixture provenance separately. |
| P1: verify before chunking | 4.2.1–4.2.2 | `indexer/pipeline/run.py`, `verify.py` | Each document has quality, completeness, recency and uniqueness outcomes and reasons; failed files are quarantined. |
| P1: incremental updates | 4.2.3–4.2.4 | `store.py`; `scripts/audit_lifecycle.py` | Unchanged embeds zero; changed document leaves another document's IDs, text, metadata and embeddings identical; deletion leaves zero rows by source. |
| P1: archive and restore | 4.2.3; 5.1 traceability | lifecycle result, archived snapshots and superseded metadata | Restore the old version and deactivate its successor; retain history. |
| P1: Batch B | 4.2.2 | `corpus/batch-b/MANIFEST.md`; verification reports | All 12 documents are reported, including two exact duplicates, one near duplicate, corruption/truncation, missing version, newer version and injection. |
| P1: golden set | 4.2.5 domain-specific datasets | `eval/golden.jsonl` | 33 questions: 22 answerable, 6 unanswerable, 5 hard; genuine human authorship/review must be confirmed by the members. |
| P2: embedding | Table 1 module level | `eval/module_level.py` | Real embeddings for 15 paraphrase and 15 unrelated pairs; gap, time per indexed chunk and repeated-text largest difference. |
| P2: retrieval | Table 1 component level | `eval/runtime.py` | Page-aware recall@3/@5, MRR, duplicate-safe nDCG@5; typo noise and every metric delta. |
| P2: answers | Table 1 end-to-end; 6.2 | `eval/runtime.py` | Faithfulness proxy, abstention correctness, citation validity, p50/p95; each response links to its real trace. |
| P2: stochasticity | 4.2.5 | `eval/run_offline_suite.py` | Two actual executions with seed 2026, metric differences and latency-variation explanation. |
| P3: one change | 4.2.5–4.2.6 | `scripts/complete_phase03.py` | Compare top-k while retaining corpus, embedding model, generator and generation parameters. |
| P3: release decision | 4.2.6 predefined thresholds | `eval/gate.json`, `eval/gate.py` | A real passing candidate and a real failing candidate, with exit codes 0 and 1. Both repeated runs must pass to authorize the handoff. |
| Release on Kubernetes | 4.2.6 staged rollout; assignment C3/F3 | Phase 6 | A P3 offline PASS is not a deployment claim. Candidate Service/collection, rollout and undo evidence remain required in P6. |

## Measured data-management evidence

The Batch A/B reports under `eval/results/20261122T181002Z/` record 639
initial chunks and five additional accepted Batch B chunks. Both unchanged
reruns embedded zero chunks. Batch B has five passes and seven failures.
The failed-check counts are quality 1, completeness 3, uniqueness 3 and recency
1; a document may fail more than one check, so these counts are not additive.
`scripts/phase03_evidence.py` checks these assertions against the JSON files.

The strengthened lifecycle run
`eval/results/lifecycle-20261123T115239Z.json` additionally proves that updating
`access-2026.md` preserves the separate library document's IDs, text, metadata
and embedding values. The old access version is restored, and deletion leaves
zero chunks for each deleted document ID.

## Evaluation configuration and interpretation

The November 23 real run uses `nomic-embed-text`, the existing verified
`audit-20261122t181002z` collection and `llama3.2:1b`. Docker exposes two CPUs and
approximately 3 GB RAM; the smaller generator replaces the interrupted 3B run
for this new baseline. The generator is held fixed for all top-k candidates.
Temperature is zero, seed is 2026 and the output budget is 384 tokens.
Historical 3B and deterministic-reference results are not mixed into this
comparison. Offline timings include the serving answer function but exclude
HTTP transport and the response cache. Each independent run really executes
retrieval and generation; trace replay is not counted as a repeated run.

Faithfulness is a deterministic lexical-support proxy, not semantic entailment:
at least 80% of non-stopword answer tokens and every numerical claim must occur
in the actual generator context. It can falsely reject valid paraphrases and
miss contradictions or negation. This limitation follows the evaluation
challenge discussed in paper section 6.2 and must remain in the final report.
No LLM judge is used, so the conditional eight-answer human/LLM agreement
requirement does not apply. Human golden authorship and synthetic-question
review are separate mandatory requirements and cannot be certified by an AI.

The gate thresholds were committed before these runs: at most 0.05 absolute
recall@5 loss, faithfulness proxy at least 0.90, p95 at most 180000 ms and all
unanswerable questions correctly abstained without regression. These are
project-specific choices, not values prescribed by the paper. Low retrieval
quality is reported even if a relative gate passes. A failed candidate must
remain rejected; thresholds must not be lowered to manufacture a passing run.

## Reproduction

With real Chroma and Ollama running, set `PYTHONPATH=api:indexer:eval`,
`RETRIEVER=chroma`, `LLM_PROVIDER=ollama-host`, `CHROMA_HOST`,
`CHROMA_COLLECTION=audit-20261122t181002z`, `OLLAMA_URL`, `EMBED_TIMEOUT=300`,
`LLM_MODEL=llama3.2:1b`, `TEMPERATURE=0`, and `OLLAMA_KEEP_ALIVE=5m`.

```text
python scripts/validate_phase1_member2.py
python scripts/audit_lifecycle.py
python scripts/complete_phase03.py --out eval/results/p03-20261123
python scripts/phase03_evidence.py --results eval/results/p03-20261123
python eval/gate.py --experiment eval/results/p03-20261123/change-topk4-run_1.json --config eval/gate.json --out eval/results/p03-20261123/gate-cli-topk4.json
```

The orchestrator exits nonzero unless it has measured at least one passing and
one failing candidate. `--resume` reuses complete compatible suites explicitly;
partial per-stage and per-answer files are evidence of progress, not a completed
suite. Screenshots must show actual commands and output from the group's
cluster. Rendered terminal illustrations are not accepted as screenshots.

## Outstanding acceptance records

- Member confirmation of the existing human-written and human-reviewed labels.
- Completed real baseline/candidate suites, decision and frozen-baseline files.
- Genuine cluster screenshots for A, B and C; the Phase 6 rollout is separate.

These items stay open until their evidence exists; this document does not
declare P0–P3 complete merely because the scripts are available.
