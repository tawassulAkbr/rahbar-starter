"""Prometheus metrics at ``/metrics`` (section 4.8).

The unprefixed metric names are the assignment contract.  ``rahbar_*`` aliases
are retained for compatibility with the starter dashboard and tests.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

router = APIRouter()

REQUESTS = Counter("rahbar_requests_total", "HTTP requests", ["path", "status"])
LATENCY = Histogram(
    "rahbar_request_seconds",
    "HTTP request latency",
    ["path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

REQUEST_COUNT = Counter("request_count", "HTTP requests", ["route", "status"])
REQUEST_LATENCY = Histogram("request_latency_seconds", "HTTP request latency", ["route"])
RETRIEVAL_LATENCY = Histogram("retrieval_latency_seconds", "Retrieval latency")
GENERATION_LATENCY = Histogram("generation_latency_seconds", "LLM generation latency")
CACHE_HITS = Counter("cache_hits", "Semantic cache hits")
CACHE_MISSES = Counter("cache_misses", "Semantic cache misses")
ABSTENTIONS = Counter("abstention_count", "Grounded-answer abstentions")
FALLBACKS = Counter("fallback_count", "Safe fallback responses")
TOKENS_IN = Counter("tokens_in", "Estimated input tokens")
TOKENS_OUT = Counter("tokens_out", "Estimated output tokens")
TRACE_TOP1_SIMILARITY = Histogram(
    "trace_top1_retrieval_similarity", "Top-1 retrieval similarity", buckets=(0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)
TRACE_ABSTENTIONS = Counter("trace_abstentions_total", "Abstentions recorded in traces")
TRACE_CACHE_HITS = Counter("trace_cache_hits_total", "Cache hits recorded in traces")
TRACE_INJECTION_ATTEMPTS = Counter("trace_injection_attempts_total", "Injection attempts flagged")


def record_trace_metrics(trace: dict) -> None:
    retrieved = trace.get("retrieved") or []
    if retrieved:
        TRACE_TOP1_SIMILARITY.observe(float(retrieved[0].get("score", 0)))
    if not trace.get("response", {}).get("answered_from_context", True):
        TRACE_ABSTENTIONS.inc()
    if trace.get("cache_hit"):
        TRACE_CACHE_HITS.inc()
    TRACE_INJECTION_ATTEMPTS.inc(len(trace.get("guardrail_actions") or []))


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
