"""The indexer Job's entry point. It runs once and exits (section 4.2).

    python -m pipeline.run --dummy    # week 1: three fake chunks, no model needed
    python -m pipeline.run            # the real pipeline: extract, clean, chunk, embed, store

Exit code 0 means the index was written; anything else fails the Job, and
Kubernetes retries it up to the Job's backoffLimit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .config import IndexerSettings, get_settings
from .models import Chunk


def log(msg: str, **fields: object) -> None:
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "logger": "rahbar.indexer", "msg": msg, **fields}), flush=True)


def _front_matter(path: Path) -> dict[str, str]:
    """Read `key: value` lines between leading '---' markers (used by eval/fixtures)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def discover(corpus_dir: str) -> list[tuple[Path, str, bool]]:
    """List (path, doc_version, superseded) for every document to index.

    corpus/fetch.py writes _index.json next to the files it downloads; use it when
    present. Otherwise read Markdown front matter (the CI fixtures work this way).
    """
    root = Path(corpus_dir)
    # `corpus/fetch.py` stores downloaded material under `corpus/raw/`, while
    # fixture and committed-corpus runs may place files directly in the root.
    # Prefer the fetched index when it exists; otherwise use the root index.
    index = root / "raw" / "_index.json"
    if not index.exists():
        index = root / "_index.json"
    if index.exists():
        entries = json.loads(index.read_text(encoding="utf-8"))
        document_root = index.parent
        known = {str(e.get("file")) for e in entries}
        # Keep committed Markdown addenda with front matter when a fetched raw
        # index is present. These are owned policy updates, not downloaded
        # files, so they are intentionally outside corpus/raw/_index.json.
        for path in sorted(root.glob("*.md")):
            if path.name.lower().startswith("readme") or path.name in known:
                continue
            metadata = _front_matter(path)
            if metadata:
                entries.append({
                    "file": path.name,
                    "doc_version": metadata.get("doc_version", "unknown"),
                    "superseded": metadata.get("superseded", "false").lower() == "true",
                    "_root_file": True,
                })
        return [
            ((root if e.get("_root_file") else document_root) / e["file"],
             str(e.get("doc_version", "unknown")), bool(e.get("superseded", False)))
            for e in entries
        ]
    found = []
    for path in sorted(root.glob("*")):
        if path.suffix.lower() not in {".pdf", ".md", ".html", ".txt"}:
            continue
        if path.name.lower().startswith("readme"):
            continue
        meta = _front_matter(path) if path.suffix.lower() == ".md" else {}
        found.append((path, meta.get("doc_version", "unknown"),
                      meta.get("superseded", "false").lower() == "true"))
    return found


def run_pipeline(settings: IndexerSettings) -> int:
    from .chunk import chunk
    from .clean import clean
    from .embed import embed
    from .extract import extract
    from .store import store

    documents = discover(settings.corpus_dir)
    if not documents:
        raise SystemExit(f"no documents found in {settings.corpus_dir}")
    all_chunks: list[Chunk] = []
    for path, doc_version, superseded in documents:
        log("extracting", source=path.name, doc_version=doc_version, superseded=superseded)
        doc = clean(extract(str(path), doc_version, superseded))
        pieces = chunk(doc, settings.chunk_size, settings.chunk_overlap)
        log("chunked", source=path.name, chunks=len(pieces))
        all_chunks.extend(pieces)
    if not all_chunks:
        raise RuntimeError("documents were discovered but produced no non-empty chunks")
    log("embedding", chunks=len(all_chunks), batch_size=settings.embed_batch_size)
    vectors = embed([c.text for c in all_chunks], settings)
    log("storing", chunks=len(all_chunks), dimension=len(vectors[0]) if vectors else 0)
    count = store(all_chunks, vectors, settings)
    log("stored", collection=settings.collection, records=count)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the RAHBAR index, then exit.")
    parser.add_argument("--dummy", action="store_true", help="write three fake chunks")
    args = parser.parse_args()
    settings = get_settings()
    log("indexer starting", dummy=args.dummy, embed_model=settings.embed_model,
        collection=settings.collection, chroma=f"{settings.chroma_host}:{settings.chroma_port}",
        pod=os.environ.get("HOSTNAME", "-"))
    started = time.perf_counter()
    try:
        if args.dummy:
            from .dummy import write_dummy_index
            from .store import get_client

            count = write_dummy_index(settings, get_client(settings))
        else:
            count = run_pipeline(settings)
    except NotImplementedError as exc:
        log("indexer stage not implemented yet", error=str(exc))
        return 2
    except Exception as exc:
        log("indexer failed", error=str(exc), error_type=type(exc).__name__)
        return 1
    log("indexer finished", chunks=count, seconds=round(time.perf_counter() - started, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
