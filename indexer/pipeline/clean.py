"""Stage 2: Clean. Remove artefacts without destroying structure."""

from __future__ import annotations

import re

from .models import Document


_HEADING = re.compile(r"^\s{0,3}(?:#{1,6}\s+|(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+)[^|]+$")
_STRUCTURAL = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\d+(?:\.\d+)+\s|\|)")


def _clean_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\ufeff", "")
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    raw_lines = []
    for line in text.split("\n"):
        line = re.sub(r" +", " ", line)
        raw_lines.append(line.strip(" ") if "\t" in line else line.strip())
    output: list[str] = []
    for line in raw_lines:
        if not line:
            if output and output[-1] != "":
                output.append("")
            continue
        if output and output[-1] != "" and not _STRUCTURAL.match(line):
            previous = output[-1]
            can_join = (not _HEADING.match(previous) and not _STRUCTURAL.match(previous)
                        and not previous.endswith((".", ":", ";", "?", "!", "|", "-"))
                        and line[0].islower())
            if can_join:
                output[-1] = f"{previous} {line}"
                continue
        output.append(line)
    return "\n".join(output).strip()


def clean(doc: Document) -> Document:
    """Strip headers and footers that repeat on every page; keep headings and
    section boundaries, because chunking and citations depend on them."""
    for page in doc.pages:
        page.text = _clean_text(page.text)
    return doc
