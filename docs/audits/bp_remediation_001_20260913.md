# BP-REMEDIATION-001 — Biomolecules blueprint subject_id fix

- Generated: `2026-09-13T17:59:32.724187+00:00`
- Final status: **GREEN — COMPLETE/VERIFIED**
- Git: **no commit / no push**

## 1. Five exact blueprint IDs
- `0b1c8f98-35eb-43f7-bb8e-2398c4a46de5` (`production-seed-v1-2026-09-02-bp-zoology-03`)
- `876a2f73-994b-4a7b-bc5d-252267f8d2a3` (`production-seed-v1-2026-09-02-bp-zoology-04`)
- `dafae464-f60d-443f-b526-3e0c93390929` (`production-seed-v2-2026-09-03-bp-zoology-06`)
- `04e93763-bc48-472e-adb3-4088d872e1c4` (`production-seed-v2-2026-09-03-bp-zoology-07`)
- `8a42a7e2-c76f-4b64-be74-8fb0e3b472b5` (`production-seed-v2-2026-09-03-bp-zoology-13`)

## 2. Before / after subject_id
- `0b1c8f98-35eb-43f7-bb8e-2398c4a46de5`: `ZOOLOGY` (`1bbd31b8-60a1-4630-bdca-23167454b934`) → `BOTANY` (`92283579-413a-45d7-8d77-0c407fe7d277`)
- `876a2f73-994b-4a7b-bc5d-252267f8d2a3`: `ZOOLOGY` (`1bbd31b8-60a1-4630-bdca-23167454b934`) → `BOTANY` (`92283579-413a-45d7-8d77-0c407fe7d277`)
- `dafae464-f60d-443f-b526-3e0c93390929`: `ZOOLOGY` (`1bbd31b8-60a1-4630-bdca-23167454b934`) → `BOTANY` (`92283579-413a-45d7-8d77-0c407fe7d277`)
- `04e93763-bc48-472e-adb3-4088d872e1c4`: `ZOOLOGY` (`1bbd31b8-60a1-4630-bdca-23167454b934`) → `BOTANY` (`92283579-413a-45d7-8d77-0c407fe7d277`)
- `8a42a7e2-c76f-4b64-be74-8fb0e3b472b5`: `ZOOLOGY` (`1bbd31b8-60a1-4630-bdca-23167454b934`) → `BOTANY` (`92283579-413a-45d7-8d77-0c407fe7d277`)

## 3. Dependency verification
- Questions biomolecules before: `{'DRAFT': 8, 'PUBLISHED': 5}`
- Questions biomolecules after: `{'DRAFT': 8, 'PUBLISHED': 5}`
- Concept IDs unchanged: `True`
- Chemistry biomolecules-chem blueprints: `0`
- Chemistry chapter subject: `{'id': '933a0d17-537f-4995-b0ae-6ce23a32a449', 'code': 'biomolecules-chem', 'class_level': '12', 'subject': 'CHEMISTRY'}`
- Rows updated: `5`
- Verification OK: `True`
- Ownership drift remaining: `0`
- Orphans: `0`
- Duplicates: `[]`

## 4. Safety snapshot
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
- Freeze OK: `True` Snapshot academic identical except intended bp metadata: `True`

## 5. Tests
- Passed: `70` Failed: `0`
- Unavailable: `['app/modules/cms/tests/test_question_blueprints.py', 'tests/test_blueprint_integrity.py', 'app/modules/academic/tests/test_cf_c2_biology.py', 'app/modules/academic/tests/test_cf_c3_gravitation.py', 'app/modules/academic/tests/test_cf_c4_biomolecules.py', 'app/modules/academic/tests/test_cf_c5_ku_backfill.py']`

```
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
70 passed, 15 warnings in 87.06s (0:01:27)

sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## 6. Exact files changed
- `docs/audits/bp_remediation_001_20260913.md`
- `docs/audits/bp_remediation_001_20260913.json`
- `apps/backend/scripts/bp_remediation_001_biomolecules_subject.py`
- `cms.question_blueprints.subject_id (5 rows only)`

## Confirmation
```json
{
  "only_subject_id_updated": true,
  "questions_mutated": false,
  "kus_mutated": false,
  "taxonomy_mutated": false,
  "provenance_rewritten": false,
  "blueprints_created": false,
  "mcqs_generated": false,
  "ai_called": false,
  "committed": false,
  "pushed": false
}
```

**STOP** — do not create new blueprints or generate MCQs.
