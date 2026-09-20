# ECAEP Editorial Campaign Control (WAVE-P0-7)

**Date:** 2026-08-31  
**Purpose:** Help SMEs execute the human NEET content campaign with clear targets and chapter diversity.  
**Not permission to auto-publish.**

## Planning targets

| Area | Subjects included | Target published |
|------|-------------------|-----------------:|
| Physics | Physics | 25 |
| Chemistry | Chemistry | 25 |
| Biology | Botany + Zoology | 25 |

Targets are **planning only**. Quality over quantity. Structural validity ≠ scientific validity.

## APIs

| Endpoint | Permission | Role |
|----------|------------|------|
| `GET /api/v1/cms/editorial-campaign` | `content.review` | Campaign dashboard |
| `GET /api/v1/cms/editorial-review-queue` | `content.review` | Queue + `priority_reasons` + `recommended_next` |
| Existing review-packet / coverage / readiness | unchanged | |

## Prioritization (explainable)

1. Structurally valid  
2. Concept mapped  
3. Known provenance lineage  
4. Campaign area below target  
5. Chapter with fewer published questions  
6. Difficulty diversification hint  
7. Older pending items  

Each queue row includes `priority_reasons` (human-readable). Example:  
“Chemistry is below target (1/25; 24 remaining)” / “Chapter X currently has no published questions.”

## UI

Admin → **Editorial Review** (`/admin/ai-review`):

- Subject progress bars (planning, not gamification)  
- Inventory badges (draft / in review / approved / published / needs changes / missing provenance / missing mapping / structurally invalid)  
- Chapter coverage table with concentration flags  
- Quality metrics with explicit structural-vs-scientific disclaimer  
- Recommended next review callout  

## Safety

- No auto-approve / auto-publish / mass draft publish  
- WAVE-P0-4 publish gates unchanged  
- Student surfaces remain PUBLISHED-only  
- Provenance missing → “Source verification required” (never invented)

## Related

- `docs/product/ECAEP_HUMAN_REVIEW.md`  
- `docs/product/CONTENT_READINESS.md`
