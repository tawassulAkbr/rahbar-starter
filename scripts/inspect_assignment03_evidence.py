"""Inspect retained cluster evidence used in the Assignment 03 report."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'eval/results/assignment03-final'
VOL = ROOT / 'eval/results/assignment03-verification/volume'
TRACE = ROOT / 'traces/assignment03-final.jsonl'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('item', choices=['batch', 'suite', 'gate', 'trace', 'rollback'])
    args = parser.parse_args()
    if args.item == 'batch':
        reports = sorted(VOL.glob('batch-b-*/verification-*.json'))
        docs = next(read(p)['documents'] for p in reversed(reports) if len(read(p)['documents']) == 12)
        for doc in docs:
            print(doc['document'], doc['verdict'].upper())
            for name, check in doc['checks'].items():
                print(' ', name, 'PASS' if check['passed'] else 'FAIL', '-', check['reason'])
        return 0
    if args.item in ('trace', 'rollback'):
        records = [json.loads(s) for s in TRACE.read_text(encoding='utf8').splitlines()]
        if args.item == 'trace':
            record = next(r for r in records if r['trace_id'] == 'f3165365119046f6a35891869cf5d8b2')
            print(json.dumps(record, ensure_ascii=False))
        else:
            for name in ['rollout-undo', 'rollout-status']:
                print(name, '(retained command output)')
                print((OLD / (name + '.txt')).read_text().strip())
            record = next(r for r in records if r['trace_id'] == read(OLD/'post-undo-answer.json')['trace_id'])
            print(json.dumps({k:record[k] for k in ['trace_id','timestamp','collection','embed_model','embed_model_version']}, indent=2))
        return 0
    answers = []
    for prefix in ['eval-results','eval-candidate-results']:
        a = read(VOL / (prefix + '-answers-run-1.json'))
        levels = read(VOL / (prefix + '-levels-run-1.json'))
        answers.append(a)
        if args.item == 'suite':
            print(a['configuration']['collection'], 'run 1 | questions:', a['questions'])
            for label, values in [('module', levels['module']), ('retrieval', levels['component']['baseline']), ('answers', a)]:
                print(label, {k:v for k,v in values.items() if k in ('paraphrase_unrelated_gap','determinism_largest_abs_difference','recall_at_3','recall_at_5','mrr','ndcg_at_5','citation_validity','faithfulness','abstention_rate','latency_ms_p50','latency_ms_p95')})
    if args.item == 'gate':
        import yaml
        policy = yaml.safe_load((ROOT/'k8s/base/configmap.yaml').read_text())['data']
        os.environ.update({k:str(v) for k,v in policy.items() if k.startswith('GATE_')})
        sys.path.insert(0, str(ROOT/'eval'))
        from run_eval import gate
        failures = gate(answers[1], answers[0])
        print('Candidate versus baseline | run 1 | repository release policy')
        print('FAIL' if failures else 'PASS', *failures, sep='\n')
        return int(bool(failures))
    return 0


if __name__ == '__main__':
    sys.exit(main())
