"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import Document
from .models import Page


_MIN_TEXT = 20


def _without_front_matter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for number, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                return "\n".join(lines[number + 1:])
    return text


def _remove_repeated_edges(pages: list[Page]) -> None:
    """Remove an edge line only when it repeats on at least two pages."""
    if len(pages) < 2:
        return
    edge_counts: dict[str, int] = {}
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        for line in {*(lines[:1]), *(lines[-1:])}:
            if len(line) > 2:
                edge_counts[line] = edge_counts.get(line, 0) + 1
    repeated = {line for line, count in edge_counts.items() if count >= 2}
    for page in pages:
        lines = page.text.splitlines()
        while lines and lines[0].strip() in repeated:
            lines.pop(0)
        while lines and lines[-1].strip() in repeated:
            lines.pop()
        page.text = "\n".join(lines)


def _ocr_page(pdf_page: Any) -> str:
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "OCR is required for a scanned PDF, but pytesseract and Pillow are not installed"
        ) from exc
    try:
        image = pdf_page.to_image(resolution=200).original
        return str(pytesseract.image_to_string(image))
    except Exception as exc:
        raise RuntimeError(
            "OCR failed; install the Tesseract executable and ensure it is on PATH"
        ) from exc


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page.

    Detect pages with no text layer and OCR them; mark those pages ocr=True.
    The OCR libraries need system packages in your Dockerfile (tesseract-ocr,
    poppler-utils), not only pip packages.
    """
    source = Path(path).name
    suffix = Path(path).suffix.lower()
    if suffix in {".md", ".txt", ".html", ".htm"}:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"could not read document {path}: {exc}") from exc
        if suffix in {".html", ".htm"}:
            text = re.sub(r"<[^>]+>", " ", text)
        return Document(source, doc_version, superseded,
                        [Page(source, 1, _without_front_matter(text))])
    if suffix != ".pdf":
        raise ValueError(f"unsupported document type: {path}")
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires the pdfplumber dependency") from exc
    pages: list[Page] = []
    try:
        with pdfplumber.open(path) as pdf:
            for number, pdf_page in enumerate(pdf.pages, 1):
                text = (pdf_page.extract_text() or "").strip()
                ocr = len(re.sub(r"\s+", "", text)) < _MIN_TEXT
                if ocr:
                    text = _ocr_page(pdf_page).strip()
                pages.append(Page(source, number, text, ocr))
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"could not read PDF {path}: {exc}") from exc
    _remove_repeated_edges(pages)
    return Document(source, doc_version, superseded, pages)
