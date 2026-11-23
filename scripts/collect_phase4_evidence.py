"""Produce summaries/replay/root-cause evidence from actual evaluation traces."""
import json
from pathlib import Path
from summarize_traces import summarize
from trace import find_trace

config = json.loads(Path('eval/results/latest-audit.json').read_text())
results = Path(config['results'])
suite = json.loads((results/'offline-real.json').read_text())
rows = suite['runs']['run_1']['end_to_end']['answers']
paths = sorted(Path('traces').glob('real-*/traces.jsonl'))
traces = {}
for path in paths:
    for line in path.read_text().splitlines():
        record = json.loads(line)
        traces[record['trace_id']] = (record, path)
selected = next(row for row in rows if not row['response']['answered_from_context'])
record, path = traces[selected['trace_id']]
(results/'trace-summary.json').write_text(json.dumps(summarize(str(path)), indent=2))
(results/'trace-replay.json').write_text(json.dumps(record, indent=2))
ids = [r['chunk_id'] for r in record['retrieved']]
versions = sorted({r['doc_version'] for r in record['retrieved']})
notes = [
    f"1. Actual Part B trace `{record['trace_id']}` records an abstention for `{record['query']}`.",
    f"2. Its retrieval filters are `{json.dumps(record['filters'])}`.",
    f"3. Retrieved chunk IDs are `{json.dumps(ids)}`; document versions are `{json.dumps(versions)}`.",
    f"4. Generation path is `{record['generation_path']}`; recorded errors/actions are `{json.dumps(record.get('pipeline_events', []))}` / `{json.dumps(record['guardrail_actions'])}`.",
    "5. " + ("No evidence reached generation; inspect the recorded filters and retrieval coverage before changing the generator."
             if not record['context'] else "Context reached the answer stage, but the response abstained; the trace supports inspecting those exact chunks and provider attempts, not assuming that retrieval was empty."),
]
Path('docs/PHASE_4_ROOT_CAUSE.md').write_text('# Trace-only root cause from a real Part B run\n\n'+'\n'.join(notes)+'\n')
Path('eval/baseline-real.json').write_text(json.dumps({
    'source': str(results/'offline-real.json'), 'golden_sha256':suite['golden_sha256'],
    'configuration':suite['configuration'], 'measurements':suite['runs']['run_1']},indent=2))
print('Real baseline, trace summary, replay record and five-line root-cause note saved.')
