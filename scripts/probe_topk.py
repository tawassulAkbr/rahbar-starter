"""Exploratory retrieval-only diagnostic; never authorizes release."""
import json
from pathlib import Path

from app.retrieval.chroma import ChromaRetriever
from app.services.answer import _exact_policy_answer
from app.tracing import detect_guardrail_actions
from runtime import settings_for, retrieval_scores
from run_eval import load_golden


golden = load_golden(Path('eval/golden.jsonl'))
results = []
for k in (4, 8, 10):
    retriever = ChromaRetriever(settings_for(k, 2026))
    exact_ids = []
    for row in golden:
        passages = retriever.retrieve(row['question'], k)
        blocked = {a['chunk_id'] for a in detect_guardrail_actions(passages)}
        passages = [p for p in passages if p.chunk_id not in blocked]
        if passages and _exact_policy_answer(row['question'], passages) is not None:
            exact_ids.append(row['id'])
    measured = {'top_k': k, 'extractive_path_ids': exact_ids,
                'retrieval': retrieval_scores(golden, retriever, k),
                'purpose': 'exploratory retrieval only; no end-to-end or release claim'}
    results.append(measured)
    print(json.dumps(measured), flush=True)
Path('eval/results/p03-20261123/topk-probe.json').write_text(json.dumps(results, indent=2))
