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
    except Exception as exc:
        raise RuntimeError(f"cannot verify chunks for {source}") from exc
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
        or previous.get(source, {}).get('doc_version') != item.get('doc_version')
        or previous.get(source, {}).get('superseded', False) != item.get('superseded', False)
    }
    deleted_sources = set(previous) - set(current)
    archives = state.setdefault("archives", {})
    superseded_sources = {
        old_source for old_source in deleted_sources
        if any(logical_document_id(old_source) == logical_document_id(source)
               and _version_key(str(previous[old_source].get("doc_version", "")))
                   < _version_key(str(item.get("doc_version", "")))
               for source, item in current.items())
    }
    orphan_chunks_removed = 0
    orphan_counts = {}
    for source in sorted(changed_sources | deleted_sources):
        old = previous.get(source, {})
        ids = _collection_ids(collection, source)
        if source in superseded_sources:
            if ids:
                collection.update(ids=ids, metadatas=[{"superseded": True}] * len(ids))
            archived = old.get("snapshot")
            if not archived or not Path(str(archived)).exists():
                original = Path(str(old.get("path", "")))
                if not original.is_file():
                    original = Path(settings.quarantine_dir) / source
                archived = _archive_file(str(original), settings) if original.is_file() else None
            if not archived:
                raise RuntimeError(f"Cannot archive superseded source {source}")
            archives[source] = {**old, "path": archived, "original_path": old.get('path'), "chunk_ids": ids, "superseded": True}
        else:
            if ids:
                collection.delete(ids=ids)
            if source in deleted_sources:
                orphan_chunks_removed += len(ids)
                orphan_counts[source] = len(_collection_ids(collection, source))

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
            if previous.get(source, {}).get('restored'):
                item['restored'] = True
    for source, item in next_documents.items():
        path = Path(str(item.get("path", "")))
        if path.is_file():
            snapshot = Path(settings.archive_dir) / logical_document_id(source) / str(item["sha256"]) / source
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            if not snapshot.exists():
                shutil.copy2(path, snapshot)
            item["snapshot"] = str(snapshot)
    state["documents"] = next_documents
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["last_run"] = {
        "embedded_chunks": len(chunks),
        "changed_documents": len(changed_sources),
        "deleted_documents": len(deleted_sources),
        "orphan_chunks_removed": orphan_chunks_removed,
        "orphan_counts_by_document": orphan_counts,
        "embedded_chunks_by_document": {source: len(pairs) for source, pairs in by_source.items()},
        "superseded_documents": sorted(superseded_sources),
    }
    _save_state(settings.state_file, state)
    _invalidate_cache(settings)
    return int(collection.count())


def restore_document(source: str, settings: IndexerSettings) -> str:
    """Restore an archived source file into the configured corpus directory."""
    if Path(source).name != source:
        raise ValueError('restore requires a document filename, not a path')
    state = load_state(settings.state_file)
    archived = state.get("archives", {}).get(source)
    if archived:
        collection = get_client(settings).get_collection(name=settings.collection)
        for sibling, item in list(state["documents"].items()):
            if logical_document_id(sibling) != logical_document_id(source):
                continue
            ids = _collection_ids(collection, sibling)
            if ids:
                collection.update(ids=ids, metadatas=[{"superseded": True}] * len(ids))
            moved = _archive_file(str(item["path"]), settings)
            state["archives"][sibling] = {**item, "path": moved or item["snapshot"], "original_path": item['path'], "superseded": True}
            del state["documents"][sibling]
        destination = Path(str(archived.get('original_path') or Path(settings.corpus_dir) / source))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(archived["path"]), destination)
        ids = _collection_ids(collection, source)
        if not ids:
            raise RuntimeError("Archived chunks are missing; restore requires reindexing")
        collection.update(ids=ids, metadatas=[{"superseded": False}] * len(ids))
        state["documents"][source] = {**archived, "path": str(destination), "superseded": False, "restored": True}
        del state["archives"][source]
        _save_state(settings.state_file, state)
        _invalidate_cache(settings)
        return str(destination)
    archive_root = Path(settings.archive_dir) / logical_document_id(source)
    matches = sorted(archive_root.rglob(Path(source).name))
    if not matches:
        raise FileNotFoundError(f"no archived copy found for {source}")
    destination = Path(settings.corpus_dir) / source
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(matches[-1], destination)
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
