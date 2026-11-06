"""Stage 4: Embed. One vector per chunk, from the pinned model only."""

from __future__ import annotations

import time
import math

from .config import IndexerSettings


class EmbeddingError(RuntimeError):
    """The configured embedding service returned an unusable result."""


def embed(texts: list[str], settings: IndexerSettings) -> list[list[float]]:
    """Embed with settings.embed_model and nothing else.

    With Ollama: POST {ollama_url}/api/embed with {"model": ..., "input": [texts]}
    returns {"embeddings": [[...], ...]}. Batch the calls; one request per chunk is slow.
    """
    if not texts:
        return []
    if not settings.embed_model:
        raise EmbeddingError("EMBED_MODEL must be configured")
    try:
        import httpx
    except ImportError as exc:
        raise EmbeddingError("embedding requires the httpx dependency") from exc
    vectors: list[list[float]] = []
    url = settings.ollama_url.rstrip("/") + "/api/embed"
    if settings.embed_batch_size <= 0:
        raise EmbeddingError("EMBED_BATCH_SIZE must be greater than zero")
    if settings.embed_retries < 0:
        raise EmbeddingError("EMBED_RETRIES cannot be negative")
    with httpx.Client(timeout=settings.embed_timeout) as client:
        for start in range(0, len(texts), settings.embed_batch_size):
            batch = texts[start:start + settings.embed_batch_size]
            last_error: Exception | None = None
            for attempt in range(settings.embed_retries + 1):
                try:
                    response = client.post(
                        url, json={"model": settings.embed_model, "input": batch}
                    )
                    response.raise_for_status()
                    payload = response.json()
                    batch_vectors = payload.get("embeddings")
                    if not isinstance(batch_vectors, list) or len(batch_vectors) != len(batch):
                        raise EmbeddingError("Ollama returned a different number of embeddings")
                    for vector in batch_vectors:
                        if (not isinstance(vector, list) or not vector
                                or not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                                           and math.isfinite(value) for value in vector)):
                            raise EmbeddingError("Ollama returned an invalid embedding vector")
                        if len(vector) != settings.expected_dimension:
                            raise EmbeddingError(
                                f"embedding dimension {len(vector)} does not match configured "
                                f"EMBED_DIMENSION={settings.expected_dimension}"
                            )
                    vectors.extend([[float(value) for value in vector] for vector in batch_vectors])
                    break
                except (httpx.HTTPError, ValueError, EmbeddingError) as exc:
                    last_error = exc
                    if isinstance(exc, EmbeddingError) and "dimension" in str(exc):
                        raise
                    if attempt < settings.embed_retries:
                        time.sleep(min(8.0, 0.5 * (2 ** attempt)))
            else:
                raise EmbeddingError(
                    f"embedding service failed after {settings.embed_retries + 1} attempts: "
                    f"{last_error}"
                ) from last_error
    return vectors
