"""Document verification, quarantine, and per-run evidence.

Verification intentionally runs on extracted documents before chunking.  The
near-duplicate check accepts a document-level embedding function so the
pipeline can use the configured embedding service without embedding chunks
that will later be skipped by the incremental updater.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .models import Document

EmbeddingFn = Callable[[list[str]], list[list[float]]]


@dataclass(frozen=True)
class VerificationReport:
    run_id: str
    document: str
    sha256: str
    checks: dict[str, dict[str, object]]
    verdict: str
    quarantined: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "document": self.document,
            "sha256": self.sha256,
            "checks": self.checks,
            "verdict": self.verdict,
            "quarantined": self.quarantined,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def logical_document_id(source: str) -> str:
    """Return a stable identity shared by versioned filenames."""
    stem = Path(source).stem.lower()
    stem = re.sub(r"(?:[-_ ]+(?:19|20)\d{2}(?:[-_ ]\d{1,2})?)$", "", stem)
    stem = re.sub(r"(?:[-_ ]+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))$", "", stem)
    return re.sub(r"[-_ ]+", "-", stem).strip("-") or stem


def _version_key(version: str) -> tuple[int, ...]:
    numbers = tuple(int(value) for value in re.findall(r"\d+", version))
    return numbers or (-1,)


def _check(passed: bool, reason: str) -> dict[str, object]:
    return {"passed": passed, "reason": reason}


def _quality(document: Document) -> dict[str, object]:
    text = "\n".join(page.text for page in document.pages)
    compact = re.sub(r"\s+", "", text)
    if not document.pages or not compact:
        return _check(False, "extracted text empty")
    if "�" in text or "\x00" in text:
        return _check(False, "extracted text contains replacement/control characters")
    printable = sum(character.isprintable() or character.isspace() for character in text)
    alphabetic = sum(character.isalpha() for character in text)
    if printable / max(1, len(text)) < 0.95 or alphabetic < 5:
        return _check(False, "extracted text appears garbled")
    return _check(True, "extracted text is non-empty and readable")


def _completeness(document: Document) -> dict[str, object]:
    if not document.source.strip():
        return _check(False, "source is missing")
    if not Path(document.source).stem.strip():
        return _check(False, "title is missing")
    if not document.doc_version or document.doc_version.lower() in {"unknown", "none", "null"}:
        return _check(False, "date/version is missing")
    if not document.pages or any(not isinstance(page.page, int) or page.page < 1 for page in document.pages):
        return _check(False, "page count or page numbering is missing")
    text = "\n".join(page.text for page in document.pages).lower()
    if re.search(r"(?:\[\s*truncated\s*\]|\.{3}\s*truncated|content truncated)", text):
        return _check(False, "text is marked truncated")
    return _check(True, "source, title, version, page count, and text completeness present")


def _recency(source: str, version: str, documents: Iterable[tuple[Path, str, bool]]) -> dict[str, object]:
    identity = logical_document_id(source)
    newer = [other_version for path, other_version, _ in documents
             if path.name != source and logical_document_id(path.name) == identity
             and _version_key(other_version) > _version_key(version)]
    if newer:
        return _check(False, f"newer version exists: {sorted(newer)[-1]}")
    return _check(True, "latest known version")


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _uniqueness(
    source: str,
    digest: str,
    text: str,
    records: list[tuple[Path, str, str, str]],
    embeddings: dict[str, list[float]] | None,
    threshold: float,
) -> dict[str, object]:
    ordered_sources = [other for _, other, _, _ in records]
    source_position = ordered_sources.index(source)
    prior_sources = set(ordered_sources[:source_position])
    exact = [other for _, other, other_digest, _ in records
             if other in prior_sources and other_digest == digest]
    if exact:
        return _check(False, f"exact duplicate of {exact[0]}")
    if embeddings and source in embeddings:
        for other_source, vector in embeddings.items():
            if (logical_document_id(other_source) != logical_document_id(source)
                    and other_source in prior_sources) and _cosine(embeddings[source], vector) >= threshold:
                return _check(False, f"near-duplicate of {other_source} (cosine >= {threshold:.2f})")
    return _check(True, "no exact or near duplicate")


def _quarantine(path: Path, quarantine_dir: Path) -> bool:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    destination = quarantine_dir / path.name
    if destination.exists():
        destination = quarantine_dir / f"{path.stem}-{hashlib.sha256(str(path).encode()).hexdigest()[:8]}{path.suffix}"
    try:
        shutil.move(str(path), str(destination))
    except OSError:
        return False
    return True


def verify_documents(
    documents: list[tuple[Path, Document, str, str, bool]],
    *,
    run_id: str,
    quarantine_dir: str,
    report_dir: str,
    near_duplicate_threshold: float = 0.97,
    embedder: EmbeddingFn | None = None,
    archive_dir: str | None = None,
) -> tuple[list[VerificationReport], list[tuple[Path, Document, str, str, bool]]]:
    """Verify documents and return reports plus only documents safe to index."""
    records = [(path, path.name, digest, version) for path, _, digest, version, _ in documents]
    embeddings: dict[str, list[float]] | None = None
    if embedder and documents:
        eligible = [item for item in documents if _quality(item[1])["passed"] and _completeness(item[1])["passed"]]
        vectors = embedder(["\n".join(page.text for page in document.pages) for _, document, *_ in eligible]) if eligible else []
        if len(vectors) != len(eligible):
            raise RuntimeError("verification embedding count mismatch")
        embeddings = {path.name: vector for (path, *_), vector in zip(eligible, vectors)}
    reports: list[VerificationReport] = []
    accepted: list[tuple[Path, Document, str, str, bool]] = []
    quarantine_root = Path(quarantine_dir)
    for path, document, digest, version, superseded in documents:
        # Rejected documents must never suppress an otherwise valid successor.
        comparison_records = [record for record in records if record[1] in {item[0].name for item in accepted} or record[1] == path.name]
        checks = {
            "quality": _quality(document),
            "completeness": _completeness(document),
            "recency": _recency(path.name, version, [(item[0], item[3], item[4]) for item in documents]),
            "uniqueness": _uniqueness(
                path.name, digest, "\n".join(page.text for page in document.pages), comparison_records,
                embeddings, near_duplicate_threshold,
            ),
        }
        passed = all(bool(check["passed"]) for check in checks.values())
        quarantined = False
        if not passed:
            if archive_dir and not checks['recency']['passed'] and checks['quality']['passed'] and checks['completeness']['passed']:
                archive = Path(archive_dir) / logical_document_id(path.name) / digest / path.name
                archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, archive)
            quarantined = _quarantine(path, quarantine_root)
        else:
            accepted.append((path, document, digest, version, superseded))
        reports.append(VerificationReport(run_id, path.name, digest, checks, "pass" if passed else "fail", quarantined))
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"verification-{run_id}.json"
    report_path.write_text(json.dumps({"run_id": run_id, "documents": [report.as_dict() for report in reports]}, indent=2), encoding="utf-8")
    return reports, accepted
