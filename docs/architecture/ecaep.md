# ECAEP — Content Authoring & Editorial Platform (v1)

Condensed in-repo reference. Full historical diagram may still show durable
`AI_CHECKED`; **runtime code collapses AI check into IN_REVIEW** (see
`content_workflow_service.py`).

## Tables

- `cms.content_items` — `id, content_type, concept_id, title, slug, tags,
  language, status, current_version_id, latest_version_id, created_by,
  created_at, updated_at`
- `cms.content_versions` — `id, content_item_id, version_no, body (jsonb),
  workflow_state, ai_check_report (jsonb), change_summary, authored_by,
  authored_at`, plus optional lineage (`knowledge_unit_id`, `model_used`, …)
- `cms.content_reviews` — `id, content_version_id, reviewer_id, decision,
  comment, reviewed_at`

## content_type values

`CONCEPT_NOTE · QUESTION · FLASHCARD · DIAGRAM · VIDEO_REF · FORMULA_SHEET`
— each with its own Pydantic body schema (see ADR-0009).

## Workflow (as implemented)

```
DRAFT --submit--> IN_REVIEW   (AI Evaluator report stored; does not block)
IN_REVIEW --approve--> APPROVED --publish--> PUBLISHED
IN_REVIEW --request_changes--> CHANGES_REQUESTED --revise--> DRAFT
PUBLISHED --archive--> ARCHIVED
```

Student-visible content = **`PUBLISHED` only** (`current_version_id`).

## Publishing quality gates (WAVE-P0-4)

Publish (and QUESTION submit) re-validate body shape. For QUESTION:

- Exactly four options A–D, unique texts, non-empty stem/explanation
- `correct_option` must match a label
- `concept_id` required
- Permission `content.publish` required
- Status must be `APPROVED` (drafts cannot publish; bulk publish fails those items)

Never mass-publish drafts. Campaign guidance: `docs/product/CONTENT_READINESS.md`.

## Admin tooling (WAVE-P0-6 / P0-7)

- `GET /api/v1/cms/editorial-review-queue` — prioritized SME queue (`priority_reasons`, `recommended_next`)  
- `GET /api/v1/cms/content-items/{id}/review-packet` — structured review packet + checklist  
- `GET /api/v1/cms/editorial-coverage` — chapter draft concentration vs published gaps  
- `GET /api/v1/cms/editorial-campaign` — Physics/Chemistry/Biology planning targets + chapter table + quality metrics  
- Admin UI: **Editorial Review & Campaign** (`/admin/ai-review`) + enriched content detail  
- Single-item review/publish/archive write audit logs (`content.review` / `content.publish` / `content.archive`)  
- See `docs/product/ECAEP_HUMAN_REVIEW.md` and `docs/product/ECAEP_CAMPAIGN_CONTROL.md`

## Roles / permissions

Author → Reviewer (`content.review`) → Publisher (`content.publish`). Seeded
roles: ADMIN, CONTENT_MANAGER (and TEACHER for create/submit). SUPER_ADMIN
bypass applies as elsewhere.

## Definition of done (item)

Create → edit → submit → human review → approve → publish → (optional archive).

## Definition of done (product content readiness)

QUALITY + COVERAGE + PROVENANCE + REVIEW + USABLE VOLUME — see product audit.
Increasing `PUBLISHED` count alone is **not** content readiness.
