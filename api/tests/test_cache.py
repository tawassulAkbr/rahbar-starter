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

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)


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


def test_follow_up_skips_existing_cache_entry():
    settings = get_settings()
    vectors = {"first": [1.0, 0.0]}
    cache = SemanticCache(settings, FakeRedis(), lambda q: vectors[q])
    cache.set("first", _response())

    assert cache.get("first", follow_up=True) is None


def test_generation_change_makes_old_entry_invisible():
    settings = get_settings()
    redis = FakeRedis()
    vectors = {"first": [1.0, 0.0]}
    cache = SemanticCache(settings, redis, lambda q: vectors[q])
    cache.set("first", _response())
    redis.data[settings.redis_generation_key] = "1"

    assert cache.get("first") is None


def test_abstentions_and_fallbacks_are_not_written():
    settings = get_settings()
    redis = FakeRedis()
    cache = SemanticCache(settings, redis, lambda q: [1.0, 0.0])
    cache.set("abstain", _response(answered=False))
    cache.set("fallback", _response(confidence="low"))

    assert list(redis.scan_iter(match="rahbar:cache:*")) == []
