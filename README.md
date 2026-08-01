# Trinetra AI Learning OS (TALOS)

AI-first learning platform. NEET is the first product built on the platform; the
architecture is exam-agnostic by design (see `docs/decisions/`).

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | FastAPI + SQLAlchemy 2.x (async) + Alembic + Pydantic v2 |
| Database | PostgreSQL 17+ (schemas: `identity`, `academic`, `cms`, `assessment`, `ai`, `analytics`, `commerce`, `system`) |
| Cache | Redis |
| AI | AI Gateway → Claude (primary) — provider-swappable by config |
| Architecture | Modular monolith, one deployable backend |

## Repository layout

```
apps/
  backend/        FastAPI application
  web/             Next.js application (student + admin, route-grouped)
packages/          Reserved for shared TS types / SDK once cross-app duplication exists
database/          ERD notes, manual SQL, seed reference data
docs/
  decisions/       Architecture Decision Records (ADR-0001 …)
  architecture/     Working notes + links to the pre-build review artifacts
infrastructure/
  docker/          docker-compose.yml + Dockerfiles for prod-parity local dev
```

## Status

Foundation (Sprint 0) in progress. See `docs/decisions/` for every frozen
architectural decision and `docs/architecture/roadmap.md` for the phase plan.

## Local development

See `apps/backend/README.md` and `apps/web/README.md` for per-app setup.
`infrastructure/docker/docker-compose.yml` provides a prod-parity stack
(Postgres 17, Redis, Mailpit) for anyone without those installed natively.
