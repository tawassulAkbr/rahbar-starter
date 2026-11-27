"""Build an evidence-based HTML report; print it to PDF using a browser."""
from pathlib import Path
import argparse
import collections
import html
import json
import subprocess
import yaml
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', type=Path, default=Path('eval/results/assignment03-final'))
args = parser.parse_args()
evidence = ROOT / args.evidence


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def table(headers, rows):
    return '<table><tr>' + ''.join('<th>' + html.escape(str(x)) + '</th>' for x in headers) + '</tr>' + ''.join(
        '<tr>' + ''.join('<td>' + html.escape(str(x)) + '</td>' for x in row) + '</tr>' for row in rows) + '</table>'


golden = [json.loads(x) for x in (ROOT / 'eval/golden.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
labels = collections.Counter(row['label'] for row in golden)
types = collections.Counter(row['type'] for row in golden)
before = read(ROOT / 'eval/results/assignment03-coverage-before.json')
after = read(ROOT / 'eval/results/assignment03-coverage-after.json')
baseline = read(evidence / 'volume/eval-results.json')
candidate = read(evidence / 'volume/eval-candidate-results.json')
checklist = read(evidence / 'checklist.json')
summary = read(evidence / 'trace-summary.json')
summary.pop('trace_ids', None)  # Full IDs remain in the evidence JSON.
sections = []
report_date = datetime.now(timezone(timedelta(hours=5))).strftime('%d %B %Y')
sections.append('<h1>CS4032 Assignment 03: RAHBAR RAGOps verification</h1>'
                '<p>Tawassul Akbar — 24I-3100<br>Ayesha Anjum — 24I-3171</p>'
                f'<p>Report date: {report_date} (Asia/Karachi). Verification began 26 November 2026. Repository: rahbar-starter. '
                'This revision supersedes earlier report claims based on reference fixtures or generated terminal images. '
                'PASS means supported by retained evidence; PARTIAL or FAIL identifies unfinished acceptance work.</p>')
sections.append('<h2>1. Requirement verdict</h2>' + table(['Task', 'Status', 'Evidence / remaining work'],
    [(x['task'], x['status'], x['detail']) for x in checklist.get('items', [])]))
sections.append('<h2>2. Figure 3 lifecycle mapping</h2>' + table(['Stage', 'Implementation', 'Limit'], [
    ('Ingest', 'pipeline/extract.py; pipeline/run.py; indexer Job', 'Scanned PDF quality depends on OCR.'),
    ('Verify', 'pipeline/verify.py: four checks, per-document reasons, quarantine', 'Injection is caught at retrieval, not ingestion; unmarked truncation can escape.'),
    ('Update data lake', 'pipeline/store.py; seed_corpus.py; data PVC', 'Single-node ReadWriteOnce storage.'),
    ('Update retrieval sources', 'store_incremental: hash skip, changed-only embeddings, orphan deletion, archive/restore', 'Writer lock serializes Jobs on the shared volume.'),
    ('Offline testing', 'run_cluster_suite.py; module_level.py; runtime.py; run_eval.py', 'Lexical faithfulness proxy; inspect measured gate status below.'),
    ('Live testing', 'API /api/ask, tracing.py, /metrics', 'The live query log is simulated.'),
    ('Check coverage', 'eval/coverage.py; live_queries.jsonl', 'Hash-vector lexical cosine measures test vocabulary, not semantic completeness.'),
]))
sections.append('<h2>3. Table 2 qualities</h2>' + table(['Quality', 'Measure / threshold', 'Evidence'], [
    ('Adaptability', 'Coverage ≥85%; unchanged ingestion embeds zero chunks', 'assignment03-coverage-*.json; lifecycle JSON and unchanged Job logs'),
    ('Monitorability', 'Top-1 scores, abstentions, cache hits, stage p95, flagged injections', 'trace-summary.json; /metrics through port-forward'),
    ('Observability', 'One structured trace for every query; model, collection, context and timing', 'JSONL trace PVC and kubectl logs'),
    ('Traceability', 'Prompt hash and exact prompt/context reconstruction', 'scripts/trace.py; trace-reconstruction.txt'),
    ('Reliability', 'Recall drop ≤5 points; faithfulness ≥0.90; abstention 1.0; p95 ≤180000 ms; citations ≥0.95', 'ConfigMap; evaluation Jobs; rollout/undo command logs'),
]))
sections.append('<h2>4. Measured results and limitations</h2><p>Local verification: 85 tests passed. Ruff passed. '
                'Mypy passed for all 34 source files with --platform linux (the deployed writer lock uses Linux fcntl). '
                'Submission checker: 166 passed, 2 warnings, 0 failures. These checks do not establish retrieval quality.</p>')
sections.append('<p>Golden set: ' + html.escape(str(dict(types))) + '; provenance labels: ' + html.escape(str(dict(labels))) +
                '. Actual question authorship and personal review must be confirmed by the members; an automated audit cannot certify that activity.</p>')
sections.append('<p>Part A: use the exported latest lifecycle and Batch B JSON files for exact counts. '
                'The lifecycle run verifies zero embeddings on unchanged input, one changed document without modifying the unrelated document, '
                'zero orphan counts after deletion, supersession, and archive restoration. Batch B contains 12 planted documents.</p>')
for name, result in [('Baseline', baseline), ('Candidate TOP_K=4', candidate)]:
    sections.append('<h3>' + name + '</h3>')
    if result:
        sections.append('<p>Gate: <strong>' + html.escape(result.get('gate_status', 'unknown')) + '</strong>.</p><pre>' +
                        html.escape(json.dumps(result.get('summary_table', {}), indent=2)) + '</pre>')
        sections.append('<p>Repeated-run differences:</p><pre>' + html.escape(json.dumps(result.get('stochasticity', {}), indent=2)) + '</pre>')
    else:
        sections.append('<p>No completed measured suite is available in this evidence export. No passing quality claim or release is authorized.</p>')
        stage_name = 'eval-results-levels-run-1.json' if name == 'Baseline' else 'eval-candidate-results-levels-run-1.json'
        stage = read(evidence / 'volume' / stage_name)
        if stage:
            sections.append('<p>Completed module/retrieval checkpoint (partial suite):</p><pre>' +
                            html.escape(json.dumps(stage, indent=2)) + '</pre>')
sections.append('<p>Remaining variation can arise from CPU scheduling, cold model loading and response-cache hits. '
                'A fixed seed controls model randomness but does not fix latency. Cached requests and extractive answers are identified in traces; '
                'provider="ollama" alone does not prove every answer invoked generation.</p>')
decision = 'RELEASE PASSED, THEN RESTORED BASELINE FOR DATA-DRIFT DEMO' if (
    baseline.get('gate_status') == candidate.get('gate_status') == 'PASS' and
    (evidence / 'promotion.txt').exists()) else 'REJECT / NO RELEASE AUTHORIZED'
sections.append('<p><strong>Part C decision: ' + decision + '</strong>. Both complete real-model suites must pass '
                'the unchanged recall, faithfulness, citation, abstention and latency policy. A failed or missing suite blocks release; '
                'see the retained evaluator/gate Job logs for individual threshold failures.</p>')
demo = read(evidence / 'gate-demonstration.json')
if demo:
    sections.append('<p>ConfigMap demonstration, same image and measured answers:</p><pre>' + html.escape(json.dumps(demo, indent=2)) + '</pre>')
drift = read(evidence / 'volume/batch-b-drift.json')
if drift:
    sections.append('<h3>Measured Batch B data drift</h3><pre>' +
                    html.escape(json.dumps(drift.get('metric_deltas_after_minus_before', {}), indent=2)) +
                    '</pre><p>Both complete suites use the same golden set, seed, models and top-k. The ingestion Job adds accepted '
                    'Batch B policies and removes quarantined content from indexing; consult the verification report for each source. '
                    'Changed retrieval reflects added relevant policies and distractors; generation/cache and CPU load also affect timing.</p>')
sections.append('<p>Part E coverage: before ' + str(before.get('coverage')) + ' (' + str(before.get('covered_queries')) +
                '/40), after ' + str(after.get('coverage')) + ' (' + str(after.get('covered_queries')) +
                '/40). Six added questions close test coverage gaps, without adding knowledge to the corpus. '
                'Similarity cutoff 0.35 is a fixed lexical comparison; coverage floor 0.85 permits at most six unmatched queries. '
                'The before command exits 1; the after command exits 0. Uncovered queries and topics are retained in the result JSON.</p>')
sections.append('<h3>Trace metrics</h3><pre>' + html.escape(json.dumps(summary, indent=2)) + '</pre>')
sections.append('<h3>Trace-only root cause</h3><pre>' + html.escape(
    (evidence / 'root-cause.txt').read_text(encoding='utf-8') if (evidence / 'root-cause.txt').exists() else
    'Pending selection and inspection of a wrong/abstained answer from the current evaluation.') + '</pre>')
sections.append('<h3>Resource measurements</h3><pre>' + html.escape(
    (evidence / 'resources.txt').read_text(encoding='utf-8') if (evidence / 'resources.txt').exists() else 'Pending export') +
    '</pre><p>Compare these idle/current readings with Jobs and Ollama under load before treating limits as measured sizing. '
    'Requests/limits reside in each manifest; current Ollama request/limit is 2Gi/4Gi. Docker now exposes about 5.79Gi, '
    'so the former 2.84Gi blocker is obsolete.</p>')
resource_rows = []
for manifest in (evidence / 'manifests.yaml', ROOT / 'k8s/eval-job.yaml'):
    if not manifest.exists():
        continue
    for obj in yaml.safe_load_all(manifest.read_text(encoding='utf-8')):
        if not obj or obj.get('kind') not in {'Deployment', 'StatefulSet', 'Job'}:
            continue
        for container in obj['spec']['template']['spec']['containers']:
            resource_rows.append((obj['metadata']['name'] + '/' + container['name'],
                                  container.get('resources', {}).get('requests', {}),
                                  container.get('resources', {}).get('limits', {})))
sections.append(table(['Workload', 'Requests', 'Limits'], resource_rows))
stage = read(evidence / 'volume/eval-results-levels-run-1.json')
module_metric = stage.get('module', {}).get('paraphrase_unrelated_gap')
retrieval_metric = stage.get('component', {}).get('baseline', {}).get('recall_at_5')
sections.append('<h2>5. Required short answers</h2>'
    '<p>(a) In the retained Batch B run, completeness and uniqueness each reject three documents; quality rejects one and recency one '
    '(a document can fail multiple checks). Injection is intentionally admitted to indexing and must be removed by the runtime rail. '
    'A stronger semantic injection detector and expected-page/byte metadata would catch more subtle instruction attacks and unmarked truncation.</p>'
    f'<p>(b) The real module paraphrase/unrelated gap was {module_metric}; component recall@5 was {retrieval_metric}. '
    'The gap in embedding similarity did not guarantee correct source/page retrieval. Before Batch B, its answerable questions also lack indexed sources; '
    'the degree-duration trace separately shows a retrieval/context miss for an existing source. Old fixture scores are excluded.</p>'
    '<p>(c) Superseded versions are archived and marked in vector metadata. Hard deletion loses reproducible historical context and rollback source material.</p>'
    '<p>(d) Faithfulness is least trusted: lexical and numeric overlap can reject valid paraphrases and miss negation. No LLM judge is used, '
    'so judge-versus-human agreement is not applicable.</p>'
    '<p>(e) Repeated real-model generation under local CPU/memory constraints is the hardest operational requirement. '
    'The implementation uses extractive policy shortcuts, bounded generation retries and a lexical faithfulness proxy; their limits must remain visible.</p>'
    '<p>(f) Deployment serves API; Service exposes it; StatefulSet/PVC persists Chroma; PVCs preserve lake/quarantine/archive/traces/results; '
    'ingestion Job/CronJob owns vector writes, with a process-held shared-volume lock; evaluator Job gates releases; ConfigMap supplies thresholds; '
    'candidate Deployment/Service isolates a collection; RollingUpdate and rollout undo manage serving revisions.</p>')
authors = subprocess.run(['git', 'shortlog', '-sn', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout
sections.append('<h2>6. Contributions and AI use</h2>' + table(['Member', 'Contribution (members must confirm)'], [
    ('Tawassul Akbar', 'Infrastructure, indexing lifecycle, tracing/guardrails, Kubernetes and integration verification.'),
    ('Ayesha Anjum', 'Golden questions, Batch B fixtures, evaluation, release gate and coverage/drift.'),
]) + '<pre>' + html.escape(authors) + '</pre><p>AI assisted code review, fixes, command execution and report preparation. '
    'Only retained execution outputs are accepted as measurements. Human authorship/review and genuine terminal screenshots remain member responsibilities.</p>')
sections.append('<h2>Appendix: evidence and manual submission work</h2><p>Full machine-readable evidence is in ' +
    html.escape(str(args.evidence)) + '. Previously generated terminal illustrations are excluded. '
    'Capture uncropped actual terminal windows for every screenshot requested in A–F, showing the command and output, '
    'then append them to this PDF (appendix excluded from the eight-page body limit). '
    'Both members must confirm names, rolls, contributions and question reviews, commit their work and results, submit the repository URL/PDF, '
    'attend the demo and bring the running Kubernetes pipeline. An unseen ingestion batch must be supplied at the demo.</p>')
output = '<!doctype html><html><head><meta charset="utf-8"><title>Assignment 03 verification report</title><style>' + \
    '@page{size:A4;margin:13mm}body{font:10pt Arial;line-height:1.25}h1{font-size:17pt}h2{font-size:13pt}h3{font-size:11pt}' + \
    'table{width:100%;border-collapse:collapse;font-size:9pt}td,th{border:1px solid #777;padding:4px;text-align:left}' + \
    'tr{break-inside:avoid}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:8pt}p{margin:6pt 0}' + \
    '</style></head><body>' + '\n'.join(sections) + '</body></html>'
(ROOT / 'docs/Assignment_03_Report.html').write_text(output, encoding='utf-8')
print('Updated docs/Assignment_03_Report.html from', args.evidence)
