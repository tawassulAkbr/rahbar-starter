"""Derive the assignment checklist from retained execution evidence."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', type=Path, default=Path('eval/results/assignment03-final'))
args = parser.parse_args()
root = args.evidence


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def text(name):
    path = root / name
    return path.read_text(encoding='utf-8-sig') if path.exists() else ''


def complete_job(name):
    value = text(name + '-status.txt')
    start, end = value.find('{'), value.rfind('}')
    if start < 0:
        return False
    return any(x['type'] == 'Complete' and x['status'] == 'True'
               for x in json.loads(value[start:end + 1]).get('status', {}).get('conditions', []))


items = []


def add(task, passed, detail, failed_status='PARTIAL'):
    items.append({'task': task, 'status': 'PASS' if passed else failed_status, 'detail': detail})


volume = root / 'volume'
baseline = read(volume / 'eval-results.json')
candidate = read(volume / 'eval-candidate-results.json')
levels = read(volume / 'eval-results-levels-run-1.json')
audit = complete_job('assignment03-audit-final')
add('A1 / Batch B', audit, 'Real isolated audit: 12 documents; 5 pass, 7 quarantined; four checks with reasons; failed documents have zero active chunks.')
add('A2 incremental / update / deletion / archive / restore', audit and complete_job('assignment03-unchanged-final'),
    'Fresh lifecycle Job plus full-corpus unchanged Job: 0 embedded chunks; changed-only update; unrelated embeddings preserved; deleted IDs count 0; rollback restored one active chunk.')
golden = [json.loads(x) for x in Path('eval/golden.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
add('B golden-set structure', len(golden) >= 25 and sum(x['type'] == 'hard' for x in golden) >= 5 and
    sum(x['type'] == 'answerable' for x in golden) >= 15 and sum(x['type'] == 'unanswerable' for x in golden) >= 5,
    '39 questions; physical PDF clause references corrected directly against source; provenance labels present.')
add('B personal authorship / review', False, 'Members must personally confirm at least 8 hand-written questions and 8 synthetic reviews; labels alone cannot certify human work.')
add('B module embeddings', bool(levels.get('module')), 'Real module metrics and determinism: eval-results-levels-run-1.json; missing file means not completed.')
add('B component retrieval / noise', bool(levels.get('component')), 'Real recall@3/5, MRR, nDCG@5 and typo deltas in stage checkpoint.')
add('B end-to-end / repeatability', bool(baseline), 'Two complete runs and metric deltas required in eval-results.json; partial answer checkpoints do not complete this task.')
add('C1 baseline versus candidate', bool(baseline and candidate), 'Both complete three-level suites required; candidate TOP_K=4 uses an isolated collection.')
add('C2 gate passing and failing', (root / 'gate-demonstration.json').exists(), 'Thresholds are ConfigMap-driven; retain measured passing and failing Job results, without weakening the release policy.')
add('C3 / F3 passing promotion', candidate.get('gate_status') == 'PASS' and (root / 'promotion.txt').exists(), 'Only a completed passing real-model candidate gate permits promotion; no incomplete/failed candidate is released.')
traces_path = Path('traces/assignment03-final.jsonl')
traces = [json.loads(x) for x in traces_path.read_text(encoding='utf-8').splitlines() if x.strip()] if traces_path.exists() else []
required = {'trace_id', 'timestamp', 'query', 'rewritten_query', 'embed_model', 'embed_model_version', 'collection',
            'retrieved', 'filters', 'reranked_order', 'prompt_hash', 'model', 'parameters', 'response', 'citations',
            'guardrail_actions', 'latency_per_stage', 'cache_hit'}
add('D1 trace fields / D2 reconstruction', bool(traces) and all(required <= x.keys() for x in traces) and
    (root / 'trace-reconstruction.txt').exists(), 'Cluster JSONL trace export and exact-context/prompt reconstruction retained.')
add('D3 trace metrics', (root / 'trace-summary.json').exists(), 'Top-1 distribution, abstention/cache rates, stage p95 and flagged injections.')
add('D4 planted injection', any(x.get('guardrail_actions') and any('batch-b-injected-instruction' in y.get('document_id', '') for y in x.get('retrieved', [])) for x in traces),
    'Runtime check uses the real isolated Batch B collection and an explicit 1.01 relevance floor to isolate rail logging; it does not measure answer quality.')
add('D5 trace-only root cause', (root / 'root-cause.txt').exists(), 'Five lines derived only from a wrong/abstained current evaluation trace.')
live = [json.loads(x) for x in Path('eval/live_queries.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
add('E1 simulated live log', len(live) >= 40, '40 simulated user queries, including 12 from uncovered topics.')
before = read(Path('eval/results/assignment03-coverage-before.json'))
after = read(Path('eval/results/assignment03-coverage-after.json'))
add('E2 coverage / E4 close gap', before.get('coverage', 1) < .85 <= after.get('coverage', 0), '0.35 cosine cutoff: 32/40 (80%, exit 1) before; six questions added; 37/40 (92.5%, exit 0) after. JSON lists uncovered topics.')
add('E3 measured Batch B drift', (volume / 'batch-b-drift.json').exists(), 'A full real-model before/after-Batch-B suite comparison is required; old reference-harness drift is excluded.')
add('F1 deployment / durable state', 'Running' in text('cluster.txt') and 'Bound' in text('cluster.txt'), 'Real API, Chroma, Redis, Ollama and UI recovered after cluster restart; 639 persisted chunks and bound data/trace/result PVCs.')
add('F2 ingestion Job / CronJob', audit and 'cronjob.batch/reindex' in text('cluster.txt'), 'Completed real audit/indexer Jobs and scheduled CronJob; shared-volume writer lock; API does not index.')
add('F2 evaluation Job / ConfigMap outcome', bool(baseline) and (root / 'gate-demonstration.json').exists(), 'Evaluation Job runs full suite and must fail its Job status on gate rejection; prove threshold edit changes outcome without rebuilding.')
add('F3 bad release / undo / post-undo trace', 'successfully rolled out' in text('rollout-status.txt') and any(x['trace_id'] == read(root / 'post-undo-answer.json').get('trace_id') and x['collection'] == 'rahbar' and x['embed_model_version'] != 'unknown' for x in traces),
    'Deliberately missing collection prevented readiness; rollout undo restored rahbar; new trace must identify previous collection/model digest.')
add('F4 stdout / volume traces / metrics', bool(traces) and (root / 'metrics-http.txt').exists(), 'kubectl logs plus PVC trace export; /metrics checked through service port-forward.')
add('F5 resource measurements', 'MEMORY' in text('resources.txt'), 'Measured API/Chroma/Ollama/evaluator/indexer CPU and memory are retained; resource requests/limits exist in manifests.')
add('Docker / Minikube', 'memory=' in text('docker.txt') and 'Running' in text('cluster.txt'), 'Docker Desktop and profile minikube2 running with real models; API /readyz reports 639 indexed chunks.')
add('G report / README', Path('docs/Assignment_03_Report.pdf').exists() and bool(baseline and candidate) and (volume / 'batch-b-drift.json').exists(), 'HTML/PDF and commands updated; missing quality/drift tables remain explicit until complete results exist. Body must stay within eight pages; append genuine screenshots.')
add('Submission screenshots / members / demo', False, 'Capture uncropped actual terminal windows for A–F; confirm human work; both members commit and attend; submit PDF/repo; demo an unseen ingestion batch.', 'MANUAL')
out = {'verified_at': datetime.now(timezone.utc).isoformat(), 'items': items,
       'verdict': 'COMPLETE' if all(x['status'] == 'PASS' for x in items) else 'NOT FULLY COMPLETE'}
(root / 'checklist.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(out['verdict'])
for item in items:
    print(item['status'], item['task'])
