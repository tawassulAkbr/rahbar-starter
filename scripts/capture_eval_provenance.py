"""Capture actual model digests, code hashes and collection identity, without secrets."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.retrieval.chroma import ChromaRetriever
from runtime import settings_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    settings = settings_for(5, 2026)
    collection = ChromaRetriever(settings).client.get_collection(settings.collection)
    data = collection.get(include=['documents', 'metadatas'])
    rows = sorted(zip(data['ids'], data['documents'], data['metadatas']), key=lambda row: row[0])
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    response = httpx.get(settings.ollama_url.rstrip('/') + '/api/tags', timeout=30)
    response.raise_for_status()
    models = response.json()['models']
    generator = settings.llm_model if ':' in settings.llm_model else settings.llm_model + ':latest'
    generator_digest = next(m['digest'] for m in models if m['name'] == generator)
    files = sorted(p for root in ('api/app', 'indexer/pipeline', 'eval') for p in Path(root).rglob('*.py')
                   if '__pycache__' not in p.parts and 'tests' not in p.parts)
    result = {
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'collection': settings.collection, 'chunk_count': len(rows), 'collection_metadata': collection.metadata,
        'collection_content_sha256': digest,
        'embedding_model': settings.embed_model, 'embedding_digest': settings.embed_model_version,
        'generator_model': generator, 'generator_digest': generator_digest,
        'golden_sha256': hashlib.sha256(Path('eval/golden.jsonl').read_bytes()).hexdigest(),
        'source_sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        'generation_parameters': {'seed': settings.seed, 'temperature': settings.temperature,
                                  'max_output_tokens': settings.max_output_tokens},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_sha256'}, indent=2))


if __name__ == '__main__':
    main()
