"""Stage 5: Store. The only code in the whole system that writes to Chroma."""

from __future__ import annotations

import logging
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import IndexerSettings
from .models import Chunk
from .verify import _version_key, logical_document_id

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
    collection = _get_or_create_collection(client, settings, dimension)
    _validate_pin(collection, settings, dimension)
    try:
        collection.upsert(ids=[chunk.id for chunk in chunks],
                          documents=[chunk.text for chunk in chunks],
                          embeddings=vectors,
                          metadatas=[chunk.metadata() for chunk in chunks])
    except Exception as exc:
        raise RuntimeError(f"failed to write Chroma collection {settings.collection!r}: {exc}") from exc
    stored_count = int(collection.count())
    if stored_count < len(set(chunk.id for chunk in chunks)):
        raise RuntimeError(
            f"Chroma reported {stored_count} records after upsert; expected at least "
            f"{len(set(chunk.id for chunk in chunks))}"
        )
    _invalidate_cache(settings)
    return stored_count


def _get_or_create_collection(client: Any, settings: IndexerSettings, dimension: int) -> Any:
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
    return collection


def _validate_pin(collection: Any, settings: IndexerSettings, dimension: int) -> None:
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


def load_state(path: str) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {"version": 1, "documents": {}}
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"could not read index state {state_path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("documents", {}), dict):
        raise RuntimeError(f"index state {state_path} has an invalid shape")
    return value


def _save_state(path: str, state: dict[str, Any]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(state_path)


def _collection_ids(collection: Any, source: str) -> list[str]:
    """Get all ids owned by a source; old Chroma versions may omit include."""
    try:
        result = collection.get(where={"source": source})
    except Exception:
        return []
    ids = result.get("ids", []) if isinstance(result, dict) else []
    return [value for value in ids if isinstance(value, str)]


def _archive_file(source_path: str, settings: IndexerSettings) -> str | None:
    path = Path(source_path)
    if not path.exists():
        return None
    destination_dir = Path(settings.archive_dir) / logical_document_id(path.name)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / path.name
    if destination.exists():
        destination = destination_dir / f"{path.stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{path.suffix}"
    shutil.move(str(path), str(destination))
    return str(destination)


def store_incremental(
    chunks: list[Chunk],
    vectors: list[list[float]],
    settings: IndexerSettings,
    current_documents: list[dict[str, object]],
) -> int:
    """Replace only changed document chunks and remove deleted document chunks."""
    if len(chunks) != len(vectors):
        raise ValueError("each changed chunk must have exactly one embedding")
    state = load_state(settings.state_file)
    previous = state.setdefault("documents", {})
    current = {str(item["source"]): item for item in current_documents}
    dimension = len(vectors[0]) if vectors else settings.expected_dimension
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("embedding vectors have inconsistent dimensions")
    if dimension != settings.expected_dimension:
        raise ValueError(f"embedding dimension {dimension} does not match configured {settings.expected_dimension}")
    client = get_client(settings)
    collection = _get_or_create_collection(client, settings, dimension)
    _validate_pin(collection, settings, dimension)

    changed_sources = {
        source for source, item in current.items()
        if previous.get(source, {}).get("sha256") != item.get("sha256")
    }
    deleted_sources = set(previous) - set(current)
    superseded_sources: set[str] = set()
    orphan_chunks_removed = 0
    for source in sorted(changed_sources | deleted_sources):
        old = previous.get(source, {})
        ids = [value for value in old.get("chunk_ids", []) if isinstance(value, str)]
        if not ids:
            ids = _collection_ids(collection, source)
        if ids:
            collection.delete(ids=ids)
        if source in deleted_sources:
            logger.info("removed deleted document source=%s orphan_chunks=%d", source, len(ids))
            orphan_chunks_removed += len(ids)

    # A newly discovered version supersedes older logical siblings. Remove
    # their chunks from retrieval and archive their source bytes for restore.
    for source, item in current.items():
        for old_source, old in previous.items():
            if old_source in current or logical_document_id(old_source) != logical_document_id(source):
                continue
            if _version_key(str(old.get("doc_version", "unknown"))) >= _version_key(str(item.get("doc_version", "unknown"))):
                continue
            ids = [value for value in old.get("chunk_ids", []) if isinstance(value, str)] or _collection_ids(collection, old_source)
            if ids:
                collection.delete(ids=ids)
            archived = _archive_file(str(old.get("path", "")), settings) if old.get("path") else None
            if archived:
                logger.info("archived superseded document source=%s path=%s", old_source, archived)
            superseded_sources.add(old_source)

    by_source: dict[str, list[tuple[Chunk, list[float]]]] = {}
    for chunk, vector in zip(chunks, vectors):
        by_source.setdefault(chunk.source, []).append((chunk, vector))
    for source in sorted(changed_sources):
        pairs = by_source.get(source, [])
        source_chunks = [pair[0] for pair in pairs]
        source_vectors = [pair[1] for pair in pairs]
        if source_chunks:
            collection.upsert(ids=[item.id for item in source_chunks],
                              documents=[item.text for item in source_chunks],
                              embeddings=source_vectors,
                              metadatas=[item.metadata() for item in source_chunks])
        current[source]["chunk_ids"] = [item.id for item in source_chunks]
    next_documents = {source: item for source, item in current.items()}
    for source in superseded_sources:
        next_documents.pop(source, None)
    for source, item in next_documents.items():
        if source not in changed_sources:
            item["chunk_ids"] = previous.get(source, {}).get("chunk_ids", [])
    state["documents"] = next_documents
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["last_run"] = {
        "embedded_chunks": len(chunks),
        "changed_documents": len(changed_sources),
        "deleted_documents": len(deleted_sources),
        "orphan_chunks_removed": orphan_chunks_removed,
    }
    _save_state(settings.state_file, state)
    _invalidate_cache(settings)
    return int(collection.count())


def restore_document(source: str, settings: IndexerSettings) -> str:
    """Restore an archived source file into the configured corpus directory."""
    archive_root = Path(settings.archive_dir) / logical_document_id(source)
    original = Path(source)
    matches = sorted(archive_root.glob(original.name))
    if not matches:
        matches = sorted(archive_root.glob(f"{original.stem}-*{original.suffix}"))
    if not matches:
        raise FileNotFoundError(f"no archived copy found for {source}")
    corpus_root = Path(settings.corpus_dir)
    corpus_root.mkdir(parents=True, exist_ok=True)
    destination = corpus_root / matches[-1].name
    shutil.move(str(matches[-1]), str(destination))
    logger.info("restored document source=%s path=%s", source, destination)
    return str(destination)


def _invalidate_cache(settings: IndexerSettings) -> None:
    if not settings.redis_url:
        logger.warning("Redis invalidation skipped: REDIS_URL is not configured")
        return
    try:
        import redis
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        # A monotonically increasing generation makes invalidation reliable even
        # when the API was temporarily disconnected from the pub/sub channel.
        generation = client.incr(settings.redis_generation_key)
        client.publish(settings.redis_channel, f"index-updated:{generation}")
        logger.info("Redis cache invalidation published channel=%s", settings.redis_channel)
    except ImportError:
        logger.warning("Redis invalidation unavailable: install the redis package")
    except Exception as exc:
        logger.warning("Redis cache invalidation failed: %s", exc)
