# PYQ P2.1E Human Review → R2 Re-Audit

**Verdict:** **YELLOW**
**Baseline (R1):** `data/staging/pyq/2020-2025/p2_1e_full/` (preserved)
**R2:** `D:\ravishori\AI Neet Exam App\data\staging\pyq\2020-2025\p2_1e_full_r2`

## Parser change

Inline option reconstruction in `parse_options_bounded()` using `OPTION_START_RE`
with line-cap on option (4) and preserved Q15→Q20 boundary truncation.

## Metrics comparison

| Metric | R1 (baseline) | R2 |
|--------|--------------:|---:|
| Questions | 4755 | 4755 |
| VALID | 2343 | 3384 (+1041 vs R1) |
| PARTIAL | 2200 | 1244 (-956 vs R1) |
| DIAGRAM_DEPENDENT | 211 | 126 (-85 vs R1) |
| NEEDS_REVIEW | 1 | 1 (0 vs R1) |
| Fidelity A+B | 48.5% | 68.8% |
| false_positive_rate | 0.0% | 0.7% |
| fragment_rate | 0.3% | 0.3% |
| cross_column_flags | 0 | 44 |
| OCR_SUCCESS | 1007 | 1007 |
| Idempotent | True | True |

## Q15 regression

R1 options: ['Negative (2) Zero', '', 'Positive (4) Infinity', '']
R2 options: ['Negative', 'Zero', 'Positive', 'Infinity']
R2 Q15 pass (no Q20 bleed): **True**

## Q5 regression

R1 stem: `An electric dipole is placed at an angle of
30° with an electric field of intensity
2x10°NC!. It experiences a torque eq`
R2 stem: `An electric dipole is placed at an angle of
30° with an electric field of intensity
2x10°NC!. It experiences a torque eq`
R2 Q5 pass: **True**

## Safety

| Check | Status |
|-------|--------|
| Production DB writes | **0** |
| P3/P4/P5 | **NOT RUN** |
| Baseline R1 preserved | **YES** |

## Decision

**YELLOW** — R2 materially improves extraction quality but is not GREEN.

### Improvements (R1 → R2)
- VALID: +1,041 (2,343 → 3,384)
- PARTIAL: −956 (2,200 → 1,244)
- Fidelity A+B: 48.5% → 68.8%
- Q15 options: cleanly reconstructed (`Negative/Zero/Positive/Infinity`)
- Q15→Q20 bleed: still blocked
- Q5 false-marker rejection: preserved

### Remaining defects
- **Q5** still PARTIAL (stem correct, options missing — OCR fragmentation across Q4/Q5 markers)
- **1,244 PARTIAL** records remain (no-options, stem fragmentation, OCR garble)
- **cross_column_flags:** 0 → 44 (more complete records now trigger geometry checks)
- **false_positive_rate:** 0.0% → 0.7% (34 class-E records; needs sample review)
- **DIAGRAM_DEPENDENT:** 211 → 126 (reclassification as options filled; diagram cues may still apply)

### Tests
**85 passed, 0 failed** (82 baseline + 3 new inline-option regression tests)

GREEN not declared without full human fidelity sampling on R2 `samples.p2_1e_full.json`.

**P3/P4/P5 were NOT run. No production DB writes.**
