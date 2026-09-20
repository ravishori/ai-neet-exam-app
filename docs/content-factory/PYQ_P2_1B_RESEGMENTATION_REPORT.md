# PYQ P2.1B Resegmentation Report — NEET 2020–2025

**Generated:** 2026-09-01T12:59:19.095415+00:00  
**Verdict:** **YELLOW**  
**Mode:** `--resegment-only` (no Tesseract / no re-OCR)  
**Staging root:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025`

## 1. Verdict

**YELLOW** — extraction rose from 238 → 3949 and matches the P2.1A probe, but **~44% of records are not VALID** (PARTIAL 1500 + NEEDS_REVIEW 191 + DIAGRAM_DEPENDENT 71). That is too high for GREEN. Quantity alone is insufficient.

Key reliability gaps:
- Many options still missing after OCR (diagrams / layout / OCR option loss)
- 77 fragment candidates and 40 within-paper hash duplicates remain classified, not deleted
- Sample bucket `missing_period_10` only filled 5 (de-interleave often restores `N.` form)
- `bilingual_instruction_10` sample empty (instruction pages largely excluded from question yield)


## 2. OLD vs NEW question counts

| Metric | Value |
|--------|------:|
| OLD (`questions.p2_1.jsonl`) | 238 |
| NEW (`questions.p2_1_resegmented.jsonl`) | 3949 |
| Delta | +3711 |
| Probe expectation (~3949) | reference only — not assumed correct |

## 3. False-positive analysis

| Quality class | Count |
|---------------|------:|
| VALID | 2187 |
| NEEDS_REVIEW | 191 |
| PARTIAL | 1500 |
| DIAGRAM_DEPENDENT | 71 |
| INCORRECT_CANDIDATE | 0 |

Instruction/header candidates: **0**

## 4. Duplicate / fragmentation analysis

| Check | Count |
|-------|------:|
| duplicate_within_paper (hash) | 40 |
| duplicate question_number groups within paper | 0 |
| fragment candidates | 77 |
| header/instruction candidates | 0 |

```json
{
  "duplicate_qnum_within_paper_groups": 0,
  "duplicate_normalized_within_paper_extra": 1,
  "fragment_candidates": 77,
  "header_or_instruction_candidates": 0
}
```

## 5. Sample validation results

| Sample bucket | N |
|---------------|--:|
| ordinary_20 | 20 |
| two_column_20 | 20 |
| missing_period_10 | 5 |
| page_boundary_10 | 10 |
| with_options_10 | 10 |
| diagram_dependent_10 | 10 |
| bilingual_instruction_10 | 0 |
| previously_missed_high_qnum_10 | 10 |

Full sample payloads: `data/staging/pyq/2020-2025/samples.p2_1b.json`

## 6. Rough-work handling

Rough-work blank pages annotated: **61**  
Status forced to OCR_SUCCESS with `rough_work_blank_page=true`; excluded from question corpus.

## 7. Instruction-page handling

Expanded instruction markers; quality class INCORRECT_CANDIDATE for instruction-like stems. Records retained for review (not auto-deleted).

## 8. Diagram-dependent handling

DIAGRAM_DEPENDENT: **71** (missing options + diagram cues). No invented option text.

## 9. Missing-options comparison

NEW missing_options count: **1733**  
Answers remain ANSWER_PENDING; no answer invention.

| Answer status | Count |
|---------------|------:|
| ANSWER_PENDING | 3949 |
| ANSWER_KNOWN | 0 |

## 10. Idempotency

| Pass | Corpus hash |
|------|-------------|
| 1 | `c3b6155d7396c38c56028fed8a26545703cc223286a9f8cdbe189b14b748657e` |
| 2 | `c3b6155d7396c38c56028fed8a26545703cc223286a9f8cdbe189b14b748657e` |
| Identical | **True** |

## 11. Tests

| Suite | Result |
|-------|--------|
| P0–P2.1 + P2.1B | **55 passed**, 0 failed |

P2.1B added regression coverage for deterministic staging IDs, rough-work exclusion, instruction/diagram quality classes, canonical hash idempotency, and resegment module exports.

## 12. Page / paper metrics

| Metric | Value |
|--------|------:|
| Papers | 31 |
| Pages | 1008 |
| OCR_SUCCESS | 1007 |
| OCR_LOW_CONFIDENCE | 1 |
| OCR_FAILED | 0 |
| OCR NEEDS_REVIEW pages (raw status) | 0 |

### By year

```json
{
  "2023": 2874,
  "2024": 473,
  "2025": 602
}
```

## 13. Safety attestation

| Check | Value |
|-------|------:|
| ai_provider_calls | 0 |
| network_calls | 0 |
| production_db_writes | 0 |
| source_zip_modified | 0 |
| source_pdfs_modified | 0 |
| env_modified | 0 |
| tesseract_invocations | 0 |
| p3_p4_p5_executed | 0 |

## 14. Recommended next step

- Human review of `samples.p2_1b.json` buckets (especially INCORRECT_CANDIDATE / PARTIAL / DIAGRAM_DEPENDENT).
- Optional: add `--resegment-only` quality thresholds before any DB import.
- Do **not** run `--force` OCR unless page text itself must change.
- Do **not** proceed to P3/P4/P5 until sample review accepts staging fidelity.

**STOP.** No production import. No P3/P4/P5.
