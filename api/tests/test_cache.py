from app.config import get_settings
from app.schemas import AskResponse
from app.services.cache import SemanticCache, never_cache


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def scan_iter(self, match=None):
        return (key for key in self.data if key.startswith("rahbar:cache:"))

    def setex(self, key, ttl, value):
        self.data[key] = value


def _response(answered=True, confidence="high"):
    return AskResponse(request_id="r", answer="answer", citations=[],
                       answered_from_context=answered, confidence=confidence,
                       retrieved=[], provider="stub")


def test_semantic_cache_hit_uses_threshold(monkeypatch):
    settings = get_settings()
    vectors = {"first": [1.0, 0.0], "same": [0.99, 0.01]}
    cache = SemanticCache(settings, FakeRedis(), lambda q: vectors[q])
    cache.set("first", _response())
    hit = cache.get("same")
    assert hit is not None and hit.cached is True


def test_never_cache_rules_cover_abstention_fallback_and_follow_up():
    assert never_cache(_response(answered=False))
    assert never_cache(_response(confidence="low"))
    assert never_cache(_response(), follow_up=True)
