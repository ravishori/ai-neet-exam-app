# PYQ P2.1G — R3 Human Fidelity Re-Audit

**Timestamp:** 2026-09-01  
**Final verdict:** **GREEN**  
**Mode:** Read-only human fidelity gate on immutable R3 staging (no parser/R1/R2/R3 modifications)

## Executive summary

R3 passes all formal GREEN gate criteria. Confirmed semantic contamination in VALID records is **0**. All 25 historical contamination cases and all 6 historically contaminated VALID records are resolved. The R2→R3 count difference of **37** is fully reconciled. Production DB import remains blocked; **P3 is allowed** to proceed per gate policy.

## Safety verification

| Metric | Expected | Observed |
|--------|----------|----------|
| Questions | 4718 | 4718 |
| VALID | 3098 | 3098 |
| PARTIAL | 1541 | 1541 |
| Confirmed contamination (VALID) | 0 | 0 |
| Contaminated VALID | 0 | 0 |
| Idempotency | TRUE | TRUE |
| Tests | 103/0 | 103/0 |

## R2→R3 count reconciliation

**Difference: 37 — Reconciled: YES**

| Component | Count |
|-----------|------:|
| Unique question IDs removed (RM4 spurious-marker rejection) | 30 |
| Duplicate record collapses (109→102 duplicate extractions) | 7 |
| **Total accounted** | **37** |

All 30 removed IDs are spurious Q4/Q20 continuation fragments rejected by RM4 (e.g. `8633a381:p5:q4`, `10030e374de702ab:p5:q4`). No records were silently deleted without documented cause.

## Historical 25 contamination cases

| Disposition | Count |
|-------------|------:|
| FIXED | 25 |
| STILL_FAILING | 0 |
| INCONCLUSIVE | 0 |

Canonical case `1d7ffd36:p2:q3` — option_c no longer contains Q5 dipole stem. Cases previously VALID with contamination are now PARTIAL with rejection reasons.

## Historical 6 contaminated VALID

**Remaining contaminated VALID: 0**

All six (`00d8cababe821fcf:p8:q3`, `8633a381:p20:q133`, `a1c3361678271d6e:p24:q162`, `a43894b5fbc8cd28:p9:q3`, `d11cf53d4d8ef5b0:p30:q195`, `f5378eb6785774c3:p21:q145`) are no longer VALID with confirmed foreign text.

## Cross-column flags (41)

| Classification | Count |
|----------------|------:|
| BENIGN_LAYOUT | 39 |
| BENIGN_OCR_ARTIFACT | 0 |
| SEMANTIC_CONTAMINATION | 0 |
| PARSER_ERROR | 0 |
| INCONCLUSIVE | 2 |

**0 semantic contamination release blockers.** Residual flags are geometry heuristics on downgraded PARTIAL/DIAGRAM records or inconclusive OCR-only patterns.

## Class-E metrics (reconciled)

| Scope | Total | False positives | True positives | FP rate |
|-------|------:|----------------:|---------------:|--------:|
| **R2 historical** (P2.1E audit) | 34 | 17 | 17 | 50% |
| **R3 current** | 37 | 35 | 0 | 94.6% |

R3 Class-E count (37) reflects `classify_fidelity()` grade **E** on records with geometry flags — not the R2 historical 34-case audit population. **R3 true positives = 0** (no VALID acceptance with contamination). The prior report’s “Class-E: 0 / FP: 17” mixed R2 historical and R3 metrics; this audit separates them explicitly.

## Fidelity sample

**Methodology:** Deterministic sampling — R3 pipeline samples + HR mandatory (Q4/Q5/Q15/Q16/Q19/Q20) + all 41 cross-column flagged records + R2→R3 changed records + VALID/PARTIAL baselines + inline residue cases.

**Sample size:** 124

| Grade | Count | Meaning |
|-------|------:|---------|
| A | 32 | Source-faithful VALID |
| B | 23 | Minor OCR/layout (incl. DIAGRAM_DEPENDENT) |
| C | 69 | PARTIAL / incomplete extraction (expected) |
| D | 0 | Severe wrong extraction |
| E | 0 | False acceptance |

**Sample A+B:** 44.4% | **Corpus A+B:** 64.1%

| Corpus | A+B fidelity |
|--------|-------------|
| R1 | 48.5% |
| R2 | 68.8% |
| R3 | 64.1% |

R3 corpus fidelity is below R2 (expected: intentional VALID→PARTIAL downgrades) but above R1, with **zero D/E grades** in the audit sample.

## Special cases

- **Q5:** PARTIAL — stem correct (`electric dipole`), 4 options present, no invented text, no cross-question bleed
- **Q15:** PASS — Negative / Zero / Positive / Infinity
- **Q15→Q20:** PASS — no temperature-token bleed

## Gates

| Gate | Status |
|------|--------|
| Structural | PASS |
| Parser regression | PASS |
| Cross-column | PASS |
| Class-E | PASS |
| Fidelity | PASS |
| Known defects | PASS |

## Release decision

| Check | Status |
|-------|--------|
| Final verdict | **GREEN** |
| Production DB | **BLOCKED** |
| P3 | **ALLOWED** |

## Artifacts

- `PYQ_P2_1G_R3_HUMAN_FIDELITY_AUDIT.json`
- `PYQ_P2_1G_R3_CROSS_COLUMN_REAUDIT.csv`
- `PYQ_P2_1G_R3_HISTORICAL_CASE_REAUDIT.csv`

Audit script (read-only): `apps/backend/scripts/audit_p2_1g_r3_fidelity.py`
