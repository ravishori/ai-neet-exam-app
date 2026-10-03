# Existing Book MCQ Extraction & Import — Audit

**Date:** 2026-10-03. **Zero AI/paid API calls.** Deterministic extraction only (PyMuPDF text layer; OCR not needed for the files actually extracted). **No database import performed** — extraction and dedup only, per the task's own "begin with a small local/staging batch and verify before continuing" and given the quality gaps disclosed in Section 6.

## 1. Material inventory

| File | Type | Text layer? | MCQs present? | Status |
|---|---|---|---|---|
| `PYExamPapers/2024/NEET 2024 Paper - Chemistry.pdf` | "Chapter & Topic-wise NEET PYQ's" compilation | **Yes, clean** (28,371 chars/12 pages) | Yes | **Extracted** |
| `PYExamPapers/2024/NEET 2024 Paper - Physics.pdf` | Same compilation style | **Yes, clean** (26,744 chars/12 pages) | Yes | **Extracted** |
| `PYExamPapers/2024/NEET 2024 Paper-Botany.pdf` | Same compilation style | **Yes, clean** (63,779 chars/20 pages) | Yes | **Extracted** |
| `PYExamPapers/NEET-2025-Answer-Key.pdf` | **Misleadingly named — this is the full 2025 exam *question* booklet** (confirmed by OCR of page 1: "Test Booklet... 180 multiple-choice questions... Physics, Chemistry and Biology"), not a standalone answer key | No (0 chars, scanned) | Yes, but needs OCR | **Not extracted this pass** — needs full-document OCR (not done; flagged, not fabricated) |
| `PYExamPapers/NEET-2026-WITH-WATER-MARK-COMP04.05.2026.pdf` | Third-party coaching-institute ("Brilliant Study Centre, Pala") mock paper, claims to include an answer key | No (1,949 chars total, mostly watermark noise) | Likely yes | **Not extracted** — scanned, needs OCR; lower source-priority (not NCERT/NTA) per this task's own Section 2 hierarchy |
| `PYExamPapers/RE-NEET-QUESTIONS-COMPRESSED.pdf` | Same coaching institute, a "re-test"/supplementary paper, claims an answer key | No (0 chars) | Likely yes | **Not extracted** — scanned, same institute, same caveat |
| `NCERT Books/Class {11,12}/*.zip` | Official NCERT textbooks | N/A | **No** — textbooks don't contain structured MCQs | Out of scope for this task (it's about extracting *existing MCQs*, and textbooks aren't MCQ sources) |

**Correction to a claim made in the immediately-prior task's report:** that report described `NEET-2025-Answer-Key.pdf` as "a genuine official answer key." **Direct inspection in this task shows that characterization was wrong** — it is the exam's question booklet, not a standalone key. Flagging this correction explicitly rather than letting it stand uncorrected.

## 2. Existing infrastructure inspected and reused

- PDF text extraction: PyMuPDF (`fitz`), already used throughout this session's prior OCR audits — reused unmodified.
- Database: `pyq.questions`, `pyq.source_files` (checksummed the 6 new files against existing `pyq.source_files.file_sha256` — **zero matches**, confirming these are not byte-identical re-uploads of already-registered sources).
- No new dependency added; no schema change.

## 3. Deterministic extraction — the 3 text-native files

A new, bounded regex-based parser (question-number line → stem lines → 4 lettered options) — **reported here as a new, one-off script, not claimed as a permanent pipeline addition**.

| Subject | Questions extracted |
|---|---:|
| Chemistry | 34 |
| Physics | 29 |
| Botany | 85 |
| **Total** | **148** |

- **8 of 148** reference a figure/diagram in the stem (`requires_figure: true`) — these were **extracted, not dropped**, but their stem text alone is incomplete without the image; flagged for separate handling, not imported as answer-ready.
- **Chapter/topic metadata extraction is unreliable** in the current parser (a lookback heuristic that did not reliably capture the preceding chapter heading in testing) — **not claimed as a working feature**; chapter/topic fields in the extracted JSON should not be trusted without a parser fix.
- **No answer, no explanation, and no difficulty rating exists anywhere in these 3 source files** — confirmed by direct reading of multiple pages; these are question-only compilations.

## 4. Answer-supported vs. answer-missing

**0 of 148 have a source-supplied or reliably-mapped answer.** No 2024-dated answer key was found among the newly provided materials (the only candidate, `NEET-2025-Answer-Key.pdf`, is itself unextracted and is for a different year regardless — see Section 1's correction). Per this task's own Section 4 rule, **none of these 148 can be imported with an answer**; all would go in as answer-missing/pending, exactly like the bulk of the existing 9,416 `ANSWER_PENDING` corpus.

## 5. Deduplication against the existing question bank (read-only check against local dev DB, 12,396 existing PYQs)

Method: normalized-text exact match (lowercased, punctuation/whitespace stripped, first 200 chars) — a strict, conservative check; **near-duplicate/fuzzy detection was not run** (disclosed limitation, not a completed check).

| Result | Count |
|---|---:|
| Exact normalized-text duplicates of an existing PYQ | **46 / 148 (31%)** |
| Unique candidates (no exact match found) | **102 / 148 (69%)** — upper bound, since fuzzy near-duplicates within this 102 were not separately checked |

**This 31% exact-duplicate rate is itself useful evidence**: it confirms these "Chapter & Topic-wise" compilations genuinely reproduce real, already-known NEET PYQ text (not fabricated or AI-paraphrased) — consistent with their being a legitimate, if reorganized, secondary compilation of real past-year questions, not a fresh/unverified source.

## 6. Database import

**Not performed in this task.** Reasons, stated plainly rather than silently skipped:
1. Chapter/topic metadata extraction is not yet reliable (Section 3).
2. Near-duplicate detection among the 102 "unique" candidates was not run — some may still overlap in intent with existing questions or with each other.
3. The 8 figure-dependent questions need a decision on how to represent "requires diagram" in the existing schema before import.
4. No answer exists for any of them — they would import as pure `ANSWER_PENDING`-equivalent, which is safe but should be a deliberate decision, not a default outcome of this pass.

**Recommended next step, not yet authorized or started:** fix the chapter-metadata lookback, add a near-duplicate pass (reusing whatever similarity tooling already exists in the Content Factory's `question_fingerprints` schema, not yet inspected for applicability here), then import the confirmed-unique, non-figure-dependent subset into a staging batch with `ANSWER_PENDING`-equivalent status, exactly as this task's own Section 9 anticipates as the next phase.

## 7. Tests

No code was added to the application (the extraction script is a one-off, kept as evidence only, not integrated into the pipeline) — **no new automated tests were written or required**. No pre-existing test suite was run in this task (no application code changed), consistent with the cost-discipline instruction from an earlier turn this session not to re-run the full suite without a reason.

## 8. Database counts before/after

**Unchanged: 12,396 PYQs before and after this task.** No import occurred.

## 9. Remaining accessible materials still requiring extraction

- `NEET-2025-Answer-Key.pdf` (actually the 2025 question booklet) — 30 pages, full OCR needed.
- `NEET-2026-WITH-WATER-MARK-COMP04.05.2026.pdf` — 30 pages, full OCR needed, third-party source.
- `RE-NEET-QUESTIONS-COMPRESSED.pdf` — 28 pages, full OCR needed, same third-party source.
- The 2024 NCERT textbook zips — confirmed not applicable (textbooks, not MCQ sources).

## 10. Recommendation for next phase

Given actual source coverage: the three deterministic-text files are the only genuinely cheap, high-confidence win available right now, and they're already extracted (148 questions, 102 likely-unique). The three scanned files could plausibly yield real official-exam-matched Q+A pairs (especially the 2025 question booklet, which explicitly states it has 180 questions) — but require a full 28–30 page OCR pass per file, not yet done, and the 2026/RE-NEET pair are third-party (not NCERT/NTA), so should be treated as lower-priority per this task's own source hierarchy even once OCR'd.

**Concrete next step, bounded and small:** (1) fix the chapter-metadata extraction bug, (2) OCR `NEET-2025-Answer-Key.pdf` fully (it may contain its own embedded answer key pages at the end, which would make it self-contained and highest-value — not yet checked), (3) only then decide on an actual staging import of the validated, deduplicated, non-figure-dependent subset. None of this was started beyond the inspection and extraction already reported here.
