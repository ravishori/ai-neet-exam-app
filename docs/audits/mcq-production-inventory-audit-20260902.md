# MCQ Production Inventory Audit
Date: 2026-09-02T10:40:14.251336+00:00
Database: `localhost:5432/trinetra_db`
Read-only: YES

_Config note:_ `Audit uses DATABASE_URL (live app DB). DATABASE_URL_SYNC may be a separate empty test database.`
- DATABASE_URL → `localhost:5432/trinetra_db` (audited)
- DATABASE_URL_SYNC → `localhost:5432/trinetra_test_db`

## Executive Numbers

| Metric | Count |
|--------|------:|
| Total MCQs (QUESTION, not deleted) | 175 |
| Published | 11 |
| Draft | 153 |
| Other statuses (sum) | 11 |
| Physics | 73 |
| Chemistry | 53 |
| Biology (BOTANY+ZOOLOGY) | 49 |
| Subject unmapped | 0 |
| Class 11 | 40 |
| Class 12 | 24 |
| Class unknown | 111 |
| Graphic-based | 48 |
| Diagram-based | 45 |
| With pyq_year | 0 |
| Missing concept_id | 0 |
| Duplicate stem groups | 1 |
| Duplicate slug groups | 0 |

## Definitions

- **total**: cms.content_items content_type=QUESTION AND deleted_at IS NULL
- **published**: status='PUBLISHED' (matches assessment.published_question_ids_for_scope)
- **draft**: status='DRAFT' only — other non-published statuses listed separately
- **subject**: JOIN concept→topic→chapter→subject; Biology executive = BOTANY+ZOOLOGY
- **class**: Priority: source_documents.class_level via latest_version KU/ingestion join; fallback ncert_reference Class 11/12; fallback relative_source_path regex. Conflicting if signals disagree.
- **diagram_based**: Linked ingestion.visual_assets on knowledge_unit (via content_version_knowledge_units or content_versions.knowledge_unit_id) with asset_type='diagram' and deleted_at IS NULL. No diagram_svg/diagram_description keys exist on QUESTION bodies.
- **graphic_based**: Any linked non-deleted visual_asset (image|diagram|table|equation|chemical_structure). Superset of diagram-based.
- **source_year**: body.pyq_year on latest_version; pilot_run_id / publisher from ingestion when joinable
- **duplicates**: duplicate slug groups; duplicate lower(trim(stem)) groups; intra-question duplicate option texts
- **version_body**: Inventory content metrics use latest_version_id; PUBLISHED live pointer = current_version_id

**Observed QUESTION body keys:** `bloom_level, correct_option, difficulty, explanation, options, pyq_year, stem`

## Status breakdown

| Status | Count |
|--------|------:|
| DRAFT | 153 |
| PUBLISHED | 11 |
| IN_REVIEW | 11 |
| Soft-deleted (excluded from totals) | 0 |

### Pointer health

```json
{
  "latest_null": 0,
  "current_null": 134,
  "latest_ne_current": 142,
  "published_current_null": 0,
  "published_aligned": 11,
  "published_current_ne_latest": 0
}
```

## Subject × status

| Subject | Bucket | Count |
|---------|--------|------:|
| BOTANY | NON_PUBLISHED | 21 |
| BOTANY | PUBLISHED | 1 |
| CHEMISTRY | NON_PUBLISHED | 52 |
| CHEMISTRY | PUBLISHED | 1 |
| PHYSICS | NON_PUBLISHED | 67 |
| PHYSICS | PUBLISHED | 6 |
| ZOOLOGY | NON_PUBLISHED | 24 |
| ZOOLOGY | PUBLISHED | 3 |

Biology executive rollup = BOTANY (22) + ZOOLOGY (27) = 49.

## Class 11 / 12

**Confidence:** LOW CONFIDENCE — majority lack class_level / ncert / path signals

Rule: Priority: source_documents.class_level via latest_version KU/ingestion join; fallback ncert_reference Class 11/12; fallback relative_source_path regex. Conflicting if signals disagree.

| Class | Count |
|-------|------:|
| 11 | 40 |
| 12 | 24 |
| Unknown | 111 |
| Conflicting signals | 0 |

## Graphic / Diagram

- Graphic-based: **48**
- Diagram-based (`asset_type=diagram`): **45**
- Both: 45
- Graphic only: 3
- Diagram only: 0
- Neither: 127
- Separate `content_type=DIAGRAM` items (not MCQs): **0**

## Source / year

### pyq_year

```json
{
  "null": 175
}
```

### Publishers

```json
[
  {
    "publisher": "(none)",
    "n": 111
  },
  {
    "publisher": "NCERT",
    "n": 64
  }
]
```

### Top pilot_run_id

```json
[
  {
    "pilot_run_id": "(none)",
    "n": 111
  },
  {
    "pilot_run_id": "phase-d-30-mcq-v1",
    "n": 34
  },
  {
    "pilot_run_id": "phase-d-30-mcq-authorized-20260825",
    "n": 30
  }
]
```

## Chapter / topic (top)

### Chapters

| Code | Name | Count |
|------|------|------:|
| current-electricity | Current Electricity | 53 |
| chemical-bonding | Chemical Bonding and Molecular Structure | 33 |
| photosynthesis | Photosynthesis in Higher Plants | 12 |
| electrostatics | Electrostatics | 10 |
| organic-chemistry-basics | Organic Chemistry - Basic Principles | 10 |
| cell-unit-of-life | Cell - The Unit of Life | 10 |
| optics | Optics | 10 |
| equilibrium | Equilibrium | 10 |
| biomolecules | Biomolecules | 8 |
| animal-kingdom | Animal Kingdom | 8 |
| human-reproduction | Human Reproduction | 8 |
| body-fluids-circulation | Body Fluids and Circulation | 3 |

_Chapter groups total: 12_

### Topics

| Code | Name | Count |
|------|------|------:|
| ohms-law | Electric Current and Ohm's Law | 33 |
| hybridization | Hybridization | 19 |
| resistance-resistivity | Resistance and Resistivity | 11 |
| kirchhoffs-laws | Kirchhoff's Laws | 9 |
| covalent-bonding-vsepr | Covalent Bonding and VSEPR Theory | 7 |
| ionic-bonding | Ionic Bonding | 7 |
| factors-affecting-photosynthesis | Factors Affecting Photosynthesis | 6 |
| electric-field-potential | Electric Field and Potential | 4 |
| electronic-effects | Electronic Effects | 4 |
| refraction-lenses | Refraction and Lenses | 4 |
| chemical-equilibrium | Chemical Equilibrium | 4 |
| cell-organelles | Cell Organelles | 4 |
| ionic-equilibrium | Ionic Equilibrium and pH | 4 |
| reproductive-systems | Male and Female Reproductive Systems | 3 |
| dark-reaction | Dark Reaction (Calvin Cycle) | 3 |

_Topic groups total: 36_
- Missing concept_id: **0**
- Concept but no chapter: **0**

## Duplicates

- Duplicate slug groups: **0**
- Duplicate stem groups: **1**
- Near-dup md5(stem|options) groups: **1**
- Questions with duplicate option texts: **0**

### Stem duplicate examples

```json
[
  {
    "stem_norm": "[fallback mode \u2014 no anthropic_api_key configured] placeholder question stem.",
    "n": 2,
    "ids": [
      "143c5687-091f-452e-899f-6b60895b8cec",
      "b521811e-208e-4627-bc70-33718cda924f"
    ]
  }
]
```

## Missing metadata

```json
{
  "missing_concept_id": 0,
  "missing_micro_competency_id": 174,
  "missing_stem": 0,
  "missing_options": 0,
  "missing_correct_option": 0,
  "missing_explanation": 0,
  "missing_difficulty": 0,
  "missing_pyq_year": 175,
  "invalid_abcd_option_set": 0,
  "missing_subject_mapping": 0,
  "missing_class_mapping": 111,
  "published_current_version_null": 0
}
```

## Non-production appendix (excluded from totals)

```json
{
  "generation_candidates": 32,
  "factory_review_items": 5,
  "note": "NON-PRODUCTION \u2014 not included in Total MCQs"
}
```

## Sanity checks

```json
{
  "sum_by_status_eq_total": true,
  "published_draft_other_eq_total": true,
  "subject_mapped_unmapped_eq_total": true,
  "class_parts_eq_total": true,
  "graphic_subset": true,
  "diagram_subset": true,
  "practice_pool_published_match": true
}
```

## SQL / script

Re-run: `apps/backend/scripts/audit_mcq_production_inventory.py`

## Risks / gaps before loading more content

- Student-visible pool is PUBLISHED-only and currently small versus authored DRAFT volume.
- Class mapping is incomplete for many rows → treat Class KPIs as partial.
- Academic subject codes split Biology into BOTANY/ZOOLOGY — report both ways.
- Sync env DB ≠ live DB — inventory tooling must target DATABASE_URL.

## Recommendation: **CONDITIONAL**

- Only 11 PUBLISHED questions in student practice pool (of 175).
- 153 remain DRAFT; 11 other non-published.
- Do not load more until Class coverage / subject mapping gaps are understood for new packs.
- No QUESTION body diagram_svg fields; graphic coverage depends on visual_asset linkage.
- DATABASE_URL_SYNC points at a different (empty) DB — keep using live DATABASE_URL for inventory.
