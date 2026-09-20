# CF-C3 — Fill zero-topic NCERT chapters

- Generated: `2026-09-13T16:55:06.839981+00:00`
- Final status: **YELLOW — PARTIALLY VERIFIED**
- Git: **no commit / no push**
- AI / Content Factory / MCQ generation: **none**

## 1. Source PDFs used

- `gravitation` ← `Class 11/Physics/keph1dd/keph1dd/keph107.pdf` exists=True validated=True
- `digestion-absorption` ← `None` exists=False validated=False

## 2. Chapter identity verification
- `gravitation` identity_ok=True discrepancy=none
  - Sections: 7.1 INTRODUCTION, 7.2 KEPLER’S LAWS, 7.3 UNIVERSAL LAW OF GRAVITATION, 7.4 THE GRAVITATIONAL CONSTANT, 7.5 ACCELERATION DUE TO GRAVITY OF
THE EARTH, 7.6 ACCELERATION DUE TO GRAVITY BELOW
AND ABOVE THE SURFACE OF EARTH, 7.7 GRAVITATIONAL POTENTIAL ENERGY
- `digestion-absorption` identity_ok=False discrepancy=none
  - Note: No canonical Class XI Biology PDF titled Digestion and Absorption exists under NCERT Books (kebo1dd). Human Physiology unit (kebo114 opener) lists Breathing, circulation, locomotion/movement and coordination — Digestion and Absorption was removed in the rationalised corpus. Refusing to invent topics/concepts without PDF.

### Digestion PDF search
```json
{
  "hits": [],
  "human_physiology_opener_excerpt": "UNIT 5 The reductionist  approach to study of life forms resulted in increasing use of physico-chemical concepts and techniques. Majority of these studies employed either surviving tissue model or straightaway cell- free systems. An explosion of knowledge resulted in molecular biology. Molecular physiology became almost synonymous with biochemistry and biophysics. However, it is now being increasingly realised that neither a purely organismic approach nor a purely reductionistic molecular approa",
  "scan_roots": [
    "D:\\ravishori\\AI Neet Exam App\\NCERT Books\\Class 11\\Biology"
  ]
}
```

## 3. Topics created per chapter
### `gravitation` (5)
- `keplers-laws` — Kepler's Laws
- `newtonian-gravitation` — Universal Law of Gravitation
- `acceleration-due-to-gravity-earth` — Acceleration due to Gravity of the Earth
- `gravitational-potential-escape` — Gravitational Potential Energy and Escape Speed
- `earth-satellites-orbital-energy` — Earth Satellites and Orbital Energy

## 4. Concepts created per chapter
### `gravitation` (9)
- `keplers-laws` / `keplers-three-laws` — Kepler's Three Laws (`NCERT Class XI Physics Ch 7 Gravitation §7.2`)
- `newtonian-gravitation` / `newton-universal-gravitation` — Newton's Universal Law of Gravitation (`NCERT Class XI Physics Ch 7 Gravitation §7.3`)
- `newtonian-gravitation` / `gravitational-constant` — The Gravitational Constant (`NCERT Class XI Physics Ch 7 Gravitation §7.4`)
- `acceleration-due-to-gravity-earth` / `g-on-earth-surface` — Acceleration due to Gravity of the Earth (`NCERT Class XI Physics Ch 7 Gravitation §7.5`)
- `acceleration-due-to-gravity-earth` / `variation-of-g-with-height-depth` — Acceleration due to Gravity Below and Above the Surface of Earth (`NCERT Class XI Physics Ch 7 Gravitation §7.6`)
- `gravitational-potential-escape` / `gravitational-potential-energy` — Gravitational Potential Energy (`NCERT Class XI Physics Ch 7 Gravitation §7.7`)
- `gravitational-potential-escape` / `escape-speed` — Escape Speed (`NCERT Class XI Physics Ch 7 Gravitation §7.8`)
- `earth-satellites-orbital-energy` / `earth-satellites` — Earth Satellites (`NCERT Class XI Physics Ch 7 Gravitation §7.9`)
- `earth-satellites-orbital-energy` / `energy-of-orbiting-satellite` — Energy of an Orbiting Satellite (`NCERT Class XI Physics Ch 7 Gravitation §7.10`)

## 5. Records already existing
- {'type': 'chapter', 'subject': 'PHYSICS', 'code': 'gravitation', 'name': 'Gravitation', 'class_level': '11'}
- {'type': 'chapter', 'subject': 'ZOOLOGY', 'code': 'digestion-absorption', 'name': 'Digestion and Absorption', 'class_level': '11'}

## 6. Records skipped
- {'type': 'no_canonical_pdf', 'code': 'digestion-absorption'}

## 7. Unresolved source items
- {'code': 'digestion-absorption', 'reason': 'No canonical Class XI Biology PDF titled Digestion and Absorption exists under NCERT Books (kebo1dd). Human Physiology unit (kebo114 opener) lists Breathing, circulation, locomotion/movement and coordination — Digestion and Absorption was removed in the rationalised corpus. Refusing to invent topics/concepts without PDF.'}

## 8. Before / after safety counts
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
  "topics": 187,
  "concepts": 309,
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
- Content safety unchanged: `True`
- Freeze OK: `True`
- Unmapped DRAFT: `5024` → `5024`
- Target chapter snapshots before: `[{'subject': 'PHYSICS', 'code': 'gravitation', 'name': 'Gravitation', 'class_level': '11', 'topics': 0, 'concepts': 0}, {'subject': 'ZOOLOGY', 'code': 'digestion-absorption', 'name': 'Digestion and Absorption', 'class_level': '11', 'topics': 0, 'concepts': 0}]`
- Target chapter snapshots after: `[{'subject': 'PHYSICS', 'code': 'gravitation', 'name': 'Gravitation', 'class_level': '11', 'topics': 5, 'concepts': 9}, {'subject': 'ZOOLOGY', 'code': 'digestion-absorption', 'name': 'Digestion and Absorption', 'class_level': '11', 'topics': 0, 'concepts': 0}]`

## 9. Database integrity results
```json
{
  "duplicate_chapters": [],
  "duplicate_topics": [],
  "duplicate_concepts": [],
  "orphan_topics": 0,
  "orphan_concepts": 0,
  "class_level_ok": true,
  "class_level_details": [
    {
      "code": "gravitation",
      "class_level": "11"
    },
    {
      "code": "digestion-absorption",
      "class_level": "11"
    }
  ],
  "p0_excluded_code_hits": [],
  "biology_xii_chapter_count": 13,
  "biology_xii_thin": [],
  "ok": true
}
```
```json
{
  "expected_topic_delta": 5,
  "actual_topic_delta": 5,
  "expected_concept_delta": 9,
  "actual_concept_delta": 9,
  "chapter_count_unchanged": true,
  "ku_unchanged": true,
  "blueprint_unchanged": true,
  "batch_unchanged": true,
  "jobs_unchanged": true,
  "runs_unchanged": true,
  "candidates_unchanged": true,
  "ok": true
}
```

## 10. Complete test results
- Passed: `70` Failed: `0` exit=`0`
- `D:\ravishori\AI Neet Exam App\apps\backend\.venv\Scripts\python.exe -m pytest app/modules/ingestion/tests/test_ncert_canonical_source.py app/modules/academic/tests/test_cf_c1_chemistry_class_12.py app/modules/academic/tests/test_chapter_class_level.py app/modules/academic/tests/test_physics_p0_taxonomy.py tests/test_cms_workflow.py tests/test_cms_publish_quality.py tests/test_phase32_content_readiness_safety.py tests/test_phase33_ecaep_publication_safety.py -q --tb=line`
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
  app\modules\academic\tests\test_cf_c1_chemistry_class_12.py:159: PytestWarning: The test <Function test_zoology_seed_is_unchanged_by_cf_c1> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_zoology_seed_is_unchanged_by_cf_c1():

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
70 passed, 15 warnings in 145.88s (0:02:25)

sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## 11. Exact files changed
- `apps/backend/scripts/curriculum_baseline_003_zero_topic_chapters.py`
- `docs/audits/curriculum_baseline_003_zero_topic_chapters_20260913.md`
- `docs/audits/curriculum_baseline_003_zero_topic_chapters_20260913.json`
- `academic.topics / academic.concepts (DB rows for gravitation only)`

## 12. Confirmation — no MCQs / AI
- No Content Factory jobs, runs, candidates, or blueprints created.
- No AI provider invoked.
- No question rows created/modified/published/superseded/deleted.
- No Knowledge Units created.
- No ECAEP changes.

