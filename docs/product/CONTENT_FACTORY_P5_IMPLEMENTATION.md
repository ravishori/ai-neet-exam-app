# FACTORY-P5 Implementation — Human Sampling + Exception Review UX

**Status:** COMPLETE · 2026-09-01  
**Scope:** Wire P4 QA/sampling to human decisions + admin queue without changing ECAEP.  
**Non-goals:** Generation · AI judge · auto-approve/publish · bulk ECAEP transitions · regeneration · pgvector · 1k scale.

---

## Architecture

```
ReviewSample (P4)
    ↓ materialize
FactoryReviewItem (GREEN_SAMPLE | YELLOW | RED)
    ↓ human decision
ACCEPT | CORRECTION_REQUIRED | REJECT
    ↓
ecaep_submit_eligible (ACCEPT only) — still DRAFT
    ↓ (manual, separate)
ECAEP submit → IN_REVIEW → APPROVE → PUBLISH
```

Factory review status ≠ ContentItem.status.

---

## ReviewSample / FactoryReviewItem

P4 `ReviewSample` retained. P5 adds `cms.factory_review_items` per candidate:

- selection_class, selection_reason, policy/qa versions
- review_status: SELECTED → IN_REVIEW → ACCEPTED | CORRECTION_REQUIRED | REJECTED
- checklist JSONB, failure_reasons[], reviewer note/timestamps
- `ecaep_submit_eligible` on ACCEPT only

Created automatically when a sample is created (and via `/review-samples/{id}/materialize`).

**Regeneration:** DEFERRED — corrections use existing CMS draft edit; do not overwrite candidates.

---

## Review workflow

1. P3 generate DRAFTs → P4 QA → P4 sample  
2. Open `/admin/factory-review`  
3. Inspect packet (question, mapping, lineage, automated QA)  
4. Complete checklist + decision  
5. If ACCEPT: optionally open content item and use normal ECAEP submit  
6. If CORRECTION_REQUIRED: edit via CMS, re-QA later as needed  
7. If REJECT: retained with reasons (not silently deleted)

---

## GREEN / YELLOW / RED

| Class | Handling |
|-------|----------|
| GREEN_SAMPLE | Stratified sample only |
| YELLOW | 100% in queue |
| RED | 100% exception queue; quarantine; excluded from GREEN sample |

---

## Checklist / decisions / feedback

Checklist A–I (scientific…provenance) persisted as evidence — never auto-approves.  
Decisions: ACCEPT / CORRECTION_REQUIRED / REJECT (note required for last two).  
Failure taxonomy: SCIENTIFIC_ERROR, WRONG_ANSWER, … NEET_UNSUITABLE.

---

## API

| Method | Path | Perm |
|--------|------|------|
| GET | `/factory-review/dashboard` | `content.review` |
| GET | `/factory-review/queue` | `content.review` |
| GET | `/factory-review/items/{id}` | `content.review` |
| POST | `/factory-review/items/{id}/decision` | `content.review` + CSRF |
| POST | `/review-samples/{id}/materialize` | `content.factory.execute` |

---

## Admin UX

- Nav: **Factory Review** → `/admin/factory-review`
- Dashboard counters (not “accuracy”)
- Risk-sorted queue with filters
- Packet + checklist + decisions
- Content detail shows `factory_qa` card + link

---

## Tests

`tests/test_content_factory_p5.py` — RBAC, ACCEPT without ECAEP mutation, reproducibility, RED∉GREEN sample.  
No live Anthropic.

---

## Live pilot readiness (do not auto-run)

1. Top up Anthropic credits  
2. `python scripts/run_factory_p3_pilot.py`  
3. `POST .../content-batches/{id}/qa`  
4. `POST .../content-batches/{id}/sample` `{"seed":42}`  
5. Review at `/admin/factory-review`  
6. ECAEP submit/approve/publish only for intentionally accepted items  

---

## Recommended next operational step

Execute the controlled **~100-question** pilot once credits are available. **Do not** scale to 1,000 until that pilot’s quality/cost metrics are reviewed.
