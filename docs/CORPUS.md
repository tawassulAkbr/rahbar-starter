# Corpus

## Current status

The repository currently contains the corpus fetcher and source template, but no
`corpus/sources.yaml`, downloaded `corpus/raw/` documents, or verified manifest.
Consequently the seven mandatory corpus properties are not yet satisfied. This is
intentional documentation of the current state; no document, page count, hash, or
policy identifier is invented here.

| Property | Status | Evidence |
| --- | --- | --- |
| At least six documents and more than 40 pages | Missing | `corpus/raw/` is absent |
| Two versions of one policy | Missing | No downloaded policy versions |
| Scanned image-only PDF | Missing | No local PDF to inspect with `pdffonts` |
| Real tables | Missing | No local corpus documents |
| Long definitions | Missing | No local corpus documents |
| Deliberately absent topic | Planned, not verified | Must be selected after corpus acquisition |
| Exact identifiers | Missing | No verified local source text |

## Acquisition and integrity procedure

Copy `corpus/sources.example.yaml` to `corpus/sources.yaml`, review every public
URL, then run:

```bash
python corpus/fetch.py
python corpus/fetch.py --verify
```

The fetcher stores files under the gitignored `corpus/raw/`, records source URLs,
versions, superseded flags, sizes, and SHA-256 hashes in `corpus/MANIFEST.md`, and
avoids downloading an unchanged file twice. `--verify` checks every manifest hash.
Confirm public-source access terms before acquisition.

After downloading, verify page counts with `pdfinfo` or `pypdf`, inspect the
scanned candidate with `pdffonts`, and search extracted text for exact clauses,
course codes, thresholds, and the deliberately absent topic. Update the manifest
with actual evidence only.

## Pipeline handling

`doc_version` and `superseded` come from `corpus/raw/_index.json` or Markdown front
matter and flow into every indexed chunk. Scanned pages use the indexer's Tesseract
fallback. Tables are preserved as extracted text where the source layout permits;
OCR table reconstruction is not claimed without evidence.
