# ADR-0002: Core technology stack

## Status
Accepted

## Decision
- Frontend: Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui
- Backend: FastAPI + SQLAlchemy 2.x (async) + Alembic + Pydantic v2
- Database: PostgreSQL 17+
- Cache: Redis

## Why
Matches what both source documents converge on independently (BRD's
Enterprise Backend/Frontend Technical Specs, and the TALOS README), and
what was explicitly specified in the build instruction. No alternative
seriously considered — this is a ratification, not an evaluation.

## Consequences
Every module follows this stack with no exceptions. If a future module
needs something the stack can't do well (e.g. a genuine graph database for
a real knowledge graph), that's a new ADR, not a silent substitution.
