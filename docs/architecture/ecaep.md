# ECAEP — Content Authoring & Editorial Platform (v1)

Condensed in-repo reference. Full spec with diagrams: the published ECAEP
artifact.

## Tables

- `cms.content_items` — `id, content_type, concept_id, title, slug, tags,
  language, status, current_version_id, latest_version_id, created_by,
  created_at, updated_at`
- `cms.content_versions` — `id, content_item_id, version_no, body (jsonb),
  workflow_state, ai_check_report (jsonb), change_summary, authored_by,
  authored_at`
- `cms.content_reviews` — `id, content_version_id, reviewer_id, decision,
  comment, reviewed_at`

## content_type values

`CONCEPT_NOTE · QUESTION · FLASHCARD · DIAGRAM · VIDEO_REF · FORMULA_SHEET`
— each with its own Pydantic body schema (see ADR-0009).

## Workflow

```
DRAFT --submit--> AI_CHECKED --(auto)--> IN_REVIEW
IN_REVIEW --approve--> APPROVED --publish--> PUBLISHED
IN_REVIEW --request_changes--> CHANGES_REQUESTED --revise--> DRAFT
PUBLISHED --edit--> DRAFT (new version; old stays live until published)
PUBLISHED --archive--> ARCHIVED
```

## Roles

Author (SME) → Reviewer → Approver (Content Manager) → Admin (break-glass
`force_edit_published`). Reuses Identity's role/permission model — no
separate role system.

## Definition of done

A content item goes through create → edit → submit → AI check → review →
approve → publish → archive with a full audit trail in `content_reviews`
and `content_versions`. AI Tutor retrieval only ever reads `PUBLISHED`
content.
