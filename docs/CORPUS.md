# Corpus

Source: FAST-NUCES public website (`nu.edu.pk`) · Documents: 7 · Pages: 224

This corpus represents the official academic policies, handbooks, regulations, and reports of the National University of Computer and Emerging Sciences (FAST-NUCES). It has been curated to satisfy all seven mandatory failure-mode properties required for evaluating the RAHBAR grounded RAG system.

---

## Required Properties Mapping Matrix

| # | Required property | Document(s) that provide it | Evidence or notes |
|---|---|---|---|
| 1 | At least 6 documents, 40 pages | Entire Corpus (7 documents, 224 pages total) | `Academic Rules and Regulations.pdf` (5 pages), `Academic-Rules-Undergrad-Aug-2023.pdf` (26 pages), `Student_Handbook_2026.pdf` (64 pages), `Grading.pdf` (3 pages), `Annual Report 2019-20.pdf` (33 pages), `Annual-Report-2023-24.pdf` (85 pages), and `Faculty Enterperuer and Startups Policy.pdf` (8 pages). Total scale: 224 pages. |
| 2 | Two versions of one policy | `Academic-Rules-Undergrad-Aug-2023.pdf` (v2023-08) vs `Academic Rules and Regulations.pdf` (v2026) | The 2023 undergraduate rules were repealed and superseded by the 2026 academic handbook. In `corpus/MANIFEST.md` and chunk metadata, the 2023 rules are explicitly tagged with `superseded: true`, whereas the 2026 handbook is tagged with `superseded: false`. This tests whether the retriever filters out superseded clauses or erroneously quotes outdated probation/warning thresholds. |
| 3 | Scanned, image-only PDF | `Grading.pdf` | Verified using font extraction analysis: `Grading.pdf` contains zero embedded font objects and zero selectable digital text layers. All 3 pages are raster scan images of circulars requiring OCR (`pytesseract` / Tesseract OCR engine) for text extraction. Tests Failure Mode C (OCR / image degradation failure). |
| 4 | A table with real information | `Annual Report 2019-20.pdf` (Section 4, Faculty & Enrollment Statistics) and `Academic Rules and Regulations.pdf` (Grading Table) | Contains multi-column letter-grade to grade-point conversion tables (Letter Grade, Numerical Marks %, Grade Points e.g., A=4.00, B+=3.33) and financial tables. Tests chunker ability to preserve row-column alignment without interleaving table rows into gibberish. |
| 5 | Long definitions | `Student_Handbook_2026.pdf` (Section 3: Code of Conduct & Academic Integrity) | Contains comprehensive, multi-paragraph definitions of academic offenses (including unauthorized AI tool usage, plagiarism definitions spanning >450 words across multiple paragraphs). Tests semantic and structure-aware chunking to prevent chopping legal definitions across arbitrary token boundaries. |
| 6 | A deliberately absent topic | Hostel Accommodation & Room Allotment Rules | The student handbook mentions that campuses have hostel facilities, but deliberately excludes the detailed room allotment priority guidelines, curfew violation penalties, and mess refund policies. When queried on *"What is the curfew time and room allotment criteria for university hostels?"*, the system MUST produce an honest abstention (`answered_from_context: false`) rather than hallucinating external university hostel rules. |
| 7 | Exact-term content | `Academic Rules and Regulations.pdf` and `Academic-Rules-Undergrad-Aug-2023.pdf` | Precise clause citations (`1. Attendance Requirement`, `Clause 1.21`), exact GPA probation thresholds (`CGPA < 2.00`), course withdrawal deadlines (`Week 10`), minimum degree credit hours (`130`), and attendance thresholds (`80%` undergraduate, `75%` graduate). Tests whether retrieval and generator faithfully preserve numerical bounds and exact clause identifiers. |

---

## Invalidation & Version Governance

All documents are fingerprinted via SHA-256 in [`corpus/MANIFEST.md`](file:///C:/Users/Tawassul/Desktop/Rahbar-Starter/corpus/MANIFEST.md). Whenever university authorities publish updated regulations, new documents are ingested with an incremented `doc_version` and the older document is updated to `superseded: true`. The indexer writes this metadata into the Chroma vector store so the API can filter `where: {"superseded": False}`.
