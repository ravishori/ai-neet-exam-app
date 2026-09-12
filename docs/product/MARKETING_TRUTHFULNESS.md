# Marketing truthfulness — TALOS

**Wave:** P0-1 (documentation only)  
**Date:** 2026-08-31

## Positioning (approved)

Use:

> **AI-powered NEET preparation platform under active development**

Avoid implying:

- Fully production-ready NEET preparation at scale  
- Complete content bank / full NEET mock readiness  
- Production-verified MFA, SMTP, or RLS  
- Vector RAG, Digital Twin, or 12-agent AI OS as shipping features  
- Fallback AI mode as equivalent to Claude-quality tutoring  

## Feature readiness ≠ production readiness

A capability may be **implemented in code** while still needing staging
verification, E2E coverage, security/ops configuration, content volume, and
monitoring before any “production-ready” claim.

## Public landing page (frontend — not changed in WAVE-P0-1)

**File:** `apps/web/src/app/(public)/page.tsx`  
**WAVE-P0-1 scope restriction:** no frontend application code changes.

### Current (stale) claims on the page

| UI claim | Reality |
|----------|---------|
| Badge “Sprint 1 — Identity & Auth” | SP0–SP9 engineering substantially done |
| Academic Engine = `next` | Implemented (seeded browse) |
| Content (ECAEP) + Question Bank = `planned` | Implemented (CMS + bank); content volume thin |
| Assessment Engine = `planned` | Implemented |
| AI Gateway agents = `planned` | Implemented (Claude + fallback) |
| Copy: “real learning modules land sprint by sprint from here” | Modules already exist; focus is content + reliability |

### Recommended copy direction (for a later UI wave)

- Headline: Trinetra AI Learning OS (TALOS)  
- Subhead: AI-powered NEET preparation under active development  
- Status chips: Identity ✓ · Academic ✓ · CMS ✓ · Assessment ✓ · AI Gateway ✓  
- Explicit caveat: published question inventory still limited; not a finished content product  
- CTAs: Sign in / Create account (unchanged)

Track follow-up as a small **docs+UI copy** wave or extend WAVE-P0-1 in a prompt that **explicitly allows** frontend marketing copy only.

## Root README

Updated in WAVE-P0-1 to match product audit language. Prefer linking stakeholders to `docs/product/` rather than the stale landing badges until the page is fixed.

## Blueprint / BRD

`docs/blueprint/volume-01/` and `BRD.docx` remain vision/narrative. They must not override `docs/product/` or Accepted ADRs for build status. Conflict order: code → ADRs → deploy docs → product docs → blueprint → BRD.
