# NCERT Physics Filename Parser Fix — Unblocking the 6 `leph2NN.pdf` Sources

**Date:** 2026-10-01
**Repository:** `ravishori/ai-neet-exam-app`
**Branch:** `feat/whatsapp-m2a-account-linking`
**Local database:** `trinetra_db` @ `localhost:5432`, `ENVIRONMENT=development` — re-confirmed fresh, `alembic current` → `d9c6e1a8f9ed` (head, unchanged, no new migration needed).

## Executive summary

Extended `extract_ncert_chapter_number()` with a second, narrowly-scoped regex recognizing NCERT's own `leph2NN.pdf` naming convention (Physics Class 12, Part 2), mapping `NN` to chapter number `NN + 8` — continuing Part 1's chapters 1–8. This is a **mechanical filename-to-number extraction fix only**; the actual chapter identity for each of the 6 files was already directly verified against real page content in the prior mapping task, not re-derived or guessed here. Dry-run confirmed all 6 resolve to their intended taxonomy codes before any write. Applied: **74/76 sources now mapped** (up from 68/76). Ingested: **74 new knowledge units** (0 errors, 0 rejected). Idempotency re-verified. Retrieval coverage: **3,647 → 3,868/9,944 pending PYQs (36.7% → 38.9%)**, with the gain entirely in Physics as expected.

**No PYQ answer was touched. No Gemini call was made. Production was never accessed.**

## 1. Inspection

- **Parser:** `app/modules/ingestion/services/study_material_ncert_parser.py` — single function, single regex (`chapter-(\d+)\.pdf$`), returns `None` for anything that doesn't match.
- **Registry:** `app/modules/ingestion/services/study_material_academic_registry.py` — `EXPLICIT_NCERT_MAPPINGS` keyed by `(source_subject_code, class_level, ncert_chapter_number)`; `lookup_explicit_mapping()` returns `None` immediately if the chapter number is `None` (confirmed by reading the function — `if ncert_chapter_number is None: return None`), which is exactly why the 6 `leph2NN.pdf` files could never resolve regardless of registry content.
- **Ingestion pipeline:** unchanged, reused as-is (`IngestionPipelineService.start_source_ingestion_job` / `run_source_ingestion`, `DeterministicStructuringService` — no AI).
- **Tests:** `app/modules/ingestion/tests/test_study_material_ncert_parser.py` (5 existing cases, all for `chapter-N.pdf` variants) — none exercised the `leph2` naming at all.
- **Working tree:** all prior uncommitted work (today's 5 earlier tasks) confirmed preserved before and after, via `git status --short`.

## 2. Exact filenames (confirmed from the database, not assumed)

```sql
SELECT relative_source_path FROM ingestion.source_documents WHERE relative_source_path LIKE '%leph2%';
```
```
Physics/Class 12-Physics/leph201.pdf
Physics/Class 12-Physics/leph202.pdf
Physics/Class 12-Physics/leph203.pdf
Physics/Class 12-Physics/leph204.pdf
Physics/Class 12-Physics/leph205.pdf
Physics/Class 12-Physics/leph206.pdf
Physics/Class 12-Physics/leph2an.pdf        -- Appendices, not a chapter
Physics/Class 12-Physics/leph2dd/leph2ps.pdf -- cover page, not a chapter
```

## 3. Parser change (minimal, additive)

Added one new regex, `_LEPH2_PART2_RE = re.compile(r"^leph2(\d{2})\.pdf$", re.IGNORECASE)`, checked only after the existing `chapter-(\d+)\.pdf$` pattern fails to match — so every previously-supported filename format is tried first and behaves identically to before. When `leph2NN.pdf` matches, the chapter number returned is `NN + 8` (Part 2 continues Part 1's numbering, which stops at Chapter 8 — confirmed directly: the 7 `ncert-book-class-12-physics-part-1-chapter-N.pdf` files registered in this database only go up to N=8).

**Why `leph2an.pdf` and `leph2dd/leph2ps.pdf` are correctly excluded by this same regex, not by a separate exception:** the pattern requires exactly two digits (`\d{2}`) immediately before `.pdf`. "an" and "ps" are not digits, so the regex simply never matches them — they continue returning `None`, identical to their behavior before this change. No special-case code was needed or added.

**File changed:** `app/modules/ingestion/services/study_material_ncert_parser.py` (12 lines added, 0 removed from existing logic — the original regex and its handling are untouched).

## 4. The six mappings and their evidence

**No new content verification was performed this round** — the chapter identity for each file was already directly confirmed against real page text in the immediately preceding task (`docs/quality/ncert-manual-mapping-expansion-2026-10-01.md`). This task only had to (a) make the chapter number extractable, and (b) apply the already-verified mapping.

| File | NCERT chapter (verified content, prior task) | Taxonomy code | Evidence (from prior task) |
|---|---|---|---|
| `leph201.pdf` | 9 — Ray Optics and Optical Instruments | `PHYSICS-U16` (Optics) | Header "Chapter Nine RAY OPTICS AND OPTICAL INSTRUMENTS" |
| `leph202.pdf` | 10 — Wave Optics | `PHYSICS-U16` (same unit as Ch9) | Header "Chapter Ten WAVE OPTICS" |
| `leph203.pdf` | 11 — Dual Nature of Radiation and Matter | `PHYSICS-U17` | Header "Chapter Eleven DUAL NATURE OF RADIATIO[N]..." |
| `leph204.pdf` | 12 — Atoms | `PHYSICS-U18` | Content: atomic structure, Thomson/Rutherford models, "Chapter Twe[lve]" |
| `leph205.pdf` | 13 — Nuclei | `PHYSICS-U18` (same unit as Ch12) | Header "Chapter Thirteen NUCLEI" |
| `leph206.pdf` | 14 — Electronic Devices | `PHYSICS-U19` | Content: semiconductor diodes, vacuum tubes, electronic devices |

Registry entries added to `EXPLICIT_NCERT_MAPPINGS` for `("PHYSICS", "12", 9)` through `("PHYSICS", "12", 14)` — no collision with the existing Part-1 entries (which only cover chapter numbers 1–8).

## 5. Dry-run (required before any write)

```python
# resolve_mapping_for_source() does not persist; session.rollback() confirms no write occurred
```
```
Physics/Class 12-Physics/leph201.pdf -> MAPPED PHYSICS-U16 PHYSICS 9
Physics/Class 12-Physics/leph202.pdf -> MAPPED PHYSICS-U16 PHYSICS 10
Physics/Class 12-Physics/leph203.pdf -> MAPPED PHYSICS-U17 PHYSICS 11
Physics/Class 12-Physics/leph204.pdf -> MAPPED PHYSICS-U18 PHYSICS 12
Physics/Class 12-Physics/leph205.pdf -> MAPPED PHYSICS-U18 PHYSICS 13
Physics/Class 12-Physics/leph206.pdf -> MAPPED PHYSICS-U19 PHYSICS 14
Physics/Class 12-Physics/leph2an.pdf -> UNMAPPED None None None
Physics/Class 12-Physics/leph2dd/leph2ps.pdf -> UNMAPPED None None None
```
All 6 resolved to exactly their intended taxonomy entries; both non-chapter files correctly stayed unmapped. **No source mapping was ambiguous** — this task's stop condition was never triggered.

## 6. Applied mapping

```
.venv/Scripts/python.exe -m app.modules.ingestion.cli.study_material map
mapped=74 (up from 68), unmapped=2 (the 2 non-chapter files, unchanged)
```

| | Before | After |
|---|---:|---:|
| Mapped sources | 68/76 | **74/76** |
| Physics mapped | 20/28 | **26/28** |
| Unmapped | 8 (6 leph2 + 2 non-chapter) | **2** (only the 2 non-chapter files) |

## 7. Ingestion (deterministic, no AI)

```
leph201.pdf: COMPLETED, 28 sections, 22 KUs created, 0 rejected
leph202.pdf: COMPLETED, 14 sections, 14 KUs created, 0 rejected
leph203.pdf: COMPLETED, 15 sections, 12 KUs created, 0 rejected
leph204.pdf: COMPLETED, 13 sections,  8 KUs created, 0 rejected
leph205.pdf: COMPLETED, 14 sections, 11 KUs created, 0 rejected
leph206.pdf: COMPLETED, 11 sections,  7 KUs created, 0 rejected
Total: 95 sections, 74 KUs created, 0 rejected, 0 errors
```

### Knowledge-unit counts, before/after

| Metric | Before this task | After |
|---|---:|---:|
| Total knowledge units | 1,038 | **1,112** |
| `PASSED` | 912 | **986** |
| `FAILED` | 126 | 126 (unchanged — no new failures) |

### Provenance verification (sample, `leph201.pdf`)

```sql
SELECT ku.concept_id IS NOT NULL, ku.source_section_id IS NOT NULL, ku.content_hash IS NOT NULL, s.source_page, ku.extraction_confidence
FROM knowledge.knowledge_units ku JOIN ingestion.ingestion_sections s ON s.id = ku.source_section_id ...
```
All sampled rows: `concept_id` populated, `source_section_id` populated, `content_hash` populated, `source_page` populated (1, 2, 3, 4, 8 — real page numbers), `extraction_confidence = 0.85` (the fixed deterministic-path value, consistent with every other knowledge unit in this database). No fabricated metadata.

### Idempotency

Re-ran ingestion for all 6 sources without `force_rerun` immediately after: all 6 correctly reused their existing `COMPLETED` job (`source_ingestion_skip_run`), `ku_created: 0, ku_rejected: 0` — `knowledge.knowledge_units` count unchanged at 1,112 before and after the re-run.

## 8. Retrieval coverage (direct code, no Gemini)

| | Before this task | After |
|---|---:|---:|
| Knowledge units in index | 1,038 | 1,112 |
| Pending PYQs with non-empty retrieval context | 3,647 | **3,868** |
| Coverage | 36.7% | **38.9%** |

| Subject | Before (matched/total) | After (matched/total) | Change |
|---|---:|---:|---:|
| (null) | 2,067 / 5,598 | 2,184 / 5,598 | +117 |
| Chemistry | 435 / 1,118 | 435 / 1,118 | 0 |
| Botany | 480 / 1,053 | 480 / 1,053 | 0 |
| Zoology | 385 / 1,086 | 385 / 1,086 | 0 |
| Physics | 280 / 1,089 | **384 / 1,089** | **+104** |

The entire gain is in Physics (+104) and the unclassified-subject pool (+117, plausibly Physics-topic questions from the 2020/2023/2024/2025 batches that don't carry a `subject` label) — Chemistry/Botany/Zoology are exactly unchanged, confirming the new knowledge units are being matched only by genuinely relevant (Optics / Dual Nature / Atoms-Nuclei / Electronic Devices) PYQs, not leaking into unrelated subjects. **This is retrieval coverage, not answer correctness**, consistent with every prior report.

## 9. Tests, lint, type-check

```
.venv/Scripts/python.exe -m pytest app/modules/ingestion/tests/ app/modules/knowledge/tests/ tests/test_pyq_resolver_worker.py -q
137 passed, 17 skipped, 7 warnings in 16.37s
```
(123 from before + 14 new: 2 regression-protection cases for the existing pattern were already covered, plus 8 new `leph2NN.pdf` positive cases, 6 new negative cases for non-chapter/malformed filenames.)

```
.venv/Scripts/python.exe -m ruff check app/modules/ingestion/services/study_material_academic_registry.py app/modules/ingestion/services/study_material_ncert_parser.py app/modules/ingestion/tests/test_study_material_ncert_parser.py
All checks passed!
```
`mypy`: not installed in this `.venv` — not run, consistent with every prior task today.

## 10. Database integrity

```
pyq.questions: 12,396 total / 2,452 verified / 9,944 pending — unchanged
pyq.answer_assertions: 2,452 — unchanged
knowledge.knowledge_units: 1,038 → 1,112 (+74, all new, 0 overwrites)
ingestion.source_academic_mappings: 68 → 74 MAPPED (+6, 0 overwrites of the prior 68)
```
No `pyq.*` table was written to at any point in this task. `git status --short` before/after confirms no unrelated working-tree file was touched — only the 3 files listed below plus this report changed.

## 11. Remaining limitations

- The 2 genuinely non-chapter files (`leph2an.pdf` appendix, `leph2dd/leph2ps.pdf` cover page) remain permanently unmapped — correct, not a gap.
- No other taxonomy or mapping gaps are currently known — this closes the last open item from the prior two reports' "outstanding decisions" sections.

## Confirmations

- **No Gemini or Claude API call was made.**
- **No PYQ answer value or status was changed.**
- **Production was never accessed or modified.**
- Nothing was committed, pushed, or merged.

## Files changed

- `apps/backend/app/modules/ingestion/services/study_material_ncert_parser.py` — parser extension.
- `apps/backend/app/modules/ingestion/services/study_material_academic_registry.py` — 6 new registry entries + updated comments.
- `apps/backend/app/modules/ingestion/tests/test_study_material_ncert_parser.py` — 14 new test cases.

## Related audit update

`docs/quality/pyq-coverage-audit.md` updated with a dated pointer to this report — prior baseline and all history preserved, unchanged.
