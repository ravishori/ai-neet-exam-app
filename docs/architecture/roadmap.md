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
| SP2 | Academic Engine — exam→subject→chapter→topic→concept | **done** — NEET seeded (4 subjects, 30 chapters, 4 fully-fleshed), full hierarchy verified |
| SP3 | ECAEP content model + Question Bank | **done** — full workflow (draft→submit→review→publish→archive) verified via curl and browser click-through, coverage grid live |
| SP4 | Assessment Engine — practice, mock tests, scoring | **done** — practice + mock generation, timed attempts, scoring (+4/−1) verified via curl and full browser click-through |
| SP5 | AI Gateway — Tutor, Question Generator, Planner, Evaluator | **done** — provider abstraction + cost/latency logging, all 4 agents, fallback-mode (no API key) verified end-to-end via curl and browser click-through |
| SP6 | Learning/Mastery (Concept → mastery score, 2-level) | **done** — concept-level mastery persisted + topic-level rollup computed live, recomputed on attempt submission, verified via curl and browser click-through (dashboard, topic list, concept page) |
| SP7 | Recommendation + spaced-repetition revision | **done** — fixed-interval revision schedule by mastery_level + rule-based recommendation ranking (due → weak → new), dashboard widgets verified via curl and browser click-through (including the "Practice now" generate→start→navigate flow) |
| SP8 | Analytics dashboard | **done** — admin-only assessment analytics (totals, by-type, 14-day trend, weakest concepts platform-wide) + AI usage/cost analytics, computed live with no new schema, verified via curl (incl. permission boundary) and browser click-through |
| SP9 | Commerce (Razorpay), Admin, hardening, deploy | not started |

Everything in the BRD beyond this list (Knowledge Graph, Micro-Competency
layer, Digital Twin, multi-tenancy, 12-agent AI OS, multi-language,
native mobile) is backlog — see ADR-0007.
