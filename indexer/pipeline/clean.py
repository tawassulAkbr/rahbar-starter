"""Stage 2: Clean. Remove artefacts without destroying structure."""

from __future__ import annotations

import re
from .models import Document, Page


def clean(doc: Document) -> Document:
    """Strip headers and footers that repeat on every page; keep headings and
    section boundaries, because chunking and citations depend on them."""
    cleaned_pages: list[Page] = []

    for p in doc.pages:
        text = p.text
        # Replace Windows carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Strip repeated page numbering and common header boilerplate patterns
        text = re.sub(r"(?i)page\s+\d+\s+of\s+\d+", "", text)
        text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
        
        # Normalize excessive inline whitespace while preserving paragraph linebreaks
        lines = [line.strip() for line in text.split("\n")]
        # Collapse multiple empty lines down to a single blank line (paragraph separator)
        condensed_text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

        cleaned_pages.append(Page(
            source=p.source,
            page=p.page,
            text=condensed_text.strip(),
            ocr=p.ocr
        ))

    return Document(
        source=doc.source,
        doc_version=doc.doc_version,
        superseded=doc.superseded,
        pages=cleaned_pages
    )
