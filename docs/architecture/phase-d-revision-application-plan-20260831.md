# Phase D.4 — Controlled Revision Application Plan

**Banner:** READ-ONLY ANALYSIS — NO DATABASE CHANGES — NO ECAEP ACTION — NO PUBLICATION

**Generated:** 2026-08-31  
**Database:** `trinetra_db` (verified read-only)  
**Pilot:** `phase-d-30-mcq-authorized-20260825`  
**Writes this phase:** `0`

**Authority:** Phase D.2 revision proposals + Phase D.3 final candidate audit. This document prepares application; it does **not** authorize Phase D.5 execution.

---

## Executive revision-application verdict

```text
READY FOR HUMAN APPROVAL
```

Caveats (must be acknowledged before D.5):

1. Taxonomy seed for Blackman (`limiting-factors`) is a **separate** human gate (see taxonomy resolution report). Body KEEP/REVISE for those two may proceed without remapping; remapping must wait for the concept to exist.
2. Prefer `ContentWorkflowService.update_draft` over raw SQL for body changes.
3. `update_draft` today does **not** copy `content_version_knowledge_units` — D.5 must extend the service or copy KU refs after creating the new version.
4. `concept_id` lives on `cms.content_items`; there is no dedicated PATCH for concept-only remaps — D.5 needs a controlled item update path.
5. Do **not** publish, submit ECAEP, or move `current_version_id` during draft revision.

---

## LIVE vs PROPOSED

### LIVE (database now)

| Check | Result |
|-------|--------|
| Pilot questions | **30** |
| DRAFT | **30** |
| PUBLISHED | **0** |
| `latest_version_id` set | 30/30 |
| `current_version_id` set | 30/30 |
| latest == current | 30/30 |
| All at `version_no` | **1** |
| Global QUESTION | DRAFT 78 / IN_REVIEW 1 / PUBLISHED 11 |

### PROPOSED (in-memory final set from D.3 — not applied)

```text
21 ORIGINAL APPROVE (unchanged bodies)
+ 1 KEEP (e6b9fb1e body unchanged; taxonomy remap deferred)
+ 6 REVISE (new content_version via update_draft)
+ 2 REPLACE (new content_version via update_draft)
= 30 candidates
```

Do not confuse LIVE row bodies with PROPOSED stems.

---

## Versioning strategy (from application code)

Source: `ContentWorkflowService` in `apps/backend/app/modules/cms/services/content_workflow_service.py`.

| Pointer | Meaning | When set |
|---------|---------|----------|
| `latest_version_id` | Editorial / history tip | `create_item`, `update_draft` |
| `current_version_id` | Published / student-served tip | **`publish` only** |

### Correct DRAFT revision pattern

```text
new content_versions row (version_no = prior + 1)
  → latest_version_id := new version
  → current_version_id UNCHANGED (still points at v1 for these DRAFTs)
  → status remains DRAFT
  → workflow_state on new version = DRAFT
  → NO publish
  → NO submit_for_review
```

Admin UI resolves **`latest_version`**. Student/search APIs require **`status = PUBLISHED`** and **`current_version_id`**. After revision, DRAFT items remain invisible to students even if `current_version_id` still points at the pre-revision body.

### Forbidden

- Overwriting existing `content_versions.body`
- Auto-advancing `current_version_id` on draft edit
- Collapsing ECAEP / publish into D.5 apply

### KU provenance gap (must fix in D.5 implementation)

`create_item` writes `ContentVersionKnowledgeUnit` rows; `update_draft` does **not**. After body revision, copy KU join rows (and singular `knowledge_unit_id` / `knowledge_unit_version` if present) from the previous latest onto the new version, or extend `update_draft` to do so. Otherwise pilot lineage and provenance audits break.

### Metadata / concept remaps

`concept_id` is on **`cms.content_items`**, not on versions. Remapping does not by itself require a new `content_version`. When body also changes (e.g. `ade9900b`), do both: new version + item `concept_id` update.

There is currently no public CMS PATCH that updates `concept_id` alone (`PATCH /content-items/{id}` only accepts body). D.5 should add a controlled service method or use an approved admin script — not ad-hoc SQL without review.

---

## Question-by-question application table

| ID | Action | Current Version | Proposed Version | Metadata Change | Answer Change | Difficulty Change | Provenance Change |
|----|--------|-----------------|------------------|-----------------|---------------|-------------------|-------------------|
| `e6b9fb1e` | KEEP | v1 `f89eded3…` | none (body) | **Deferred** → `limiting-factors` after seed | No | No | No |
| `8d50e829` | REVISE | v1 `a614bc69…` | **new v2** | **Deferred** taxonomy; body only in D.5 body gate | No (A) | hard→medium | Copy KU to v2 |
| `85fee888` | REPLACE | v1 `d4c89a95…` | **new v2** | Keep `photorespiration` | A→**B** | No | Copy KU to v2 |
| `87f621ab` | REVISE | v1 `012ca4ee…` | **new v2** | No | No (C) | hard→medium | Copy KU to v2 |
| `863f1289` | REVISE | v1 `e8c46c44…` | **new v2** | No | No (B) | No | Copy KU to v2 |
| `ade9900b` | REVISE | v1 `32b58f53…` | **new v2** | **Yes** → `ohms-law` / `ohms-law-concept` (`9071ef5d…`) | No (A) | No | Copy KU to v2 |
| `c7a54ae9` | REPLACE | v1 `4117b472…` | **new v2** | No (already ohms-law) | No (A, new item) | No | Copy KU to v2 |
| `7b80d6db` | REVISE | v1 `fef85035…` | **new v2** | No | No (**A** retained) | No | Copy KU to v2 |
| `a42a3589` | REVISE | v1 `8d39848a…` | **new v2** | No | No (A) | medium→easy | Copy KU to v2 |
| *21 others* | KEEP | v1 (unchanged) | none | No | No | No | No |

Counts for flagged set: **KEEP 1 · REVISE 6 · REPLACE 2**. Plus **21** untouched originals.

---

## Special re-verifications (proposals only)

### `85fee888` REPLACE — photorespiration pathway consequences

| Check | Result |
|-------|--------|
| NCERT | §11.9 — no sugar/ATP/NADPH; CO₂ released; ATP utilised |
| Correct | **B** |
| Options | Four distinct; single best answer |
| Dup vs `10d4d997` | Cleared (different LO; products twin retained) |
| Concept | `photorespiration` — appropriate |
| Difficulty | medium |

### `c7a54ae9` REPLACE — Ohm scaling

| Check | Result |
|-------|--------|
| Relation | V = RI ⇒ R = V/I |
| Transform | V×2, I÷2 ⇒ R×4 |
| Correct | **A** (“becomes four times”) |
| Concept | `ohms-law-concept` |

### `7b80d6db` REVISE — Kirchhoff wording

Independent derivation (D.3): I labelled P→N ⇒ V(P)−V(N)=ε+Ir ⇒ V(N)−V(P)=−ε−Ir. Correct remains **A**. Revision clarifies labelling; does not change the key.

### `ade9900b` metadata

Retag from `kirchhoffs-laws` / `kcl-kvl` → `ohms-law` / `ohms-law-concept` (`9071ef5d-b62f-4159-91b6-90436a7705e6`). Body REVISE still creates a new version; concept remap is item-level.

### Blackman pair — taxonomy

Do **not** auto-create or remapped in the MCQ apply transaction unless taxonomy seed is **separately** approved. See `phase-d-taxonomy-resolution-20260831.md`.

---

## Before-snapshot SQL (for future D.5 — do not run writes now)

Read-only capture of the 30 (parameterize `:pilot_ids` as the known UUID array):

```sql
-- BEFORE SNAPSHOT (SELECT only)
SELECT
  ci.id AS content_item_id,
  ci.status,
  ci.concept_id,
  ac.code AS concept_code,
  t.code AS topic_code,
  ch.code AS chapter_code,
  s.code AS subject_code,
  ci.current_version_id,
  ci.latest_version_id,
  cv.id AS content_version_id,
  cv.version_no,
  cv.workflow_state,
  cv.body,
  cv.model_used,
  cv.prompt_version,
  cv.knowledge_unit_id,
  cv.knowledge_unit_version,
  (
    SELECT json_agg(json_build_object(
      'knowledge_unit_id', k.knowledge_unit_id,
      'knowledge_unit_version', k.knowledge_unit_version
    ))
    FROM cms.content_version_knowledge_units k
    WHERE k.content_version_id = cv.id
  ) AS ku_relationships
FROM cms.content_items ci
JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
LEFT JOIN academic.concepts ac ON ac.id = ci.concept_id
LEFT JOIN academic.topics t ON t.id = ac.topic_id
LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
LEFT JOIN academic.subjects s ON s.id = ch.subject_id
WHERE ci.id = ANY(:pilot_ids)
ORDER BY ci.id;
```

Persist snapshot to file before any D.5 transaction.

---

## Future transaction plan (Phase D.5 — NOT executed here)

Prefer application services over inventing raw SQL.

```text
BEGIN (or service-level unit of work)
  1. Verify pilot = 30 DRAFT, 0 PUBLISHED; pointers intact; global counts
  2. Load before-snapshot; assert expected latest version_ids match plan
  3. FOR each REVISE/REPLACE:
       ContentWorkflowService.update_draft(body=proposed, change_summary=…)
       Copy KU refs from prior latest → new latest
       Assert status=DRAFT; current_version_id unchanged; latest_version_id advanced
  4. FOR ade9900b:
       Update content_items.concept_id → ohms-law-concept UUID
  5. IF taxonomy seed separately approved:
       Remap e6b9fb1e + 8d50e829 concept_id → limiting-factors
     ELSE:
       Skip remap; leave AMBER taxonomy note
  6. Verify: 30 still DRAFT; 21 untouched version_ids unchanged;
     8 new versions exist; no PUBLISHED; no IN_REVIEW transition; student APIs still hide DRAFT
COMMIT
```

**Out of scope for D.5 apply:** `submit_for_review`, `review`, `publish`, ECAEP approval, taxonomy seed creation (unless separately authorized).

---

## Rollback plan

| Change | Rollback |
|--------|----------|
| New `content_versions` | Point `latest_version_id` back to pre-apply version IDs from snapshot; leave orphan versions soft-ignored (do not DELETE unless ops policy requires) |
| `concept_id` remaps | Restore prior `concept_id` from snapshot |
| Taxonomy seed (if applied) | Separate reverse migration; remapped items first |
| Status / publish | Must not have changed; if accidentally published — escalate (out of D.5 design) |

Do not execute rollback in D.4 (nothing to roll back).

---

## Test plan for future application

### Database

- [ ] Still exactly 30 pilot questions
- [ ] 30 DRAFT, 0 PUBLISHED
- [ ] 8 items: `latest_version_id` ≠ pre-apply; `version_no` = 2
- [ ] Those 8: `current_version_id` still equals pre-apply v1
- [ ] 22 KEEP items: version pointers unchanged
- [ ] KU count ≥ 1 on every new latest version
- [ ] Global DRAFT/IN_REVIEW/PUBLISHED counts unchanged except as expected by intentional concept-only updates (counts by status unchanged)

### Content

- [ ] Proposed stems/options/answers/explanations match D.2 JSON for each REVISE/REPLACE
- [ ] `85fee888` answer B; `c7a54ae9` R×4 → A; `7b80d6db` answer A

### Taxonomy

- [ ] `ade9900b` → `ohms-law-concept`
- [ ] Blackman pair: either remapped to `limiting-factors` (if seed approved) or still `photorespiration` with documented deferral

### API

- [ ] Admin GET item returns **latest** body (revised)
- [ ] Student browse/search with PUBLISHED filter returns **0** of these 30

### Regression

- [ ] 21 approved originals byte-identical bodies
- [ ] Unrelated CMS questions untouched
- [ ] Near-dup with `10d4d997` remains cleared

---

## ECAEP governance (must not collapse)

```text
AI proposal (D.2/D.3/D.4)
    ↓
Human review of proposed revisions (+ separate taxonomy approval)
    ↓
Explicit approval
    ↓
Controlled application (D.5)
    ↓
Post-application audit
    ↓
ECAEP submission
    ↓
Human ECAEP decision
    ↓
Publication
```

D.4 stops at “prepare for human approval.”

---

## Safety confirmation

```text
Database modified = NO
ECAEP submitted = NO
Questions published = NO
Revisions applied = NO
Taxonomy concept created = NO
```
