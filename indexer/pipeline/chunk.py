"""Stage 3: Chunk. Structure-aware, with overlap."""

from __future__ import annotations

import hashlib
import logging
import re

from .models import Chunk, Document

logger = logging.getLogger(__name__)
_TOKEN = re.compile(r"\S+")
_MD_HEADING = re.compile(r"^\s*#{1,6}\s+(.+)$")
_PDF_CLAUSE = re.compile(r"^\s*(\d+(?:\.\d+)+)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def _count(text: str) -> int:
    return len(_TOKEN.findall(text))


def _section_label(line: str) -> str:
    cleaned = re.sub(r"^#+\s*", "", line).strip()
    match = _PDF_CLAUSE.match(cleaned)
    if match:
        return match.group(1)
    return cleaned


def _extract_sections(doc: Document) -> list[tuple[str, int, str]]:
    """Extract (section_heading, page, text) tuples respecting document structure."""
    sections: list[tuple[str, int, str]] = []
    current_section = "Unsectioned"
    current_page = 1
    current_lines: list[str] = []
    is_md = doc.source.lower().endswith(".md")

    for page in doc.pages:
        paragraphs = re.split(r"\n\s*\n+", page.text.strip()) if page.text.strip() else []
        for paragraph in paragraphs:
            lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
            for line in lines:
                new_sec: str | None = None
                if is_md:
                    m = _MD_HEADING.match(line)
                    if m:
                        new_sec = _section_label(m.group(1))
                else:
                    m = _PDF_CLAUSE.match(line)
                    if m and len(line) < 160:
                        new_sec = m.group(1)
                    elif len(line) < 60 and re.match(r"^[A-Z0-9\s:.-]+$", line):
                        new_sec = line.strip()

                if new_sec is not None:
                    if current_lines:
                        sections.append((current_section, current_page, "\n".join(current_lines)))
                        current_lines = []
                    current_section = new_sec
                    current_page = page.page
                else:
                    current_lines.append(line)

    if current_lines:
        sections.append((current_section, current_page, "\n".join(current_lines)))
    return sections


def _window_section(sec_text: str, size: int, overlap: int) -> list[str]:
    words = sec_text.split()
    if len(words) <= size:
        return [sec_text]

    paragraphs = re.split(r"\n\s*\n+", sec_text.strip())
    units: list[str] = []
    for paragraph in paragraphs:
        sentences = _SENTENCE.split(paragraph.strip())
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence_words = sentence.split()
            if len(sentence_words) <= size:
                units.append(sentence)
            else:
                for start in range(0, len(sentence_words), max(1, size)):
                    units.append(" ".join(sentence_words[start:start + size]))

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        unit_len = len(unit.split())
        if current and current_len + unit_len > size:
            pieces.append(" ".join(current))
            overlap_words = (" ".join(current).split()[-overlap:]) if overlap else []
            current = list(overlap_words)
            current_len = len(current)
            if current_len + unit_len > size:
                current = []
                current_len = 0
        current.extend(unit.split())
        current_len += unit_len

    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on sections, then paragraphs, then sentences, keeping each chunk under
    `size` tokens, with `overlap` tokens shared between neighbours. Every chunk keeps
    the section heading it sits under, its page, doc_version and superseded."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size must be positive and overlap must be between 0 and size-1")

    sections = _extract_sections(doc)
    original_tokens = sum(_count(page.text) for page in doc.pages)
    if not sections or original_tokens == 0:
        return []

    chunks: list[Chunk] = []
    global_pos = 0

    for sec_title, page_num, sec_text in sections:
        pieces = _window_section(sec_text, size, overlap)
        for piece in pieces:
            piece_words = _count(piece)
            digest = hashlib.sha256(
                f"{doc.source}\0{doc.doc_version}\0{global_pos}\0{piece}".encode()
            ).hexdigest()[:24]
            chunks.append(
                Chunk(
                    id=digest,
                    text=piece,
                    source=doc.source,
                    section=sec_title,
                    page=page_num,
                    doc_version=doc.doc_version,
                    superseded=doc.superseded,
                    original_tokens=original_tokens,
                    stored_tokens=piece_words,
                )
            )
            global_pos += 1

    stored_tokens = sum(c.stored_tokens for c in chunks)
    logger.info(
        "chunked source=%s chunks=%d storage_amplification=%.3f",
        doc.source,
        len(chunks),
        stored_tokens / original_tokens if original_tokens else 0.0,
    )
    return chunks
