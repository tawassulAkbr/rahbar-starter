"""Liveness and readiness (section 4.3). They answer different questions."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, Response

router = APIRouter()
log = logging.getLogger("rahbar.health")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Is the process alive? Must never touch Chroma, Redis or the LLM."""
    return {"status": "alive"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, Any]:
    settings = request.app.state.settings
    checks: dict[str, Any] = {}
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        heartbeat = getattr(client, "heartbeat", None)
        if not callable(heartbeat):
            raise RuntimeError("Chroma client does not expose heartbeat")
        heartbeat()
        collection = client.get_collection(name=settings.collection)
        metadata = collection.metadata or {}
        count = int(collection.count())
        checks["chroma"] = {
            "heartbeat": "ok",
            "count": count,
            "embed_model": metadata.get("embed_model"),
            "dimension": metadata.get("dimension"),
        }
        if count == 0:
            checks["chroma"]["error"] = "collection is empty"
        if metadata.get("embed_model") != settings.embed_model:
            coll_model = metadata.get("embed_model")
            api_model = settings.embed_model
            message = f"Embedding model mismatch! Collection built with {coll_model}, but API configured with {api_model}"
            log.error(message, extra={"collection_embed_model": coll_model, "api_embed_model": api_model})
            checks["chroma"]["error"] = message
        if int(metadata.get("dimension", -1)) != settings.embed_dimension:
            checks["chroma"]["error"] = "embedding dimension does not match EMBED_DIMENSION"
    except Exception as exc:
        checks["chroma"] = {"error": str(exc)}

    if settings.redis_url:
        try:
            import redis
            redis.Redis.from_url(settings.redis_url, decode_responses=True).ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = {"error": str(exc)}
    else:
        checks["redis"] = "skipped: REDIS_URL is not configured"

    failures = [name for name, value in checks.items() if isinstance(value, dict) and "error" in value]
    if failures:
        response.status_code = 503
        return {"status": "not_ready", "checks": checks, "failed": failures}
    return {"status": "ready", "checks": checks}
