"""Ollama provider: ollama-host or ollama-incluster (section 3.5). Yours to build."""

from __future__ import annotations

import json

import httpx

from ...config import Settings
from ...schemas import Answer, Passage
from .base import ProviderError


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings   # ollama_url, llm_model, temperature

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        from ...services.answer import build_grounded_prompt

        last_error: Exception | None = None
        # One retry gives the model a chance to repair malformed JSON without
        # allowing an unbounded request loop.
        for retry in range(2):
            correction = str(last_error) if retry and last_error else ""
            try:
                from ...tracing import record_generation
                actual_prompt = build_grounded_prompt(question, passages, correction)
                record_generation(actual_prompt, self.settings.llm_model,
                                  {"temperature": self.settings.temperature, "seed": self.settings.seed, 'num_predict':self.settings.max_output_tokens})
                response = httpx.post(
                    self.settings.ollama_url.rstrip("/") + "/api/chat",
                    json={
                        "model": self.settings.llm_model,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": self.settings.temperature, "seed": self.settings.seed, 'num_predict':self.settings.max_output_tokens},
                        'keep_alive': self.settings.ollama_keep_alive,
                        "messages": [{"role": "user", "content": actual_prompt}],
                    },
                    timeout=self.settings.embed_timeout,
                )
                response.raise_for_status()
                content = response.json().get("message", {}).get("content")
                return Answer.model_validate(json.loads(content))
            except Exception as exc:
                last_error = exc
        raise ProviderError(f"Ollama returned invalid structured output: {last_error}") from last_error
