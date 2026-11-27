"""Run two real suites per variant and preserve an auditable P0-P3 handoff.

Run from the repository root with PYTHONPATH=api:indexer:eval and real services.
Existing complete suites are reused only when explicitly requested with --resume.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from change_experiment import _metric_delta
from gate import evaluate
from run_offline_suite import run_suite


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def variant(suite, run):
    config = suite['configuration']
    return {**suite['runs'][run], 'configuration': {
        **config, 'embed_model': config['embedding_model'], 'change': 'retrieval_top_k'}}


def compare(baseline, candidate):
    return {
        'module': _metric_delta(baseline['module'], candidate['module'], (
            'mean_paraphrase_cosine', 'mean_unrelated_cosine', 'paraphrase_unrelated_gap',
            'embedding_time_ms_per_chunk', 'determinism_largest_abs_difference')),
        'component': _metric_delta(baseline['component']['baseline'], candidate['component']['baseline'],
                                   ('recall_at_3', 'recall_at_5', 'mrr', 'ndcg_at_5')),
        'end_to_end': _metric_delta(baseline['end_to_end'], candidate['end_to_end'], (
            'faithfulness', 'abstention_correctness', 'citation_validity', 'latency_ms_p50', 'latency_ms_p95')),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--golden', type=Path, default=Path('eval/golden.jsonl'))
    parser.add_argument('--candidates', type=int, nargs='+', default=[4, 1])
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if any(k < 1 or k == 5 for k in args.candidates):
        parser.error('candidate top-k must be positive and differ from baseline 5')
    args.out.mkdir(parents=True, exist_ok=True)
    golden_hash = hashlib.sha256(args.golden.read_bytes()).hexdigest()
    gate_config = json.loads(Path('eval/gate.json').read_text())
    suites = {}
    for k in [5, *args.candidates]:
        label = 'baseline' if k == 5 else f'topk{k}'
        path = args.out / f'{label}.json'
        if args.resume and path.exists():
            suite = json.loads(path.read_text())
            config = suite['configuration']
            if (suite['golden_sha256'] != golden_hash or config['top_k'] != k
                    or config['collection'] != os.environ.get('CHROMA_COLLECTION', 'rahbar')
                    or config['generator'] != os.environ.get('LLM_MODEL', 'llama3.2:3b')):
                raise RuntimeError(f'Refusing incompatible saved suite: {path}')
        else:
            os.environ['TRACE_DIR'] = str(Path('traces') / args.out.name / label)
            suite = run_suite(Path('corpus'), args.golden, 2026, k, args.out / label)
            write(path, suite)
        suites[k] = suite
        print(f'completed {label}: {path}', flush=True)
    decisions = []
    for k in args.candidates:
        gates = []
        for run in ('run_1', 'run_2'):
            baseline, candidate = variant(suites[5], run), variant(suites[k], run)
            experiment = {
                'experiment': 'retrieval_top_k', 'seed': 2026,
                'golden_sha256': golden_hash, 'baseline': baseline, 'candidate': candidate,
                'comparison': compare(baseline, candidate),
                'rollout_handoff': {'top_k': k, 'source_collection': candidate['configuration']['collection'],
                                    'generator': candidate['configuration']['generator'],
                                    'embedding_model': candidate['configuration']['embed_model'],
                                    'embedding_version': candidate['configuration']['embedding_version'],
                                    'deployment_status': 'not_deployed; Kubernetes F3 required'},
            }
            write(args.out / f'change-topk{k}-{run}.json', experiment)
            gate = evaluate(experiment, gate_config)
            write(args.out / f'gate-topk{k}-{run}.json', gate)
            gates.append(gate)
            print(f'top_k={k} {run} gate={gate["status"]} {gate["failures"]}', flush=True)
        decisions.append({'top_k': k, 'status': 'PASS' if all(g['status'] == 'PASS' for g in gates) else 'FAIL'})
    write(args.out / 'release-decision.json', {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'candidates': decisions,
        'policy': 'Both independent repeated runs must pass unchanged thresholds',
        'deployment_status': 'not_deployed', 'gate_config': gate_config,
        'golden_sha256': golden_hash,
    })
    write(args.out / 'baseline-freeze.json', {
        'source': str(args.out / 'baseline.json'), 'configuration': suites[5]['configuration'],
        'golden_sha256': golden_hash, 'baseline_sha256': hashlib.sha256((args.out / 'baseline.json').read_bytes()).hexdigest(),
        'status': 'measured; release eligibility is determined separately by gate results',
    })
    return 0 if {'PASS', 'FAIL'} <= {d['status'] for d in decisions} else 1


if __name__ == '__main__':
    raise SystemExit(main())
