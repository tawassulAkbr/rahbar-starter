"""Finish the real cluster acceptance sequence, preserving failed outcomes.

Prerequisites: baseline and candidate evaluation Jobs already running, real
models ready, and the assignment03 manifests/images prepared as in k8s/README.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'eval/results/assignment03-final'
MANIFESTS = ROOT / 'k8s/assignment03'
OUT.mkdir(parents=True, exist_ok=True)


def command(name, args, timeout=120):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout)
    (OUT / (name + '.txt')).write_text('$ ' + subprocess.list2cmdline(args) + '\n' +
        result.stdout + result.stderr + f'\nExit code: {result.returncode}\n', encoding='utf-8')
    return result


def wait_job(name):
    deadline = time.monotonic() + 14400
    while time.monotonic() < deadline:
        result = command(name + '-status', ['kubectl', 'get', 'job/' + name, '-n', 'rahbar', '-o', 'json'])
        obj = json.loads(result.stdout) if result.returncode == 0 else {}
        terminal = next((x['type'] for x in obj.get('status', {}).get('conditions', [])
                         if x['type'] in {'Complete', 'Failed'} and x['status'] == 'True'), None)
        if terminal:
            command(name, ['kubectl', 'logs', 'job/' + name, '-n', 'rahbar', '--all-containers=true'])
            print(name, terminal, flush=True)
            return terminal
        time.sleep(20)
    raise TimeoutError(f'{name} did not reach a terminal state in four hours')


def apply_job(name, spec):
    path = MANIFESTS / (name + '.json')
    spec['metadata']['name'] = name
    path.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
    result = command(name + '-apply', ['kubectl', 'apply', '-f', str(path)])
    if result.returncode:
        raise RuntimeError(result.stderr)
    return wait_job(name)


def export():
    result = command('collection-log', [sys.executable, 'scripts/collect_assignment03.py', '--out', str(OUT)])
    if result.returncode:
        raise RuntimeError(result.stderr)


def load(name):
    path = OUT / 'volume' / name
    return json.loads(path.read_text()) if path.exists() else {}


wait_job('eval-job')
wait_job('eval-candidate-job')
export()
baseline, candidate = load('eval-results.json'), load('eval-candidate-results.json')

# Exercise the same gate against retained complete measurements. Rejudging
# does not require another expensive generation run or an image rebuild.
if baseline and candidate:
    original = command('config-before-gate-demo', ['kubectl', 'get', 'configmap', 'rahbar-config', '-n', 'rahbar', '-o', 'json'])
    original_data = json.loads(original.stdout)['data']
    gate_job = yaml.safe_load((ROOT / 'k8s/eval-job.yaml').read_text())
    gate_container = gate_job['spec']['template']['spec']['containers'][0]
    gate_container['command'] = ['python', '-c']
    gate_container['args'] = [
        "import json,sys; from run_eval import gate; "
        "b=json.load(open('/results/eval-results.json'))['runs'][0]['end_to_end']; "
        "c=json.load(open('/results/eval-candidate-results.json'))['runs'][0]['end_to_end']; "
        "failures=gate(c,b); print(json.dumps({'gate':'FAIL' if failures else 'PASS','failures':failures})); "
        "sys.exit(1 if failures else 0)"]
    default_status = apply_job('assignment03-gate-default', gate_job)
    try:
        patch = OUT / 'strict-threshold-patch.json'
        patch.write_text(json.dumps({'data': {'GATE_P95_MAX_MS': '1'}}))
        command('strict-threshold-edit', ['kubectl', 'patch', 'configmap', 'rahbar-config', '-n', 'rahbar', '--type=merge', '--patch-file', str(patch)])
        strict_job = json.loads(json.dumps(gate_job))
        strict_status = apply_job('assignment03-gate-strict', strict_job)
    finally:
        restore = OUT / 'restore-threshold-patch.json'
        restore.write_text(json.dumps({'data': {'GATE_P95_MAX_MS': original_data['GATE_P95_MAX_MS']}}))
        command('restore-threshold', ['kubectl', 'patch', 'configmap', 'rahbar-config', '-n', 'rahbar', '--type=merge', '--patch-file', str(restore)])
    if default_status == 'Complete' and strict_status == 'Failed':
        (OUT / 'gate-demonstration.json').write_text(json.dumps({'default': default_status, 'strict_p95_1ms': strict_status,
            'same_image': True, 'same_measured_answers': True, 'release_policy_restored': True}, indent=2))

if baseline.get('gate_status') == candidate.get('gate_status') == 'PASS':
    result = command('promotion', ['kubectl', 'set', 'env', 'deployment/api', '-n', 'rahbar',
                                  'CHROMA_COLLECTION=rahbar-candidate', 'TOP_K=4'])
    if result.returncode == 0:
        command('promotion-rollout', ['kubectl', 'rollout', 'status', 'deployment/api', '-n', 'rahbar', '--timeout=180s'], timeout=200)
        # Restore the baseline for a data-only drift comparison. Promoting an
        # old candidate after ingesting new data would lose those new sources.
        command('release-demo-undo', ['kubectl', 'rollout', 'undo', 'deployment/api', '-n', 'rahbar'])
        command('release-demo-undo-status', ['kubectl', 'rollout', 'status', 'deployment/api', '-n', 'rahbar', '--timeout=180s'], timeout=200)
else:
    print('Release rejected: no completed passing baseline and candidate gates.', flush=True)

# Measure data drift after both pre-Batch-B suites. Candidate collection remains
# an isolated pre-Batch-B snapshot; the baseline serves the evolving corpus.
command('batch-b-apply', ['kubectl', 'apply', '-f', 'k8s/assignment03/batch-b.json'])
batch_status = wait_job('assignment03-batch-b')
if batch_status == 'Complete':
    after_job = yaml.safe_load((ROOT / 'k8s/eval-job.yaml').read_text())
    container = after_job['spec']['template']['spec']['containers'][0]
    container['args'] = [container['args'][0].replace('/results/eval-results.json', '/results/eval-after-b-results.json').replace('--bootstrap-baseline', '')]
    apply_job('assignment03-eval-after-b', after_job)
export()
after = load('eval-after-b-results.json')
if baseline and after:
    def delta(left, right):
        return {key: right[key] - left[key] for key in left.keys() & right.keys()
                if isinstance(left[key], (int, float)) and isinstance(right[key], (int, float))}
    drift = {'method': 'Complete real Kubernetes suites before and after ingestion Job; same golden set and seed.',
             'before': baseline, 'after': after,
             'metric_deltas_after_minus_before': {
                 section: delta(baseline['summary_table'][section], after['summary_table'][section])
                 for section in ('module', 'component', 'end_to_end')}}
    (OUT / 'volume/batch-b-drift.json').write_text(json.dumps(drift, indent=2) + '\n')

summary = subprocess.run([sys.executable, 'scripts/summarize_traces.py', '--path',
                          'traces/assignment03-final.jsonl'], cwd=ROOT, capture_output=True, text=True)
if summary.returncode == 0:
    (OUT / 'trace-summary.json').write_text(summary.stdout, encoding='utf-8')

for script in ('scripts/assignment03_checklist.py', 'scripts/build_assignment03_report.py'):
    result = subprocess.run([sys.executable, script], cwd=ROOT)
    if result.returncode:
        raise RuntimeError(f'{script} failed')
print('Acceptance sequence finished; inspect checklist.json. Failed quality is retained as failed.', flush=True)
