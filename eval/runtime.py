"""Evaluate the serving implementation; golden labels never enter inference."""
from dataclasses import replace
import json
import os
import time
import re
from pathlib import Path

from app.config import get_settings, resolve_embedding_version
from app.retrieval.chroma import ChromaRetriever
from app.providers.llm import get_provider
from app.services.answer import answer_question
from metrics import average, percentile, reciprocal_rank, ndcg, tokens
from run_eval import load_golden, citation_validity

def settings_for(top_k, seed):
    settings = replace(get_settings(), top_k=top_k, seed=seed,
                       ollama_keep_alive=os.environ.get('OLLAMA_KEEP_ALIVE', '0'))
    if settings.retriever != 'chroma' or settings.llm_provider == 'stub':
        raise RuntimeError('Real evaluation requires RETRIEVER=chroma and a real LLM_PROVIDER')
    return resolve_embedding_version(settings)

def retrieval_scores(golden, retriever, top_k, noisy=False):
    values = {key: [] for key in ('recall_at_3', 'recall_at_5', 'mrr', 'ndcg_at_5')}
    for row in golden:
        expected = {(r['source'], r.get('page')) for r in row.get('relevant', [])}
        if not expected:
            continue
        query = row['question']
        if noisy:
            words = query.split()
            words = [w[1] + w[0] + w[2:] if len(w) > 5 else w for w in words]
            query = ' '.join(words)
        passages = retriever.retrieve(query, top_k)
        actual = [(p.source, p.page) for p in passages]
        for k in (3, 5):
            values[f'recall_at_{k}'].append(len(expected & set(actual[:k])) / len(expected))
        values['mrr'].append(reciprocal_rank(expected, actual))
        values['ndcg_at_5'].append(ndcg(expected, actual, 5))
    return {k: average(v) for k, v in values.items()}

def component(golden_path, seed, top_k):
    settings = settings_for(top_k, seed)
    retriever = ChromaRetriever(settings)
    golden = load_golden(golden_path)
    baseline = retrieval_scores(golden, retriever, top_k)
    noisy = retrieval_scores(golden, retriever, top_k, True)
    return {'level': 'component_retrieval', 'retriever': 'chroma', 'top_k': top_k,
            'baseline': baseline, 'noise_test': {'method': 'transpose first two letters of words longer than five characters',
            'metrics': noisy, 'deltas': {k: noisy[k] - baseline[k] for k in baseline}}}

def end_to_end(golden_path, seed, top_k):
    settings = settings_for(top_k, seed)
    retriever, provider = ChromaRetriever(settings), get_provider(settings)
    rows, latencies, faithful, citations, abstentions = [], [], [], [], []
    for question in load_golden(golden_path):
        start = time.perf_counter()
        result = answer_question(question['question'], retriever, provider, settings)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        trace_path = Path(settings.trace_dir) / 'traces.jsonl'
        trace = next(json.loads(line) for line in trace_path.read_text().splitlines()
                     if json.loads(line).get('trace_id') == result.trace_id)
        context = ' '.join(trace['context'])
        terms = tokens(result.answer) - {'the', 'a', 'an', 'is', 'are', 'of', 'to', 'and', 'in'}
        support = len(terms & tokens(context)) / max(1, len(terms))
        numbers = set(re.findall(r'\b\d+(?:\.\d+)?%?', result.answer))
        context_numbers = set(re.findall(r'\b\d+(?:\.\d+)?%?', context))
        if result.answered_from_context:
            faithful.append(float(support >= .8 and numbers <= context_numbers))
        if question['must_abstain']:
            abstentions.append(float(not result.answered_from_context))
        validity = citation_validity(result.model_dump())
        if validity is not None:
            citations.append(validity)
        rows.append({'id': question['id'], 'trace_id': result.trace_id, 'response': result.model_dump(),
                     'latency_ms': elapsed, 'lexical_support': support})
        checkpoint = os.environ.get('EVAL_ANSWER_CHECKPOINT')
        if checkpoint:
            destination = Path(checkpoint)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps({'status': 'in_progress', 'top_k': top_k,
                                               'answers': rows}, indent=2), encoding='utf-8')
        print(f"evaluated {question['id']} trace={result.trace_id} latency_ms={elapsed:.1f}", flush=True)
    return {'level': 'end_to_end_answers', 'mode': 'serving-pipeline',
            'faithfulness': average(faithful) if faithful else 0.0,
            'faithfulness_judge': 'lexical support >= 0.8 and all numeric claims present; proxy, not semantic entailment',
            'abstention_correctness': average(abstentions), 'citation_validity': average(citations),
            'latency_ms_p50': percentile(latencies, .5), 'latency_ms_p95': percentile(latencies, .95),
            'answers': rows}
