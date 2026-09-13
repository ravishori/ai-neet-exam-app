# Content readiness inventory (2026-09-13)

**Phase 3.2** · SELECT-only · DB-derived · never publish

Target: `localhost:5432/trinetra_db`

## Safety

- Student-visible status: **PUBLISHED** only
- No auto-publish; do not mass-publish unmapped drafts
- Provenance ≠ NCERT certification

## Chemistry

```json
{
  "DRAFT": 73,
  "PUBLISHED": 46
}
```

Readiness: `{"NEEDS REVIEW": 73, "NEEDS SOURCE": 1, "READY": 45}`
Chapters with zero published: **0**
NCERT-verified (evidence-based count): **45**

## Zoology

```json
{
  "PUBLISHED": 23,
  "DRAFT": 41,
  "IN_REVIEW": 100
}
```

Readiness: `{"NEEDS SOURCE": 3, "NEEDS REVIEW": 141, "READY": 20}`
Chapters with zero published: **2**

## Unmapped DRAFT disposition (heuristic)

```json
{
  "UNMAPPED": 5024
}
```

## NEET mock

Zoology published=23 (<45 minimum for balanced Biology allocation). Chemistry published=46. Revalidate before claiming mock readiness.

## Revalidation

Re-run: cd apps/backend && python scripts/content_readiness_inventory.py. Do not hard-code these counts into product docs as permanent truth.
