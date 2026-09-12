# Content readiness & ECAEP publishing campaign (WAVE-P0-4)

**Date:** 2026-08-31  
**Database audited:** local `trinetra_db` (development)  
**Rule:** Quality + coverage + provenance + review + usable volume — **not** raw publish count.

## Baseline (QUESTIONs, before this wave’s code changes)

| Metric | Count |
|--------|------:|
| Total questions | 90 |
| DRAFT | 78 |
| IN_REVIEW | 1 |
| APPROVED | 0 |
| PUBLISHED | **11** |
| ARCHIVED | 0 |

### By subject (status)

| Subject | DRAFT | IN_REVIEW | PUBLISHED |
|---------|------:|----------:|----------:|
| Physics | 38 | 1 | 6 |
| Chemistry | 30 | 0 | 1 |
| Botany | 10 | 0 | 1 |
| Zoology | 0 | 0 | 3 |

### Chapter concentration (drafts)

Almost all drafts sit on three chapters: *Current Electricity* (Physics), *Chemical Bonding…* (Chemistry), *Photosynthesis in Higher Plants* (Botany). Coverage is **narrow**, not syllabus-wide.

### Draft classification (non-destructive)

| Class | Count | Meaning |
|-------|------:|---------|
| READY_FOR_HUMAN_REVIEW | 77 | Structurally complete + concept mapped + version lineage (`model_used` / KU) |
| NEEDS_PROVENANCE | 1 | No model/KU lineage on latest version |
| STRUCTURALLY_INVALID | 0 | — |
| NEEDS_MAPPING | 0 | — |
| Suspect duplicate stem groups | 1 | Same stem in DRAFT + IN_REVIEW |

**Published quality check:** 0 of 11 published questions failed structural gates in the audit script.

## Actual lifecycle (code)

```
SOURCE / INGESTION (optional) → DRAFT
    → submit (+ AI check report, non-blocking) → IN_REVIEW
    → review approve → APPROVED
    → publish → PUBLISHED (student-visible)
    → archive → ARCHIVED
IN_REVIEW → request_changes → CHANGES_REQUESTED → edit → DRAFT
```

`AI_CHECKED` does **not** persist as `content_items.status` (instantaneous in v1).

### Permissions

| Action | Permission | Typical roles |
|--------|------------|---------------|
| Create | `content.create` | ADMIN, CONTENT_MANAGER, TEACHER |
| Edit own draft | `content.edit_own_draft` | + ownership |
| Submit | `content.submit_for_review` | same |
| Review (approve / changes) | `content.review` | ADMIN, CONTENT_MANAGER |
| Publish / bulk publish | `content.publish` | ADMIN, CONTENT_MANAGER |
| Archive | `content.archive` (single); bulk archive currently uses publish perm | ADMIN, CONTENT_MANAGER |

Students never receive non-`PUBLISHED` items on browse/practice/search.

## Quality gates (WAVE-P0-4)

On **create / update / submit / publish** for QUESTION:

- Stem + explanation non-empty  
- Exactly four options labeled A–D  
- Unique option texts  
- `correct_option` ∈ {A,B,C,D}  
- `difficulty` ∈ easy|medium|hard  
- `concept_id` required before submit/publish  

Bulk publish still only succeeds for **APPROVED** items that pass the same gates (per-item failures; no draft mass-publish).

Provenance: version fields `model_used`, `knowledge_unit_id`, prompt/cost metadata. Missing lineage logs `publish_without_version_lineage` — **does not invent NTA/official labels**.

## First content target (recommended)

Do **not** auto-publish the 77 “structurally ready” drafts.

Human campaign target (after SME review):

1. **≥25 published / subject** (Physics, Chemistry, Botany, Zoology) with explanations  
2. Prefer expanding **chapter diversity** over deepening one chapter only  
3. Full NEET mock (~180) remains **out of reach** until inventory grows  

Suggested interim label: **“limited practice bank”** — never “NEET content ready.”

## Admin tooling

- `GET /api/v1/cms/content-readiness` — status counts, subject breakdown, gate notes, chapter imbalance  
- Admin Content UI banner + **Editorial Review** queue (WAVE-P0-6)  
- Review packet + human checklist — see `docs/product/ECAEP_HUMAN_REVIEW.md`  
- Existing coverage grid remains for syllabus completeness  

## Student insufficient content

Practice/mock already return `NO_QUESTIONS_AVAILABLE` (422) with a clear message; practice UI shows `Alert`. No silent empty exam.

## What this wave did **not** do

- Did not mass-publish drafts  
- Did not claim content readiness  
- Did not redesign CMS / add RAG / SRS / auth changes  
- Did not modify production data  

## After implementation metrics

Published count is **unchanged by automation** (still 11 until humans publish). New safeguards reduce risk that invalid/unmapped items become student-visible.
