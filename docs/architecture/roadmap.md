# Build roadmap

Full architecture review and dependency graph: see the published review
artifact (Pre-Build Architecture Review). This file is the condensed,
in-repo reference.

## Dependency order

```
Foundation (SP0) → Identity (SP1) → Academic Engine (SP2)
    → Content/CMS + Question Bank (SP3)
    → Assessment Engine (SP4)
    → AI Gateway + Tutor + Planner (SP5)
    → Learning/Mastery, simplified (SP6)
    → Recommendation + Revision (SP7)
    → Analytics (SP8)
    → Commerce + Admin + hardening/deploy (SP9)
```

## Sprints

| Sprint | Scope | Status |
|---|---|---|
| SP0 | Repo, Docker, Postgres, FastAPI, Next.js foundation | **done** — verified against real Postgres 18 + Redis, both apps run and render |
| SP1 | Identity & Auth — JWT, RBAC, sessions | **done** — register/login/refresh/logout/CSRF/permissions verified via curl + browser click-through |
| SP2 | Academic Engine — exam→subject→chapter→topic→concept | not started |
| SP3 | ECAEP content model + Question Bank | not started |
| SP4 | Assessment Engine — practice, mock tests, scoring | not started |
| SP5 | AI Gateway — Tutor, Question Generator, Planner, Evaluator | not started |
| SP6 | Learning/Mastery (Concept → mastery score, 2-level) | not started |
| SP7 | Recommendation + spaced-repetition revision | not started |
| SP8 | Analytics dashboard | not started |
| SP9 | Commerce (Razorpay), Admin, hardening, deploy | not started |

Everything in the BRD beyond this list (Knowledge Graph, Micro-Competency
layer, Digital Twin, multi-tenancy, 12-agent AI OS, multi-language,
native mobile) is backlog — see ADR-0007.
