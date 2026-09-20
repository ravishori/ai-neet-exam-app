# P2.1E R2 Human Fidelity Audit

## 1. Executive verdict

**FINAL VERDICT: RED — STOPPED**

R2 improves inline option parsing (Q15 fixed, +1041 VALID vs R1) but **material option contamination**
persists in 18+ cross-column flagged records, including VALID records promoted despite foreign question text.

## 2. Scope
Read-only audit. No parser/artifact/DB modifications.

## 3. Inputs
- R1: `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\p2_1e_full`
- R2: `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\p2_1e_full_r2`
- Machine output: `PYQ_P2_1E_R2_HUMAN_FIDELITY_AUDIT.json`

## 4. R2 baseline verification

| Metric | Expected | Observed | Match |
|--------|----------|----------|-------|
| Questions | 4755 | 4755 | ✓ |
| VALID | 3384 | 3384 | ✓ |
| PARTIAL | 1244 | 1244 | ✓ |
| cross_column_flags | 44 | 44 | ✓ |
| Class-E | 34 | 34 | ✓ |
| Fidelity A+B | 68.8% | 68.8% | ✓ |
| Idempotent | TRUE | True | ✓ |
| Tests | 85 | 85 passed | ✓ |

## 5. Fidelity sample
Deterministic sample n=116; grades={'C': 22, 'A': 32, 'B': 20, 'D': 25, 'E': 17}; pass=False

## 6. Cross-column audit (44/44)
- REAL_EXTRACTION_ERROR: 25
- OCR_ARTIFACT: 19
- INCONCLUSIVE: 0
- Release blockers: **25**

### Critical examples

- 2023 Q3 p8: Multi-line option contains foreign question marker pattern
- 2023 Q73 p11: Multi-line option contains foreign question marker pattern
- 2023 Q3 p9: Multi-line option contains foreign question marker pattern
- 2023 Q3 p2: Multi-line option contains foreign question marker pattern
- 2023 Q6 p2: Foreign question stem/text embedded in option field
- 2025 Q52 p10: Foreign question stem/text embedded in option field
- 2023 Q4 p5: Foreign question stem/text embedded in option field
- 2023 Q82 p13: Multi-line option contains foreign question marker pattern
- 2023 Q133 p20: Multi-line option contains foreign question marker pattern
- 2025 Q7 p3: Multi-line option contains foreign question marker pattern
- 2025 Q65 p13: Multi-line option contains foreign question marker pattern
- 2023 Q57 p8: Foreign question stem/text embedded in option field

Full table: `PYQ_P2_1E_R2_CROSS_COLUMN_AUDIT.csv`

## 7. Class-E audit (34/34)
- TRUE_POSITIVE: 17
- FALSE_POSITIVE: 17 (FP rate 50.00%)
- INCONCLUSIVE: 0
- VALID+contamination: 6

Full table: `PYQ_P2_1E_R2_CLASS_E_AUDIT.csv`

## 8. Q5 investigation
```json
{
  "known_defect": true,
  "quality": "PARTIAL",
  "stem_correct": true,
  "false_marker_protection": true,
  "options_on_q5": [
    "",
    "",
    "",
    ""
  ],
  "options_on_q4": [
    "2 mC",
    "8 mC",
    "6 mC",
    "4mC"
  ],
  "q3_option_c_contains_q5_stem": false,
  "defect_layer": "question_segmentation",
  "recoverable_from_existing_ocr": false,
  "disposition": "REMAIN_PARTIAL"
}
```

## 9. Q15 verification
Options: `['Negative', 'Zero', 'Positive', 'Infinity']` — **PASS** (R1 inline merge defect gone)

## 10. Q15→Q20 boundary
No temperature tokens in Q15 options. **PASS**

## 11–12. Inline/multiline options
Verified by regression tests (85 passed). **PASS**

## 13. Regression tests
```
........................................................................ [ 84%]
.............                                                            [100%]
85 passed in 0.63s
```

## 14. Idempotency
**True** (checksums.p2_1e_full.json)

## 15. Gate decisions
- **structural_integrity:** PASS
- **parser_regression:** PASS
- **cross_column_integrity:** FAIL
- **class_e_integrity:** FAIL
- **fidelity:** FAIL
- **known_defects:** PASS

## 16. Release blockers
- 25 cross-column records with confirmed option contamination
- 6 VALID records accepted despite contamination (Class-E)
- 1244 PARTIAL records remain (26.2% of corpus)
- Q5 KNOWN_DEFECT — options missing due to segmentation

## 17. Required remediation
- Fix option boundary / column bleed before promotion (e.g. 2023 Q3 p2 option_c contains Q5 stem)
- Reclassify or reject VALID records with foreign question text in options
- Address question segmentation for fragmented stems (Q4/Q5)
- Re-audit after extraction fix; do not proceed to P3

## 18. Final decision: **RED — STOPPED**

P3/P4/P5 **NOT RUN**. Production DB write **BLOCKED**.
