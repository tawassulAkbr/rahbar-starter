"""Redis-backed semantic cache with generation-based invalidation.

The cache is deliberately best-effort: Redis outages never make the answer API
unavailable. Vectors are stored with the complete response so a hit skips both
retrieval and generation.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any, Callable

from ..config import Settings
from ..schemas import AskResponse


class SemanticCache:
    def __init__(self, settings: Settings, redis_client: Any = None,
                 embedder: Callable[[str], list[float]] | None = None) -> None:
        self.settings = settings
        self._redis = redis_client
        self._embedder = embedder

    @property
    def enabled(self) -> bool:
        return self._redis is not None and self._embedder is not None

    @classmethod
    def from_settings(cls, settings: Settings) -> "SemanticCache":
        if not settings.redis_url:
            return cls(settings)
        try:
            import redis
            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            return cls(settings, client, lambda question: _embed(question, settings))
        except Exception:
            return cls(settings)

    def get(self, question: str, *, follow_up: bool = False) -> AskResponse | None:
        """Return a current-generation entry unless this is a follow-up.

        Follow-ups depend on conversation context that is not part of the cache
        key, so they must always go through retrieval and generation.
        """
        if not self.enabled or follow_up:
            return None
        try:
            embedder = self._embedder
            redis_client = self._redis
            assert embedder is not None and redis_client is not None
            vector = embedder(question)
            generation = redis_client.get(self.settings.redis_generation_key) or "0"
            best: tuple[float, AskResponse] | None = None
            for key in redis_client.scan_iter(match="rahbar:cache:*"):
                raw = redis_client.get(key)
                if not raw:
                    continue
                item = json.loads(raw)
                if str(item.get("generation", "0")) != str(generation):
                    continue
                similarity = cosine_similarity(vector, item.get("vector", []))
                if similarity >= self.settings.cache_threshold and (best is None or similarity > best[0]):
                    best = (similarity, AskResponse.model_validate(item["response"]))
            return best[1].model_copy(update={"cached": True}) if best else None
        except Exception:
            return None

    def invalidate(self) -> None:
        """Remove cache entries immediately; generation checks remain the normal path."""
        if not self.enabled:
            return
        try:
            keys = list(self._redis.scan_iter(match="rahbar:cache:*"))
            if keys:
                self._redis.delete(*keys)
        except Exception:
            return

    def set(self, question: str, response: AskResponse, *, follow_up: bool = False) -> None:
        if not self.enabled or never_cache(response, follow_up=follow_up):
            return
        try:
            embedder = self._embedder
            redis_client = self._redis
            assert embedder is not None and redis_client is not None
            vector = embedder(question)
            generation = redis_client.get(self.settings.redis_generation_key) or "0"
            digest = hashlib.sha256(question.strip().lower().encode()).hexdigest()
            payload = {"question": question, "vector": vector, "response": response.model_dump(),
                       "timestamp": time.time(), "generation": generation}
            redis_client.setex(f"rahbar:cache:{digest}", self.settings.cache_ttl, json.dumps(payload))
        except Exception:
            return


def never_cache(response: AskResponse, *, follow_up: bool = False) -> bool:
    """Abstentions, fallbacks, and conversational follow-ups are not reusable."""
    return follow_up or not response.answered_from_context or response.confidence == "low"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return -1.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else -1.0


def _embed(question: str, settings: Settings) -> list[float]:
    from ..retrieval.chroma import _query_embedding
    return _query_embedding(question, settings)
