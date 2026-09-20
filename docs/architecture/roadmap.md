# Build roadmap

Full architecture review and dependency graph: see the published review
artifact (Pre-Build Architecture Review). This file is the condensed,
in-repo reference for **historical engineering sprints**.

**Forward product strategy (authoritative):**
[`docs/product/MASTER_ROADMAP.md`](../product/MASTER_ROADMAP.md)  
**Feature inventory / gaps:** [`docs/product/`](../product/)

> SP0–SP9 below are **substantially implemented as engineering scope**. That
> does **not** mean the NEET product is production-ready: published content,
> SMTP, MFA UI, E2E, and Coolify production verification remain open
> (see product audit).

## Dependency order (historical)

```
Foundation (SP0) → Identity (SP1) → Academic Engine (SP2)
    → Content/CMS + Question Bank (SP3)
    → Assessment Engine (SP4)
    → AI Gateway + Tutor + Planner (SP5)
    → Learning/Mastery, simplified (SP6)
    → Recommendation + revision schedule (SP7)
    → Analytics (SP8)
    → Commerce + Admin + hardening/deploy (SP9)
```

## Sprints (engineering — done)

| Sprint | Scope | Status |
|---|---|---|
| SP0 | Repo, Docker, Postgres, FastAPI, Next.js foundation | **done** — verified against real Postgres + Redis, both apps run and render |
| SP1 | Identity & Auth — JWT, RBAC, sessions | **done** — register/login/refresh/logout/CSRF/permissions verified via curl + browser click-through |
| SP2 | Academic Engine — exam→subject→chapter→topic→concept | **done** — NEET seeded hierarchy verified |
| SP3 | ECAEP content model + Question Bank | **done** — workflow + coverage grid; **inventory is DB-derived** (revalidate; Chem/Zoo + full mock still product gaps) |
| SP4 | Assessment Engine — practice, mock tests, scoring | **done** — engine + UI; quality depends on published questions |
| SP5 | AI Gateway — Tutor, Question Generator, Planner, Evaluator | **done** — Claude + FallbackProvider; eval harness not production-grade |
| SP6 | Learning/Mastery | **done** — concept/micro/KU mastery recompute on submit |
| SP7 | Recommendation + revision schedule | **done** — rule-based recs + **concept mastery** `next_review_at` (fixed intervals). **Not** flashcard SRS decks |
| SP8 | Analytics dashboard | **done** — admin assessment + AI usage aggregates; student scorecard is separate FE |
| SP9 | Commerce (Razorpay), Admin, hardening, deploy | **done** as code/docs — Coolify path **not production-verified** in-repo; premium does not yet gate features |

This closes out the originally-scoped 9-sprint **engineering** roadmap (SP0–SP9).

Phase 2 ADRs (0019–0029) and StudyMaterial (0030–0032) extend the platform
without reopening BRD-scale scope. Everything still deferred per ADR-0007
includes: full Knowledge Graph, Digital Twin, 12-agent AI OS, multi-tenancy,
native mobile, vector RAG platform.

## Post-roadmap: NEET StudyMaterial corpus (ADR-0030)

| Phase | Scope | Status |
|---|---|---|
| **A** | Source registry + recursive discovery (Physics/Chemistry/Biology only; Maths/Uploads excluded; SHA-256 identity) | **implemented — not DoD complete** |
| **B** | Academic mapping + SourceDocument → IngestionJob provenance | **implemented — not DoD complete** |
| **D** | Mandatory 30-MCQ pilot (10+10+10, ECAEP review required) | **implemented — pilot execution / publish separate** |
| — | Scaled ~600 MCQ generation | blocked on pilot sign-off |

See `docs/architecture/studymaterial-ingestion-runbook.md`,
`docs/decisions/ADR-0030-neet-studymaterial-source-registry.md`, and
`docs/decisions/ADR-0031-neet-studymaterial-academic-mapping.md`.

## Forward product phases (summary)

Do **not** promote advanced work ahead of content and reliability:

1. Product/documentation truth  
2. Content readiness (ECAEP publish)  
3. Core exam reliability  
4. Staging / E2E  
5. Personalization / mastery  
6. AI quality / evaluation  
7. Analytics depth  
8. Notifications / engagement  
9. Advanced SRS / RAG / adaptive  
10. Production hardening  

Details and Cursor waves: `docs/product/MASTER_ROADMAP.md`,
`docs/product/CURSOR_IMPLEMENTATION_PLAN.md`.
