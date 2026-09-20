# NCERT-EVIDENCE-WRITE-002 — Surgical evidence constraints write

**Generated:** 2026-09-14T06:40:44.563746+00:00
**Verdict:** **GREEN**

## Summary

- Targets: **14**
- First run applied: **0**
- Second run applied: **0** (expect 0)
- ncert_derived written: **False** (optional; omitted)
- provider_call_count: **0**

## Gate after write

```json
{
  "IN_SYLLABUS_EVIDENCE_READY": 146,
  "SYLLABUS_MAPPING_REVIEW_REQUIRED": 248,
  "IN_SYLLABUS_EVIDENCE_NOT_REQUIRED": 7,
  "IN_SYLLABUS_EVIDENCE_INSUFFICIENT": 44
}
```

## Database

- Unchanged (inventory): **True**
- Populations before: `{'CANONICAL_NCERT': 322, 'SOURCE_MISSING': 23, 'LEGACY_STUDYMATERIAL': 100}`
- Populations after: `{'CANONICAL_NCERT': 322, 'SOURCE_MISSING': 23, 'LEGACY_STUDYMATERIAL': 100}`

## Idempotency

```json
{
  "ok": true,
  "first_applied": 0,
  "second_applied": 0
}
```

## Provider smoke

```json
{
  "review_blueprint_id": "0d707747-0340-4628-826a-c20561cc8c91",
  "review_stop": "SYLLABUS_MAPPING_REVIEW_REQUIRED",
  "target_blueprint_id": "dc569dd4-30d6-46c2-acb1-25dec036b15d",
  "target_forced_insuff_stop": "NCERT_EVIDENCE_INSUFFICIENT",
  "provider_calls": 0,
  "ok": true
}
```

## Tests

```json
{
  "pending": true
}
```

## Failures

- None

## Limitations

- ncert_derived was omitted (optional for gate; path alone declares NCERT).
- provenance_tier remains ai for all 14.
- 49 provenance-review / 2 Electrostatics / 248 syllabus-review cases untouched.
- No MCQ generation performed.
