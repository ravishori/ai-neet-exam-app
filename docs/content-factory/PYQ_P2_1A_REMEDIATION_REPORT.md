# PYQ P2.1A — Targeted Visual Validation + Segmentation Diagnostic

**Generated:** 2026-09-01  
**Mode:** Staging diagnostic + targeted code fix — no full OCR rerun, no DB writes, no AI  
**Prior P2.1 verdict:** YELLOW (unchanged; this phase does not claim GREEN)

## P2.1A VERDICT: READY FOR TARGETED FIX

Systemic multi-column OCR segmentation failure is confirmed by page visuals and OCR text.
Smallest targeted fixes are implemented and tested. **Full 31-paper resegmentation/OCR rerun is prepared but NOT executed** (per task gate).

---

## 1. Existing failure pattern

| Pattern | Evidence |
|---------|----------|
| **A. Multi-column reading order** | All 31 SCANNED papers are 2-column booklets. OCR lines merge left\|right (e.g. `1 A vehicle … \| 6 The amount …`). |
| **B. Question-number detection failure** | Extractor required `(?m)^\s*(\d{1,3})\.\s+`. OCR often drops `.` (`1 A vehicle`) and places Q# mid-line after `\|`. On OCR_SUCCESS pages: period_line=477 vs noperiod_line=3035, pipe_q=957. |
| **D. Rough-work / blank last pages** | 32/33 NEEDS_REVIEW pages are last pages with ~36 chars: `SPACE FOR ROUGH WORK` + footer. Misclassified as NEEDS_REVIEW despite successful OCR. |
| **F. Diagram-dependent options** | Several NEEDS_REVIEW questions reference circuits/graphs with empty options. |
| **Instruction false positives** | 2024 p48 bilingual instruction page (low confidence) produced garbage “questions”. |

Low yield (**238** questions / 31 papers) is primarily **algorithmic segmentation**, not OCR failure (OCR_FAILED=0, OCR_SUCCESS=975).

---

## 2. Evidence from the 32 NEEDS_REVIEW pages

Diagnostic artifact: `data/staging/pyq/2020-2025/diagnostics_p2_1a_needs_pages.json`  
Renders: `data/staging/pyq/2020-2025/diagnostics_p2_1a_renders/`

| Category | Count (approx) | Notes |
|----------|---------------:|-------|
| G / blank low-yield → actually rough-work | 32 | Last page “SPACE FOR ROUGH WORK”; visual confirm page 32 of 2023 papers |
| G OCR character / low confidence | 1 | 2024 `Paper_20250124133115.pdf` p48 bilingual instructions |
| A multi-column (on NEEDS_REVIEW set) | 1–2 | Same instruction page; content pages are multi-column but were OCR_SUCCESS |

**Note:** Count is 33 in staging JSON vs 32 reported at P2.1 (one extra page status edge). Treat as ~32 blank/rough-work + 1 instruction/low-confidence.

| Field | Typical blank last page |
|-------|-------------------------|
| text_chars | 36 |
| q_markers | 0 |
| opt_markers | 0 |
| confidence | ~88–95 |
| OCR text | `SPACE FOR ROUGH WORK\nG2_English \| 32` |

---

## 3. Evidence from the 14 NEEDS_REVIEW questions

Artifact: `data/staging/pyq/2020-2025/diagnostics_p2_1a_needs_questions_validated.json`

| Verdict | Count |
|---------|------:|
| PARTIAL | 7 |
| REQUIRES_RESEGMENTATION | 4 |
| DIAGRAM_DEPENDENT | 2 |
| INCORRECT | 1 |
| VALID | 0 |

Examples:
- **REQUIRES_RESEGMENTATION:** stems contain `\| 18 A full wave…` / `\| 64 — Given below…` (right column glued into left stem).
- **DIAGRAM_DEPENDENT:** circuit questions with empty/partial options.
- **INCORRECT:** instruction-page text mentioning “candidate” / attendance rules (2024 p48).

No answers were inferred.

---

## 4. Exact code/files modified

| File | Change |
|------|--------|
| `apps/backend/app/modules/cms/pyq/pyq_extraction.py` | `normalize_ocr_multicolumn_text` / `normalize_ocr_corpus`; OCR-tolerant `OCR_QUESTION_START_RE`; OCR section header `Physics : Section-A`; OCR-mode path in `segment_questions_from_text` |
| `apps/backend/app/modules/cms/pyq/pyq_ocr.py` | Rough-work blank pages → `OCR_SUCCESS` + anomaly `rough_work_blank_page` (not NEEDS_REVIEW) |
| `apps/backend/app/modules/cms/tests/test_pyq_p2_1.py` | New tests for de-interleave, OCR segmentation without periods, rough-work status, TEXT-mode unchanged |
| `apps/backend/scripts/diag_pyq_p2_1a.py` | Diagnostic locator (read-only) |
| `apps/backend/scripts/diag_pyq_p2_1a_questions.py` | 14-question validator (read-only) |
| `apps/backend/scripts/probe_pyq_p2_1a_reseg.py` | Read-only resegmentation probe on existing OCR text |

**Not modified:** source ZIP/PDFs, `.env`, DB, answer logic, production schemas.

---

## 5. Expected impact (probe only — not written to staging)

Read-only resegmentation of existing `ocr.pages.p2_1.jsonl` text (no re-OCR):

| Metric | Before (stored) | After (probe) |
|--------|----------------:|--------------:|
| Questions from OCR (31 papers) | 238 | **3949** |
| Delta | — | **+3711** |

Typical paper moves from ~2–15 extracted questions toward ~160–180 (NEET booklet scale). Remaining gaps: diagram options, bilingual instruction pages, residual OCR character errors.

Rough-work reclassification should drop most of the 32 NEEDS_REVIEW **pages** to OCR_SUCCESS (blank) on next OCR status pass / force refresh.

---

## 6. Tests

| Suite | Before P2.1A | After P2.1A |
|-------|-------------:|------------:|
| P0–P2.1 | 44 passed | **48 passed** |

Newly added:
- `test_normalize_ocr_multicolumn_deinterleaves_pipe_columns`
- `test_ocr_segmentation_recovers_questions_without_periods`
- `test_rough_work_page_classified_ocr_success`
- `test_text_mode_segmentation_unchanged_by_ocr_patterns`

Failures: **0**

---

## 7. Safety verification

| Check | Value |
|-------|------:|
| AI / Gemini / Anthropic / OpenAI / Mistral calls | 0 |
| Network OCR APIs | 0 |
| Production DB writes | 0 |
| cms.pyq tables | 0 |
| content_items / versions / KUs / ECAEP / publication | 0 |
| Source ZIP / PDF modified | 0 |
| `.env` modified | 0 |
| Full 31-paper OCR rerun executed | **0 (stopped)** |
| GREEN claimed | No |

---

## Exact next rerun command (DO NOT RUN YET unless authorized)

Resegment from cached OCR page text + refresh rough-work statuses (force regenerates `questions.p2_1.jsonl` / OCR manifests). Prefer a **resegment-only** pass if added later; until then the existing force OCR path works but re-runs Tesseract (~25+ min):

```powershell
Set-Location "D:\ravishori\AI Neet Exam App\apps\backend"
$env:PYTHONPATH="."
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
.\.venv\Scripts\python.exe scripts/run_pyq_ocr_p2_1.py --dpi 200 --force
```

**Recommended lighter follow-up (when authorized):** add a `--resegment-only` flag that rebuilds `questions.p2_1.jsonl` from existing `ocr.pages.p2_1.jsonl` without re-OCR, then update `manifest.p2_1.json`.

---

## STOP

P2.1A complete. No production import. No P3/P4/P5. Verdict remains **READY FOR TARGETED FIX** (code landed; corpus refresh pending explicit rerun authorization).
