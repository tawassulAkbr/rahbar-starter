"""Liveness and readiness (section 4.3). They answer different questions."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Is the process alive? Must never touch Chroma, Redis or the LLM."""
    return {"status": "alive"}


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    checks: dict[str, object] = {}
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        heartbeat = getattr(client, "heartbeat", None)
        if callable(heartbeat):
            heartbeat()
        collection = client.get_collection(name=settings.collection)
        metadata = collection.metadata or {}
        checks["chroma"] = {
            "count": int(collection.count()),
            "embed_model": metadata.get("embed_model"),
            "dimension": metadata.get("dimension"),
        }
        if checks["chroma"]["count"] == 0:
            raise RuntimeError("collection is empty")
        if metadata.get("embed_model") != settings.embed_model:
            raise RuntimeError("embedding model does not match configured EMBED_MODEL")
        if int(metadata.get("dimension", -1)) != settings.embed_dimension:
            raise RuntimeError("embedding dimension does not match EMBED_DIMENSION")
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
