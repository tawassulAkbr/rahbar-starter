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


def measure_drift_stage(label):
    if '--measure-drift' not in sys.argv:
        return
    from run_offline_suite import run_suite

    os.environ['CHROMA_COLLECTION'] = settings.collection
    os.environ['TRACE_DIR'] = str(root / 'traces' / run_id / label)
    suite = run_suite(corpus, root / 'eval/golden.jsonl', checkpoint_dir=results / label)
    (results / f'{label}-suite.json').write_text(json.dumps(suite, indent=2))

run('batch-a')
unchanged = run('batch-a-unchanged')
assert unchanged['embedded_chunks'] == 0
measure_drift_stage('before')
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
measure_drift_stage('after')
if '--measure-drift' in sys.argv:
    from complete_phase03 import compare, variant
    before, after = [json.loads((results / f'{label}-suite.json').read_text()) for label in ('before', 'after')]
    drift = {run: compare(variant(before, run), variant(after, run)) for run in before['runs']}
    (results / 'batch-b-drift.json').write_text(json.dumps(drift, indent=2))
config = {'collection': settings.collection, 'results': str(results), 'work': str(work), 'state_file': settings.state_file}
(root/'eval/results/latest-audit.json').write_text(json.dumps(config, indent=2))
print(json.dumps(config))
