"""Phase 4 trace writer and retrieval-rail helpers."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
generation_attempts: ContextVar[list | None] = ContextVar('generation_attempts', default=None)
retrieval_details: ContextVar[dict | None] = ContextVar('retrieval_details', default=None)


def record_generation(prompt: str, model: str, parameters: dict) -> None:
    attempts = generation_attempts.get()
    if attempts is not None:
        attempts.append({'prompt': prompt, 'prompt_hash': prompt_hash(prompt),
                         'model': model, 'parameters': parameters})


def new_trace_id() -> str:
    return uuid.uuid4().hex


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def detect_guardrail_actions(passages: list[Any]) -> list[dict[str, str]]:
    """Flag document instructions as untrusted data; never execute them."""
    patterns = re.compile(r"ignore\s+(?:all\s+)?previous|system\s+prompt|instruction\s+to\s+(?:the\s+)?assistant|reveal\s+.*prompt", re.I)
    actions = []
    for passage in passages:
        if patterns.search(passage.text):
            actions.append({
                "action": "ignore_untrusted_instruction",
                "chunk_id": passage.chunk_id,
                "document_id": passage.source,
                "reason": "prompt-injection pattern in retrieved document",
            })
    return actions


def emit_trace(record: dict[str, Any], trace_dir: str) -> None:
    """Emit one JSON line to stdout and to the configured trace volume."""
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    print(line, flush=True)
    path = Path(trace_dir)
    path.mkdir(parents=True, exist_ok=True)
    with _lock:
        with (path / "traces.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def base_record(*, trace_id: str, query: str, settings: Any, collection: str,
                retrieved: list[dict[str, Any]], filters: dict[str, Any],
                reranked_order: list[str], prompt: str, context: list[str],
                model: str, parameters: dict[str, Any], response: dict[str, Any],
                citations: list[dict[str, Any]], guardrail_actions: list[dict[str, Any]],
                latency_per_stage: dict[str, float], cache_hit: bool) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "rewritten_query": query,
        "embed_model": settings.embed_model,
        "embed_model_version": settings.embed_model_version,
        "collection": collection,
        "retrieved": retrieved,
        "filters": filters,
        "reranked_order": reranked_order,
        "prompt_hash": prompt_hash(prompt),
        "prompt": prompt,
        "context": context,
        "model": model,
        "parameters": parameters,
        "response": response,
        "citations": citations,
        "guardrail_actions": guardrail_actions,
        "latency_per_stage": latency_per_stage,
        "cache_hit": cache_hit,
    }
