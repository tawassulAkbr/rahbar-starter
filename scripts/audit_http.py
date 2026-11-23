"""Exercise the running Docker API and capture cache/metrics evidence."""
import json
import os
from pathlib import Path
import httpx

url = os.environ.get('AUDIT_API_URL', 'http://rahbar-api-phase4:8000')
with httpx.Client(timeout=600) as client:
    health = client.get(url + '/healthz')
    ready = client.get(url + '/readyz')
    health.raise_for_status()
    ready.raise_for_status()
    question = 'For a passed course repeated for grade improvement, which grade is used in CGPA?'
    responses = []
    for _ in range(2):
        response = client.post(url + '/api/ask', json={'question': question})
        response.raise_for_status()
        responses.append({'cache': response.headers.get('X-Cache'), 'body': response.json()})
    metrics = client.get(url + '/metrics')
    metrics.raise_for_status()
    assert 'trace_top1_retrieval_similarity' in metrics.text
    assert responses[0]['body']['trace_id'] != responses[1]['body']['trace_id']
    assert responses[1]['cache'] == 'HIT', responses
    Path('eval/results/http-audit.json').write_text(json.dumps({'health':health.json(),'ready':ready.json(),
                                                               'responses':responses},indent=2))
    Path('eval/results/http-metrics.txt').write_text(metrics.text)
    print('HTTP health, readiness, cache hit, trace IDs, and metrics: PASS')
