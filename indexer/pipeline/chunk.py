"""Stage 3: Chunk. Structure-aware, with overlap."""

from __future__ import annotations

import hashlib
import logging
import re

from .models import Chunk, Document

logger = logging.getLogger(__name__)
_TOKEN = re.compile(r"\S+")
_HEADING = re.compile(r"^\s*(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]?\s+)")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def _count(text: str) -> int:
    return len(_TOKEN.findall(text))


def _units(doc: Document, max_tokens: int) -> tuple[list[tuple[str, int, str]], int]:
    units: list[tuple[str, int, str]] = []
    original = 0
    for page in doc.pages:
        section = ""
        paragraphs = re.split(r"\n\s*\n+", page.text.strip()) if page.text.strip() else []
        for paragraph in paragraphs:
            lines = paragraph.splitlines()
            for line in lines:
                if _HEADING.match(line) or (
                    len(line) < 140 and re.match(r"^\d+(?:\.\d+)*\s", line)
                ):
                    section = line.strip()
            text = paragraph.strip()
            if not text:
                continue
            original += _count(text)
            if _count(text) <= 1:
                units.append((text, page.page, section))
                continue
            sentences = _SENTENCE.split(text)
            for sentence in sentences:
                if sentence.strip():
                    sentence = sentence.strip()
                    words = sentence.split()
                    for start in range(0, len(words), max(1, max_tokens)):
                        units.append(
                            (" ".join(words[start:start + max_tokens]), page.page, section)
                        )
    return units, original


def _windows(
    units: list[tuple[str, int, str]], size: int, overlap: int
) -> list[tuple[str, int, str]]:
    pieces: list[tuple[str, int, str]] = []
    current: list[str] = []
    current_tokens = 0
    current_page = 1
    current_section = ""
    for text, page, section in units:
        tokens = _count(text)
        if current and current_tokens + tokens > size:
            pieces.append((" ".join(current), current_page, current_section))
            overlap_words = (" ".join(current).split()[-overlap:]
                             if overlap else [])
            overlap_words = overlap_words[-max(0, size - tokens):]
            # Keep the rolling buffer as a list.  Assigning the joined string
            # here makes the next `extend()` append characters instead of words.
            current = list(overlap_words)
            current_tokens = len(current)
            current_page, current_section = page, section or current_section
            if current_tokens + tokens > size:
                current = []
                current_tokens = 0
        if not current:
            current_page, current_section = page, section
        current.extend(text.split())
        current_tokens += tokens
    if current:
        pieces.append((" ".join(current), current_page, current_section))
    return pieces


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on sections, then paragraphs, then sentences, keeping each chunk under
    `size` tokens, with `overlap` tokens shared between neighbours. Every chunk keeps
    the section heading it sits under, its page, doc_version and superseded."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size must be positive and overlap must be between 0 and size-1")
    units, original_tokens = _units(doc, size)
    if not units:
        return []
    pieces = _windows(units, size, overlap)
    chunks: list[Chunk] = []
    for position, (text, page, section) in enumerate(pieces):
        digest = hashlib.sha256(
            f"{doc.source}\0{doc.doc_version}\0{position}\0{text}".encode()
        ).hexdigest()[:24]
        chunks.append(Chunk(digest, text, doc.source, section or "Unsectioned", page,
                            doc.doc_version, doc.superseded, original_tokens, _count(text)))
    stored_tokens = sum(chunk.stored_tokens for chunk in chunks)
    logger.info("chunked source=%s chunks=%d storage_amplification=%.3f", doc.source,
                len(chunks), stored_tokens / original_tokens if original_tokens else 0.0)
    return chunks
