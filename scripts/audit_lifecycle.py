"""Real Chroma/Ollama incremental and rollback evidence on isolated documents."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json
from pipeline.config import get_settings
from pipeline.run import run_pipeline
from pipeline.store import load_state, get_client, restore_document

stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
root = Path('.audit-data') / ('lifecycle-' + stamp)
corpus = root/'corpus'
corpus.mkdir(parents=True)
settings = replace(get_settings(), corpus_dir=str(corpus), collection='lifecycle-' + stamp.lower(),
                   state_file=str(root/'state.json'), archive_dir=str(root/'archive'),
                   quarantine_dir=str(root/'quarantine'), verification_report_dir='eval/results')
def write(name, version, text):
    path = corpus/name
    path.write_text(f'---\ndoc_version: {version}\n---\n# Campus policy\n{text}\n')
    return path
def ingest(label):
    run_pipeline(settings)
    return {'step': label, **load_state(settings.state_file)['last_run']}
evidence = []
old = write('access-2026.md', '2026', 'Access permissions are reviewed every six months.')
sentinel = write('library-2026.md', '2026', 'The library lends printed books for fourteen days.')
evidence.append(ingest('initial'))
collection = get_client(settings).get_collection(name=settings.collection)
sentinel_before = collection.get(where={'source': sentinel.name}, include=['documents', 'embeddings', 'metadatas'])
evidence.append(ingest('unchanged'))
assert evidence[-1]['embedded_chunks'] == 0
write(old.name, '2026', 'Access permissions are reviewed every three months.')
evidence.append(ingest('changed'))
sentinel_after = collection.get(where={'source': sentinel.name}, include=['documents', 'embeddings', 'metadatas'])
assert sentinel_before['ids'] == sentinel_after['ids']
assert sentinel_before['documents'] == sentinel_after['documents']
assert sentinel_before['metadatas'] == sentinel_after['metadatas']
assert (sentinel_before['embeddings'] == sentinel_after['embeddings']).all()
assert set(evidence[-1]['embedded_chunks_by_document']) == {old.name}
evidence[-1]['unrelated_document_unchanged'] = {
    'document_id': sentinel.name, 'chunk_count': len(sentinel_after['ids']),
    'ids_text_metadata_embeddings_identical': True,
}
write('access-2027.md', '2027', 'Access permissions are reviewed every month.')
evidence.append(ingest('superseded'))
collection = get_client(settings).get_collection(name=settings.collection)
old_rows = collection.get(where={'source': old.name})
assert old_rows['ids'] and all(m['superseded'] for m in old_rows['metadatas'])
restore_document(old.name, settings)
restored = collection.get(where={'source': old.name})
assert all(not m['superseded'] for m in restored['metadatas'])
assert all(m['superseded'] for m in collection.get(where={'source':'access-2027.md'})['metadatas'])
evidence.append({'step':'rollback', 'restored_document': old.name, 'active_chunks':len(restored['ids'])})
sentinel.unlink()
evidence.append(ingest('delete-unrelated-document'))
assert not collection.get(where={'source': sentinel.name})['ids']
old.unlink()
evidence.append(ingest('delete-final-active-document'))
assert not collection.get(where={'source':old.name})['ids']
output=Path('eval/results')/f'lifecycle-{stamp}.json'
output.write_text(json.dumps({'collection':settings.collection,'steps':evidence},indent=2))
print(output)
