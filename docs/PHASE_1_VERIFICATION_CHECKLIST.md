# Phase 1 verification checklist

This checklist maps every Phase 1 requirement to an implementation location
and a command that proves it. Run commands from the repository root.

## Automated checks

Install the development dependencies if the local environment does not have
pytest:

```text
python -m pip install -r requirements-dev.txt
python -m pytest indexer/tests -q
```

The Phase 1 tests are in
[`indexer/tests/test_phase1_lifecycle.py`](../indexer/tests/test_phase1_lifecycle.py).
They cover all four checks, report generation, quarantine, near-duplicate
embeddings, unchanged zero-embed runs, deletion/orphan cleanup, and restore.

Static and manifest checks:

```text
python -m compileall -q indexer/pipeline
kubectl kustomize k8s/base
git diff --check
```

## Requirement-to-code map

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Verify after extraction, before chunking | `indexer/pipeline/run.py` calls `extract`, `clean`, `verify_documents`, then `chunk` | `run_pipeline()` order |
| Quality check | `indexer/pipeline/verify.py::_quality` | Empty/garbled text test |
| Completeness check | `verify.py::_completeness` | Source/title/version/page/truncation checks |
| Recency check | `verify.py::_recency` | Version ordering and newer-version reason |
| Exact and near uniqueness | `verify.py::_uniqueness` and `_cosine` | Hash and embedding-cosine test |
| Quarantine | `verify.py::_quarantine` | Failed files move under `QUARANTINE_DIR` |
| Per-run report | `verify.py::verify_documents` | `verification-<run_id>.json` in `VERIFY_REPORT_DIR` |
| Hash-based incremental skip | `run.py` + `store.py::store_incremental` | State SHA comparison; unchanged `embedded_chunks: 0` |
| Changed-document replacement | `store_incremental` | Deletes prior chunk IDs, upserts only changed source |
| Deleted-document cleanup | `store_incremental` | Removes prior IDs and records `orphan_chunks_removed` |
| Superseded archive | `store_incremental::_archive_file` | Archives older logical sibling under `ARCHIVE_DIR` |
| Restore | `store.py::restore_document` | Moves archived source back to `CORPUS_DIR` |
| Persistent data lake | `k8s/base/data-lake-pvc.yaml` | 10Gi PVC rendered by Kustomize |
| Job/CronJob mounts | `k8s/base/indexer-job.yaml`, `reindex-cronjob.yaml` | Both mount PVC at `/data` |
| ConfigMap integration | `k8s/base/configmap.yaml` | Verification, archive, quarantine, report, and state keys |

## Runtime proof with a Chroma-backed indexer

1. Ensure Chroma, the embedding service, and the indexer image are running.
2. Run the indexer once and save logs. Confirm `embedded_chunks` is greater than zero and that `/data/index-state.json` contains each accepted source and its `chunk_ids`.
3. Run the same Job again without changing the corpus. Confirm the log says `unchanged; skipping chunks` and ends with `embedded_chunks: 0`.
4. Modify one document. Confirm only that source is chunked/embedded and its old IDs are deleted before upsert.
5. Remove one document and rerun. Inspect `last_run.orphan_chunks_removed` and query Chroma by the deleted source; it must return zero IDs.
6. Add a newer version of an existing logical document. Confirm the old source is under `/data/archive/<logical-id>/`, its metadata is not served, and `restore_document()` moves it back to the corpus.
7. Inspect `/data/reports/verification-*.json`. Every document must have `quality`, `completeness`, `recency`, and `uniqueness` results with a `passed` boolean and reason.

## Kubernetes proof

```text
kubectl apply -k k8s/base
kubectl -n rahbar get pvc rahbar-data-lake
kubectl -n rahbar describe job indexer-job
kubectl -n rahbar logs job/indexer-job
kubectl -n rahbar exec <indexer-pod> -- sh -c 'cat /data/index-state.json'
kubectl -n rahbar exec <indexer-pod> -- sh -c 'find /data/quarantine /data/archive /data/reports -maxdepth 2 -type f -print'
```

Phase 1 does not fabricate Batch A/B evidence: no committed `corpus/batch-b/`
input is present in this worktree. Once Batch B is added, run the normal
indexer Job and commit the generated verification and incremental reports
under `eval/results/`.
