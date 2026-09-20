# BP-COVERAGE-002 — Blueprint / concept / provenance reconciliation

- Generated: `2026-09-13T17:47:03.935745+00:00`
- Final status: **YELLOW — PARTIALLY VERIFIED**
- Mode: **READ-ONLY** (no DB mutation)
- Git: **no commit / no push**

## 1. Exact 309-vs-318 reconciliation
- Live concepts: `318`
- CF-C3 before/after: `309` → `318`
- CF-C5 snapshot concepts: `318`
- Reconstructed pre-CF-C3 (309) count: `309`
- Delta: `9` (all Physics XI Gravitation)
- Conclusive: `True`

The '309' figure is the pre-CF-C3 concept count (CF-C3 before snapshot). CF-C3 created exactly 9 Physics XI Gravitation concepts from keph107.pdf, raising live concepts to 318. CF-C5 itself recorded concepts=318 before and after (taxonomy_unchanged). BP-COVERAGE-001 brief still cited 309 from the earlier verified state; live DB and CF-C5 snapshots already showed 318.

## 2. All 9 discrepancy records
- `earth-satellites` (41d531b3-0d36-4a56-a45f-deed5c332d7d) — Earth Satellites — PHYSICS / class 11 / gravitation/earth-satellites-orbital-energy — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `energy-of-orbiting-satellite` (19abaa12-0397-4a9a-824f-db3dcd6cb4fe) — Energy of an Orbiting Satellite — PHYSICS / class 11 / gravitation/earth-satellites-orbital-energy — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `escape-speed` (d8bddfc9-3762-40f8-88a3-5abed2bad064) — Escape Speed — PHYSICS / class 11 / gravitation/gravitational-potential-escape — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `g-on-earth-surface` (f097d7c0-2bac-4736-8b07-bc485892c5d7) — Acceleration due to Gravity of the Earth — PHYSICS / class 11 / gravitation/acceleration-due-to-gravity-earth — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `gravitational-constant` (53c7ab2f-294a-4001-b25a-d63561b23bcb) — The Gravitational Constant — PHYSICS / class 11 / gravitation/newtonian-gravitation — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `gravitational-potential-energy` (8987b90d-a615-4e74-9709-f3eea3c25def) — Gravitational Potential Energy — PHYSICS / class 11 / gravitation/gravitational-potential-escape — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `keplers-three-laws` (88099925-0a94-40cc-a647-1a3220b6f542) — Kepler's Three Laws — PHYSICS / class 11 / gravitation/keplers-laws — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `newton-universal-gravitation` (7d1dd1cb-b115-42d3-8045-054fd65fb1d0) — Newton's Universal Law of Gravitation — PHYSICS / class 11 / gravitation/newtonian-gravitation — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**
- `variation-of-g-with-height-depth` (c8c04eff-8e55-4bdd-95f1-c2d8dfe5f48d) — Acceleration due to Gravity Below and Above the Surface of Earth — PHYSICS / class 11 / gravitation/acceleration-due-to-gravity-earth — KU=1 BP=0 Q=0 — **B. newly created legitimate concept**

## 3. Biomolecules blueprint ownership drift
- Chapter ownership: `{'id': '17f6994c-9776-4e66-8627-c44f7e0f08fe', 'code': 'biomolecules', 'name': 'Biomolecules', 'class_level': '11', 'subject': 'BOTANY', 'updated_at': '2026-09-13 22:40:39.770537+05:30'}`
- Drift kind: **metadata-only**
- Affected blueprints: `5`
- Safe remediation: Owner-authorized UPDATE of cms.question_blueprints.subject_id from ZOOLOGY subject UUID → BOTANY subject UUID for the 5 Biomolecules blueprint rows only, WHERE chapter_id = Biomolecules chapter AND concept_id unchanged. Do not touch content_items, KUs, topics, or concepts. Re-validate generation_eligible / last_validation after update.
- Preserve questions: `{'published_questions_expected': 5, 'draft_questions_expected': 8, 'observed_question_status_counts': {'DRAFT': 8, 'PUBLISHED': 5}}`

### Affected blueprints
- `dafae464-f60d-443f-b526-3e0c93390929` key=`production-seed-v2-2026-09-03-bp-zoology-06` subject_id=`ZOOLOGY` chapter_subject=`BOTANY` concept=`biomolecule-classes` KU=0 pubQ=1 draftQ=2
- `876a2f73-994b-4a7b-bc5d-252267f8d2a3` key=`production-seed-v1-2026-09-02-bp-zoology-04` subject_id=`ZOOLOGY` chapter_subject=`BOTANY` concept=`dna-rna` KU=1 pubQ=2 draftQ=3
- `04e93763-bc48-472e-adb3-4088d872e1c4` key=`production-seed-v2-2026-09-03-bp-zoology-07` subject_id=`ZOOLOGY` chapter_subject=`BOTANY` concept=`dna-rna` KU=1 pubQ=2 draftQ=3
- `0b1c8f98-35eb-43f7-bb8e-2398c4a46de5` key=`production-seed-v1-2026-09-02-bp-zoology-03` subject_id=`ZOOLOGY` chapter_subject=`BOTANY` concept=`enzyme-basics` KU=1 pubQ=2 draftQ=3
- `8a42a7e2-c76f-4b64-be74-8fb0e3b472b5` key=`production-seed-v2-2026-09-03-bp-zoology-13` subject_id=`ZOOLOGY` chapter_subject=`BOTANY` concept=`enzyme-basics` KU=1 pubQ=2 draftQ=3

## 4. Provenance classifications (all 137)
- Counts: `{'SOURCE_MISSING': 37, 'LEGACY_SOURCE': 100}`
- Canonical NCERT root: `D:\ravishori\AI Neet Exam App\NCERT Books`

## 5. All 137 blueprint blockers
- Readiness counts (unchanged rules): `{'NEEDS_KU': 108, 'NEEDS_SOURCE': 17, 'NEEDS_REVIEW': 12}`
- Validity counts: `{'PARTIALLY_VALID': 128, 'VALID': 9}`
- Schema note: allowed SOURCE_TIERS=`['authoritative', 'licensed', 'human', 'ai', 'derived']`; BP-001 GENERATION_READY requires `provenance_tier=='ncert'` which is **not** a valid tier → structural reason GENERATION_READY=0.

Full per-blueprint blocker list is in the JSON (`blueprint_blockers`).

## 6. KU / blueprint relationship analysis
```json
{
  "blueprint_to_concept_authoritative": true,
  "blueprint_to_ku_direct_column_exists": false,
  "generation_requires_ku_in_schema": false,
  "generation_requires_ku_in_factory_service": false,
  "audit_policy_requires_passed_ku_for_ncert_pilot": true,
  "multi_ku_concepts": [
    {
      "concept_code": "sp-sp2-sp3",
      "ku_count": 18,
      "blueprint_count": 4
    },
    {
      "concept_code": "factors-affecting-resistance",
      "ku_count": 10,
      "blueprint_count": 1
    },
    {
      "concept_code": "kcl-kvl",
      "ku_count": 10,
      "blueprint_count": 1
    },
    {
      "concept_code": "ohms-law-concept",
      "ku_count": 10,
      "blueprint_count": 2
    },
    {
      "concept_code": "vsepr-theory",
      "ku_count": 6,
      "blueprint_count": 2
    },
    {
      "concept_code": "lattice-energy",
      "ku_count": 6,
      "blueprint_count": 3
    },
    {
      "concept_code": "drift-velocity",
      "ku_count": 5,
      "blueprint_count": 1
    },
    {
      "concept_code": "abo-blood-grouping",
      "ku_count": 3,
      "blueprint_count": 1
    },
    {
      "concept_code": "photorespiration",
      "ku_count": 2,
      "blueprint_count": 1
    }
  ],
  "multi_ku_creates_ambiguity": true,
  "blueprints_bypassing_ku_via_concept_only": 108,
  "future_recommendation": "For NCERT-derived generation, prefer either (a) exactly one PASSED KU per concept before attaching a blueprint, or (b) add an optional blueprint.knowledge_unit_id in a future owner-approved migration \u2014 not in this reconciliation.",
  "model_file": "apps/backend/app/modules/cms/models/content_factory_planning.py",
  "allowed_provenance_tiers": [
    "authoritative",
    "licensed",
    "human",
    "ai",
    "derived"
  ],
  "ncert_source_guard": "assert_blueprint_ncert_source in ncert_canonical_source.py"
}
```

## 7. Subject-wise 400-pilot readiness (BLOCKED)
### PHYSICS
- `{'concepts': 67, 'concepts_with_passed_ku': 13, 'ku_rows_on_concepts': 44, 'existing_blueprints_by_subject_id': 48, 'biomolecules_chapter_owned_blueprints': 0, 'canonical_ncert_backed_blueprints': 0, 'generation_ready_blueprints': 0, 'blocked_blueprints': 48, 'source_gap_blueprints': 48, 'ku_gap_blueprints': 43, 'ownership_issue_blueprints': 0, 'pilot_status': 'BLOCKED', 'note': '400 pilot remains BLOCKED: zero CANONICAL_NCERT_BACKED + GENERATION_READY blueprints under current inventory and BP-001 readiness rules.'}`
### CHEMISTRY
- `{'concepts': 96, 'concepts_with_passed_ku': 65, 'ku_rows_on_concepts': 92, 'existing_blueprints_by_subject_id': 47, 'biomolecules_chapter_owned_blueprints': 0, 'canonical_ncert_backed_blueprints': 0, 'generation_ready_blueprints': 0, 'blocked_blueprints': 47, 'source_gap_blueprints': 47, 'ku_gap_blueprints': 36, 'ownership_issue_blueprints': 0, 'pilot_status': 'BLOCKED', 'note': '400 pilot remains BLOCKED: zero CANONICAL_NCERT_BACKED + GENERATION_READY blueprints under current inventory and BP-001 readiness rules.'}`
### BOTANY
- `{'concepts': 97, 'concepts_with_passed_ku': 47, 'ku_rows_on_concepts': 48, 'existing_blueprints_by_subject_id': 21, 'biomolecules_chapter_owned_blueprints': 5, 'canonical_ncert_backed_blueprints': 0, 'generation_ready_blueprints': 0, 'blocked_blueprints': 21, 'source_gap_blueprints': 21, 'ku_gap_blueprints': 15, 'ownership_issue_blueprints': 0, 'pilot_status': 'BLOCKED', 'note': '400 pilot remains BLOCKED: zero CANONICAL_NCERT_BACKED + GENERATION_READY blueprints under current inventory and BP-001 readiness rules.'}`
### ZOOLOGY
- `{'concepts': 58, 'concepts_with_passed_ku': 16, 'ku_rows_on_concepts': 18, 'existing_blueprints_by_subject_id': 21, 'biomolecules_chapter_owned_blueprints': 0, 'canonical_ncert_backed_blueprints': 0, 'generation_ready_blueprints': 0, 'blocked_blueprints': 21, 'source_gap_blueprints': 21, 'ku_gap_blueprints': 14, 'ownership_issue_blueprints': 5, 'pilot_status': 'BLOCKED', 'note': '400 pilot remains BLOCKED: zero CANONICAL_NCERT_BACKED + GENERATION_READY blueprints under current inventory and BP-001 readiness rules.'}`

## 8. Exact remediation recommendations
- Do NOT create blueprints or generate MCQs until owner review of this reconciliation.
- Accept live concept count = 318; document 309 as pre-CF-C3 baseline (Gravitation +9).
- Owner-authorized metadata fix: realign 5 Biomolecules blueprint.subject_id ZOOLOGY→BOTANY; preserve concept_id and all questions.
- For NCERT-derived 400 pilot: create NEW blueprints only after owner approval, bound to NCERT Books paths + PASSED KU concepts; do not rewrite legacy ai-tier provenance silently.
- Resolve MULTI_KU_REVIEW concepts before attaching NCERT generation quotas.
- Decide whether audit GENERATION_READY should map to provenance_tier='authoritative' + canonical path (schema-aligned) instead of impossible 'ncert' tier.
- Keep Digestion & Absorption excluded.
- 400 pilot remains BLOCKED on existing inventory.

## 9. Safety counts
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
  "chapters": 56,
  "topics": 192,
  "concepts": 318,
  "knowledge_units": 202,
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
  "chapters": 56,
  "topics": 192,
  "concepts": 318,
  "knowledge_units": 202,
  "question_blueprints": 137,
  "content_batches": 11,
  "generation_jobs": 204,
  "generation_runs": 204,
  "generation_candidates": 392
}
```
- Snapshot identical: `True`
- Question freeze OK: `True`

## 10. Tests
- Passed: `76` Failed: `0`
- Unavailable: `['app/modules/cms/tests/test_question_blueprints.py', 'tests/test_question_blueprints.py', 'tests/test_blueprint_integrity.py', 'app/modules/academic/tests/test_cf_c2_biology.py', 'app/modules/academic/tests/test_cf_c3_gravitation.py', 'app/modules/academic/tests/test_cf_c4_biomolecules.py', 'app/modules/academic/tests/test_cf_c5_ku_backfill.py']`
- Notes: `['No dedicated CF-C2/CF-C3/CF-C4/CF-C5 pytest modules found under expected names.', 'CF-C1 covered by test_cf_c1_chemistry_class_12.py.', 'Blueprint integrity covered via live SQL checks in this script + CMS safety tests.']`

```
app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_all_nine_new_chem12_chapters_present_in_seed
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:76: PytestWarning: The test <Function test_all_nine_new_chem12_chapters_present_in_seed> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_all_nine_new_chem12_chapters_present_in_seed():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_electrochemistry_seed_row_is_unchanged
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:84: PytestWarning: The test <Function test_electrochemistry_seed_row_is_unchanged> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_electrochemistry_seed_row_is_unchanged():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_no_duplicate_chapter_slugs_across_all_chemistry
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:97: PytestWarning: The test <Function test_no_duplicate_chapter_slugs_across_all_chemistry> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_no_duplicate_chapter_slugs_across_all_chemistry():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_topic_slugs_are_unique_within_chemistry
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:102: PytestWarning: The test <Function test_topic_slugs_are_unique_within_chemistry> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_topic_slugs_are_unique_within_chemistry():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_concept_slugs_are_unique_within_chemistry
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:109: PytestWarning: The test <Function test_concept_slugs_are_unique_within_chemistry> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_concept_slugs_are_unique_within_chemistry():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_every_new_chapter_has_source_grounded_topics_and_concepts
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:116: PytestWarning: The test <Function test_every_new_chapter_has_source_grounded_topics_and_concepts> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_every_new_chapter_has_source_grounded_topics_and_concepts():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_physics_seed_is_unchanged_by_cf_c1
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:134: PytestWarning: The test <Function test_physics_seed_is_unchanged_by_cf_c1> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_physics_seed_is_unchanged_by_cf_c1():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_botany_seed_is_unchanged_by_cf_c1
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:149: PytestWarning: The test <Function test_botany_seed_is_unchanged_by_cf_c1> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_botany_seed_is_unchanged_by_cf_c1():

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_zoology_seed_is_unchanged_by_cf_c1
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:160: PytestWarning: The test <Function test_zoology_seed_is_unchanged_by_cf_c1> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_zoology_seed_is_unchanged_by_cf_c1():

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
76 passed, 15 warnings in 118.73s (0:01:58)

sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## 11. Exact files inspected
- `cms.question_blueprints`
- `academic.concepts/topics/chapters/subjects`
- `knowledge.knowledge_units`
- `cms.content_items (counts only)`
- `docs\audits\curriculum_baseline_003_zero_topic_chapters_20260913.json`
- `docs\audits\curriculum_baseline_005_ku_backfill_20260913.json`
- `docs\audits\bp_coverage_001_20260913.json`
- `apps/backend/app/modules/cms/models/content_factory_planning.py`
- `apps/backend/app/modules/cms/models/content_factory.py (SOURCE_TIERS)`
- `apps/backend/app/modules/ingestion/services/ncert_canonical_source.py`
- `apps/backend/app/modules/cms/services/content_factory_generation_service.py`
- `apps/backend/scripts/bp_coverage_001_readonly.py`

## 12. Exact files changed
- `docs/audits/bp_coverage_002_reconciliation_20260913.md`
- `docs/audits/bp_coverage_002_reconciliation_20260913.json`
- `apps/backend/scripts/bp_coverage_002_reconciliation.py`

## Confirmation
```json
{
  "db_mutated": false,
  "blueprints_mutated": false,
  "questions_mutated": false,
  "kus_mutated": false,
  "taxonomy_mutated": false,
  "ai_called": false,
  "mcqs_generated": false,
  "pilot_remains_blocked": true
}
```

**STOP** — do not create/repair blueprints or generate MCQs until owner review.
