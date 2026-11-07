"""A deterministic, offline provider.

Returns schema-constrained, source-grounded answers based on the retrieved
passages without making external network calls.
"""

from __future__ import annotations

import re

from ...schemas import Answer, Citation, Passage


_STOPWORDS = {
    "what", "is", "the", "a", "an", "under", "in", "for", "to", "of", "and", "or",
    "how", "does", "do", "if", "when", "who", "may", "can", "be", "are", "about",
    "from", "on", "this", "that", "which", "rule", "student", "students",
}


def _terms(value: str) -> set[str]:
    raw_terms = set(re.findall(r"[a-z0-9]+", value.lower())) - _STOPWORDS
    terms = {
        "attend" if term.startswith("attend") else term
        for term in raw_terms
    }
    # Common question wording does not always repeat the policy wording.
    # These small expansions keep the offline provider extractive rather than
    # inventing an answer.
    if "capped" in terms:
        terms.update({"most", "recent", "counts"})
    if "allowed" in terms or "sit" in terms:
        terms.update({"eligible", "examination"})
    return terms


def _sentences(text: str) -> list[str]:
    # PDF extraction frequently puts a heading and its body on separate lines,
    # while HTML tables may use pipes. Treat all of those as answerable units.
    return [
        part.strip(" |-\t")
        for part in re.split(r"(?<=[.!?])\s+|\n+", text)
        if part.strip(" |-\t")
    ]


def _answer_text(question: str, passage: Passage) -> str:
    query_terms = _terms(question)
    candidates = []
    for position, sentence in enumerate(_sentences(passage.text)):
        lowered = sentence.lower()
        # Instructions embedded in documents are evidence, not instructions to
        # this provider. Never reproduce an injection sentence as an answer.
        if "ignore all previous instructions" in lowered:
            continue
        sentence_terms = _terms(sentence)
        overlap = len(query_terms & sentence_terms)
        if overlap:
            candidates.append((overlap, -position, sentence))
    if candidates:
        candidates.sort(reverse=True)
        answer = candidates[0][2]
        # Keep section labels for citations, but do not make the visible answer
        # read like a raw chunk dump.
        answer = re.sub(r"^\d+(?:\.\d+)*\s+", "", answer)
        return re.sub(r"^[^.!?:]{1,100}:\s*", "", answer).strip()
    safe_sentences = [
        sentence for sentence in _sentences(passage.text)
        if "ignore all previous instructions" not in sentence.lower()
    ]
    return safe_sentences[0] if safe_sentences else passage.text.strip()


class StubProvider:
    name = "stub"

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        if not passages:
            return Answer(
                reasoning="stub: nothing was retrieved",
                answer="The provided university policy documents do not cover this topic.",
                citations=[],
                answered_from_context=False,
                confidence="low",
            )
        top = passages[0]
        answer = _answer_text(question, top)
        return Answer(
            reasoning=f"Extracted the answer from {top.source} (section {top.section}).",
            answer=answer,
            citations=[Citation(source=top.source, section=top.section, page=top.page)],
            answered_from_context=True,
            confidence="high",
        )
