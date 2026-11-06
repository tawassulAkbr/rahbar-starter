"""The real retriever. Yours to build (sections 3.2 and 4.4).

Connection details are already here; the query is not.
"""

from __future__ import annotations

import re

import httpx

from ..config import Settings
from ..schemas import Passage


class RetrievalError(RuntimeError):
    """The vector store or query embedding service returned an unusable result."""


def _query_embedding(question: str, settings: Settings) -> list[float]:
    url = settings.ollama_url.rstrip("/") + "/api/embed"
    try:
        response = httpx.post(url, json={"model": settings.embed_model, "input": [question]},
                              timeout=settings.embed_timeout)
        response.raise_for_status()
        embeddings = response.json().get("embeddings")
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise RetrievalError(f"query embedding failed: {exc}") from exc
    if not isinstance(embeddings, list) or len(embeddings) != 1:
        raise RetrievalError("query embedding response did not contain one vector")
    vector = embeddings[0]
    if (not isinstance(vector, list) or len(vector) != settings.embed_dimension
            or not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       for value in vector)):
        raise RetrievalError(
            f"query embedding dimension or values do not match {settings.embed_dimension}"
        )
    return [float(value) for value in vector]


def _requests_older_version(question: str) -> bool:
    return bool(re.search(r"\b(?:19|20)\d{2}(?:[-/]\d{1,2})?\b", question))


def _requested_version(question: str) -> str | None:
    match = re.search(r"\b((?:19|20)\d{2}(?:[-/]\d{1,2})?)\b", question)
    return match.group(1).replace("/", "-") if match else None


class ChromaRetriever:
    name = "chroma"

    def __init__(self, settings: Settings) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.settings = settings
        self.client = chromadb.HttpClient(
            host=settings.chroma_host, port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

    def retrieve(self, question: str, k: int) -> list[Passage]:
        if k <= 0:
            return []
        try:
            collection = self.client.get_collection(name=self.settings.collection)
            if collection.count() == 0:
                return []
            embedding = _query_embedding(question, self.settings)
            requested_version = _requested_version(question)
            query: dict[str, object] = {"query_embeddings": [embedding], "n_results": k}
            if requested_version:
                query["where"] = {"doc_version": requested_version}
            else:
                query["where"] = {"superseded": False}
            result = collection.query(**query)
        except RetrievalError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Chroma retrieval failed: {exc}") from exc
        if not isinstance(result, dict):
            raise RetrievalError("Chroma returned a non-object query result")
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if not all(isinstance(value, list) for value in (ids, documents, metadatas, distances)):
            raise RetrievalError("Chroma returned malformed query result lists")
        passages: list[Passage] = []
        for position, chunk_id in enumerate(ids):
            if not isinstance(chunk_id, str) or position >= len(documents):
                continue
            metadata = metadatas[position] if position < len(metadatas) else {}
            metadata = metadata if isinstance(metadata, dict) else {}
            text = documents[position]
            if not isinstance(text, str) or not text.strip():
                continue
            distance = distances[position] if position < len(distances) else 1.0
            if not isinstance(distance, (int, float)):
                distance = 1.0
            score = max(0.0, min(1.0, 1.0 - float(distance)))
            try:
                page = int(metadata["page"]) if metadata.get("page") is not None else None
            except (TypeError, ValueError):
                page = None
            passages.append(Passage(
                chunk_id=chunk_id, text=text,
                source=str(metadata.get("source", "unknown")),
                section=str(metadata.get("section", "Unsectioned")),
                page=page, score=score,
            ))
        return passages
