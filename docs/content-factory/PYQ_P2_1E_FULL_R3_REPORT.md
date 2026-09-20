# PYQ P2.1E Full-Corpus Bbox OCR Report

**Generated:** 2026-09-01T17:10:15.596436+00:00
**Verdict:** **YELLOW**
**Mode:** Full-corpus staging re-OCR with persisted Tesseract word geometry
**Output:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\p2_1e_full_r3`

## 1. Executive verdict

**YELLOW** — P2.1E full-corpus run on **31** papers, **1008** pages.

- Questions extracted: **4718**
- Fidelity rate (A+B): **64.1%**
- HR regression pass: **True**
- Q5 regression: **PASS**
- Q15 regression: **PASS**
- Idempotent: **True**

## 2. Corpus processing summary

| Metric | Value |
|--------|------:|
| Papers processed | 31 |
| Pages processed | 1008 |
| Processing errors | 0 |

## 3. OCR metrics

| Status | Pages |
|--------|------:|
| OCR_SUCCESS | 1007 |
| OCR_LOW_CONFIDENCE | 1 |
| OCR_FAILED | 0 |

## 4. BBOX persistence

Word-level geometry persisted to `ocr.words.p2_1e_full.jsonl` with fields: source_sha256, page, block_num, par_num, line_num, word_num, text, confidence, left, top, width, height.

- Words hash pass1: `cc5fb3239ad62768…`
- Words hash pass2: `cc5fb3239ad62768…`
- Hash match: **True**

## 5. Layout detection

| Layout | Pages |
|--------|------:|
| ONE_COLUMN | 92 |
| TWO_COLUMN | 916 |
| UNKNOWN | 0 |
| rough_work_blank_page | 61 |

## 6. Question extraction metrics

| Quality | Count |
|---------|------:|
| DIAGRAM_DEPENDENT | 78 |
| NEEDS_REVIEW | 1 |
| PARTIAL | 1541 |
| VALID | 3098 |

## 7. Option-boundary analysis

Option association uses `parse_options_bounded()` — first contiguous (1)–(4) set only; truncates at second `(1)` marker to prevent Q15→Q20 bleed.

Q15 options: ['Negative', 'Zero', 'Positive', 'Infinity']

## 8. Q5 regression

Stem: `An electric dipole is placed at an angle of
30° with an electric field of intensity
2x10°NC!. It experiences a torque equal to
4 Nm. Calculate the magnitude of charge
on the dipole, if the dipole leng`
Quality: PARTIAL

## 9. Q15 regression

Stem: `The net magnetic flux through any closed
surface is :`
Options: ['Negative', 'Zero', 'Positive', 'Infinity']

## 10. False-positive analysis

- false_positive_candidates: **1**
- fragment_candidates: **2**

## 11. Fragment analysis

```json
{
  "fragment_candidates": 2,
  "false_positive_candidates": 1
}
```

## 12. Duplicate analysis

```json
{
  "duplicate_within_paper": 0,
  "ocr_equivalent_duplicates": 0,
  "cross_paper_repeated_source": 299,
  "truncated_boilerplate": 0,
  "unique_hashes_with_collisions": 188
}
```

## 13. Cross-column contamination

- cross_column_flags: **41**

## 14. Human-review sample

See `samples.p2_1e_full.json` — includes 30 TWO_COLUMN, 20 PARTIAL, 20 NEEDS_REVIEW, 20 DIAGRAM_DEPENDENT, 20 VALID, 10 page-boundary, 10 instruction pages, 10 complex options, plus Q5/Q15 regression cases.

## 15. Idempotency

- Words identical: **True**
- Questions identical: **True**

## 16. Tests

Run: `pytest app/modules/cms/tests/test_pyq_p2_1e.py app/modules/cms/tests/test_pyq_p2_1c.py`

## 17. Safety attestation

| Check | Status |
|-------|--------|
| production_db_writes | **0** |
| ai_provider_calls | **0** |
| network_calls | **0** |
| source_zip_modified | **0** |
| source_pdfs_modified | **0** |
| env_modified | **0** |
| p3_run | **0** |
| p4_run | **0** |
| p5_run | **0** |
| P2.1E-POC artifacts preserved | **NOT OVERWRITTEN** |
| Production import | **NOT RUN** |
| P3/P4/P5 | **NOT RUN** |

## 18. Recommendation

Compare pipeline metrics below. Do not treat higher question count as automatically better.

```json
{
  "p2_1": {
    "question_count": 238,
    "quality_breakdown": {
      "EXTRACTED": 224,
      "NEEDS_REVIEW": 14
    },
    "cross_column_flags": 0
  },
  "p2_1b": {
    "question_count": 3949,
    "quality_breakdown": {
      "PARTIAL": 1500,
      "NEEDS_REVIEW": 191,
      "VALID": 2187,
      "DIAGRAM_DEPENDENT": 71
    },
    "cross_column_flags": 0
  },
  "p2_1c": {
    "question_count": 6217,
    "quality_breakdown": {
      "PARTIAL": 2814,
      "VALID": 1465,
      "DIAGRAM_DEPENDENT": 197,
      "NEEDS_REVIEW": 1741
    },
    "cross_column_flags": 9
  },
  "p2_1e_full": {
    "question_count": 4718,
    "quality_breakdown": {
      "PARTIAL": 1541,
      "VALID": 3098,
      "DIAGRAM_DEPENDENT": 78,
      "NEEDS_REVIEW": 1
    },
    "cross_column_flags": 41,
    "fidelity": {
      "fidelity_rate": 64.1,
      "false_positive_rate": 0.8,
      "fragment_rate": 0.3,
      "counts": {
        "C": 1426,
        "A": 3017,
        "F": 217,
        "D": 13,
        "E": 37,
        "B": 8
      },
      "total": 4718
    }
  }
}
```

Next step (if authorized separately): human review of samples before any P3+ work.
