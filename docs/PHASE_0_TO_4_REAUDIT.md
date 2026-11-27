# Assignment 03 Phase 0–4 re-audit

This audit supersedes the earlier completion checklists. The scope is Assignment
03 Parts A–D and the associated Phase 0 contracts. Phase 5 coverage, Phase 6
Kubernetes release demonstration, and Phase 7 report remain separate work.

The paper's two lifecycles require evaluation of the system actually serving
queries. The former lexical reference harness generated missing passages from
golden answers and used labels to decide abstention. Those results are retained
with `evidence_status: superseded-reference-harness-not-valid-for-release` and
cannot authorize a release. New evaluation invokes the serving Chroma retriever,
real embedding model, and the same answer function/provider as the API. Golden
labels are used only for scoring. Cache and HTTP transport are excluded from
offline inference timings; separate HTTP checks cover serving and cache behavior.

## Changes mapped to the brief

| Phase / brief | Correction |
|---|---|
| 0 / contracts | Resolve real embedding digests; preserve baseline/reference provenance |
| 1 / A1 | Verify raw extracted text before cleaning; compare duplicates only against accepted documents; two exact duplicate documents in Batch B |
| 1 / A2 | Preserve source snapshots and superseded chunk metadata; restore active version; handle deletion of the final active document; record document counts |
| 2 / B | Real embeddings, real Chroma retrieval, typo noise, page-aware ranking metrics, real answers and trace IDs; no answer-derived evidence |
| 3 / C | Gate rejects synthetic results and non-finite values; ConfigMap environment overrides; thresholds describe a real CPU inference budget |
| 4 / D | Actual provider prompts including retries, document versions, model digest, embedding/rerank timings, cache provenance, and enforced injection rail |

Faithfulness is an explicitly limited deterministic proxy: at least 80% of
non-stopword answer tokens and every numeric claim must occur in retrieved
context. It cannot establish semantic entailment or reliably detect negation.
No LLM judge is used, so the eight-human-label judge-agreement condition does
not apply. Existing human authorship/review labels are preserved, not newly
certified by this audit.

## Reproduce in Docker Desktop

Start the existing Chroma, Ollama and Redis services, with `nomic-embed-text` and
`llama3.2:3b` available. The audit image layers the existing `rahbar-api:dev` and
`rahbar-indexer:dev` dependencies and adds pinned pytest:

```powershell
docker build -f Dockerfile.audit -t rahbar-audit:phase4 .
docker run --rm -v D:/rahbar-starter:/workspace -e TRACE_DIR=/tmp/tests rahbar-audit:phase4 -m pytest api/tests indexer/tests eval/tests -q --junitxml=eval/results/audit-tests.xml
docker run --rm --network rahbar_default -v D:/rahbar-starter:/workspace -e CHROMA_HOST=chroma -e OLLAMA_URL=http://ollama:11434 -e EMBED_TIMEOUT=300 rahbar-audit:phase4 scripts/audit_lifecycle.py
```

`scripts/audit_docker.py` copies the image corpus to `.audit-data/`, uses a new
collection, verifies Batch A then Batch B, and saves counts/reports under
`eval/results/<timestamp>/`. It never moves repository corpus files into
quarantine. `eval/results/latest-audit.json` identifies the resulting collection.

For the evaluation scripts set `PYTHONPATH=api:indexer:eval` (Linux),
`RETRIEVER=chroma`, `LLM_PROVIDER=ollama-host`, `CHROMA_HOST`,
`CHROMA_COLLECTION` from that audit, `OLLAMA_URL`, `EMBED_TIMEOUT=300`,
`TEMPERATURE=0`, and `TRACE_DIR=traces/<run-id>`:

```text
python eval/run_offline_suite.py
python eval/change_experiment.py --candidate-top-k 4 --out eval/results/change-real-topk4.json
python eval/gate.py --experiment eval/results/change-real-topk4.json --config eval/gate.json --out eval/results/gate-real-topk4.json
python scripts/trace.py <trace-id> --path traces/<run-id>/traces.jsonl
python scripts/summarize_traces.py --path traces/<run-id>/traces.jsonl
python -m pipeline.run --restore <archived-document-filename>
```

A failed real candidate remains rejected. Historical reference PASS files must
not be presented as successful real release evidence. Docker verification is
not the Kubernetes demo required by Part F.
