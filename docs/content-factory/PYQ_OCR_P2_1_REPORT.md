# PYQ OCR P2.1 Report — NEET 2020–2025

**Generated:** 2026-09-01T12:34:59.147070+00:00  
**Verdict:** **YELLOW**  
**Mode:** Local Tesseract OCR + staging revalidation — no AI, no DB writes  
**Source ZIP:** `D:\ravishori\AI Neet Exam App\NEET_PYQ_OFFICIAL.zip`  
**ZIP SHA-256:** `4b5925fd554e6f3e37c446904c9b71719fc681994059c21d0f51813c610eda4a`  
**Staging root:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025`

## Environment

| Item | Value |
|------|-------|
| OCR engine | tesseract |
| Tesseract version | v5.5.0.20241111 |
| Discovery method | env_TESSERACT_CMD |
| DPI | 200 |

## Results

| Metric | Value |
|--------|------:|
| Papers targeted (SCANNED) | 31 |
| Pages targeted/processed | 1008 |
| OCR_SUCCESS | 975 |
| OCR_LOW_CONFIDENCE | 1 |
| OCR_FAILED | 0 |
| OCR NEEDS_REVIEW | 32 |
| Questions extracted from OCR | 238 |
| Questions requiring review | 14 |
| missing_options before | 296 |
| missing_options resolved | 0 |
| missing_options still_missing | 0 |
| missing_options needs_review | 296 |
| missing_options ocr_failed | 0 |
| ANSWER_KNOWN | 0 |
| ANSWER_PENDING | 238 |
| ANSWER_CONFLICT | 0 |
| Subject classified (OCR set) | 0 |
| Subject UNKNOWN (OCR set) | 238 |
| Mathematics count | 0 |
| 2022 status | SOURCE_MISSING |
| Source checksums unchanged | True |
| Idempotent second pass | True |

## Verdict rationale

Local OCR enabled and SCANNED papers processed, but explicit gaps remain:

- OCR_FAILED pages: 0
- OCR_LOW_CONFIDENCE pages: 1
- OCR NEEDS_REVIEW pages: 32 (typically cover/blank/low-yield pages — not treated as authoritative)
- Questions still NEEDS_REVIEW: 14
- missing_options remaining (needs_review+still_missing): 296 (all on TEXT papers with diagram/image options; OCR of SCANNED papers does not resolve them)
- ANSWER_KNOWN remains 0 (no authoritative keys invented)
- NEET 2022: **SOURCE_MISSING**
- Question segmentation yield from OCR text is low (**238** records across 31 papers) because multi-column scanned layouts often lack clean `N.` question markers after OCR. Full page OCR text is preserved in `ocr.pages.p2_1.jsonl` for review — we do **not** invent missing stems/options.

## Artifacts

```text
data/staging/pyq/2020-2025/
  manifest.p2_1.json
  checksums.p2_1.json
  missing_options.p2_1.json
  papers/{sha256}/
    ocr.p2_1.json
    ocr.pages.p2_1.jsonl
    questions.p2_1.jsonl
```

## Tests

P0 + P1 + P2 + P2.1 regression suite: **44 passed**.

## Safety attestation

| Check | Value |
|-------|------:|
| ai_provider_calls | 0 |
| gemini_calls | 0 |
| anthropic_calls | 0 |
| openai_calls | 0 |
| mistral_calls | 0 |
| content_factory_generation | 0 |
| production_db_writes | 0 |
| cms_pyq_tables | 0 |
| content_items_modified | 0 |
| content_versions_modified | 0 |
| knowledge_units_modified | 0 |
| ecaep_changes | 0 |
| publication_changes | 0 |
| original_zip_modified | 0 |
| original_pdfs_modified | 0 |
| env_modified | 0 |

**STOP.** No production import. Do not proceed to P3/P4/P5.
