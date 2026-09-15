# PYTHON-MCQ-ENGINE-014 — Expanded Reviewed Cohort Evaluation

**Verdict:** **GREEN**
**Measured unique cohort:** **234** (hypothesized 334 — not observed)
**Facts evaluated:** **234**
**Candidates generated:** **234**
**Generation skips:** **0**
**Independent PASS/FAIL/AMBIGUOUS:** **232 / 0 / 2**
**Verified yield:** **0.9915**
**Duplicate rate / ambiguity rate:** **0.0 / 0.0085**

## Cohort inventory

| Source | Count |
|--------|-------|
| ENGINE-007 surviving (006 excl. retired) | 99 |
| ENGINE-012 eligible | 58 |
| ENGINE-013 eligible | 77 |
| Unique after dedupe | **234** |

- RELATIONSHIP_FORMULA: excluded
- ENGINE-008 retired Chemical Kinetics rate-law fact: **excluded / not regenerated**

## ENGINE-007 comparison

| Metric | ENGINE-007 | ENGINE-014 |
|--------|------------|------------|
| Facts evaluated | 100 | 234 |
| Generated | 99 | 234 |
| PASS | 99 | 232 |
| FAIL | 0 | 0 |
| AMBIGUOUS | 0 | 2 |
| Verified yield | **1.0** | **0.9915** |

### By cohort source

| Cohort | Generated | PASS | AMBIGUOUS | Yield |
|--------|-----------|------|-----------|-------|
| ENGINE-007 | 99 | 99 | 0 | **1.0** |
| ENGINE-012 | 58 | 57 | 1 | **0.9828** |
| ENGINE-013 | 77 | 76 | 1 | **0.9870** |

## Type success rates

| Type | Generated | PASS | AMBIGUOUS | Yield |
|------|-----------|------|-----------|-------|
| DIRECT_FACT | 68 | 68 | 0 | **1.0** |
| CONTROLLED_ASSOCIATION | 55 | 53 | 2 | **0.9636** |
| CONTROLLED_NUMERICAL | 12 | 12 | 0 | **1.0** |
| SI_UNIT_DIMENSION | 3 | 3 | 0 | **1.0** |
| DEFINITION | 96 | 96 | 0 | **1.0** |
| DEFINITION_IDENTIFICATION (Q-type) | 96 | 96 | 0 | **1.0** |

## Question-type distribution (generated)

`CONTROLLED_ASSOCIATION 55 / DIRECT_FACT 80 / DEFINITION_IDENTIFICATION 96 / SI_UNIT_TERMINOLOGY 3`

## FAIL / AMBIGUOUS records (exact reasons)

1. `ncert-fact-v1-22abff908e184501ebb4bad1ee510839259caf88894d199319d68c0a32f7128e` — ENGINE-013 / CONTROLLED_ASSOCIATION / PHYSICS / Kinetic Theory — **AMBIGUOUS**: Multiple options independently fill the NCERT statement: `d2`
2. `ncert-fact-v1-2ff298663c928fceca42e26b6f01fb7874cf8957a2063e975e2c1f7936a03037` — ENGINE-012 / CONTROLLED_ASSOCIATION / CHEMISTRY / Biomolecules — **AMBIGUOUS**: Multiple options independently fill the NCERT statement: `d3`

No replacements were manufactured for these cases.

## Skip reasons

None (0 generation skips).

## Reproducibility and safety

- Reproducible: **True** (seed `20260914`)
- Runtime seconds: **350.192**
- Peak memory: see JSON `metrics.peak_memory_bytes`
- Provider/API calls: **0**
- Production DB mutations: **0**
- Source fixtures (006/010/012/013): **unchanged**
- Tests: **4 passed** · Regression: **11 passed (014+007+013)** · Ruff: **passed**

## Conclusion

ENGINE-007’s perfect verification (99/99) largely generalizes to the expanded non-definitional types: overall yield **0.9915**, with perfect yields for DIRECT_FACT, CONTROLLED_NUMERICAL, SI_UNIT_DIMENSION, and DEFINITION. The only softness is **2/55** CONTROLLED_ASSOCIATION ambiguities.

**Do not auto-start ENGINE-015.** Review the two AMBIGUOUS association facts before any staging dry-run.
