# Zoology IN_REVIEW — Controlled ECAEP Review Campaign (Preparation)

**Status:** Preparation only — not publication complete  
**Checkpoint base:** Phase 3.3-R1 `4ac1423`  
**Scope:** `subject_name=Zoology` + `status=IN_REVIEW` only  

## Purpose

Make the existing Zoology **IN_REVIEW** inventory easy and safe for **human** ECAEP review.

This document does **not** authorize:

- approve / reject / request_changes / publish / certify NCERT  
- bulk processing, mapping, regeneration, or Practice/Mock changes  
- any mutation of the ~5,024 unmapped DRAFT backlog  

## How to open the campaign

1. Admin login (editorial permission: `content.review`).
2. Open: `/admin/ai-review?subject_name=Zoology&status=IN_REVIEW`
3. Confirm the **matching total** equals the authoritative API/DB count (re-query; do not hard-code).
4. Open each row → review packet / Admin content page.
5. Complete the human checklist. Leave Approve / Publish / Reject / Certify **untouched** until an authorized editorial session.

API equivalents:

- `GET /api/v1/cms/editorial-review-queue?subject_name=Zoology&status=IN_REVIEW`
- `GET /api/v1/cms/content-items/{id}/review-packet`

## Review packet fields (as exposed)

Where available, the packet surfaces:

| Field | Source |
|-------|--------|
| Question ID | `item_id` |
| Subject / Chapter / Topic / Concept | `academic.*` |
| Class | `academic.class_level` (from `academic.chapters.class_level`; may be null → unavailable) |
| Stem / Options A–D / Correct / Explanation / Difficulty | `question.*` |
| Provenance | `provenance` (as stored — verify; do not invent) |
| NCERT evidence | `ncert` (provenance ≠ certification) |
| Structural readiness | `structural` (≠ scientific validity) |
| Publication eligibility / blockers | `publication_eligibility` |
| Suspected duplicates | `suspected_duplicates` (exact stem; human decides) |
| Checklist | `checklist` (assistive only) |

Missing evidence must be reported as missing — never fabricated.

## ECAEP human checklist (must be judged by a person)

A. Scientific correctness  
B. Exactly one defensible answer  
C. Four meaningful options  
D. No duplicate / near-duplicate  
E. Clear wording  
F. No ambiguity  
G. Correct chapter / topic / concept  
H. NCERT alignment / evidence  
I. Appropriate NEET relevance  
J. Appropriate difficulty  
K. Explanation correctness  
L. Provenance completeness  
M. Publication blockers  

A field existing is **not** a pass.

## No quota publishing

Do **not** treat “45 Zoology published for mock” as an acceptance criterion.  
Only questions that pass human ECAEP gates may later become publication-eligible.

## Read-only campaign prep artifact

```bash
cd apps/backend
python scripts/zoology_in_review_campaign_prep.py
```

Writes SELECT-only audit files under `docs/audits/zoology_in_review_campaign_prep_YYYYMMDD.{json,md}`.

## Related

- `docs/product/ECAEP_HUMAN_REVIEW.md`
- `docs/product/ECAEP_CAMPAIGN_CONTROL.md`
- `docs/product/CONTENT_READINESS.md`
- `docs/architecture/ecaep.md`
