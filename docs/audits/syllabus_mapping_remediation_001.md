# SYLLABUS-MAPPING-REMEDIATION-001 — Read-only NEET-2026 reconciliation

**Generated:** 2026-09-14T05:48:08.945168+00:00
**Mode:** READ-ONLY (no blueprint/question/provenance mutation)
**Syllabus:** `D:\ravishori\AI Neet Exam App\NEETSyllabus.txt` (`82a616e31ba75d6e…`)
**Unit counts:** Physics 20 / Chemistry 20 / Biology 10

## Summary

- Total blueprints: **445**
- Canonical NCERT: **308**
- Legacy StudyMaterial: **100**
- SOURCE_MISSING: **37**
- OTHER: **0**
- `SYLLABUS_MAPPING_CONFIRMED`: **197**
- `SYLLABUS_MAPPING_REVIEW_REQUIRED`: **248**
- `SYLLABUS_OUT_OF_SCOPE`: **0**

## By subject (confirmed / review / out)

| Subject | Confirmed | Review | Out |
|---|---:|---:|---:|
| BOTANY | 60 | 61 | 0 |
| CHEMISTRY | 62 | 77 | 0 |
| PHYSICS | 52 | 63 | 0 |
| ZOOLOGY | 23 | 47 | 0 |

## Review-required reason groups

| Reason | Count |
|---|---:|
| `no_deterministic_exact_mapping` | 196 |
| `unit_exact_but_topic_ambiguous` | 47 |
| `ambiguous_exact_phrase_hits_across_topics` | 5 |

## Confirmed mapping bases

| Basis | Count |
|---|---:|
| `exact_phrase_in_syllabus:chapter_name` | 84 |
| `exact_phrase_in_syllabus:topic_name` | 58 |
| `exact_phrase_in_syllabus:concept_name` | 45 |
| `exact_unit_name_plus_phrase:topic_name` | 5 |
| `exact_unit_name_plus_phrase:concept_name` | 3 |
| `exact_chapter_name_equals_unit_name_single_topic` | 2 |

## Unmapped NEET-2026 units (zero confirmed blueprints)

Count: **15** / 50

- PHYSICS Unit 8: THERMODYNAMICS
- PHYSICS Unit 10: OSCILLATIONS AND WAVES
- PHYSICS Unit 13: MAGNETIC EFFECTS OF CURRENT AND MAGNETISM
- PHYSICS Unit 14: ELECTROMAGNETIC INDUCTION AND ALTERNATING CURRENTS
- PHYSICS Unit 15: ELECTROMAGNETIC WAVES
- PHYSICS Unit 17: DUAL NATURE OF MATTER AND RADIATION
- PHYSICS Unit 18: ATOMS AND NUCLEI
- PHYSICS Unit 19: ELECTRONIC DEVICES
- CHEMISTRY Unit 9: CLASSIFICATION OF ELEMENTS AND PERIODICITY IN PROPERTIES
- CHEMISTRY Unit 10: P-BLOCK ELEMENTS
- CHEMISTRY Unit 13: PURIFICATION AND CHARACTERISATION OF ORGANIC COMPOUNDS
- CHEMISTRY Unit 15: HYDROCARBONS
- CHEMISTRY Unit 16: ORGANIC COMPOUNDS CONTAINING HALOGENS
- CHEMISTRY Unit 17: ORGANIC COMPOUNDS CONTAINING OXYGEN
- CHEMISTRY Unit 20: PRINCIPLES RELATED TO PRACTICAL CHEMISTRY

## Capacity-matrix 13 coverage gaps (preserved)

Count: **13** — not fabricated here.

- PHYSICS Unit 10: OSCILLATIONS AND WAVES — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 13: MAGNETIC EFFECTS OF CURRENT AND MAGNETISM — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 14: ELECTROMAGNETIC INDUCTION AND ALTERNATING CURRENTS — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 15: ELECTROMAGNETIC WAVES — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 17: DUAL NATURE OF MATTER AND RADIATION — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 18: ATOMS AND NUCLEI — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 19: ELECTRONIC DEVICES — no_GENERATION_READY_blueprint_mapped_to_unit
- PHYSICS Unit 20: EXPERIMENTAL SKILLS — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 9: CLASSIFICATION OF ELEMENTS AND PERIODICITY IN PROPERTIES — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 10: P-BLOCK ELEMENTS — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 13: PURIFICATION AND CHARACTERISATION OF ORGANIC COMPOUNDS — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 16: ORGANIC COMPOUNDS CONTAINING HALOGENS — no_GENERATION_READY_blueprint_mapped_to_unit
- CHEMISTRY Unit 20: PRINCIPLES RELATED TO PRACTICAL CHEMISTRY — no_GENERATION_READY_blueprint_mapped_to_unit

## Deterministic evidence rules

1. Explicit `constraints.neet_ug_2026` validated by SYLLABUS-GATE-001
2. Exact full-text match of chapter/topic/concept to a syllabus topic bullet
3. Exact phrase presence of chapter/topic/concept (≥6 chars) in exactly one syllabus topic/unit name
4. Exact chapter name = unit name, with single topic or unique within-unit phrase

Token-overlap similarities are **diagnostic only** and never confirm.

## Database before/after

- Unchanged: **True**
- Before: `{"status": {"DRAFT": 5444, "PUBLISHED": 1479, "SUPERSEDED": 6, "IN_REVIEW": 111}, "unmapped_draft": 5034, "kus": 381, "blueprints": 445, "candidates": 995, "jobs": 751, "runs": 751}`
- After: `{"status": {"DRAFT": 5444, "PUBLISHED": 1479, "SUPERSEDED": 6, "IN_REVIEW": 111}, "unmapped_draft": 5034, "kus": 381, "blueprints": 445, "candidates": 995, "jobs": 751, "runs": 751}`

## Safety

- No blueprint mutation
- No question / ECAEP / provenance mutation
- No LLM / provider calls
- Syllabus gate not weakened
- No commit/push

## Verdict: **YELLOW**

197 confirmed; 248 require human/taxonomy review; 0 out of scope. Gate unchanged; DB unchanged.

## Tests

| Suite | Result |
|---|---|
| `tests/test_syllabus_mapping_remediation_001.py` | passed |
| `tests/test_syllabus_gate_001.py` | passed |
| `tests/test_mcq_ncert_grounding_001.py` | passed |
| Combined | **47 passed** |

No DB mutation. No LLM calls. Syllabus gate not weakened.
