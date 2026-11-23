"""POST /api/ask. The Ingress sends /api/* here unchanged, so the prefix stays."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..schemas import AskRequest, AskResponse
from ..logjson import request_id_var
from . import metrics
from ..services.answer import answer_question
from ..tracing import base_record, emit_trace, new_trace_id

router = APIRouter(prefix="/api")


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request, response: Response) -> AskResponse:
    state = request.app.state
    cached = state.cache.get(body.question, follow_up=body.follow_up)
    if cached is not None:
        metrics.CACHE_HITS.inc()
        response.headers["X-Cache"] = "HIT"
        result = cached.model_copy(update={"request_id": request_id_var.get()})
        trace = base_record(
            trace_id=new_trace_id(), query=body.question, settings=state.settings,
            collection=state.settings.collection,
            retrieved=[{"chunk_id": p.chunk_id, "document_id": p.source,
                         "doc_version": "unknown", "score": p.score} for p in result.retrieved],
            filters={"cache": True}, reranked_order=[p.chunk_id for p in result.retrieved],
            prompt="", context=[], model=result.provider,
            parameters={"top_k": state.settings.top_k, "temperature": state.settings.temperature},
            response={"answer": result.answer, "answered_from_context": result.answered_from_context,
                      "confidence": result.confidence},
            citations=[citation.model_dump() for citation in result.citations],
            guardrail_actions=[], latency_per_stage={"total_ms": 0.0}, cache_hit=True,
        )
        emit_trace(trace, state.settings.trace_dir)
        metrics.record_trace_metrics(trace)
        return result
    result = answer_question(body.question, state.retriever, state.provider, state.settings)
    metrics.CACHE_MISSES.inc()
    state.cache.set(body.question, result, follow_up=body.follow_up)
    response.headers["X-Cache"] = "MISS"
    return result
