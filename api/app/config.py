"""Runtime configuration, read once from environment variables.

On the cluster these variables come from your ConfigMap and Secret (section 4.1).
Nothing here is baked into the image, so one image runs in every environment.
Add your own keys (relevance floor, cache settings, ...) the same way.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    # Which implementations to load. "stub" needs no cluster, no model, no network.
    retriever: str = "stub"          # RETRIEVER: stub | chroma
    llm_provider: str = "stub"       # LLM_PROVIDER: stub | ollama-host | ollama-incluster | hosted

    # The embedding pin (section 4.4). The indexer reads the same ConfigMap key.
    embed_model: str = "nomic-embed-text"
    embed_dimension: int = 768
    embed_timeout: float = 30.0

    # Vector store
    chroma_host: str = "chroma"
    chroma_port: int = 8000
    collection: str = "rahbar"
    redis_url: str = ""
    cache_threshold: float = 0.92
    cache_ttl: int = 3600
    redis_generation_key: str = "rahbar:index_generation"

    # Retrieval and generation
    top_k: int = 5
    relevance_floor: float = 0.6
    seed: int = 2026
    max_output_tokens: int = 384
    ollama_keep_alive: str = '5m'
    temperature: float = 0.2
    llm_model: str = "llama3.2:3b"
    ollama_url: str = "http://host.minikube.internal:11434"
    hosted_base_url: str = ""        # e.g. an OpenAI-compatible endpoint
    llm_api_key: str = field(default="", repr=False)   # from the Secret; never log it
    corpus_dir: str = ""                  # optional local corpus for offline development
    trace_dir: str = "traces"
    embed_model_version: str = "unknown"

    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings(
        retriever=os.environ.get("RETRIEVER", "stub"),
        llm_provider=os.environ.get("LLM_PROVIDER", "stub"),
        embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        embed_dimension=_int("EMBED_DIMENSION", 768),
        embed_timeout=_float("EMBED_TIMEOUT", 30.0),
        chroma_host=os.environ.get("CHROMA_HOST", "chroma"),
        chroma_port=_int("CHROMA_PORT", 8000),
        collection=os.environ.get("CHROMA_COLLECTION", "rahbar"),
        redis_url=os.environ.get("REDIS_URL", ""),
        cache_threshold=_float("CACHE_THRESHOLD", 0.92),
        cache_ttl=_int("CACHE_TTL", 3600),
        redis_generation_key=os.environ.get("REDIS_GENERATION_KEY", "rahbar:index_generation"),
        top_k=_int("TOP_K", 5),
        relevance_floor=_float("RELEVANCE_FLOOR", 0.6),
        seed=_int("RANDOM_SEED", 2026),
        max_output_tokens=_int('MAX_OUTPUT_TOKENS', 384),
        ollama_keep_alive=os.environ.get('OLLAMA_KEEP_ALIVE', '5m'),
        temperature=_float("TEMPERATURE", 0.2),
        llm_model=os.environ.get("LLM_MODEL", "llama3.2:3b"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"),
        hosted_base_url=os.environ.get("HOSTED_BASE_URL", ""),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        corpus_dir=os.environ.get("CORPUS_DIR", ""),
        trace_dir=os.environ.get("TRACE_DIR", "traces"),
        embed_model_version=os.environ.get("EMBED_MODEL_VERSION", "unknown"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )


def resolve_embedding_version(settings: Settings) -> Settings:
    """Resolve the actual model digest once when starting a real runtime."""
    if settings.retriever != 'chroma' or settings.embed_model_version != 'unknown':
        return settings
    from dataclasses import replace
    import httpx
    response = httpx.get(settings.ollama_url.rstrip('/') + '/api/tags', timeout=30)
    response.raise_for_status()
    name = settings.embed_model if ':' in settings.embed_model else settings.embed_model + ':latest'
    digest = next((m['digest'] for m in response.json()['models'] if m['name'] == name), None)
    if not digest:
        raise RuntimeError(f'Cannot resolve embedding version for {name}')
    return replace(settings, embed_model_version=digest)
