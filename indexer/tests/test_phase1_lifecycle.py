from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pipeline.models import Document, Page, Chunk
from pipeline.store import restore_document, store_incremental
from pipeline.verify import sha256_file, verify_documents


def _document(source: str, version: str = "2026") -> Document:
    return Document(source, version, False, [Page(source, 1, "A readable policy document with enough text.")])


def test_verification_writes_report_and_quarantines_failures(tmp_path: Path) -> None:
    good = tmp_path / "policy-2026.md"
    duplicate = tmp_path / "policy-copy-2026.md"
    empty = tmp_path / "empty-2026.md"
    for path in (good, duplicate):
        path.write_text("same readable policy content", encoding="utf-8")
    empty.write_text("", encoding="utf-8")
    documents = [
        (good, _document(good.name), sha256_file(good), "2026", False),
        (duplicate, _document(duplicate.name), sha256_file(duplicate), "2026", False),
        (empty, Document(empty.name, "2026", False, [Page(empty.name, 1, "")]), sha256_file(empty), "2026", False),
    ]
    reports, accepted = verify_documents(
        documents, run_id="batch-b", quarantine_dir=str(tmp_path / "quarantine"),
        report_dir=str(tmp_path / "reports"),
    )
    assert len(reports) == 3
    assert {report.document for report in reports if report.verdict == "fail"} == {"policy-copy-2026.md", "empty-2026.md"}
    assert [item[0].name for item in accepted] == ["policy-2026.md"]
    assert (tmp_path / "quarantine" / "empty-2026.md").exists()
    report = json.loads((tmp_path / "reports" / "verification-batch-b.json").read_text())
    assert report["documents"][0]["checks"].keys() == {"quality", "completeness", "recency", "uniqueness"}


def test_verification_detects_newer_version_and_embedding_near_duplicate(tmp_path: Path) -> None:
    old = tmp_path / "rules-2023.md"
    new = tmp_path / "rules-2026.md"
    other = tmp_path / "other-2026.md"
    for path in (old, new, other):
        path.write_text(path.name, encoding="utf-8")
    documents = [(path, _document(path.name, version), sha256_file(path), version, False)
                 for path, version in ((old, "2023"), (new, "2026"), (other, "2026"))]
    reports, _ = verify_documents(
        documents, run_id="versions", quarantine_dir=str(tmp_path / "q"),
        report_dir=str(tmp_path / "reports"),
        embedder=lambda texts: [[1.0, 0.0] for _ in texts], near_duplicate_threshold=0.9,
    )
    by_document = {report.document: report for report in reports}
    assert by_document["rules-2023.md"].checks["recency"]["passed"] is False
    assert by_document["other-2026.md"].checks["uniqueness"]["passed"] is False


class FakeCollection:
    def __init__(self) -> None:
        self.metadata = {"embed_model": "test", "dimension": 2}
        self.rows: dict[str, dict[str, Any]] = {}

    def get(self, where: dict[str, str]) -> dict[str, list[str]]:
        return {"ids": [key for key, row in self.rows.items() if row["metadata"]["source"] == where["source"]]}

    def delete(self, ids: list[str]) -> None:
        for key in ids:
            self.rows.pop(key, None)

    def upsert(self, *, ids, documents, embeddings, metadatas) -> None:
        for key, document, vector, metadata in zip(ids, documents, embeddings, metadatas):
            self.rows[key] = {"document": document, "embedding": vector, "metadata": metadata}

    def count(self) -> int:
        return len(self.rows)

    def update(self, *, ids, metadatas):
        for key, metadata in zip(ids, metadatas):
            self.rows[key]['metadata'].update(metadata)


def _settings(tmp_path: Path):
    from pipeline.config import get_settings
    base = get_settings()
    return base.__class__(**{
        **base.__dict__, "embed_model": "test", "expected_dimension": 2,
        "state_file": str(tmp_path / "state.json"), "archive_dir": str(tmp_path / "archive"),
        "corpus_dir": str(tmp_path / "corpus"), "redis_url": "",
    })


def test_incremental_store_skips_unchanged_and_removes_orphans(tmp_path: Path, monkeypatch) -> None:
    collection = FakeCollection()
    monkeypatch.setattr("pipeline.store.get_client", lambda settings: SimpleNamespace(
        get_collection=lambda name: collection,
    ))
    settings = _settings(tmp_path)
    first_chunk = Chunk("a-1", "one", "a.md", "Section", 1, "2026", False)
    current: list[dict[str, object]] = [
        {"source": "a.md", "sha256": "a", "doc_version": "2026", "path": str(tmp_path / "a.md")}
    ]
    assert store_incremental([first_chunk], [[1.0, 0.0]], settings, current) == 1
    assert store_incremental([], [], settings, current) == 1
    assert json.loads((tmp_path / "state.json").read_text())["last_run"]["embedded_chunks"] == 0
    assert store_incremental([], [], settings, []) == 0
    assert json.loads((tmp_path / "state.json").read_text())["last_run"]["orphan_chunks_removed"] == 1


def test_restore_moves_archived_document_back_to_corpus(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    archived = Path(settings.archive_dir) / "rules" / "rules-2023.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("old policy", encoding="utf-8")
    restored = restore_document("rules-2023.md", settings)
    assert Path(restored).read_text() == "old policy"
    assert Path(restored).parent == Path(settings.corpus_dir)


def test_newer_version_archives_old_source_and_replaces_its_chunks(tmp_path: Path, monkeypatch) -> None:
    collection = FakeCollection()
    monkeypatch.setattr("pipeline.store.get_client", lambda settings: SimpleNamespace(
        get_collection=lambda name: collection,
    ))
    settings = _settings(tmp_path)
    old = tmp_path / "rules-2023.md"
    new = tmp_path / "rules-2026.md"
    old.write_text("old policy", encoding="utf-8")
    new.write_text("new policy", encoding="utf-8")
    old_item: list[dict[str, object]] = [
        {"source": old.name, "sha256": "old", "doc_version": "2023", "path": str(old)}
    ]
    new_item: list[dict[str, object]] = [
        {"source": new.name, "sha256": "new", "doc_version": "2026", "path": str(new)}
    ]
    store_incremental([Chunk("old-1", "old", old.name, "S", 1, "2023", False)], [[1.0, 0.0]], settings, old_item)
    store_incremental([Chunk("new-1", "new", new.name, "S", 1, "2026", False)], [[0.0, 1.0]], settings, new_item)
    assert list((Path(settings.archive_dir) / "rules").rglob(old.name))
    assert collection.rows['old-1']['metadata']['superseded'] is True
    assert "new-1" in collection.rows
    restore_document(old.name, settings)
    assert collection.rows['old-1']['metadata']['superseded'] is False
    assert collection.rows['new-1']['metadata']['superseded'] is True


def test_new_version_not_rejected_as_duplicate_of_rejected_old(tmp_path):
    paths = [tmp_path/'rules-2023.md', tmp_path/'rules-2026.md']
    for path in paths:
        path.write_text(path.name)
    docs = [(p, _document(p.name, version), sha256_file(p), version, False)
            for p, version in zip(paths, ['2023', '2026'])]
    _, accepted = verify_documents(docs, run_id='test', quarantine_dir=str(tmp_path/'q'),
                                  report_dir=str(tmp_path/'r'), embedder=lambda texts: [[1, 0]] * len(texts))
    assert [item[0].name for item in accepted] == ['rules-2026.md']
