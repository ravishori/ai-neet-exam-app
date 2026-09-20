# PYTHON-MCQ-ENGINE-013 — High-Yield Non-definitional Expansion

**Verdict:** **GREEN**
**Candidates selected / reviewed:** **200 / 200**
**MCQ_ELIGIBLE:** **77**
**REVIEW_REQUIRED:** **0**
**REJECTED:** **123**
**Eligibility rate:** **0.385**

## Baseline

- ENGINE-010: **414**
- ENGINE-012: **58**
- ENGINE-013 new eligible: **77**
- Combined if merged: **549**

## Target mix vs selected / eligible

| Category | Target | Available unused | Selected | Shortfall | Eligible |
|----------|--------|------------------|----------|-----------|----------|
| DIRECT_FACT | 100 | 173 | 100 | 0 | 34 |
| CONTROLLED_ASSOCIATION | 60 | 82 | 60 | 0 | 34 |
| CONTROLLED_NUMERICAL | 25 | 34 | 25 | 0 | 8 |
| SI_UNIT_DIMENSION | 15 | 16 | 15 | 0 | 1 |

## ENGINE-012 distractor-failure analysis (19)

- Count: **19**
- Classifications: `{'distractor_construction_failure': 15, 'ocr_evidence_quality_problem': 3, 'underlying_fact_invalid': 1}`
- ENGINE-013 does not weaken distractor safety to recover these candidates. RELATIONSHIP_FORMULA remains deferred.

## Gate failure counts (this wave)

- Duplicates: **0**
- Ambiguity: **3**
- Insufficient evidence: **0**
- Syllabus failures: **0**
- Taxonomy failures: **0**
- Distractor failures: **9**

### Selected subject breakdown

{'PHYSICS': 71, 'BOTANY': 57, 'CHEMISTRY': 68, 'ZOOLOGY': 4}

### Eligible subject breakdown

{'PHYSICS': 31, 'BOTANY': 15, 'CHEMISTRY': 31}

Zoology: only **4** unused ENGINE-011 candidates remained after ENGINE-012; all 4 were reviewed and rejected (association-span unsafe / numerical-range ambiguous). No fabricated Zoology fill.

## Safety

- Provider/API calls: **0**
- Production DB mutations: **0**
- ENGINE-006 / 010 / 011 / 012 fixtures: **unchanged**
- ENGINE-010 eligible count: **414 unchanged**
- ENGINE-012 eligible count: **58 unchanged**
- ENGINE-008 retired fact: **excluded**
- RELATIONSHIP_FORMULA: **deferred**
- Automatic promotion: **False**
- Tests: **4 passed** · Regression: **8 passed (012+013)** · Ruff: **passed**

Fixture: `python_mcq_engine_013_reviewed_nondef_v1.json`
