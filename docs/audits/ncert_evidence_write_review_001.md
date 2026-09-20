# NCERT-EVIDENCE-WRITE-REVIEW-001 — Design review for 14 recoveries

**Generated:** 2026-09-14T06:28:30.914425+00:00
**Mode:** READ_ONLY
**Verdict:** **YELLOW**

## Scope

- Records reviewed: **14** (exact SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW set)
- Population: all SOURCE_MISSING / provenance_tier=ai
- GENERATION_READY untouched: **132**
- REVIEW_REQUIRED untouched: **248**

## Existing architecture (reuse)

```json
{
  "canonical_evidence_mechanism": [
    "constraints.ncert_source_path (primary PDF binding)",
    "constraints.ncert_source_relative (optional relative path)",
    "constraints.ncert_derived (optional explicit NCERT flag)",
    "constraints.ncert_section_heading (optional section hint)",
    "constraints.ku_id (optional KU linkage for evidence composition)",
    "blueprint.provenance_tier == 'authoritative' also forces NCERT declaration"
  ],
  "resolver": "app.modules.cms.services.ncert_generation_evidence.resolve_ncert_evidence_pack",
  "source_gate": "app.modules.ingestion.services.ncert_canonical_source.assert_blueprint_ncert_source",
  "generation_order": [
    "syllabus assert_blueprint_neet_syllabus_scope",
    "resolve_ncert_evidence_pack (if requires_ncert)",
    "provider call only if evidence ready or NCERT not required"
  ],
  "no_new_table_required": true
}
```

## Recommendations

```json
{
  "SAFE_FOR_SURGICAL_EVIDENCE_WRITE": 14,
  "EXISTING_REPRESENTATION_REUSE": 0,
  "KU_REQUIRED_SEPARATE_TASK": 0,
  "PROVENANCE_REVIEW_REQUIRED": 0,
  "REMAIN_BLOCKED": 0
}
```

## Key finding

All 14 are provenance_tier='ai' with no ncert_source_path today, so the NCERT grounding gate does not currently require evidence (NCERT_EVIDENCE_NOT_REQUIRED). The existing canonical mechanism is constraints.ncert_source_path (+ optional ku_id / ncert_derived). Simulated merge of the recovered canonical PDF path yields NCERT_EVIDENCE_READY for 14/14 while leaving provenance_tier unchanged. No new table/API is required. Upgrading ai→authoritative is a separate provenance decision and is not recommended here.

## Per-blueprint summary

| Blueprint | Subject | Chapter | PDF | KU | Simulated evidence | Recommendation |
|---|---|---|---|---|---|---|
| `660f336a` | BOTANY | Photosynthesis in Higher Plants | kebo111.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `3c8f1b03` | PHYSICS | Current Electricity | leph103.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `77576605` | PHYSICS | Current Electricity | leph103.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `b23de1f1` | BOTANY | Photosynthesis in Higher Plants | kebo111.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `dc569dd4` | BOTANY | Photosynthesis in Higher Plants | kebo111.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `f0c87b9d` | CHEMISTRY | Equilibrium | kech106.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `e8721ebe` | CHEMISTRY | Organic Chemistry - Basic Principles | kech202.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `106e56f4` | PHYSICS | Kinematics | keph102.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `937515bc` | PHYSICS | Mechanical Properties of Fluids | keph202.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `38772f04` | PHYSICS | Optics | leph201.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `fc3eac99` | ZOOLOGY | Body Fluids and Circulation | kebo115.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `0b1c8f98` | BOTANY | Biomolecules | kebo109.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `4d923ceb` | CHEMISTRY | Equilibrium | kech106.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |
| `327ca1ed` | PHYSICS | Kinematics | keph103.pdf | PRESENT_PASSED | NCERT_EVIDENCE_READY | SAFE_FOR_SURGICAL_EVIDENCE_WRITE |

## Database freeze

- Unchanged: **True**
- Before: `{"chapters": 56, "topics": 192, "concepts": 318, "kus": 381, "blueprints": 445, "status": {"DRAFT": 5444, "PUBLISHED": 1479, "SUPERSEDED": 6, "IN_REVIEW": 111}, "unmapped_draft": 5034, "candidates": 995, "jobs": 751, "runs": 751}`
- After: `{"chapters": 56, "topics": 192, "concepts": 318, "kus": 381, "blueprints": 445, "status": {"DRAFT": 5444, "PUBLISHED": 1479, "SUPERSEDED": 6, "IN_REVIEW": 111}, "unmapped_draft": 5034, "candidates": 995, "jobs": 751, "runs": 751}`

## Provider

- provider_call_count: **0**

## Tests

```json
{
  "pending": true
}
```

## Failures

- None

## Limitations

- Read-only: no constraints/provenance/KU/blueprint writes performed.
- Recommendations are design guidance for a future authorized surgical write task.
- ncert_derived=true is optional for gate activation (path alone suffices) but matches peer canonical blueprints.
- generation_eligible already True; attaching NCERT path would tighten the grounding gate (good).
- StudyMaterial / 49 provenance-review / 2 Electrostatics cases were not touched.
