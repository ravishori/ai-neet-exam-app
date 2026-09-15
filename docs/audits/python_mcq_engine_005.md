# PYTHON-MCQ-ENGINE-005 — 100-Fact Read-Only Evaluation

**Verdict:** **GREEN**
**Facts selected:** **100**
**FACT_APPROVED / REVIEW_REQUIRED / REJECTED:** **5 / 95 / 0**
**Candidates generated:** **5**
**Independent PASS/FAIL/AMBIGUOUS:** **5 / 0 / 0**
**Read-only evaluation verified yield:** **1.0**

## Subject / chapter coverage

- Subject distribution: `{'CHEMISTRY': 25, 'BOTANY': 25, 'ZOOLOGY': 25, 'PHYSICS': 25}`
- Chapters used: **20**

## Honesty

- Exactly 100 facts were selected.
- Only previously REVIEWED ENGINE-004 facts were treated as reviewed.
- EXTRACTED facts were not silently upgraded.
- Rejected / review-required facts are first-class evaluation results.

## Reproducibility and safety

- Reproducible: **True**
- Runtime seconds: **63.314**
- Provider/API calls: **0**
- Production DB mutations: **0**
- Invariants unchanged: **True**
- Worker observation: **UNKNOWN / UNKNOWN**

## Tests

- Focused: **9 passed**
- Regression: **51 passed** (ENGINE-005 + deterministic engine/adapter/loader/gate)
- Ruff: **passed**

## Major failure patterns

- CONCEPT_BINDING_REVIEW_REQUIRED:95
- FACT_REVIEW_REQUIRED:95

## Limitations

- Only five ENGINE-004 facts were REVIEWED; 95 facts are EXTRACTED and fail closed until reviewed.
- This evaluation measures pipeline behavior, not production readiness.
- Independent verification applies only to generated candidates.
- No semantic embedding dedupe was available.
- OpenAI worker observation is UNKNOWN; continuity is not claimed.

**Recommended next task:** PYTHON-MCQ-ENGINE-006: curate and independently review additional multi-subject fact packs until each of Physics/Chemistry/Botany/Zoology has at least 25 REVIEWED+MCQ_ELIGIBLE facts with question templates, then re-run this read-only 100-fact evaluation without persistence.
