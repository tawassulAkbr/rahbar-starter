import httpx
import pytest

from app.config import Settings
from app.providers.llm.base import ProviderError
from app.providers.llm.ollama import OllamaProvider


def test_generation_timeout_is_separate_and_not_retried(monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(kwargs['timeout'])
        raise httpx.ReadTimeout('slow generation')

    monkeypatch.setattr(httpx, 'post', timeout)
    provider = OllamaProvider(Settings(embed_timeout=300, generation_timeout=60))
    with pytest.raises(ProviderError, match='generation timed out'):
        provider.generate('What is the policy?', [])
    assert calls == [60]
