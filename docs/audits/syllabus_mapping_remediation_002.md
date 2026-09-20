# SYLLABUS-MAPPING-REMEDIATION-002 — Apply 197 confirmed bindings

**Generated:** 2026-09-14T05:52:43.057884+00:00
**Verdict:** **GREEN**

## Summary

- Confirmed mappings in input: **197**
- Applied (first run): **197**
- Skipped identical (first run): **0**
- Second run applied: **0** (expect 0)
- Second run skipped identical: **197**

## Before / after counts

- Blueprints: 445 → 445
- Populations before: `{'SOURCE_MISSING': 37, 'CANONICAL_NCERT': 308, 'LEGACY_STUDYMATERIAL': 100}`
- Populations after: `{'SOURCE_MISSING': 37, 'CANONICAL_NCERT': 308, 'LEGACY_STUDYMATERIAL': 100}`
- Questions by status before: `{'DRAFT': 5444, 'PUBLISHED': 1479, 'SUPERSEDED': 6, 'IN_REVIEW': 111}`
- Questions by status after: `{'DRAFT': 5444, 'PUBLISHED': 1479, 'SUPERSEDED': 6, 'IN_REVIEW': 111}`
- Unmapped DRAFT: 5034 → 5034
- KUs / candidates / jobs / runs: 381/995/751/751 (unchanged)
- Database inventory unchanged: **True**

## Gate scan

- Before: `{'SYLLABUS_MAPPING_REVIEW_REQUIRED': 445}`
- After IN_SYLLABUS: **197** (expect 197)
- After REVIEW_REQUIRED: **248** (expect 248)
- After OUT_OF_SCOPE: **0** (expect 0)

## Applied mappings

- Exact number applied: **197**
- Machine-readable `changed_blueprints`: **197** IDs
- Academic subject distribution: `{'CHEMISTRY': 62, 'BOTANY': 60, 'PHYSICS': 52, 'ZOOLOGY': 23}`
- NEET subject distribution: `{'BIOLOGY': 83, 'CHEMISTRY': 62, 'PHYSICS': 52}`
- Population distribution: `{'CANONICAL_NCERT': 132, 'LEGACY_STUDYMATERIAL': 44, 'SOURCE_MISSING': 21}`

## Unit distribution of applied bindings

| Unit | Count |
|---|---:|
| BIOLOGY:U06 | 15 |
| PHYSICS:U02 | 12 |
| BIOLOGY:U05 | 12 |
| BIOLOGY:U07 | 11 |
| BIOLOGY:U04 | 11 |
| BIOLOGY:U01 | 11 |
| CHEMISTRY:U03 | 9 |
| BIOLOGY:U10 | 8 |
| BIOLOGY:U03 | 7 |
| CHEMISTRY:U12 | 7 |
| PHYSICS:U12 | 7 |
| CHEMISTRY:U18 | 6 |
| CHEMISTRY:U08 | 6 |
| CHEMISTRY:U06 | 6 |
| CHEMISTRY:U05 | 6 |
| PHYSICS:U09 | 6 |
| BIOLOGY:U08 | 5 |
| CHEMISTRY:U07 | 5 |
| CHEMISTRY:U01 | 4 |
| CHEMISTRY:U02 | 4 |
| PHYSICS:U11 | 4 |
| PHYSICS:U07 | 4 |
| PHYSICS:U05 | 4 |
| PHYSICS:U04 | 4 |
| CHEMISTRY:U19 | 3 |
| CHEMISTRY:U14 | 3 |
| PHYSICS:U06 | 3 |
| PHYSICS:U03 | 3 |
| PHYSICS:U16 | 3 |
| CHEMISTRY:U04 | 2 |
| BIOLOGY:U02 | 2 |
| BIOLOGY:U09 | 1 |
| CHEMISTRY:U11 | 1 |
| PHYSICS:U20 | 1 |
| PHYSICS:U01 | 1 |

## Review-required (untouched)

- Count: **248** (must remain fail-closed)
- Machine-readable list: `review_required_blueprints` in JSON (248 entries)
- Leaked bindings outside confirmed set: **0**

## Preservation

```json
{
  "provenance_unchanged": true,
  "ncert_source_metadata_unchanged": true,
  "taxonomy_ids_unchanged": true,
  "target_count_unchanged": true,
  "unrelated_constraints_preserved": true,
  "questions_unchanged": true,
  "published_unchanged": true,
  "unmapped_draft_unchanged": true,
  "kus_unchanged": true,
  "candidates_unchanged": true,
  "jobs_runs_unchanged": true,
  "ecaep_unchanged": true,
  "no_publication": true,
  "note": "Only constraints.neet_ug_2026 merged on 197 confirmed blueprint IDs; apply script verified unrelated_field_diffs empty for all changes."
}
```

## Idempotency

```json
{
  "first_run_applied": 197,
  "second_run_applied": 0,
  "ok": true
}
```

## Provider-blocking

```json
{
  "confirmed_blueprint_id": "8ad065bb-9656-45f7-b0bc-31b4759f9a28",
  "confirmed_gate": "IN_SYLLABUS",
  "confirmed_preflight_stop": "NCERT_EVIDENCE_INSUFFICIENT",
  "confirmed_provider_calls": 0,
  "review_blueprint_id": "0d707747-0340-4628-826a-c20561cc8c91",
  "review_gate": "SYLLABUS_MAPPING_REVIEW_REQUIRED",
  "review_preflight_stop": "SYLLABUS_MAPPING_REVIEW_REQUIRED",
  "review_provider_calls": 0,
  "ok": true
}
```

## Tests

```json
{
  "pending": false,
  "suites": [
    {
      "name": "test_syllabus_gate_001 + remediation_001 + ncert_grounding + provider_abstraction",
      "passed": 65,
      "failed": 0,
      "result": "PASS"
    },
    {
      "name": "test_content_factory_p3",
      "passed": 7,
      "failed": 0,
      "result": "PASS"
    }
  ],
  "all_green": true
}
```

## Failures

- None

## Limitations

- 248 blueprints remain SYLLABUS_MAPPING_REVIEW_REQUIRED (fail-closed; no LLM).
- Bindings copied exactly from REMEDIATION-001 proposed_neet_ug_2026 (not recomputed).
- Confirmed blueprints may still fail NCERT evidence preflight (provider not called until evidence passes).
- Academic BOTANY/ZOOLOGY map to NEET BIOLOGY subject in bindings; taxonomy subject_id unchanged.
