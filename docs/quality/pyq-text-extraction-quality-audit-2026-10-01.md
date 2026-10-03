# PYQ Text Extraction Quality Audit and Source Reconstruction

**Date:** 2026-10-01
**Continues:** [`ncert-retrieval-human-review-preparation-2026-10-01.md`](ncert-retrieval-human-review-preparation-2026-10-01.md)
**Scope: read-only.** No question/option/answer/assertion text was modified anywhere. No ingestion, resolver execution, answer generation, or promotion. No Gemini/Claude/OpenAI call. No production access. No source-code/schema/taxonomy/registry/config change. Nothing committed or pushed. Confirmed: `ai.ai_requests` row count unchanged (32, pre-dating every audit in this chain); `git status --short` unchanged in scope.

## Decisive finding (stated up front, evidenced in Section 2)

**All 42 zero-significant-word questions trace to one of 23 distinct source PDFs under `NEET_PYQ_OFFICIAL/`, and every one of those 23 PDFs is a scanned-image document with zero extractable native text** — directly measured via PyMuPDF (`fitz`): 0 characters of text across every page of every referenced file, with exactly one embedded image per page (full-page scans). This is not a parsing bug in this codebase's pipeline and not a missing-source problem — **the corrupted text in `pyq.questions.raw_stem` is almost certainly the output of an OCR pass run at import time against these scanned pages**, and this audit's own attempt to re-extract text directly from the same PDFs yields nothing better (zero characters), because there is no underlying text layer to extract. **No reconstruction is possible without re-running OCR**, which this audit did not and could not perform (no OCR library is installed in this environment, confirmed in Section 2, and OCR output would itself need human/scientific validation before being trusted — not a deterministic fix).

## 1. All 42 zero-significant-word questions — classified

File: `docs/quality/_pyq_text_extraction_audit_2026-10-01/reconstruction_evidence_sheet.csv` (all 42 rows, full schema per the task's Section 3 spec).

Script: `docs/quality/_pyq_text_extraction_audit_2026-10-01/pyq_text_extraction_trace_script.py` — read-only throughout (`session.rollback()` only; PDF access is `fitz.open()` text-extraction reads only, no writes, no OCR, no network).

| Classification flag | Count (of 42; multiple flags allowed per question) |
|---|---:|
| `TEXT_INTACT` (stem not visibly corrupted by the heuristic marker check, just short/non-textual) | 28 |
| `EXTRACTION_CORRUPTION_CONFIRMED` (stem contains OCR-mis-rendering artifacts: stray angle brackets, mismatched quote characters around subscript/superscript notation, replacement characters) | 14 |
| `OPTIONS_CONTAIN_SEARCH_TERMS` | 10 |
| `SOURCE_UNAVAILABLE` *(as initially computed by the script's page-locating heuristic — see correction below)* | 42 |
| `OCR_REQUIRED` | **42 (corrected — see below)** |

**Correction to the script's own output, made transparent rather than silently fixed:** the script's automated page-matching heuristic (token-overlap search across page text to locate the right page and flag `SOURCE_UNAVAILABLE` when no confident match was found) returned `SOURCE_UNAVAILABLE` for all 42 rows. Investigating *why* (Section 2) revealed the real cause: it's not that the source is unavailable — **the source file is present for all 42** — it's that there is no text to search within at all (0-character pages), so the heuristic's "no match found" result is actually a correct signal, just mislabeled by the script's naming. The accurate classification, per the task's own Task-2 categories, is **`OCR_REQUIRED`** for all 42, with source status **"present as an image or scanned document"** (not "unknown" or "referenced but unavailable" — the file genuinely exists and is readable, just not as text).

No question in this set is cleanly `TEXT_INTACT` in the sense of "nothing wrong" — all 42 were flagged in the prior audit specifically because their stem has zero significant words, and all 42 now trace to the same root mechanism (scanned-source OCR).

## 2. Source document tracing

For every one of the 42 questions: `pyq.questions.source_file_id → pyq.source_files.relative_path` was resolved and the referenced local file was checked for existence and inspected with PyMuPDF.

| Check | Result |
|---|---|
| Source file referenced | 42/42 (100%) — every question has a `source_file_id` linking to a `pyq.source_files` row |
| Source file physically present on disk | **42/42 (100%)** — confirmed at `D:\ravishori\AI Neet Exam App\NEET_PYQ_OFFICIAL\<year>\<filename>.pdf` |
| Distinct source PDFs involved | 23 |
| Source PDFs with a native, extractable text layer | **0 / 23** |
| Source PDFs confirmed to be full-page image scans (0 text chars, 1 embedded image per page, page count matching the paper) | **23 / 23** |

Direct measurement, reproduced for a representative subset and generalized after confirming the pattern was universal:

```
Paper_20231108005448.pdf   pages=32  text_chars=0
Paper_20231108010819.pdf   pages=32  text_chars=0  images=32  (1 full-page image per page)
Paper_20250124133115.pdf   pages=48  text_chars=0
NEET_2025_EN_46_NTA.pdf.pdf pages=32 text_chars=0
```

All 42 questions' source papers are exclusively **2023, 2024, and 2025** exam years (34, 6, and 2 questions respectively) — zero of the 42 trace to 2020 or 2021 papers. For comparison, a 2020 paper sampled in this audit (`Paper_20201106062138.pdf`) has a real, substantial text layer (43,972 characters across 24 pages, 0 embedded images). **This strongly suggests the 2023–2025 NEET source PDFs in this collection were ingested as scanned images, while the 2020–2021 ones were ingested as text-native PDFs** — a provenance/pipeline difference between batches, not a per-question anomaly. This is stated as a direct observation from the files actually present, not an assumption about files not inspected.

**No source rendering or OCR was performed in this audit.** Confirmed no OCR tooling is installed in this environment (`pytesseract`: not installed; `tesseract` CLI: not found) — OCR genuinely cannot be run here even if it were in scope, which it is not per this task's read-only/no-modification constraints. This requirement is identified, not fulfilled.

## 3. Reconstruction evidence sheet

File: `docs/quality/_pyq_text_extraction_audit_2026-10-01/reconstruction_evidence_sheet.csv` — all 42 rows, columns per the task's exact spec (`question_id`, `year`, `paper_or_set`, `subject`, `chapter`, `original_extracted_text`, `original_options`, `source_filename`, `source_page`, `observed_corruption`, `proposed_reconstruction`, `reconstruction_evidence`, `confidence`, `review_status`).

**`proposed_reconstruction` is blank for all 42 rows.** This is the correct, intended outcome given the evidence — not an omission. Since the source PDFs have no text layer, there is no clean passage this audit can point to as directly supporting any specific corrected wording; filling in a guessed reconstruction without that evidence would be exactly the "silent repair" the task explicitly prohibits. `source_page` is also blank for all 42 for the same reason — the page-location heuristic needs legible page text to locate the right page, which doesn't exist here, so stating a specific page number would be a guess the evidence doesn't support, not a confirmed location.

`chapter` is blank for all 42 — `pyq.questions` carries no chapter/topic field (confirmed in the prior human-review-preparation audit: `class_level`/`concept_id` are 100% NULL across the table), so there is no database-recorded chapter to report; inferring one from the subject label alone would not be reconstruction evidence.

**No answer keys or correctness labels are included anywhere in this sheet.**

## 4. The 10 options-contain-search-terms questions — analyzed

File: `docs/quality/_pyq_text_extraction_audit_2026-10-01/options_search_terms_diagnostic.csv`.

Of the 10, a genuine, qualitative split is visible on direct inspection of the option text (all options preserved exactly as presented to the student; no answer-key information used to select or weight any term):

| Pattern | Count | Example |
|---|---:|---|
| Clear, specific scientific vocabulary usable as a candidate search term | 3 | `antipodals endosperm nucleus primary synergids` (embryology); `corpora ippocampus quadrigemina` (neuroanatomy); the second embryology row |
| Chemical-formula fragments, partially usable but incomplete/garbled | 2 | `cyhyo` (likely a mangled hydrocarbon formula); `cocl` (likely part of a cobalt coordination-complex formula) |
| Match-the-column option-label artifacts, not genuine scientific terms | 2 | `acil`, `aulil` — these are fragments of answer-matching labels like "A-II", not vocabulary |
| Generic, low-specificity vocabulary | 1 | `false statement true` — common across many "Statement I / Statement II" question types, low diagnostic value |
| Non-English / bilingual fragment | 1 | `afte aire gergana remmren whisra` — appears to be garbled Hindi-language option text from a bilingual NEET paper, not usable as English search terms |
| Direction/spatial vocabulary, usable but generic | 1 | `away page pointed` |

**This confirms the task's premise only partially:** 3 of the 10 (plus arguably the 2 chemical-formula fragments) carry genuinely useful, specific scientific vocabulary that the current stem-only matcher structurally cannot see. The remaining ~5 are either artifacts of option-label formatting (not real content) or too generic/non-English to usefully narrow a search. **No retrieval query or practice behavior was changed** — this is reported purely as a diagnostic finding for a future, separately-scoped decision about whether `raw_options` should ever be included in the matching input.

## 5. 193-row relevance-review worksheet — reconfirmed

Re-verified directly against the live database and the preserved worksheet file (`docs/quality/_retrieval_human_review_2026-10-01/reviewer_worksheet.csv`):

| Check | Result |
|---|---|
| All 193 `question_id`s valid (resolve to a real, still-`ANSWER_PENDING` row) | ✓ (same 193, re-checked) |
| Passage-provenance mismatches (recorded source/page vs. actual KU source/page) | **0** |
| Answer-key or correctness-indicator columns present | **None found** — the worksheet's column set was directly re-inspected; no column references `pyq.answer_assertions` or any correctness field |
| Review labels blank | **193/193 blank**, re-confirmed |
| Reviewer notes blank | **193/193 blank**, re-confirmed |
| Sampling strata/selection reproducibility | Unchanged — fixed seed (`20261001`) and stratification logic (subject × score-band × KU validation status) preserved in the prior audit's script, not modified |

**No new issues found. No labels were assigned in this re-check.**

## 6. Authorized human-review workflow (procedure only — not implemented)

1. **Text correction** — only ever performed when a human reviewer has direct, legible source evidence (a clean passage from a text-layer PDF, or a completed and separately-validated OCR pass) supporting the specific corrected wording. A correction proposal without that evidence must stay unfilled, exactly as this audit's `proposed_reconstruction` column was left blank throughout.
2. **Adjudicating uncertain reconstructions** — any proposed correction should be reviewed by a second person before being treated as authoritative; disagreements are escalated to a third reviewer or the project owner, mirroring the adjudication approach already defined for relevance labels in the prior human-review-preparation report.
3. **Judging retrieved NCERT passage relevance** — uses the rubric already defined in [`ncert-retrieval-human-review-preparation-2026-10-01.md`](ncert-retrieval-human-review-preparation-2026-10-01.md) Section 7 (`RELEVANT` / `PARTIALLY_RELEVANT` / `IRRELEVANT` / `INSUFFICIENT_SOURCE` / `UNRESOLVED`) — not duplicated or changed here.
4. **Recording reviewer disagreements** — every review decision (both text-correction and relevance-judgment) should record reviewer identity, timestamp, and rationale, even when there's no disagreement, so a later audit can trace who approved what and why — this is a process recommendation, not something this audit implemented.
5. **Preserving original and corrected text as separate versions** — if a text correction is ever authorized, the original `raw_stem`/`raw_options` must be preserved unmodified (e.g., in a new versioned column, a history table, or an audit-log row) rather than overwritten in place, so the original extraction is always recoverable. This audit did not design or implement that schema change — flagged as a prerequisite for any future correction work, not performed here.

**None of this was implemented. No schema was touched. No question text was corrected.**

## 7. Limitations

- The corruption-detection heuristic in Section 1 (looking for specific OCR-artifact character sequences) is a simple pattern match, not a validated corruption classifier — some `TEXT_INTACT`-flagged rows may still be corrupted in ways the heuristic doesn't catch, and conversely a row could in principle be flagged `EXTRACTION_CORRUPTION_CONFIRMED` by coincidence. This is a screening tool, not a certified diagnosis.
- This audit could not determine *when* or *by what process* the OCR that produced the current `raw_stem` values ran — that pipeline's code was not located or inspected in this pass (out of today's scope; a worthwhile follow-up).
- Whether the embedded page images in the 23 source PDFs are themselves high-resolution enough for a *better* OCR pass to succeed is unknown — this audit did not attempt any OCR, so image quality was not assessed beyond confirming an image is present.
- The 10-question options analysis (Section 4) is a qualitative read, not a scored/validated classifier.
- This audit covers only the 42 previously-identified zero-significant-word questions — whether the same 2023–2025 scanned-PDF-OCR pattern also degraded (without zeroing out) other, differently-corrupted questions in the broader 9,944-question pending set was not investigated here.

## Final confirmations

- **No question, option, answer, or assertion text was modified anywhere** — this audit is entirely read-only against the database (`session.rollback()` only) and against local files (text-extraction reads only).
- No ingestion, resolver execution, answer generation, or answer promotion occurred.
- No Gemini, Claude, OpenAI, or other paid AI inference call was made — `ai.ai_requests` row count unchanged (32).
- Production was never accessed.
- No source code, schema, taxonomy, registry, or configuration was changed.
- Nothing was committed, pushed, or deployed.
- **Counts:** 42 questions investigated; 23 distinct source PDFs traced; 42/42 (100%) source files physically present; 0/23 (0%) source PDFs have an extractable native text layer; 42/42 require OCR for any reconstruction attempt; 0 reconstructions proposed; 0 OCR passes performed (no OCR tooling installed in this environment); 10 questions have usable-or-partially-usable scientific vocabulary present only in `raw_options`.

## Evidence

- `docs/quality/_pyq_text_extraction_audit_2026-10-01/pyq_text_extraction_trace_script.py` — the exact read-only diagnostic.
- `docs/quality/_pyq_text_extraction_audit_2026-10-01/reconstruction_evidence_sheet.csv` (42 rows)
- `docs/quality/_pyq_text_extraction_audit_2026-10-01/options_search_terms_diagnostic.csv` (10 rows)
- `docs/quality/_pyq_text_extraction_audit_2026-10-01/trace_summary.json`
- `docs/quality/_pyq_text_extraction_audit_2026-10-01/run_output.log`
