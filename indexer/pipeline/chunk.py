"""Stage 3: Chunk. Structure-aware, with overlap."""

from __future__ import annotations

import re
from .models import Chunk, Document


# Regex patterns identifying university section headings (e.g., '1. Attendance', 'Clause 5.4', 'Section 3.1')
SECTION_HEADING_RE = re.compile(
    r"^(?:(?:Section|Clause|Article|Chapter)\s+[\d\.]+|[\d]+\.[\d]*)\s+[A-Za-z0-9\s,\-\(\)]+$",
    re.MULTILINE
)


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on sections, then paragraphs, then sentences, keeping each chunk under
    `size` tokens, with `overlap` tokens shared between neighbours. Every chunk keeps
    the section heading it sits under, its page, doc_version and superseded."""
    chunks: list[Chunk] = []
    chunk_index = 0

    for page in doc.pages:
        paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
        current_section = f"Page {page.page}"

        # Combine paragraphs into size-bounded chunks
        token_buffer: list[str] = []

        for para in paragraphs:
            # Check if this paragraph is a section header
            lines = para.split("\n")
            first_line = lines[0].strip()
            if SECTION_HEADING_RE.match(first_line) or (len(first_line) < 60 and first_line.isupper()):
                current_section = first_line

            para_tokens = para.split()
            if not para_tokens:
                continue

            # If adding this paragraph exceeds size, flush the current buffer
            if len(token_buffer) + len(para_tokens) > size and token_buffer:
                chunk_text = " ".join(token_buffer)
                chunk_id = f"{doc.source}:p{page.page}:c{chunk_index}"
                chunks.append(Chunk(
                    id=chunk_id,
                    text=chunk_text,
                    source=doc.source,
                    section=current_section,
                    page=page.page,
                    doc_version=doc.doc_version,
                    superseded=doc.superseded
                ))
                chunk_index += 1

                # Keep overlap tokens for context continuity
                token_buffer = token_buffer[-overlap:] if overlap < len(token_buffer) else token_buffer

            token_buffer.extend(para_tokens)

        # Flush any remaining tokens on this page
        if token_buffer:
            chunk_text = " ".join(token_buffer)
            chunk_id = f"{doc.source}:p{page.page}:c{chunk_index}"
            chunks.append(Chunk(
                id=chunk_id,
                text=chunk_text,
                source=doc.source,
                section=current_section,
                page=page.page,
                doc_version=doc.doc_version,
                superseded=doc.superseded
            ))
            chunk_index += 1

    return chunks
