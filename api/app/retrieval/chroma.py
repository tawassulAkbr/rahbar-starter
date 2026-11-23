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
    # A historical year mentioned for comparison should not override an
    # explicit request for the current/latest policy.
    if re.search(r"\b(?:current|currently|latest|now)\b", question, flags=re.IGNORECASE):
        return None
    season = re.search(
        r"\b(Fall|Spring|Summer|Winter)\s+((?:19|20)\d{2})\b",
        question,
        flags=re.IGNORECASE,
    )
    if season:
        return f"{season.group(2)}-{season.group(1).title()}"
    match = re.search(r"\b((?:19|20)\d{2}(?:[-/]\d{1,2})?)\b", question)
    return match.group(1).replace("/", "-") if match else None


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


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
            # Fetch enough candidates for lexical and clause-aware reranking.
            # An explicit version request must include that version even when
            # superseded. General queries stay on current documents. The wider
            # candidate pool gives clause and exact-term reranking room to work.
            query: dict[str, object] = {
                "query_embeddings": [embedding], "n_results": max(k, 50),
                "where": ({"doc_version": requested_version} if requested_version
                          else {"superseded": False}),
            }
            result = collection.query(**query)  # type: ignore[arg-type]
            ignored = {
                "what", "is", "the", "a", "an", "to", "of", "for", "does", "if", "how",
                "who", "under", "and", "in", "on", "when", "superseded", "both", "indexed",
                "which", "version", "should", "answer", "question", "current", "latest",
            }
            keyword_terms = _tokens(question) - ignored
            if len(keyword_terms) > 1:
                keyword_vector = _query_embedding(" ".join(sorted(keyword_terms)), self.settings)
                keyword_result = collection.query(
                    **{**query, "query_embeddings": [keyword_vector]}
                )  # type: ignore[arg-type]
                if isinstance(result, dict) and isinstance(keyword_result, dict):
                    for key in ("ids", "documents", "metadatas", "distances"):
                        original = result.get(key) or [[]]
                        additional = keyword_result.get(key) or [[]]
                        if (original and additional and isinstance(original[0], list)
                                and isinstance(additional[0], list)):
                            result[key] = [original[0] + additional[0]]
                # Exact document-term probes recover lexical hits that both
                # vector formulations may rank below their candidate cutoff.
                lexical_terms = sorted(
                    (term for term in keyword_terms if len(term) >= 6 and not term.isdigit()),
                    key=lambda term: (-len(term), term),
                )[:2]
                for term in lexical_terms:
                    lexical_result = collection.query(
                        **{**query, "query_embeddings": [keyword_vector],
                           "where_document": {"$contains": term}}
                    )  # type: ignore[arg-type]
                    if isinstance(result, dict) and isinstance(lexical_result, dict):
                        for key in ("ids", "documents", "metadatas", "distances"):
                            original = result.get(key) or [[]]
                            additional = lexical_result.get(key) or [[]]
                            if (original and additional and isinstance(original[0], list)
                                    and isinstance(additional[0], list)):
                                result[key] = [original[0] + additional[0]]
        except RetrievalError:
            raise
        except Exception as exc:
            raise RetrievalError(f"Chroma retrieval failed: {exc}") from exc
        if not isinstance(result, dict):
            raise RetrievalError("Chroma returned a non-object query result")
        raw_ids = result.get("ids") or [[]]
        raw_documents = result.get("documents") or [[]]
        raw_metadatas = result.get("metadatas") or [[]]
        raw_distances = result.get("distances") or [[]]
        if not all(isinstance(value, list)
                   for value in (raw_ids, raw_documents, raw_metadatas, raw_distances)):
            raise RetrievalError("Chroma returned malformed query result lists")
        ids = raw_ids[0]
        documents = raw_documents[0]
        metadatas = raw_metadatas[0]
        distances = raw_distances[0]
        passages: list[Passage] = []
        seen_ids: set[str] = set()
        for position, chunk_id in enumerate(ids):
            if not isinstance(chunk_id, str) or position >= len(documents):
                continue
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
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
        stopwords = {"what", "is", "the", "a", "an", "to", "of", "for", "does", "if", "how", "who", "under", "and", "in", "on", "when", "superseded", "both", "indexed", "which", "version", "should", "answer", "question", "current", "latest"}
        terms = _tokens(question) - stopwords
        clause_numbers = set(re.findall(r"\b\d+(?:\.\d+)+\b", question))
        document_frequency = {
            term: sum(term in (_tokens(passage.text) | _tokens(passage.section))
                      for passage in passages)
            for term in terms
        }

        def rank(passage: Passage) -> tuple[float, float]:
            passage_terms = _tokens(passage.text)
            section_terms = _tokens(passage.section)
            matched_terms = terms & passage_terms
            lexical_score = sum(
                1.0 + (len(passages) / (document_frequency[term] + 1)) ** 0.5
                for term in matched_terms
            )
            # Exact clause IDs and distinctive query phrases carry more weight
            # than generic semantic similarity alone.
            clause_bonus = 3.0 if any(
                re.search(rf"(?<!\d){re.escape(clause)}(?!\d)", passage.text)
                or clause in passage.section for clause in clause_numbers
            ) else 0.0
            section_bonus = 1.5 * len(terms & section_terms)
            phrase_bonus = 2.0 if len(terms) >= 2 and " ".join(
                re.findall(r"[a-z0-9]+", question.lower())
            ) in passage.text.lower() else 0.0
            version_bonus = 0.0
            if requested_version:
                normalized_version = requested_version.lower()
                if normalized_version in passage.source.lower():
                    version_bonus = 2.0
                elif normalized_version[:4] in passage.source.lower():
                    version_bonus = 1.0
            return (lexical_score + section_bonus + clause_bonus + phrase_bonus + version_bonus
                    + passage.score,
                    passage.score)

        passages.sort(key=rank, reverse=True)
        return passages[:k]
