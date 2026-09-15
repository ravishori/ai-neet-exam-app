# PYTHON-MCQ-ENGINE-007 — Reviewed 100-Fact Read-Only Evaluation

**Verdict:** **GREEN**
**Facts evaluated:** **100**
**FACT_APPROVED / MCQ_ELIGIBLE / blocked:** **100 / 100 / 0**
**Candidates generated:** **99**
**Generation failure rate:** **0.01** (1 skip: `NCERT_GROUNDING_FAILED`)
**Independent PASS/FAIL/AMBIGUOUS:** **99 / 0 / 0**
**READ-ONLY EVALUATION VERIFIED YIELD:** **1.0** (99/99 generated)

## Verified yield breakdown

| Dimension | Result |
|-----------|--------|
| Subject | Botany 1.0 (25/25), Chemistry 1.0 (24/24), Physics 1.0 (25/25), Zoology 1.0 (25/25) |
| Class | 11 → 1.0 (39/39), 12 → 1.0 (60/60) |
| Question type | DEFINITION_IDENTIFICATION 1.0 (96/96), CONTROLLED_ASSOCIATION 1.0 (2/2), DIRECT_FACT 1.0 (1/1) |

Chapter/topic yields are all 1.0 among generated candidates (see JSON `verified_yield_by_chapter` / `verified_yield_by_topic`).

## Generation shortfall (not replaced)

- **1** Chemistry / Chemical Kinetics / Rate Law and Order of Reaction fact skipped
- `fact_id`: `ncert-fact-v1-bbe13bb91d3757573671d3531c1912cd7c7c92e825153cf6400470f1f625fa99`
- Reason: `NCERT_GROUNDING_FAILED`
- No replacement candidate was manufactured

## Duplication

- Within-evaluation duplicate rate: **0.0**
- Read-only production stem_hash overlap: **0**

## Reproducibility and safety

- Reproducible: **True** (seed `20260914`, first=second=99)
- Runtime seconds: **412.87**
- Provider/API calls: **0** / ₹0
- Production DB mutations: **0**
- Invariants unchanged: **True**
- Fixture unchanged: **True**
- Worker: **UNKNOWN / UNKNOWN** (continuity not claimed)

## Tests

- Focused: **3 passed**
- Regression: **57 passed** (007 + 006 + engine/adapter/loader/gate)
- Ruff: **passed**

## Major failure patterns

- `NCERT_GROUNDING_FAILED:1` (generation skip only; no independent FAIL/AMBIGUOUS among created candidates)

## Method note

- Generation used **per-fact** evidence context so chapter/topic/concept stamp matches each reviewed fact.
- Independent verification does **not** treat FACT_APPROVED / MCQ_ELIGIBLE as NCERT certification.

## Limitations

- Independent verification is PDF/syllabus/taxonomy evidence review only.
- Production corpus overlap uses stem_hash fingerprints only (read-only).
- No semantic embedding dedupe was available.
- OpenAI worker observation is UNKNOWN.
- ENGINE-006 fixture was not modified.

**Recommended next task:** PYTHON-MCQ-ENGINE-008: investigate and remediate the single Chemical Kinetics `NCERT_GROUNDING_FAILED` reviewed fact (or retire it from the eligible pack), then run a gated non-production staging dry-run / scale plan for additional reviewed chapters — still without production persistence or provider calls.
