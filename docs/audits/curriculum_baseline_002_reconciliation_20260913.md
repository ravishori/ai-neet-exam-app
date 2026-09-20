# CURRICULUM-BASELINE-002 — Owner-approved curriculum reconciliation

- Generated: `2026-09-13T11:04:41.304244+00:00`
- Final status: **YELLOW — PARTIALLY VERIFIED**
- Git commit: **not performed** (awaiting owner review)

## Owner decisions recorded

- Approved Rationalised Reprint 2026–27 under NCERT Books as curriculum baseline
- Biology XII ownership mapping: NOT SUPPLIED (placeholder) — unresolved
- Apply CF-C1 Chemistry XII scaffolding where absent; preserve Electrochemistry
- Preserve legacy/aggregate taxonomy unless explicit mapping requires change
- Do not modify 5,024 unmapped DRAFTs / PUBLISHED / IN_REVIEW / SUPERSEDED
- Do not change ECAEP publication/safety rules

## Applied changes

- Chemistry XII CF-C1 chapters applied: `9`
- Topics applied: `34`
- Concepts applied: `62`

## Already existing

- `electrochemistry` — Electrochemistry (preserved; not modified)

## Biology XII — unresolved (no owner mapping supplied)

- Ch 1: Sexual Reproduction in Flowering Plants — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 2: Human Reproduction — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 3: Reproductive Health — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 4: Principles of Inheritance and Variation — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 5: Molecular Basis of Inheritance — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 6: Evolution — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 7: Human Health and Disease — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 8: Microbes in Human Welfare — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 9: Biotechnology: Principles and Processes — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 10: Biotechnology and its Applications — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 11: Organisms and Populations — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 12: Ecosystem — **CURRICULUM-OWNER DECISION REQUIRED**
- Ch 13: Biodiversity and Conservation — **CURRICULUM-OWNER DECISION REQUIRED**

## Physics

- Gravitation PDF validated: `True`
- Gravitation DB row: `{'code': 'gravitation', 'name': 'Gravitation', 'class_level': '11', 'topics': 0, 'concepts': 0}`
- Aggregate taxonomy (e.g. Kinematics): **preserved / not replaced**

## Safety counts

### Before
```json
{
  "status": {
    "DRAFT": 5298,
    "PUBLISHED": 1479,
    "SUPERSEDED": 6,
    "IN_REVIEW": 111
  },
  "unmapped_draft": 5024,
  "chapters": 36,
  "topics": 125,
  "concepts": 192,
  "knowledge_units": 73,
  "question_blueprints": 137,
  "content_batches": 11,
  "generation_jobs": 204,
  "generation_runs": 204,
  "generation_candidates": 392
}
```

### After
```json
{
  "status": {
    "DRAFT": 5298,
    "PUBLISHED": 1479,
    "SUPERSEDED": 6,
    "IN_REVIEW": 111
  },
  "unmapped_draft": 5024,
  "chapters": 45,
  "topics": 159,
  "concepts": 254,
  "knowledge_units": 73,
  "question_blueprints": 137,
  "content_batches": 11,
  "generation_jobs": 204,
  "generation_runs": 204,
  "generation_candidates": 392
}
```

- Content safety unchanged (status + unmapped DRAFT): `True`
- Unmapped DRAFT before/after: `5024` / `5024`

## Tests

- Passed: `40`
- Failed: `0`
- Command: `pytest app/modules/ingestion/tests/test_ncert_canonical_source.py app/modules/academic/tests/test_cf_c1_chemistry_class_12.py app/modules/academic/tests/test_chapter_class_level.py -q`

## Skipped / unresolved

- Biology XII Botany/Zoology ownership mapping was a placeholder — no taxonomy applied
- No blueprints generated
- No MCQs generated
- Legacy aggregate Physics taxonomy (e.g. Kinematics) preserved
- Full seed_academic() not run — surgical CF-C1 Chemistry XII only

