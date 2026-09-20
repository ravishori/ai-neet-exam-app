# PYTHON-MCQ-ENGINE-011 — Fact-Type Expansion Analysis

**Verdict:** **GREEN**
**Baseline MCQ_ELIGIBLE:** **414** (Physics 86 / Chemistry 169 / Botany 107 / Zoology 52)
**Baseline composition:** {'DEFINITION': 411, 'ASSOCIATION': 2, 'DIRECT_FACT': 1}
**Genuinely reviewable new candidates:** **2130** (schema-ready mechanical gates only)
**Safely MCQ_ELIGIBLE now:** **0** (no auto-promotion; no templates/distractors/scope_review)

## Recommended next curation types (schema-ready)

- **DIRECT_FACT** — 913 potentially reviewable
- **RELATIONSHIP_FORMULA** — 543 potentially reviewable
- **CONTROLLED_ASSOCIATION** — 422 potentially reviewable
- **CONTROLLED_NUMERICAL** — 180 potentially reviewable
- **SI_UNIT_DIMENSION** — 72 potentially reviewable

## Per-type mechanical gate counts

| Category | Discovered | NCERT | Syllabus | Taxonomy | Dup | Ambiguous | Rejected | Potentially reviewable | Schema |
|----------|------------|-------|----------|----------|-----|-----------|----------|------------------------|--------|
| DIRECT_FACT | 914 | 913 | 913 | 913 | 1 | 0 | 0 | 913 | ready |
| CONTROLLED_ASSOCIATION | 427 | 427 | 427 | 427 | 0 | 5 | 5 | 422 | ready |
| SI_UNIT_DIMENSION | 81 | 81 | 81 | 81 | 0 | 9 | 9 | 72 | ready |
| RELATIONSHIP_FORMULA | 587 | 587 | 587 | 587 | 0 | 44 | 44 | 543 | ready |
| CONTROLLED_NUMERICAL | 183 | 183 | 183 | 183 | 0 | 3 | 3 | 180 | ready |
| SEQUENCE_ORDER | 687 | 687 | 687 | 687 | 0 | 1 | 687 | 0 | SCHEMA_GAP |
| PROCESS_MECHANISM | 276 | 276 | 276 | 276 | 0 | 0 | 276 | 0 | SCHEMA_GAP |
| CAUSE_EFFECT | 691 | 691 | 691 | 691 | 0 | 11 | 691 | 0 | SCHEMA_GAP |
| COMPARISON | 277 | 277 | 277 | 277 | 0 | 4 | 277 | 0 | SCHEMA_GAP |
| EXCEPTION_NEGATION | 344 | 343 | 343 | 343 | 1 | 4 | 343 | 0 | SCHEMA_GAP |

## Subject-wise reviewable opportunities (schema-ready)

| Subject | DIRECT_FACT | ASSOCIATION | FORMULA | NUMERICAL | SI_UNIT |
|---------|-------------|-------------|---------|-----------|--------|
| ZOOLOGY | 71 | 49 | 0 | 27 | 1 |
| PHYSICS | 374 | 63 | 356 | 68 | 37 |
| BOTANY | 201 | 114 | 8 | 25 | 11 |
| CHEMISTRY | 267 | 196 | 179 | 60 | 23 |

## Sample independent verification

Representative samples (subject-diverse) for each schema-ready type: NCERT/syllabus/taxonomy PASS; answer_defensibility and distractor_safety remain PENDING_REVIEW until templates exist. Overall: VIABLE_FOR_REVIEW only.

## Quality risks

- Most ENGINE-010 facts are DEFINITION; non-definitional types need distractor packs before eligibility.
- SEQUENCE/PROCESS/CAUSE_EFFECT/COMPARISON/EXCEPTION lack schema FactType support today.
- Token-overlap taxonomy binding can misbind concepts (ENGINE-008 lesson).
- Multi-cue sentences risk ambiguity and must stay fail-closed.
- CONTROLLED_NUMERICAL needs calculation_check contracts, not sentence mining alone.

## Safety

- Provider/API calls: **0**
- Production DB mutations: **0**
- ENGINE-006 / ENGINE-010 fixtures: **unchanged**
- ENGINE-008 retired fact: **excluded**
- Isolated candidate fixture: `python_mcq_engine_011_fact_type_candidates.json` (EXTRACTED/REVIEW_REQUIRED only)
- Runtime seconds: **25.575**

**Recommendation:** Next authorized curation wave should prioritize schema-ready types ['DIRECT_FACT', 'RELATIONSHIP_FORMULA', 'CONTROLLED_ASSOCIATION', 'CONTROLLED_NUMERICAL'] with full scope_review + distractor templates, especially for Zoology/Physics chapters showing reviewable association/direct-fact density. Do not auto-start another engine task.
