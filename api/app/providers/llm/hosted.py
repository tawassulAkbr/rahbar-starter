"""Hosted free-tier provider (Groq, Google AI Studio, OpenRouter). Yours to build.

The key arrives as LLM_API_KEY from a Kubernetes Secret created on the command
line. It never appears in a file you commit, and never in a log line.
"""

from __future__ import annotations

import json

import httpx

from ...config import Settings
from ...schemas import Answer, Passage
from .base import ProviderError


class HostedProvider:
    name = "hosted"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings   # hosted_base_url, llm_model, llm_api_key, temperature

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        if not self.settings.llm_api_key:
            raise ProviderError("LLM_API_KEY is required for the hosted provider")
        if not self.settings.hosted_base_url:
            raise ProviderError("HOSTED_BASE_URL is required for the hosted provider")
        from ...services.answer import build_grounded_prompt

        last_error: Exception | None = None
        for _attempt in range(2):
            correction = str(last_error) if last_error else ""
            try:
                response = httpx.post(
                    self.settings.hosted_base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                    json={
                        "model": self.settings.llm_model,
                        "temperature": self.settings.temperature,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "user", "content": build_grounded_prompt(
                            question, passages, correction)}],
                    },
                    timeout=self.settings.embed_timeout,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return Answer.model_validate(json.loads(content))
            except Exception as exc:
                last_error = exc
        raise ProviderError(f"hosted provider returned invalid structured output: {last_error}") from last_error
