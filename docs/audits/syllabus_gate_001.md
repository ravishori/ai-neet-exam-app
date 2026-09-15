# SYLLABUS-GATE-001 — Hard NEET-UG-2026 pre-generation gate

**Generated:** 2026-09-14T04:47:41.470904+00:00
**Syllabus:** `D:\ravishori\AI Neet Exam App\NEETSyllabus.txt`
**SHA-256:** `82a616e31ba75d6e5d6422537c8ef5a4ceafb7a7e3449109696b12839b100ceb`

## Unit counts

- Physics: **20**
- Chemistry: **20**
- Biology: **10**
- Topics parsed: **145**

## Implementation

- Parser: `app.modules.cms.syllabus.neet_2026_parser`
- Registry: `app.modules.cms.syllabus.neet_2026_registry`
- Gate: `app.modules.cms.syllabus.neet_2026_scope.assert_blueprint_neet_syllabus_scope`
- Pre-LLM: `content_factory_generation_service._execute_run: syllabus gate → NCERT evidence gate → provider`

## Authorization rule

Exact match only via constraints.neet_ug_2026 (subject + unit_number + topic_id|topic). Fuzzy match never authorizes.

## Existing blueprint scan (no mutation)

- IN_SYLLABUS: **0**
- SYLLABUS_OUT_OF_SCOPE: **0**
- SYLLABUS_MAPPING_REVIEW_REQUIRED: **445**
- Missing explicit `neet_ug_2026` binding: **445**

## 13 capacity-matrix coverage gaps

Count from capacity matrix: **13**

- PHYSICS Unit 10: OSCILLATIONS AND WAVES — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 536)
- PHYSICS Unit 13: MAGNETIC EFFECTS OF CURRENT AND MAGNETISM — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 536)
- PHYSICS Unit 14: ELECTROMAGNETIC INDUCTION AND ALTERNATING CURRENTS — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 179)
- PHYSICS Unit 15: ELECTROMAGNETIC WAVES — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 179)
- PHYSICS Unit 17: DUAL NATURE OF MATTER AND RADIATION — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 179)
- PHYSICS Unit 18: ATOMS AND NUCLEI — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 179)
- PHYSICS Unit 19: ELECTRONIC DEVICES — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 179)
- PHYSICS Unit 20: EXPERIMENTAL SKILLS — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 3387)
- CHEMISTRY Unit 9: CLASSIFICATION OF ELEMENTS AND PERIODICITY IN PROPERTIES — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 165)
- CHEMISTRY Unit 10: P-BLOCK ELEMENTS — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 165)
- CHEMISTRY Unit 13: PURIFICATION AND CHARACTERISATION OF ORGANIC COMPOUNDS — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 492)
- CHEMISTRY Unit 16: ORGANIC COMPOUNDS CONTAINING HALOGENS — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 165)
- CHEMISTRY Unit 20: PRINCIPLES RELATED TO PRACTICAL CHEMISTRY — no_GENERATION_READY_blueprint_mapped_to_unit (usable target 1801)

Blocker class: **blueprint coverage / explicit syllabus binding** (not fabricated in this task).

## Database before/after

- Unchanged: **True**
- Before: `{"status": {"DRAFT": 5444, "PUBLISHED": 1479, "SUPERSEDED": 6, "IN_REVIEW": 111}, "unmapped_draft": 5034, "kus": 381, "blueprints": 445, "candidates": 995, "jobs": 751, "runs": 751}`
- After: `{"status": {"DRAFT": 5444, "PUBLISHED": 1479, "SUPERSEDED": 6, "IN_REVIEW": 111}, "unmapped_draft": 5034, "kus": 381, "blueprints": 445, "candidates": 995, "jobs": 751, "runs": 751}`

## Safety

- No question mutation
- No publication / certification / ECAEP change
- Frozen unmapped DRAFTs unchanged
- No MCQ generation
- No commit/push

## Known limitations

- Existing production blueprints mostly lack `constraints.neet_ug_2026`; they now correctly fail closed with `SYLLABUS_MAPPING_REVIEW_REQUIRED` until explicit bindings are added in a later remediation task.
- Exact topic text match is strict (casefold + whitespace only).
- NCERT VERIFY-001 n=5 yield remains low-confidence for capacity planning (unchanged by this gate).

## Tests

| Suite | Result |
|---|---|
| `tests/test_syllabus_gate_001.py` | **21 passed** (incl. provider_call_count==0 proofs) |
| `tests/test_mcq_ncert_grounding_001.py` | **16 passed** |
| `tests/test_mcq_provider_abstraction_001.py` | **passed** (run in batch) |
| `tests/test_content_factory_p3.py` | **7 passed** (seeds updated with explicit `neet_ug_2026`) |

## Verdict

**YELLOW** — Gate is implemented and provider-blocking is proven, but all **445** existing blueprint keys lack explicit `neet_ug_2026` bindings (`SYLLABUS_MAPPING_REVIEW_REQUIRED`). Taxonomy/syllabus remediation is required before generation can resume on those blueprints. Out-of-scope blueprints cannot reach the LLM (**not RED**).
