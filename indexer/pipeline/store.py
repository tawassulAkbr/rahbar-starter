"""Stage 5: Store. The only code in the whole system that writes to Chroma."""

from __future__ import annotations

from typing import Any

from .config import IndexerSettings
from .models import Chunk


def get_client(settings: IndexerSettings) -> Any:
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                               settings=ChromaSettings(anonymized_telemetry=False))


def store(chunks: list[Chunk], vectors: list[list[float]], settings: IndexerSettings) -> int:
    """Write every chunk with its vector and metadata, and record the embedding model
    and vector dimension in the collection metadata (section 4.4). Return the count."""
    if not chunks:
        return 0

    client = get_client(settings)
    dim = len(vectors[0]) if vectors and len(vectors) > 0 else 768

    # Store embedding model and dimension in collection metadata for the API pin guardrail check
    collection_metadata = {
        "embed_model": settings.embed_model,
        "dimension": dim,
        "chunk_count": len(chunks),
    }

    # Atomic or recreated collection for clean re-indexing without mixing versions
    collection = client.get_or_create_collection(
        name=settings.collection,
        metadata=collection_metadata
    )

    # Batch inserts into Chroma
    batch_size = 100
    total_stored = 0

    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i : i + batch_size]
        batch_vectors = vectors[i : i + batch_size]

        ids = [c.id for c in batch_chunks]
        documents = [c.text for c in batch_chunks]
        metadatas = [c.metadata() for c in batch_chunks]

        collection.upsert(
            ids=ids,
            embeddings=batch_vectors,
            documents=documents,
            metadatas=metadatas
        )
        total_stored += len(batch_chunks)

    return total_stored
