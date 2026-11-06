"""POST /api/ask. The Ingress sends /api/* here unchanged, so the prefix stays."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..schemas import AskRequest, AskResponse
from ..logjson import request_id_var
from ..services.answer import answer_question

router = APIRouter(prefix="/api")


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request, response: Response) -> AskResponse:
    state = request.app.state
    cached = state.cache.get(body.question, follow_up=body.follow_up)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached.model_copy(update={"request_id": request_id_var.get()})
    result = answer_question(body.question, state.retriever, state.provider, state.settings)
    state.cache.set(body.question, result, follow_up=body.follow_up)
    response.headers["X-Cache"] = "MISS"
    return result
