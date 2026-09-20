# PROVENANCE-CONTRACT-001 — NCERT provenance contract audit

- Generated: `2026-09-13T17:54:33.040318+00:00`
- Final status: **GREEN — COMPLETE/VERIFIED**
- Mode: **READ-ONLY**
- Git: **no commit / no push**

## 1. Provenance enum / schema
- SOURCE_TIERS / PROVENANCE_TIERS: `['authoritative', 'licensed', 'human', 'ai', 'derived']`
- SOURCE_TYPES (batch): `['HUMAN', 'AI', 'LICENSED', 'AUTHORITATIVE', 'DERIVED', 'MIXED']`
- Rejected false claims: `['official', 'official_source', 'nta', 'ncert_official']`
- DB: `provenance_tier is String(30) NOT NULL with no DB CHECK enum; allowed values enforced in Pydantic + planning service.`
- Live blueprint tiers: `[{'provenance_tier': 'ai', 'n': 137}]`

## 2. Implementation locations
- `apps/backend/app/modules/cms/models/content_factory.py (SOURCE_TIERS)`
- `apps/backend/app/modules/cms/models/content_factory_planning.py (PROVENANCE_TIERS)`
- `apps/backend/app/modules/cms/schemas/content_factory_planning.py (Pydantic validator)`
- `apps/backend/app/modules/cms/schemas/content_factory.py (batch source_tier)`
- `apps/backend/app/modules/cms/services/content_factory_planning_service.py (PROVENANCE_FALSE_CLAIM)`
- `apps/backend/app/modules/cms/services/content_factory_generation_service.py (assert_blueprint_ncert_source)`
- `apps/backend/app/modules/ingestion/services/ncert_canonical_source.py (CF-SOURCE-001)`
- `apps/backend/alembic/versions/f6a7b8c9d0e1_cms_content_factory_p2_planning.py`
- `apps/backend/alembic/versions/e5f6a7b8c9d0_cms_content_factory_p1.py`
- `docs/architecture/ncert_canonical_source.md`
- `docs/product/CONTENT_FACTORY_P2_IMPLEMENTATION.md`
- `docs/product/CONTENT_FACTORY_DATA_MODEL.md`
- `docs/product/CONTENT_FACTORY_ARCHITECTURE.md`
- `apps/backend/scripts/bp_coverage_001_readonly.py (incorrect audit gate)`
- `apps/backend/scripts/bp_coverage_002_reconciliation.py (reproduces audit gate)`

## 3. Meaning of each provenance tier
```json
{
  "authoritative": {
    "meaning": "Authority-class / source-of-truth material for factory provenance \u2014 trusted textbook grounding, NOT a claim of official NTA endorsement or that TALOS content is 'official NCERT'.",
    "ncert_fit": true,
    "evidence": [
      "content_factory_planning.py: PROVENANCE_TIERS = SOURCE_TIERS; rejects official claims",
      "test_ncert_canonical_source.test_blueprint_with_canonical_source_accepts uses provenance_tier='authoritative' + ncert_source_path under NCERT Books",
      "blueprint_declares_ncert_source: tier=='authoritative' implies NCERT binding required",
      "CONTENT_FACTORY_DATA_MODEL.md: source_tier = Authority class",
      "CONTENT_FACTORY_P2_IMPLEMENTATION.md: rejects official_source/nta/ncert_official"
    ],
    "why_appropriate_for_canonical_ncert": "Existing CF-SOURCE-001 tests and factory guards already bind authoritative + ncert_source_path to NCERT_SOURCE_ROOT. No schema change required to represent canonical NCERT PDFs."
  },
  "licensed": {
    "meaning": "Licensed third-party corpus (not the default NCERT Books path)."
  },
  "human": {
    "meaning": "Human-authored generation contract / SME-authored lineage."
  },
  "ai": {
    "meaning": "AI-assisted generation contract; does not by itself require NCERT PDF binding."
  },
  "derived": {
    "meaning": "Derived from other content without claiming primary textbook authority."
  },
  "explicitly_not_allowed": {
    "values": [
      "official",
      "official_source",
      "nta",
      "ncert_official",
      "ncert"
    ],
    "reason": "'ncert' is not in PROVENANCE_TIERS (Pydantic rejects). official/nta/ncert_official rejected as false official claims. Product rule: never invent official NTA/NCERT labels on content."
  }
}
```

## 4. Canonical NCERT representation (existing architecture)
Canonical NCERT is already representable without schema change: provenance_tier='authoritative' plus constraints binding a PDF under D:\ravishori\AI Neet Exam App\NCERT Books.

### Contract triple (schema-compatible)
1. `provenance_tier = authoritative`
2. `constraints.ncert_derived = true` (recommended explicit)
3. `constraints.ncert_source_path` (or alias keys) resolving under `NCERT Books`

### Why no new `ncert` tier
Adding 'ncert' would (1) invent a non-enum value already rejected by Pydantic, (2) risk false official-claim confusion already blocked for official/nta/ncert_official, and (3) diverge from CF-SOURCE-001 tests that already use authoritative.

## 5. Source / evidence representation
```json
{
  "canonical_ncert_pdf_path": {
    "supported": true,
    "where": "question_blueprints.constraints JSONB keys: ncert_source_path, canonical_ncert_pdf, source_pdf_path",
    "guard": "assert_blueprint_ncert_source / validate_ncert_generation_source",
    "root": "NCERT_SOURCE_ROOT / Settings.ncert_source_root \u2192 NCERT Books"
  },
  "source_document_identity": {
    "supported_on_blueprint": false,
    "note": "No blueprint.source_document_id column. Identity is path string in constraints; ingestion.source_documents exists for KU/ingestion lineage, not blueprint FK."
  },
  "chapter": {
    "supported": true,
    "where": "question_blueprints.chapter_id \u2192 academic.chapters"
  },
  "section": {
    "supported": false,
    "note": "No first-class blueprint section field; KU may link ingestion_sections."
  },
  "page_or_section_evidence": {
    "supported_on_blueprint": "partial/optional via unconstrained constraints JSONB",
    "supported_on_questions": "ncert_evidence body/tags on ContentItem (ECAEP certification path)",
    "note": "Blueprint constraints may store free-form keys but factory REQUIRED_CONSTRAINT_KEYS only mandate question_format/correct_option_count/explanation_required."
  },
  "ncert_verification_state": {
    "on_blueprint": false,
    "on_question": true,
    "note": "ECAEP certify-ncert / ncert_evidence.verification_level \u2014 orthogonal to blueprint tier."
  },
  "provenance_tier": {
    "supported": true,
    "allowed": [
      "authoritative",
      "licensed",
      "human",
      "ai",
      "derived"
    ],
    "rejected_false_claims": [
      "official",
      "official_source",
      "nta",
      "ncert_official"
    ],
    "canonical_ncert_representation": "authoritative + constraints path under NCERT Books"
  },
  "gaps": [
    "No dedicated blueprint.knowledge_unit_id",
    "No dedicated blueprint.source_document_id",
    "No structured page/section schema on blueprints",
    "No DB CHECK enum for provenance_tier (app-layer only)",
    "StudyMaterial paths can sit in constraints until generation assert rejects for ncert_derived"
  ]
}
```

## 6. Generation-gate mismatch
- Classification: **A. incorrect audit/test gate (BP-COVERAGE-001/002 readiness classifier) + B. outdated audit contract relative to FACTORY-P2 / CF-SOURCE-001. Not a production generation-service requirement.**
- Production gate: content_factory_generation_service.assert_blueprint_ncert_source: NCERT PDF path required only when blueprint_declares_ncert_source (ncert_derived / path keys / provenance_tier==authoritative). AI-tier blueprints skip NCERT path requirement.
- Pydantic probe (`ncert` accepted?): `{'accepted': False, 'error': "1 validation error for QuestionBlueprintCreateRequest\nprovenance_tier\n  Value error, provenance_tier must be one of ('authoritative', 'licensed', 'human', 'ai', 'derived') [type=value_error, input_value='ncert', input_type=str]\n    For further information visit https://errors.pydantic.dev/2.10/v/value_error"}`
- Pydantic probe (`authoritative` accepted?): `{'accepted': True, 'error': None}`

## 7. Legacy blueprint treatment
- Reverified counts: `{'LEGACY_SOURCE_StudyMaterial': 100, 'SOURCE_MISSING': 37, 'CANONICAL_NCERT_BACKED': 0}`
- CF-SOURCE-001 non-goals: does not rewrite existing question/blueprint provenance. Equivalent NCERT Books PDFs existing on disk do not rewrite historical StudyMaterial constraint paths. New NCERT-derived blueprints must be created explicitly with authoritative + NCERT Books path after owner approval.

## 8. Biomolecules drift
- Count: `5`
- All ZOOLOGY subject / BOTANY chapter: `True`
- Remediation (not applied): Owner-authorized UPDATE subject_id ZOOLOGY→BOTANY for these 5 rows only; preserve chapter_id/topic_id/concept_id and all PUBLISHED/DRAFT questions/KUs. Not applied in this audit.

## 9. Exact recommended remediation
- Do NOT add provenance_tier='ncert' to the schema (would conflict with false-claim policy and Pydantic enum).
- Represent future NCERT-derived blueprints as: provenance_tier='authoritative' + constraints.ncert_derived=true + constraints.ncert_source_path under NCERT Books (validated by assert_blueprint_ncert_source).
- Update BP-COVERAGE audit GENERATION_READY gate to match production: authoritative + canonical path + PASSED KU policy — not provenance_tier=='ncert'.
- Do not silently rewrite the 100 StudyMaterial-backed or 37 SOURCE_MISSING blueprints.
- Owner-authorized Biomolecules subject_id ZOOLOGY→BOTANY metadata fix only (preserve concept/question FKs).
- Do not create blueprints or generate MCQs until owner review of this contract audit.

## 10. Safety counts
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
- Identical: `True` Freeze OK: `True`

## 11. Tests
- Passed `74` / Failed `0`
- Unavailable: `['app/modules/cms/tests/test_question_blueprints.py', 'tests/test_blueprint_integrity.py', 'app/modules/academic/tests/test_cf_c2_biology.py', 'app/modules/academic/tests/test_cf_c3_gravitation.py', 'app/modules/academic/tests/test_cf_c4_biomolecules.py', 'app/modules/academic/tests/test_cf_c5_ku_backfill.py']`

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
74 passed, 15 warnings in 114.47s (0:01:54)

sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## 12. Unresolved owner/engineering decisions
- When to authorize creation of NEW NCERT-derived blueprints (authoritative + NCERT Books path) for the 400 pilot — not a schema question.
- When to authorize Biomolecules subject_id metadata fix (already specified; not applied here).
- Whether to update BP-COVERAGE-* audit scripts' GENERATION_READY classifier in a follow-up (documentation/tooling only).
- Optional future enhancement (not required for contract): blueprint.source_document_id / knowledge_unit_id columns — owner/engineering ADR if desired.

## Files inspected
- `cms.question_blueprints (read-only)`
- `information_schema / pg_constraint for blueprint columns`
- `apps/backend/app/modules/cms/models/content_factory.py`
- `apps/backend/app/modules/cms/models/content_factory_planning.py`
- `apps/backend/app/modules/cms/schemas/content_factory_planning.py`
- `apps/backend/app/modules/cms/services/content_factory_planning_service.py`
- `apps/backend/app/modules/cms/services/content_factory_generation_service.py`
- `apps/backend/app/modules/ingestion/services/ncert_canonical_source.py`
- `apps/backend/app/modules/ingestion/tests/test_ncert_canonical_source.py`
- `docs/architecture/ncert_canonical_source.md`
- `docs/product/CONTENT_FACTORY_P2_IMPLEMENTATION.md`
- `docs/product/CONTENT_FACTORY_DATA_MODEL.md`
- `docs/product/CONTENT_FACTORY_ARCHITECTURE.md`
- `docs/audits/bp_coverage_002_reconciliation_20260913.json`

## Files changed
- `docs/audits/provenance_contract_001_20260913.md`
- `docs/audits/provenance_contract_001_20260913.json`
- `apps/backend/scripts/provenance_contract_001_readonly.py`

## Confirmation
```json
{
  "db_mutated": false,
  "blueprints_mutated": false,
  "provenance_rewritten": false,
  "questions_mutated": false,
  "kus_mutated": false,
  "ai_called": false,
  "mcqs_generated": false,
  "committed": false,
  "pushed": false
}
```

**STOP** — do not repair provenance, modify blueprints, or generate MCQs.
