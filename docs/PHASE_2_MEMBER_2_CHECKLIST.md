# Phase 2 Member 2 verification checklist

Phase 2 is implemented on the existing
`feature/assignment-03-phase1-integrated` branch. No new branch was created;
`main` and `dev` are untouched.

## One command

From the repository root:

```text
make eval-offline
```

This writes `eval/results/offline-<UTC timestamp>.json` and runs the suite
twice with seed `2026`.

The equivalent direct command is:

```text
python eval/run_offline_suite.py --corpus corpus --golden eval/golden.jsonl
```

## Requirement mapping

| Requirement | Implementation | Result field |
| --- | --- | --- |
| 15 paraphrase pairs | `eval/module_level.py` | `paraphrase_pairs` |
| 15 unrelated pairs | `eval/module_level.py` | `unrelated_pairs` |
| Mean cosine and gap | `eval/metrics.py`, `module_level.py` | `mean_*_cosine`, `paraphrase_unrelated_gap` |
| Embedding time per text | `module_level.py` | `embedding_time_ms_per_text` |
| Determinism | Same text embedded twice | `determinism_largest_abs_difference`, `determinism_pass` |
| recall@3/5 | `eval/component_level.py` | `baseline.recall_at_3/5` |
| MRR and nDCG@5 | `component_level.py`, `metrics.py` | `baseline.mrr`, `baseline.ndcg_at_5` |
| Three irrelevant documents | `_noise_passages()` | `noise_test.irrelevant_documents_added` |
| Noise metric deltas | `component_level.py` | `noise_test.deltas` |
| Faithfulness | Deterministic lexical-support judge | `faithfulness` |
| Abstention correctness | Unanswerable golden rows | `abstention_correctness` |
| Citation validity | Citation-to-retrieved matching | `citation_validity` |
| p50/p95 latency | `metrics.percentile()` | `latency_ms_p50/p95` |
| Two seeded runs | `run_offline_suite.py` | `runs.run_1`, `runs.run_2` |
| Per-metric stochasticity deltas | Same seed comparison | `stochasticity.metric_deltas_run_2_minus_run_1` |
| Timestamped result | Orchestrator output path | `eval/results/offline-*.json` |

## Individual commands

```text
python eval/module_level.py
python eval/component_level.py --corpus corpus --golden eval/golden.jsonl
python eval/e2e_level.py --corpus corpus --golden eval/golden.jsonl
```

The module evaluator defaults to the deterministic, dependency-free reference
embedder. To measure an available Ollama model instead:

```text
python eval/module_level.py --ollama-url http://localhost:11434 --model nomic-embed-text
```

The component/e2e harness skips expensive PDF parsing and uses transparent
golden-evidence fallback passages when extracted PDF text is unavailable. The
result records the number in `corpus.fallback_passages`. This makes the suite
reproducible offline; a live Chroma/API run is still required for production
evidence.

## Acceptance checklist

- [x] Three levels produce numeric metrics.
- [x] Noise test adds three irrelevant documents and reports deltas.
- [x] Two same-seed runs are recorded.
- [x] Per-metric stochasticity deltas are recorded.
- [x] One command writes a timestamped result file.
- [x] Result artifact is committed under `eval/results/`.
