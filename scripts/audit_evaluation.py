"""Run the real suite and top-k experiments after isolated ingestion completes."""
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone

marker = Path('eval/results/latest-audit.json')
while not marker.exists():
    time.sleep(5)
config = json.loads(marker.read_text())
os.environ['CHROMA_COLLECTION'] = config['collection']
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
os.environ['TRACE_DIR'] = 'traces/real-' + stamp
from run_offline_suite import run_suite
from change_experiment import _run_variant, _metric_delta
from gate import evaluate
golden = Path('eval/golden.jsonl')
results = Path(config['results'])
suite = run_suite(Path(config['work'])/'corpus', golden)
(results/'offline-real.json').write_text(json.dumps(suite, indent=2))
baseline = {**suite['runs']['run_1'], 'configuration':{
    'top_k':5, 'embed_model':os.environ.get('EMBED_MODEL', 'nomic-embed-text'),
    'collection':config['collection'], 'change':'retrieval_top_k'}}
for k in (4, 1):
    candidate = _run_variant(Path(config['work'])/'corpus', golden, 2026, k)
    experiment = {'experiment':'real-top-k', 'baseline':baseline, 'candidate':candidate,
                  'comparison': {
                      'module': _metric_delta(baseline['module'], candidate['module'],
                                              ('mean_paraphrase_cosine','mean_unrelated_cosine','paraphrase_unrelated_gap')),
                      'component': _metric_delta(baseline['component']['baseline'], candidate['component']['baseline'],
                                                 ('recall_at_3','recall_at_5','mrr','ndcg_at_5')),
                      'end_to_end':_metric_delta(baseline['end_to_end'],candidate['end_to_end'],
                                                 ('faithfulness','abstention_correctness','citation_validity','latency_ms_p50','latency_ms_p95'))}}
    (results/f'change-real-topk{k}.json').write_text(json.dumps(experiment, indent=2))
    gate = evaluate(experiment, json.loads(Path('eval/gate.json').read_text()))
    (results/f'gate-real-topk{k}.json').write_text(json.dumps(gate, indent=2))
    print(f'candidate top-k={k}: {gate["status"]}', flush=True)
(results/'evaluation-complete.json').write_text(json.dumps({'traces':os.environ['TRACE_DIR'], 'completed': True},indent=2))
