# CF-C4b — Biomolecules ownership migration (owner-approved)

- Generated: `2026-09-13T17:17:32.616749+00:00`
- Final status: **GREEN — COMPLETE/VERIFIED**
- Decision applied: Biology XI Biomolecules → **BOTANY**, class_level=**11**
- Source PDF: `Class 11/Biology/kebo1dd/kebo109.pdf` (project taxonomy decision; not an NCERT subject claim)
- Git: **no commit / no push**

## Migration
```json
{
  "action": "already_on_botany",
  "chapter_id": "17f6994c-9776-4e66-8627-c44f7e0f08fe",
  "class_level_set": "11"
}
```

## Before / after chapter state
- Before: `[{'subject': 'BOTANY', 'chapter_id': '17f6994c-9776-4e66-8627-c44f7e0f08fe', 'code': 'biomolecules', 'name': 'Biomolecules', 'class_level': '11', 'topics': 3, 'concepts': 3}]`
- After: `[{'subject': 'BOTANY', 'chapter_id': '17f6994c-9776-4e66-8627-c44f7e0f08fe', 'code': 'biomolecules', 'name': 'Biomolecules', 'class_level': '11', 'topics': 3, 'concepts': 3}]`

## Preservation / revalidation
```json
{
  "ownership": {
    "subject": "BOTANY",
    "class_level": "11",
    "code": "biomolecules",
    "name": "Biomolecules"
  },
  "zoo_biomolecules_remaining": 0,
  "chemistry_biomolecules_chem": {
    "subject": "CHEMISTRY",
    "class_level": "12",
    "topics": 4
  },
  "concept_ids_preserved": true,
  "questions_preserved": true,
  "blueprints_preserved": true,
  "published_derive_class_11": true,
  "published_count": 5,
  "published_derivable": 5,
  "ok": true
}
```

## Safety
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
  "chapters": 56,
  "topics": 192,
  "concepts": 318,
  "knowledge_units": 73,
  "question_blueprints": 137,
  "content_batches": 11,
  "generation_jobs": 204,
  "generation_runs": 204,
  "generation_candidates": 392
}
```
- Freeze OK: `True`
- Content safety unchanged: `True`

## Integrity
```json
{
  "duplicate_chapters": [],
  "orphan_topics": 0,
  "orphan_concepts": 0,
  "ok": true
}
```

## Tests
- Passed: `70` Failed: `0` exit=`0`
- `D:\ravishori\AI Neet Exam App\apps\backend\.venv\Scripts\python.exe -m pytest app/modules/ingestion/tests/test_ncert_canonical_source.py app/modules/academic/tests/test_cf_c1_chemistry_class_12.py app/modules/academic/tests/test_chapter_class_level.py app/modules/academic/tests/test_physics_p0_taxonomy.py tests/test_cms_workflow.py tests/test_cms_publish_quality.py tests/test_phase32_content_readiness_safety.py tests/test_phase33_ecaep_publication_safety.py -q --tb=line`
```
<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:241
  <frozen importlib._bootstrap>:241: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

app/modules/academic/tests/test_cf_c1_chemistry_class_12.py::test_seed_shape_all_chemistry_chapters_are_5_tuples
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:65: PytestWarning: The test <Function test_seed_shape_all_chemistry_chapters_are_5_tuples> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_seed_shape_all_chemistry_chapters_are_5_tuples():

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
70 passed, 15 warnings in 131.41s (0:02:11)

sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## Files changed
- `apps/backend/scripts/curriculum_baseline_004b_biomolecules_ownership.py`
- `apps/backend/app/modules/academic/seed.py`
- `apps/backend/app/modules/academic/models/chapter.py`
- `apps/backend/app/modules/academic/tests/test_chapter_class_level.py`
- `apps/backend/app/modules/academic/tests/test_cf_c1_chemistry_class_12.py`
- `docs/audits/curriculum_baseline_004b_biomolecules_ownership_20260913.md`
- `docs/audits/curriculum_baseline_004b_biomolecules_ownership_20260913.json`

