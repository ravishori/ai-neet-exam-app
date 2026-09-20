# NCERT-EVIDENCE-REMEDIATION-001 — Canonical source recovery audit

**Generated:** 2026-09-14T06:18:40.844424+00:00
**Mode:** READ_ONLY
**Verdict:** **YELLOW**

## Population

- Audited (`NCERT_EVIDENCE_MISSING`): **65**
- StudyMaterial: **44**
- SOURCE_MISSING: **21**
- GENERATION_READY untouched: **132**
- REVIEW_REQUIRED untouched: **248**

## Recovery classifications (sum → 65)

- CANONICAL_EVIDENCE_RECOVERABLE: **47**
- CANONICAL_SOURCE_EXISTS_BUT_MAPPING_REVIEW: **2**
- CANONICAL_SOURCE_NOT_FOUND: **0**
- NCERT_EVIDENCE_INSUFFICIENT: **0**
- SOURCE_PROVENANCE_REVIEW: **16**
- Sum: **65**

## By subject

| Subject | Recoverable | Mapping review | Not found | Insufficient | Provenance review |
|---|---:|---:|---:|---:|---:|
| BOTANY | 10 | 0 | 0 | 0 | 2 |
| CHEMISTRY | 14 | 0 | 0 | 0 | 7 |
| PHYSICS | 20 | 2 | 0 | 0 | 1 |
| ZOOLOGY | 3 | 0 | 0 | 0 | 6 |

## By class

```json
{
  "11": {
    "CANONICAL_EVIDENCE_RECOVERABLE": 39,
    "SOURCE_PROVENANCE_REVIEW": 15
  },
  "12": {
    "CANONICAL_EVIDENCE_RECOVERABLE": 8,
    "CANONICAL_SOURCE_EXISTS_BUT_MAPPING_REVIEW": 2,
    "SOURCE_PROVENANCE_REVIEW": 1
  }
}
```

## Future actions

```json
{
  "SAFE_FOR_SEPARATE_EVIDENCE_WRITE_REVIEW": 14,
  "PROVENANCE_REVIEW_REQUIRED": 49,
  "TAXONOMY_REVIEW": 2
}
```

## Special attention

```json
{
  "digestion_absorption": [],
  "biomolecules_botany_xi": [
    {
      "blueprint_id": "0b1c8f98-35eb-43f7-bb8e-2398c4a46de5",
      "subject": "BOTANY",
      "class_level": "11",
      "candidate": "Class 11/Biology/kebo1dd/kebo109.pdf",
      "classification": "CANONICAL_EVIDENCE_RECOVERABLE",
      "ownership_ok": true
    },
    {
      "blueprint_id": "dafae464-f60d-443f-b526-3e0c93390929",
      "subject": "BOTANY",
      "class_level": "11",
      "candidate": "Class 11/Biology/kebo1dd/kebo109.pdf",
      "classification": "SOURCE_PROVENANCE_REVIEW",
      "ownership_ok": true
    },
    {
      "blueprint_id": "8a42a7e2-c76f-4b64-be74-8fb0e3b472b5",
      "subject": "BOTANY",
      "class_level": "11",
      "candidate": "Class 11/Biology/kebo1dd/kebo109.pdf",
      "classification": "CANONICAL_EVIDENCE_RECOVERABLE",
      "ownership_ok": true
    }
  ],
  "gravitation_keph107": [],
  "chemistry_xii_biomolecules_lech205": []
}
```

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

- Read-only: no provenance/ncert_source_path/KU/blueprint writes performed.
- CANONICAL_EVIDENCE_RECOVERABLE does not authorize provenance migration.
- Chapter→PDF map derived from existing canonical sibling blueprints only.
- Multi-PDF academic chapters (Optics/Electrostatics/Kinematics) require exact phrase disambiguation.
- StudyMaterial text was never used as factual evidence.
- YELLOW when recoverable or provenance-review items exist — separate write task required.
