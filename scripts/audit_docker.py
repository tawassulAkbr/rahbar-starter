"""Run on a disposable copy of image corpus; never mutate repository inputs."""
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import replace

from pipeline.config import get_settings
from pipeline.run import run_pipeline
from pipeline.store import load_state, get_client, restore_document

root = Path('/workspace')
run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
work = root / '.audit-data' / run_id
work.mkdir(parents=True)
corpus = work / 'corpus'
shutil.copytree('/corpus', corpus)
results = root / 'eval/results' / run_id
results.mkdir(parents=True)
settings = replace(get_settings(), corpus_dir=str(corpus), collection='audit-' + run_id.lower(),
                   archive_dir=str(work/'archive'), quarantine_dir=str(work/'quarantine'),
                   state_file=str(work/'state.json'), verification_report_dir=str(results))
def run(label):
    count = run_pipeline(settings)
    evidence = {'label': label, 'collection_count': count, **load_state(settings.state_file)['last_run']}
    (results/f'{label}.json').write_text(json.dumps(evidence, indent=2))
    return evidence
run('batch-a')
unchanged = run('batch-a-unchanged')
assert unchanged['embedded_chunks'] == 0
# Merge Batch B into the same authoritative data lake and discovery index.
index = corpus/'raw/_index.json'
entries = json.loads(index.read_text())
from pipeline.run import _front_matter
for source in (root/'corpus/batch-b').iterdir():
    if source.name == 'MANIFEST.md':
        continue
    destination = index.parent/source.name
    shutil.copy2(source, destination)
    meta = _front_matter(source) if source.suffix == '.md' else {}
    entries.append({'file': source.name, 'doc_version': meta.get('doc_version', 'unknown'), 'superseded': False})
index.write_text(json.dumps(entries))
run('batch-b')
assert run('batch-b-unchanged')['embedded_chunks'] == 0
config = {'collection': settings.collection, 'results': str(results), 'work': str(work), 'state_file': settings.state_file}
(root/'eval/results/latest-audit.json').write_text(json.dumps(config, indent=2))
print(json.dumps(config))
