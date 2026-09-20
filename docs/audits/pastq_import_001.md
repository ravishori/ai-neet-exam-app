# PASTQ-IMPORT-001 — Past Question Paper Import Pipeline

**Date:** 2026-09-14  
**Final verdict:** **YELLOW**  
**Source root (read-only):** `D:\ravishori\AI Neet Exam App\PastQuestionPapers`

| State | Status |
|-------|--------|
| IMPLEMENTED | YES |
| TESTED | YES (13/13 unit tests) |
| PILOT-IMPORTED | YES (10 DRAFT CMS items tagged `import:pastq-001`) |
| FULLY-IMPORTED | **NO** |
| VERIFIED (full 2015–2026 corpus) | **NO** |

---

## Summary counts

| Metric | Value |
|--------|------:|
| Files discovered | 15 |
| Files readable | 15 |
| Papers detected (excl. syllabus) | 14 |
| Papers requiring review | 2 |
| Questions extracted (text segmentable) | 1066 |
| Questions valid (structural) | 783 |
| Questions invalid | 283 |
| Questions requiring review | many (OCR placeholders + warnings) |
| Ready for CMS import (answer + 4 opts) | 20 |
| Answers detected | 169 |
| Answer conflicts | 0 |
| Visual-flagged | 102 |
| UNIQUE / DUPLICATE_WITHIN_IMPORT | 981 / 85 |
| Pilot DRAFTs created | 10 |
| PUBLISHED after pilot | **1479 (unchanged)** |
| IN_REVIEW | **111 (unchanged)** |
| Unmapped DRAFT (`concept_id IS NULL`) | 5034 (was 5024; +10 pilot DRAFTs) |

---

## Architecture

Reuses existing `cms.pyq` extraction (`extract_paper`) and `ContentWorkflowService.create_item`.

New package: `apps/backend/app/modules/cms/acquisition/pastq/`

| Module | Role |
|--------|------|
| `inventory.py` | SHA-256 inventory; never modifies sources |
| `paper_meta.py` | Deterministic year/set; conflict → NULL + NEEDS_REVIEW |
| `enrich.py` | Letter options (a–d), inline `Ans.(n)`, visual flags |
| `validate.py` | Structural + provenance-safe validation |
| `dedupe.py` | UNIQUE / DUPLICATE_WITHIN_IMPORT / POTENTIAL_DUPLICATE / DUPLICATE_EXISTING |
| `pipeline.py` | Dry-run extract → JSONL staging |
| `importer.py` | Idempotent DRAFT-only import; `origin=past_question_paper`; **not** NCERT |
| `cli.py` | CLI entrypoint |

Staging output: `data/staging/pastq_import_001/`

---

## Provenance isolation (critical)

Imported bodies use:

```json
"provenance": { "origin": "past_question_paper", ... }
```

- Tags include `not-ncert-derived`, `origin:past-question-paper`, `ecaep:intake-draft-only`
- `ncert_evidence` is **null** (not certified)
- `ncert_derived` is **never** set
- PastQuestionPapers is **never** used as NCERT source root

---

## Source inventory highlights

See `docs/audits/pastq_import_001_source_inventory.md`.

- 15 PDFs only (no EPUB/ZIP in folder)
- Scanned / empty-text (OCR required): NEET2015, 2017, 2021, 2022, 2026-11, 2026-12, RENeet2026
- Text-extractable: 2016, 2018, 2019, 2020, 2023, 2024, NEET2026.pdf (partial)
- `NeetSyllabus.pdf` excluded as non-paper
- **Year conflict:** `NEET2026.pdf` filename vs text `NEET (UG)-2025` → year NULL + NEEDS_REVIEW

---

## Safety verification

| Check | Result |
|-------|--------|
| Source PDFs unmodified | PASS |
| NCERT Books unmodified | PASS |
| No auto-publish | PASS (DRAFT only) |
| No NCERT certification | PASS |
| PUBLISHED unchanged 1479 | PASS |
| IN_REVIEW unchanged 111 | PASS |
| Existing 5024 unmapped rows not edited | PASS (10 **new** DRAFTs added) |
| ECAEP / Practice selection unchanged | PASS (code untouched) |
| Idempotent re-import | PASS after fix (already_exists) |

---

## Tests

`apps/backend/tests/test_pastq_import_001.py` — **13 passed**

Covers: inventory/SHA-256, year/set detection, conflicts, letter options, inline answers, conflicts, validation, duplicates, provenance not-NCERT, visual/mapping gaps, live NEET2019 sample.

---

## Commands used

```text
python -m app.modules.cms.acquisition.pastq.cli --dry-run
python -m app.modules.cms.acquisition.pastq.cli --import --pilot --limit 5
python -m pytest tests/test_pastq_import_001.py -q
```

---

## Known limitations (why YELLOW, not GREEN)

1. **Major OCR gap:** 7/15 PDFs are scanned/empty text — no reliable segmentation without OCR pipeline.
2. **Few import-ready rows:** only 20/1066 have both 4 options and associated answers (CMS schema requires `correct_option`).
3. **Subject/chapter/concept:** not auto-mapped (`ACADEMIC_MAPPING_REVIEW_REQUIRED`).
4. **NEET2023** uses `a./b./c./d.` — letter repair helps some, not all.
5. **Full corpus not imported** — by design STOP before bulk.
6. Pilot accidentally created **10** DRAFTs (5+5) before idempotency fix; subsequent runs are stable.

---

## Exact next recommended step

1. Run OCR path (`cms.pyq` P2.1 geometry/OCR) on the 7 scanned PDFs **into staging only**.
2. Improve answer-key association for papers without inline `Ans.(n)`.
3. Re-dry-run; import another small pilot only after OCR quality gates pass.
4. **Do not** bulk-import 2015–2026 until OCR + answer coverage is acceptable.

**Do not claim the full collection is imported.**
