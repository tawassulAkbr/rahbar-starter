"""Stage 5: Store. The only code in the whole system that writes to Chroma."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .config import IndexerSettings
from .models import Chunk

logger = logging.getLogger(__name__)


def get_client(settings: IndexerSettings) -> Any:
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                               settings=ChromaSettings(anonymized_telemetry=False))


def store(chunks: list[Chunk], vectors: list[list[float]], settings: IndexerSettings) -> int:
    """Write every chunk with its vector and metadata, and record the embedding model
    and vector dimension in the collection metadata (section 4.4). Return the count."""
    if not chunks:
        raise ValueError("cannot store an empty index: no chunks were produced")
    if len(chunks) != len(vectors):
        raise ValueError("each chunk must have exactly one embedding")
    dimension = len(vectors[0]) if vectors else settings.expected_dimension
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("embedding vectors have inconsistent dimensions")
    if dimension != settings.expected_dimension:
        raise ValueError(
            f"embedding dimension {dimension} does not match configured "
            f"{settings.expected_dimension}"
        )
    client = get_client(settings)
    metadata = {"hnsw:space": "cosine", "embed_model": settings.embed_model,
                "dimension": dimension, "created_at": datetime.now(timezone.utc).isoformat()}
    try:
        collection = client.get_collection(name=settings.collection)
    except Exception:
        try:
            collection = client.create_collection(name=settings.collection, metadata=metadata)
        except Exception:
            try:
                collection = client.get_collection(name=settings.collection)
            except Exception as exc:
                raise RuntimeError(
                    f"could not access Chroma collection {settings.collection!r}: {exc}"
                ) from exc
    existing = collection.metadata or {}
    model = existing.get("embed_model")
    old_dimension = existing.get("dimension")
    try:
        compatible_dimension = int(str(old_dimension))
    except (TypeError, ValueError):
        compatible_dimension = -1
    if model != settings.embed_model or compatible_dimension != dimension:
        raise RuntimeError(
            f"collection {settings.collection!r} is pinned to embed_model={model!r}, "
            f"dimension={old_dimension!r}; configured values are {settings.embed_model!r}, "
            f"{dimension}. Delete/recreate the collection and re-index safely before "
            "changing embeddings."
        )
    try:
        collection.upsert(ids=[chunk.id for chunk in chunks],
                          documents=[chunk.text for chunk in chunks],
                          embeddings=vectors,
                          metadatas=[chunk.metadata() for chunk in chunks])
    except Exception as exc:
        raise RuntimeError(f"failed to write collection {settings.collection!r}: {exc}") from exc
    stored_count = int(collection.count())
    if stored_count < len(set(chunk.id for chunk in chunks)):
        raise RuntimeError(
            f"Chroma reported {stored_count} records after upsert; expected at least "
            f"{len(set(chunk.id for chunk in chunks))}"
        )
    _invalidate_cache(settings)
    return stored_count


def _invalidate_cache(settings: IndexerSettings) -> None:
    if not settings.redis_url:
        logger.warning("Redis invalidation skipped: REDIS_URL is not configured")
        return
    try:
        import redis
        redis.Redis.from_url(settings.redis_url, decode_responses=True).publish(
            settings.redis_channel, "index-updated")
        logger.info("Redis cache invalidation published channel=%s", settings.redis_channel)
    except ImportError:
        logger.warning("Redis invalidation unavailable: install the redis package")
    except Exception as exc:
        logger.warning("Redis cache invalidation failed: %s", exc)
