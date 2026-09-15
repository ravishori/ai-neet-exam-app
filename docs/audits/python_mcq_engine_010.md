# PYTHON-MCQ-ENGINE-010 — Reviewed Corpus Expansion

**Verdict:** **GREEN** (honest shortfall; fail-closed)
**MCQ_ELIGIBLE facts:** **414**
**Reached 250/subject:** **False**
**Reached 1,000 total:** **False**
**Subject counts:** Physics 86 / Chemistry 169 / Botany 107 / Zoology 52
**Shortfalls to 250:** Physics 164 / Chemistry 81 / Botany 143 / Zoology 198

## Expansion summary

- Seeded from ENGINE-006 excluding ENGINE-008 retired fact: **99**
- New reviewed MCQ_ELIGIBLE facts added: **315**
- Rejected during curation: **88** (mostly `DUPLICATE_FACT_ID`; plus 1 retired exclusion; 1 near-duplicate ambiguity)
- New fixture: `apps/backend/tests/fixtures/python_mcq_engine_010_reviewed_corpus.json`
- ENGINE-006 fixture: **not modified**
- ENGINE-008 retired fact: **absent** from new corpus

## Why the 1,000 / 250-per-subject targets were not met

Available canonical NCERT chapters with NEET-UG-2026 blueprint bindings are limited (especially Zoology: 7 chapters). Safe definitional mining + anti-ambiguity + quality-gate filters were exhausted without fabricating or promoting unreviewed facts.

## Safety

- Provider/API calls: **0**
- Production DB mutations: **0**
- Invariants unchanged: **True**
- Focused tests: **4 passed**
- Regression: **12 passed** (010+009+008)
- Ruff: **passed**
- Runtime: **581.3 s**

## Readiness recommendation

Corpus remains below 1,000 / 250-per-subject. Further expansion requires additional safe reviewed fact types or more NCERT-bound taxonomy coverage — not auto-promotion of EXTRACTED facts. Do not auto-start ENGINE-011. Do not start production generation.
