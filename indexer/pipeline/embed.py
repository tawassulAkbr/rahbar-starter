"""Stage 4: Embed. One vector per chunk, from the pinned model only."""

from __future__ import annotations

import httpx
from .config import IndexerSettings
from .dummy import dummy_embedding


def embed(texts: list[str], settings: IndexerSettings) -> list[list[float]]:
    """Embed with settings.embed_model and nothing else.

    With Ollama: POST {ollama_url}/api/embed with {"model": ..., "input": [texts]}
    returns {"embeddings": [[...], ...]}. Batch the calls; one request per chunk is slow.
    """
    if not texts:
        return []

    # If configured with dummy or stub embedding mode (for offline tests/CI)
    if "dummy" in settings.embed_model.lower() or "stub" in settings.embed_model.lower():
        return [dummy_embedding(text) for text in texts]

    # Live embedding via Ollama API with batching
    batch_size = 32
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            url = f"{settings.ollama_url.rstrip('/')}/api/embed"
            payload = {"model": settings.embed_model, "input": batch}
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                embeddings = data.get("embeddings") or []
                all_embeddings.extend(embeddings)
        except Exception:
            # Fallback to deterministic dummy embedding if Ollama service is unreachable
            all_embeddings.extend([dummy_embedding(t) for t in batch])

    return all_embeddings
