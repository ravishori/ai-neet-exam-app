# Practice availability & thin-content resilience (WAVE-P0-5)

**Date:** 2026-08-31  
**Goal:** Safe, honest student experience when published inventory is thin — **not** “content ready.”

## Behaviour before

| Area | Behaviour |
|------|-----------|
| Practice/mock pool | PUBLISHED only (already) |
| Zero published in scope | `422 NO_QUESTIONS_AVAILABLE` |
| Fewer than requested | Silent shrink to available count |
| Recommendations / revision due | Could point at concepts with **0** published questions → Practice Now dead-end |
| Dashboard CTA errors | Generic Alert message |
| Soft-deleted rows | Not excluded from assessment pool |

## Behaviour after

| Area | Behaviour |
|------|-----------|
| Practice/mock pool | PUBLISHED + `deleted_at IS NULL` |
| Zero published | Same code `NO_QUESTIONS_AVAILABLE` with clearer student copy |
| Fewer than requested | Unchanged shrink contract; `meta.available_count` / `requested_count` / `delivered_count` / `shrunk` on practice/mock create |
| Recommendations / revision | SQL `EXISTS` published QUESTION filter; `published_question_count` on payloads |
| Dashboard / practice / mock UX | Code-aware copy + links (try another topic / dashboard) |
| Critical alerts | Expected scarcity remains `AppError` 422 — not unhandled 500 |

## Contract notes

- Recommendations remain **rule-based** (due → weak → new), not ML.
- Shrinking a requested N when fewer PUBLISHED exist is the **existing** product contract; meta makes it auditable.
- This wave does **not** publish content or claim content readiness.

## Related

- Content campaign: `docs/product/CONTENT_READINESS.md`
- Assessment repository: `published_question_ids_for_scope`
- Learning: `MasteryRepository._concept_has_published_questions`
