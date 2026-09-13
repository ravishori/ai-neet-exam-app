# Content readiness & ECAEP publishing campaign

**Rule:** Quality + coverage + provenance + review + usable volume — **not** raw publish count.
**Inventory truth:** Counts below in the original WAVE-P0-4 baseline are **historical**. Current inventory is **DB-derived and must be revalidated**.

```bash
cd apps/backend
python scripts/content_readiness_inventory.py
# Admin (authorized): GET /api/v1/cms/content-readiness
# Editorial queue: GET /api/v1/cms/editorial-review-queue
# Subject intake: GET /api/v1/cms/content-intake?subject_name=Chemistry&status=DRAFT
# Zoology queue: GET /api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW
```

Do **not** hard-code published counts into product claims. Do **not** mass-publish the unmapped DRAFT backlog. Provenance/source fields are **not** NCERT certification.

**Full 180-question NEET-pattern mock:** remains **blocked** until subject published allocation supports the exam engine (notably Zoology). Do not publish solely to hit a numerical quota.

### Phase 3.3 operational additions

- Zoology IN_REVIEW filter via `subject_name=Zoology` (queue rows include `ncert` + `blocking_reasons`)
- Review packet exposes first-class `ncert` and `publication_eligibility` (approval is not publication)
- Controlled Chemistry/Zoology intake via `GET /content-intake` (read-only; excludes unmapped backlog)
- Unmapped ~5,024 DRAFTs remain **frozen**

### Phase 3.3-R1 Admin queue UX + complete campaign counts

Admin UI: `/admin/ai-review`

- **Subject filter** (academic subjects from API; maps to `subject_name`)
- **Status filter** (persisted workflow states + All)
- URL state example: `?subject_name=Zoology&status=IN_REVIEW`
- Defaults: `IN_REVIEW`, Batch A / pilot gates **off** (so Zoology IN_REVIEW is directly selectable)
- Queue pagination already uses `limit`/`offset` + `meta.total` (total = complete matching population; page shows a slice)
- Campaign dashboard inventory / subject / Biology pipeline counts are **COMPLETE DB aggregates**
- Structural quality percentages remain an explicit **SAMPLE** (not labelled as full-inventory totals)
- Still admin/editorial-only (`content.review`); never auto-approves or auto-publishes

---

## Historical baseline (WAVE-P0-4, 2026-08-31) — NOT current truth

The following table is retained for audit trail only. It described a local DB snapshot at wave start (**90** questions / **11** PUBLISHED). Later audits (Phase 3.1+) found a much larger bank; **always re-run the inventory script**.

| Metric (historical) | Count |
|---------------------|------:|
| Total questions | 90 |
| DRAFT | 78 |
| IN_REVIEW | 1 |
| APPROVED | 0 |
| PUBLISHED | **11** |
| ARCHIVED | 0 |

### Phase 3.2 operational focus

1. Chemistry readiness measurable (status / mapping / chapters / NCERT evidence)
2. Zoology readiness measurable (incl. IN_REVIEW queue)
3. ECAEP queue visibility (`editorial-review-queue`, review packets, campaign dashboard)
4. No-auto-publish safeguards preserved (approve â‰  publish; generate â‰  publish)
5. Unmapped DRAFT disposition labels (`disposition:*` model) â€” classify, do not bulk-publish

## Actual lifecycle (code)

```
SOURCE / INGESTION (optional) â†’ DRAFT
    â†’ submit (+ AI check report, non-blocking) â†’ IN_REVIEW
    â†’ review approve â†’ APPROVED
    â†’ publish â†’ PUBLISHED (student-visible)
    â†’ archive â†’ ARCHIVED
IN_REVIEW â†’ request_changes â†’ CHANGES_REQUESTED â†’ edit â†’ DRAFT
```

`AI_CHECKED` does **not** persist as `content_items.status` (instantaneous in v1).
`certify-ncert` does **not** publish.

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

## Quality gates

On **create / update / submit / publish** for QUESTION:

- Stem + explanation non-empty
- Exactly four options labeled Aâ€“D
- Unique option texts
- `correct_option` âˆˆ {A,B,C,D}
- `difficulty` âˆˆ easy|medium|hard
- `concept_id` required before submit/publish

Bulk publish still only succeeds for **APPROVED** items that pass the same gates (per-item failures; no draft mass-publish).

Provenance: version fields `model_used`, `knowledge_unit_id`, prompt/cost metadata. Missing lineage logs `publish_without_version_lineage` â€” **does not invent NTA/official labels**.

## First content target (recommended)

Do **not** auto-publish structurally ready or unmapped drafts.

Human campaign guidance:

1. Prefer **Chemistry** and **Zoology** ECAEP progression with chapter diversity
2. Prefer expanding **chapter diversity** over deepening one chapter only
3. Full NEET mock (~180) remains **out of reach** until published subject allocation supports it

Suggested interim label: **â€œlimited practice bankâ€** â€” never â€œNEET content ready.â€

## Admin tooling

- `GET /api/v1/cms/content-readiness` â€” status counts, subject breakdown, gate notes, chapter imbalance
- `GET /api/v1/cms/editorial-review-queue` â€” prioritized ECAEP queue
- `GET /api/v1/cms/content-items/{id}/review-packet` â€” review packet
- `GET /api/v1/cms/editorial-campaign` / `editorial-coverage` â€” campaign + imbalance
- Admin Content UI banner + **Editorial Review** queue
- Review packet + human checklist â€” see `docs/product/ECAEP_HUMAN_REVIEW.md`

## Student insufficient content

Practice/mock already return `NO_QUESTIONS_AVAILABLE` (422) with a clear message; practice UI shows `Alert`. No silent empty exam. Practice selects **QUESTION + PUBLISHED only**.

## What Phase 3.2 did **not** do

- Did not mass-publish drafts or the unmapped backlog
- Did not invent NCERT verification
- Did not redesign student UI / add RAG / SRS / multi-tenancy
- Did not modify production data via automation

