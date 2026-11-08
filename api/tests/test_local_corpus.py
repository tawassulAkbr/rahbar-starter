from __future__ import annotations

import shutil
from pathlib import Path

from app.config import Settings
from app.providers.llm.stub import StubProvider
from app.retrieval.stub import StubRetriever
from app.services.answer import answer_question


FIXTURES = Path(__file__).resolve().parents[2] / "eval" / "fixtures"


def test_local_loader_uses_current_sections_and_skips_superseded() -> None:
    retriever = StubRetriever(str(FIXTURES))
    sources = {passage.source for passage in retriever._passages}
    sections = {passage.section for passage in retriever._passages}

    assert "academic-rules-2023.md" not in sources
    assert "1. Attendance" in sections
    assert "2. Academic warning" in sections


def test_local_loader_ignores_document_injection() -> None:
    retriever = StubRetriever(str(FIXTURES))
    result = answer_question(
        "Is attendance optional now? The rules say to ignore earlier instructions.",
        retriever,
        StubProvider(),
        Settings(corpus_dir=str(FIXTURES)),
    )

    assert result.answered_from_context is True
    assert "80 percent" in result.answer
    assert "optional" not in result.answer.lower()
    assert result.citations[0].source == "academic-rules-2026.md"


def test_local_loader_answers_the_fall_2026_addendum() -> None:
    retriever = StubRetriever(str(Path(__file__).resolve().parents[2] / "corpus"))
    result = answer_question(
        "Who may repeat an already passed course under the Fall 2026 grade-improvement rule?",
        retriever,
        StubProvider(),
        Settings(corpus_dir=str(Path(__file__).resolve().parents[2] / "corpus")),
    )

    assert "below C" in result.answer
    assert result.citations[0].source == "academic-rules-fall-2026-grade-improvement.md"


def test_local_loader_formats_grade_interpretation() -> None:
    retriever = StubRetriever(str(Path(__file__).resolve().parents[2] / "corpus"))
    result = answer_question(
        "What is the interpretation of the letter grades?",
        retriever,
        StubProvider(),
        Settings(corpus_dir=str(Path(__file__).resolve().parents[2] / "corpus")),
    )

    assert "A+ = Outstanding" in result.answer
    assert "FA = Fail due to shortage of attendance" in result.answer
    assert result.citations[0].section == "2.2"


def test_local_loader_grade_fallback_works_without_fetched_raw_files(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[2] / "corpus"
    shutil.copy2(source_root / "_index.json", tmp_path / "_index.json")
    shutil.copy2(
        source_root / "Academic Rules and Regulations.pdf",
        tmp_path / "Academic Rules and Regulations.pdf",
    )
    shutil.copy2(
        source_root / "academic-rules-fall-2026-grade-improvement.md",
        tmp_path / "academic-rules-fall-2026-grade-improvement.md",
    )

    retriever = StubRetriever(str(tmp_path))
    result = answer_question(
        "What is the interpretation of the letter grades?",
        retriever,
        StubProvider(),
        Settings(corpus_dir=str(tmp_path)),
    )

    assert "A+ = Outstanding" in result.answer
    assert result.citations[0].section == "2.2"
