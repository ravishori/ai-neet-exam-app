# ECAEP Human Editorial Review Campaign (WAVE-P0-6)

**Date:** 2026-08-31  
**Purpose:** Make human SME review efficient, auditable, and safe.  
**Not the purpose:** Auto-publish drafts, certify scientific correctness, or claim content readiness.

## Lifecycle (unchanged)

```
DRAFT → submit → IN_REVIEW → approve → APPROVED → publish → PUBLISHED
                 ↘ request_changes → CHANGES_REQUESTED → edit → DRAFT
```

AI check on submit is **assistance only** — it does not approve or publish.

## Reviewer workflow

1. Open **Admin → Editorial Review** (`/admin/ai-review`).
2. Filter by status / difficulty / provenance / structural readiness.
3. Prefer structurally ready items in coverage-gap chapters (queue prioritization).
4. Open the item → review packet shows stem, options, correct answer, explanation, mapping, provenance as stored, suspected duplicates, checklist.
5. Complete checklist (assistive) → **Approve** or **Request changes** with a note.
6. Publisher (same CONTENT_MANAGER/ADMIN roles today) **Publish** only when status is APPROVED and WAVE-P0-4 gates pass.

## Prioritization (explainable)

1. Structurally valid body  
2. Concept mapped  
3. Known version lineage (`model_used` or `knowledge_unit_id`)  
4. Chapters with fewer PUBLISHED questions (coverage gap)  
5. Difficulty balance hint  
6. Older submissions first  

Scores do **not** certify science.

## APIs

| Endpoint | Permission | Notes |
|----------|------------|-------|
| `GET /api/v1/cms/editorial-review-queue` | `content.review` | Filtered, prioritized queue |
| `GET /api/v1/cms/content-items/{id}/review-packet` | `content.review` | Full SME packet + checklist |
| `GET /api/v1/cms/editorial-coverage` | `content.review` | Chapter concentration guidance |
| Existing submit / review / publish | unchanged | Plus audit logs on review/publish/archive |

## Campaign target (human)

≥25 **reviewed and published** questions per Physics / Chemistry / Botany / Zoology **while** improving chapter diversity.

Do **not** define success as “publish all drafts.”

## Safety

- No mass status updates in this wave  
- No inventing provenance  
- Publish gates from WAVE-P0-4 preserved  
- Students still see **PUBLISHED** only  
- TEACHER can create/submit but cannot review/publish  
- STUDENT cannot access editorial endpoints  

## Related

- `docs/architecture/ecaep.md`  
- `docs/product/CONTENT_READINESS.md`  
- `docs/product/PRACTICE_AVAILABILITY.md`
