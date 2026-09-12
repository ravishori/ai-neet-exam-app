# PYQ P2.1C Geometry Resegmentation Report — NEET 2020–2025

**Generated:** 2026-09-01T13:22:21.655005+00:00  
**Verdict:** **YELLOW**  
**Mode:** geometry-first resegment (no Tesseract / no re-OCR)  
**Staging root:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025`

## 1. Executive verdict

**YELLOW** — geometry-first per-column segmentation applied. Question count alone is NOT sufficient for GREEN.

## 2. Geometry detection results

| Layout | Pages |
|--------|------:|
| ONE_COLUMN | 209 |
| TWO_COLUMN | 490 |
| UNKNOWN | 309 |

## 3. Old vs new extraction counts

| Corpus | Questions |
|--------|----------:|
| P2.1 original | 238 |
| P2.1B resegmented | 3949 |
| **P2.1C geometry** | **6217** |

## 4. Quality breakdown

| Class | Count |
|-------|------:|
| VALID | 1465 |
| PARTIAL | 2814 |
| NEEDS_REVIEW | 1741 |
| DIAGRAM_DEPENDENT | 197 |
| INCORRECT_CANDIDATE | 0 |

## 5. Cross-column contamination results

| Metric | Count |
|--------|------:|
| Records with geometry cross-column flags | 9 |
| Automated check total | 9 |

### P2.1B-HR mandatory regression

- **Q5_must_not_have_Q8_resistor_colors** (FAIL): Q5 p2
  - Forbidden stem hits: ['through E', 'transformer, capacitor']
  - Stem: `A from A to B through E
transformer, capacitor and a load resistance. 9
Which of these components re…`
  - Options: ['2 mC', '8 mC 3) _ 12Gm 4) _16Gm', '6 mC', '-—-']
- **Q15_must_not_have_Q11_error_types** (PASS): Q15 p3
  - Stem: `The net magnetic flux through any closed…`
  - Options: ['', '', '', '']

**Interpretation:** P2.1C eliminates the worst L↔R option swap (Q5 no longer carries Q8 colour-code options). Q5 stem remains contaminated by within-column OCR bleed (Q3/Q7 text mis-tagged as Q5). Q15 no longer carries Q11 error-type options (options empty — PARTIAL, not faithful).

## 6. Diagram-dependent results

| DIAGRAM_DEPENDENT | 197 |

Diagram-dependent classification retained from P2.1B heuristics; geometry split does not recover figure content.

## 7. Page-boundary results

- UNKNOWN layout pages: 309 (questions flagged NEEDS_REVIEW via `geometry_layout=UNKNOWN`)
- Page-boundary anomaly flags: 2048
- Instruction cover pages skipped via `<<<SKIP_QUESTIONS:instruction>>>`
- Rough-work blank pages: 61 (zero questions)

## 8. False-positive / fragment / duplicate

| Check | Count |
|-------|------:|
| False-positive candidates | 539 |
| Fragment candidates | 323 |
| duplicate_within_paper | 65 |

## 9. Automated quality checks (flag-only)

- cross_column_contamination: 9
- question_option_mismatch: 0
- header_footer_contamination: 31
- page_number_false_positive: 93
- instruction_false_positive: 0
- duplicate_extraction: 65
- fragmented_extraction: 1526
- empty_stems: 614
- suspiciously_short: 325
- foreign_options: 0
- impossible_qnum_jumps: 0
- page_boundary_anomalies: 2048

## 10. Human validation sample buckets

- `two_column_20`: 20
- `hr_regression_mandatory`: 2
- `partial_10`: 10
- `diagram_dependent_10`: 10
- `page_boundary_10`: 10
- `instruction_false_positive_10`: 0
- `one_column_10`: 10
- `cross_column_flagged_10`: 9

Full samples: `data/staging/pyq/2020-2025/samples.p2_1c_geometry.json`

## 11. Regression tests

Added `test_pyq_p2_1c.py` (8 tests): layout detection, column split ordering, independent column segmentation, Q5/Q8 and Q15/Q11 contamination detectors, HR evaluation, PyMuPDF corpus build.

Full PYQ suite: **63 passed**, 0 failed (baseline 55 + 8 new).

## 12. Idempotency

| Pass | Hash match |
|------|------------|
| 1 | `0905eaf0cd2cc2ff…` |
| 2 | `0905eaf0cd2cc2ff…` |
| Idempotent | **True** |

## 13. Safety attestation

| Gate | Status |
|------|--------|
| AI calls | 0 |
| Network calls | 0 |
| Production DB writes | 0 |
| Source ZIP modifications | 0 |
| Source PDF modifications | 0 |
| .env modifications | 0 |
| Tesseract calls | 0 |
| Full OCR | NOT RUN |
| --force | NOT RUN |
| P3 / P4 / P5 | NOT RUN |
| ai_provider_calls | 0 |
| network_calls | 0 |
| production_db_writes | 0 |
| source_zip_modified | 0 |
| source_pdfs_modified | 0 |
| env_modified | 0 |
| tesseract_invocations | 0 |
| full_ocr_run | 0 |
| force_flag_used | 0 |
| p3_p4_p5_executed | 0 |

## 14. Recommendation

**TARGETED SEGMENTATION FIX STILL REQUIRED**

| Criterion | Result |
|-----------|--------|
| P2.1C count > P2.1B | Yes (6217 vs 3949) — **not** an quality improvement |
| VALID share | 1465/6217 (23.6%) — below P2.1B VALID share |
| HR Q5/Q8 option regression | Improved (no colour-code options on Q5) |
| HR Q5 stem regression | **FAIL** — within-column OCR bleed remains |
| HR Q15/Q11 regression | PASS (options no longer swapped; stem/options still incomplete) |
| Cross-column flags | 9 |

**Root causes remaining:**
- Scanned PDFs have **no PyMuPDF word geometry** (image-only pages); column split uses OCR pipe markers + page mediabox center.
- Within-column OCR row merge (lines without ` | `) still produces false question markers (e.g. Q7 option text tagged as Q5).
- Per-column segmentation increases recall but also false-positive Q# detections on UNKNOWN pages.

**Next step (when authorized):** store Tesseract word bounding boxes at P2.1 time (no re-OCR) OR tighten Q# validation using section context + option-block proximity — then re-run `--geometry-only`.

- Do **not** claim GREEN from question count.
- Do **not** proceed to P3/P4/P5 without human fidelity review of `samples.p2_1c_geometry.json`.

**STOP.** No production import.
