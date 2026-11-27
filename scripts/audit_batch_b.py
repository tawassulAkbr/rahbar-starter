"""Exercise all planted Batch B problems against an already indexed old policy."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil

from pipeline.config import get_settings
from pipeline.run import run_pipeline
from pipeline.store import get_client, load_state


stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
root = Path('.audit-data') / f'batch-b-{stamp}'
corpus = root / 'corpus'
corpus.mkdir(parents=True)
results = Path('eval/results') / f'batch-b-{stamp}'
results.mkdir(parents=True)
settings = replace(get_settings(), corpus_dir=str(corpus), collection=f'batch-b-{stamp.lower()}',
                   state_file=str(root / 'state.json'), archive_dir=str(root / 'archive'),
                   quarantine_dir=str(root / 'quarantine'), verification_report_dir=str(results))
old_name = 'batch-b-policy-2026.md'
shutil.copy2(Path('corpus/batch-b') / old_name, corpus / old_name)
# Before the newer batch exists, this version is the active policy. Only the
# disposable baseline copy changes; the planted Batch B fixture stays intact.
old_path = corpus / old_name
old_path.write_text(old_path.read_text().replace('superseded: true', 'superseded: false'), encoding='utf-8')


def ingest(label):
    count = run_pipeline(settings)
    evidence = {'label': label, 'collection_count': count, **load_state(settings.state_file)['last_run']}
    (results / f'{label}.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence), flush=True)
    return evidence


ingest('baseline-old-version')
initial_collection = get_client(settings).get_collection(name=settings.collection)
initial_old = initial_collection.get(where={'source': old_name}, include=['metadatas'])
assert initial_old['ids'] and all(not m['superseded'] for m in initial_old['metadatas'])
assert ingest('baseline-unchanged')['embedded_chunks'] == 0
for path in Path('corpus/batch-b').iterdir():
    if path.is_file() and path.name != 'MANIFEST.md':
        shutil.copy2(path, corpus / path.name)
batch = ingest('batch-b')
assert old_name in batch['superseded_documents']
collection = get_client(settings).get_collection(name=settings.collection)
old = collection.get(where={'source': old_name}, include=['metadatas'])
assert old['ids'] and all(meta['superseded'] for meta in old['metadatas'])
assert list(Path(settings.archive_dir).rglob(old_name))
assert ingest('batch-b-unchanged')['embedded_chunks'] == 0
reports = sorted(results.glob('verification-*.json'))
batch_report = next(json.loads(p.read_text()) for p in reports
                    if len(json.loads(p.read_text())['documents']) == 12)
failed = [row for row in batch_report['documents'] if row['verdict'] == 'fail']
for row in failed:
    active = collection.get(where={'$and': [{'source': row['document']}, {'superseded': False}]})
    assert active['ids'] == [], row['document']
summary = {'collection': settings.collection, 'batch_b_documents': 12,
           'pass': 12 - len(failed), 'fail': len(failed),
           'previously_indexed_version': old_name, 'superseded_chunks': len(old['ids']),
           'failed_document_active_chunk_counts': {row['document']: 0 for row in failed}}
(results / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
