"""Summarize measured evidence without substituting missing runs with fixtures."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('eval/results/p03-20261123'))
    parser.add_argument('--part', choices=['all', 'A', 'B', 'C'], default='all')
    parser.add_argument('--variant', default='baseline')
    args = parser.parse_args()
    golden = [json.loads(line) for line in Path('eval/golden.jsonl').read_text().splitlines() if line]
    batch_root = Path('eval/results/20261122T181002Z')
    verification = read(batch_root / 'verification-20261122T182951Z.json')
    batch_b = [r for r in verification['documents'] if r['document'].startswith('batch-b-')]
    assert len(batch_b) == 12, 'Batch B verification must include all 12 inputs'
    counts = Counter(check for row in batch_b for check, outcome in row['checks'].items() if not outcome['passed'])
    assert all(row['quarantined'] for row in batch_b if row['verdict'] == 'fail')
    for label in ('batch-a-unchanged', 'batch-b-unchanged'):
        assert read(batch_root / f'{label}.json')['embedded_chunks'] == 0
    result = {
        'golden': {'questions': len(golden), 'types': dict(Counter(r['type'] for r in golden)),
                   'human_labelled': sum(r['label'] == 'human' for r in golden),
                   'reviewed_synthetic_labelled': sum(r['label'] == 'synthetic' and r['reviewed'] for r in golden),
                   'authorship_status': 'Existing labels; member confirmation must be supplied by the group'},
        'batch_b': {'documents': len(batch_b), 'verdicts': dict(Counter(r['verdict'] for r in batch_b)),
                    'failures_per_check': dict(counts), 'source_report': str(batch_root / 'verification-20261122T182951Z.json')},
        'unchanged_embedded_chunks': {label: read(batch_root / f'{label}.json')['embedded_chunks']
                                     for label in ('batch-a-unchanged', 'batch-b-unchanged')},
        'suites': {},
    }
    candidates = sorted(p for p in args.results.glob('topk*.json') if p.stem[4:].isdigit())
    for path in [args.results / 'baseline.json', *candidates]:
        if not path.exists():
            continue
        suite = read(path)
        result['suites'][path.stem] = {
            'source': str(path), 'configuration': suite['configuration'],
            'summary': suite['summary_table'], 'stochasticity': suite['stochasticity']}
        answerable = {r['id'] for r in golden if r['type'] != 'unanswerable'}
        result['suites'][path.stem]['answerable_response_coverage'] = {
            run: sum(bool(row['response']['answered_from_context']) for row in measured['end_to_end']['answers']
                     if row['id'] in answerable) / len(answerable)
            for run, measured in suite['runs'].items()
        }
    decision = args.results / 'release-decision.json'
    result['release_decision'] = read(decision) if decision.exists() else {'status': 'pending measured candidates'}
    args.results.mkdir(parents=True, exist_ok=True)
    (args.results / 'evidence-summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if args.part in ('all', 'A'):
        print('A: Batch B verification (Q=quality C=completeness R=recency U=uniqueness)')
        for row in batch_b:
            checks = ' '.join(f'{key[0].upper()}={"PASS" if row["checks"][key]["passed"] else "FAIL"}'
                              for key in ('quality', 'completeness', 'recency', 'uniqueness'))
            print(f'{row["document"]}: {checks}; quarantine={row["quarantined"]}')
            for key, outcome in row['checks'].items():
                if not outcome['passed']:
                    print(f'  {key}: {outcome["reason"]}')
        print('Unchanged embedded chunks:', result['unchanged_embedded_chunks'])
    if args.part in ('all', 'B'):
        path = args.results / f'{args.variant}.json'
        print(f'B: {args.variant} three-level suite')
        if not path.exists():
            print('PENDING: complete suite result is not available')
        else:
            suite = read(path)
            print(f'{"Level / metric":48s} {"Run 1":>12s} {"Run 2":>12s} {"Delta":>12s}')
            for level, deltas in suite['stochasticity']['metric_deltas_run_2_minus_run_1'].items():
                for metric, delta in deltas.items():
                    values = []
                    for run in ('run_1', 'run_2'):
                        record = suite['runs'][run]
                        measured = (record['component']['noise_test']['metrics'] if level == 'component_noise'
                                    else record['component']['baseline'] if level == 'component'
                                    else record[level])
                        values.append(measured[metric])
                    formatted = [f'{v:.5f}' if v is not None else 'N/A' for v in [*values, delta]]
                    print(f'{level + "/" + metric:48s} {formatted[0]:>12s} {formatted[1]:>12s} {formatted[2]:>12s}')
            print('Answerable response coverage:', result['suites'][args.variant]['answerable_response_coverage'])
            print('Faithfulness is a lexical proxy; timings exclude HTTP/cache.')
    if args.part in ('all', 'C'):
        print('C: release decisions')
        print(json.dumps(result['release_decision'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
