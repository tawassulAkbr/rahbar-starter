"""Indexer configuration, from the same ConfigMap the API reads (section 4.1)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class IndexerSettings:
    embed_model: str        # EMBED_MODEL: must equal the API's value (section 4.4)
    chroma_host: str
    chroma_port: int
    collection: str
    corpus_dir: str         # where the documents and _index.json sit inside the Job's pod
    chunk_size: int
    chunk_overlap: int
    ollama_url: str
    expected_dimension: int = 768
    embed_batch_size: int = 32
    embed_retries: int = 3
    embed_timeout: float = 60.0
    redis_url: str = ""
    redis_channel: str = "rahbar:index-updated"
    redis_generation_key: str = "rahbar:index_generation"

    @property
    def chroma_collection(self) -> str:
        """Name used by the Phase 2 specification, retained alongside collection."""
        return self.collection


def get_settings() -> IndexerSettings:
    return IndexerSettings(
        embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        chroma_host=os.environ.get("CHROMA_HOST", "chroma"),
        chroma_port=int(os.environ.get("CHROMA_PORT", 8000)),
        collection=os.environ.get("CHROMA_COLLECTION", "rahbar"),
        corpus_dir=os.environ.get("CORPUS_DIR", "/corpus"),
        chunk_size=int(os.environ.get("CHUNK_SIZE", 400)),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", 50)),
        ollama_url=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"),
        expected_dimension=int(os.environ.get("EMBED_DIMENSION",
                                             os.environ.get("EMBED_DIM", 768))),
        embed_batch_size=int(os.environ.get("EMBED_BATCH_SIZE", 32)),
        embed_retries=int(os.environ.get("EMBED_RETRIES", 3)),
        embed_timeout=float(os.environ.get("EMBED_TIMEOUT", 60.0)),
        redis_url=os.environ.get("REDIS_URL", ""),
        redis_channel=os.environ.get("REDIS_INVALIDATION_CHANNEL", "rahbar:index-updated"),
        redis_generation_key=os.environ.get("REDIS_GENERATION_KEY", "rahbar:index_generation"),
    )
