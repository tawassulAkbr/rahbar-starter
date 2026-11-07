from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

from pipeline.chunk import chunk
from pipeline.clean import clean
from pipeline.config import get_settings
from pipeline.embed import EmbeddingError, embed
from pipeline.extract import extract
from pipeline.models import Chunk
from pipeline.store import store


FIXTURES = Path(__file__).resolve().parents[2] / "eval" / "fixtures"


def test_markdown_extraction_skips_front_matter() -> None:
    document = extract(str(FIXTURES / "fees-2026.md"), "2026", False)
    assert document.pages[0].text.startswith("# Margalla")
    assert "doc_version:" not in document.pages[0].text


def test_clean_preserves_structure_and_tables() -> None:
    document = extract(str(FIXTURES / "fees-2026.md"), "2026", False)
    document.pages[0].text = "## 1. Fees\nA wrapped\nline.\n\n| Fee | Amount |\n\tBS\t100"
    cleaned = clean(document).pages[0].text
    assert "## 1. Fees" in cleaned
    assert "A wrapped line." in cleaned
    assert "| Fee | Amount |" in cleaned
    assert "\tBS\t100" in cleaned


def test_chunking_is_stable_and_respects_overlap_budget() -> None:
    document = clean(extract(str(FIXTURES / "academic-rules-2026.md"), "2026", False))
    first = chunk(document, size=12, overlap=3)
    second = chunk(document, size=12, overlap=3)
    assert [item.id for item in first] == [item.id for item in second]
    assert first
    assert all(item.stored_tokens <= 12 for item in first)
    assert all(item.metadata()["source"] == "academic-rules-2026.md" for item in first)


def test_empty_document_produces_no_chunks(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    document = clean(extract(str(empty), "unknown", False))
    assert chunk(document, size=10, overlap=2) == []


def test_extracts_plain_text_and_html(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    html_path = tmp_path / "notes.html"
    text_path.write_text("plain text", encoding="utf-8")
    html_path.write_text("<h1>Heading</h1><p>Body</p>", encoding="utf-8")
    assert extract(str(text_path), "v1", False).pages[0].text == "plain text"
    assert extract(str(html_path), "v1", False).pages[0].text == " Heading  Body "


def test_pdf_pages_preserve_numbers_and_remove_repeated_edges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakePdf:
        pages = [FakePage("Header\nFirst page\nFooter"), FakePage("Header\nSecond page\nFooter")]

        def __enter__(self) -> "FakePdf":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda path: FakePdf()))
    pdf_path = tmp_path / "rules.pdf"
    pdf_path.write_bytes(b"not a real PDF for the mocked extractor")
    document = extract(str(pdf_path), "2026", False)
    assert [page.page for page in document.pages] == [1, 2]
    assert document.pages[0].text == "First page"
    assert document.pages[1].text == "Second page"


def test_scanned_pdf_uses_ocr_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return ""

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self) -> "FakePdf":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda path: FakePdf()))
    monkeypatch.setattr("pipeline.extract._ocr_page", lambda page: "Recovered by OCR")
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"mock")
    page = extract(str(pdf_path), "2026", False).pages[0]
    assert page.ocr is True
    assert page.text == "Recovered by OCR"


def test_embedding_batches_and_uses_the_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    settings = settings.__class__(**{**settings.__dict__, "expected_dimension": 3,
                                     "embed_batch_size": 2})
    calls: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"embeddings": [[1.0, 2.0, 3.0] for _ in calls[-1]["json"]["input"]]}

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> FakeResponse:
            calls.append({"url": url, **kwargs})
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: FakeClient())
    vectors = embed(["one", "two", "three"], settings)
    assert len(calls) == 2
    assert all(call["json"]["model"] == settings.embed_model for call in calls)
    assert len(vectors) == 3


def test_embedding_rejects_dimension_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    settings = settings.__class__(**{**settings.__dict__, "expected_dimension": 3})

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"embeddings": [[1.0, 2.0]]}

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: FakeClient())
    with pytest.raises(EmbeddingError, match="dimension"):
        embed(["one"], settings)


def test_store_pins_configuration_and_invalidates_after_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    settings = settings.__class__(**{**settings.__dict__, "expected_dimension": 3})
    chunk_item = Chunk("id-1", "text", "source.md", "Section", 1, "2026", False)

    class FakeCollection:
        metadata = {"embed_model": settings.embed_model, "dimension": 3}
        rows: dict[str, object] = {}

        def upsert(self, **kwargs: object) -> None:
            self.rows = kwargs

        def count(self) -> int:
            return 1

    collection = FakeCollection()
    client = SimpleNamespace(get_collection=lambda name: collection)
    invalidations: list[bool] = []
    monkeypatch.setattr("pipeline.store.get_client", lambda value: client)
    monkeypatch.setattr("pipeline.store._invalidate_cache", lambda value: invalidations.append(True))
    assert store([chunk_item], [[1.0, 2.0, 3.0]], settings) == 1
    assert invalidations == [True]
    metadatas = collection.rows["metadatas"]
    assert isinstance(metadatas, list)
    assert isinstance(metadatas[0], dict)
    assert metadatas[0]["source"] == "source.md"


def test_store_rejects_embedding_pin_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    settings = settings.__class__(**{**settings.__dict__, "expected_dimension": 3})
    collection = SimpleNamespace(metadata={"embed_model": "different-model", "dimension": 3})
    client = SimpleNamespace(get_collection=lambda name: collection)
    monkeypatch.setattr("pipeline.store.get_client", lambda value: client)
    chunk_item = Chunk("id-1", "text", "source.md", "Section", 1, "2026", False)
    with pytest.raises(RuntimeError, match="Delete/recreate"):
        store([chunk_item], [[1.0, 2.0, 3.0]], settings)
