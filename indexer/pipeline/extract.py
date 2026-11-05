"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page."""

from __future__ import annotations

import os
from pathlib import Path
import pypdf

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from pdf2image import convert_from_path
except ImportError:
    pytesseract = None
    convert_from_path = None

from .models import Document, Page


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page.

    Detect pages with no text layer and OCR them; mark those pages ocr=True.
    The OCR libraries need system packages in your Dockerfile (tesseract-ocr,
    poppler-utils), not only pip packages.
    """
    file_path = Path(path)
    source_name = file_path.name
    doc = Document(source=source_name, doc_version=doc_version, superseded=superseded)

    if file_path.suffix.lower() == ".pdf":
        _extract_pdf(file_path, doc)
    elif file_path.suffix.lower() in {".txt", ".md", ".html"}:
        _extract_text(file_path, doc)
    else:
        # Fallback reading
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        doc.pages.append(Page(source=source_name, page=1, text=content, ocr=False))

    return doc


def _extract_pdf(file_path: Path, doc: Document) -> None:
    source_name = file_path.name
    reader = pypdf.PdfReader(str(file_path))

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        raw_text = page.extract_text() or ""
        
        # If the page has virtually no digital text layer, attempt OCR
        if len(raw_text.strip()) < 30:
            ocr_text = _run_ocr_page(file_path, page_num)
            if ocr_text and len(ocr_text.strip()) >= 30:
                doc.pages.append(Page(source=source_name, page=page_num, text=ocr_text, ocr=True))
                continue

        doc.pages.append(Page(source=source_name, page=page_num, text=raw_text, ocr=False))


def _run_ocr_page(file_path: Path, page_num: int) -> str:
    """Attempt OCR on a specific PDF page using pdf2image and pytesseract."""
    if not pytesseract or not convert_from_path:
        return ""
    try:
        images = convert_from_path(str(file_path), first_page=page_num, last_page=page_num)
        if images:
            return pytesseract.image_to_string(images[0])
    except Exception:
        pass
    return ""


def _extract_text(file_path: Path, doc: Document) -> None:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    doc.pages.append(Page(source=file_path.name, page=1, text=text, ocr=False))
