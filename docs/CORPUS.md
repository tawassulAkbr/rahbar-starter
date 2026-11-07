# Corpus

## Verified acquisition

The local corpus contains nine manifest entries. `python corpus/fetch.py --verify`
reports **9 of 9 match the manifest**. The PDFs have 279 pages in total, including
the active June 2026 academic rules handbook and the superseded August 2023 rules.

| Property | Status | Evidence |
| --- | --- | --- |
| At least six documents and more than 40 pages | Verified | 9 manifest entries; 279 PDF pages |
| Two versions of one policy | Verified | `undergraduate-academic-rules-aug-2023.pdf` and `academic-rules-handbook-jun-2026.pdf` |
| Scanned image-only PDF | Verified | `pdffonts` returns no fonts for `faculty-entrepreneurship-and-technical-start-ups-policy.pdf` |
| Real tables | Verified | Fee and grading HTML tables; tabular PDF content in the annual reports |
| Long definitions | Verified | Student Handbook 2026 and Academic Rules Handbook 2026 |
| Deliberately absent topic | Verified for golden set | Hostel allotment and mess-refund procedures are not represented; the handbook only mentions hostel facilities |
| Exact identifiers and clauses | Verified | Academic Rules Handbook clauses `1.21`, `4.2`, `5.4`; fee page value `Rs. 12,000` |

The downloaded bytes and metadata are recorded in `corpus/MANIFEST.md` and
`corpus/raw/_index.json`. The 2023 rules PDF is image-only, so its detailed text
must be extracted in the production/indexer image where Tesseract is installed.
The host-side OCR check is therefore environment-dependent and must not be
reported as a successful OCR run without that executable.

### Fall 2026 policy update

The user-supplied university notice about repetition of passed courses is
stored as the committed Markdown source
`corpus/academic-rules-fall-2026-grade-improvement.md`. It is effective from
Fall 2026 and is deliberately marked `2026-Fall`, `superseded: false`, and
separate from the June 2026 handbook. It says that the better of the two grades
is used for CGPA, and limits repetition to students not on academic warning
with a grade below C when the course was offered to the batch within the last
academic year. This is a supplied addendum, not a claim that a new official PDF
has already been downloaded; the source note identifies the replacement step
when the university publishes one.

## Reverification

```bash
python corpus/fetch.py --verify
pdfinfo corpus/raw/academic-rules-handbook-jun-2026.pdf | grep Pages
pdffonts corpus/raw/faculty-entrepreneurship-and-technical-start-ups-policy.pdf
```

`doc_version` and `superseded` come from `corpus/raw/_index.json` and flow into
every indexed chunk. Scanned pages use the indexer's Tesseract fallback. Tables
are preserved as extracted text where the source layout permits.
