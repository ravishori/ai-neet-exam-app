# Trinetra AI Learning OS (TALOS)

**AI-powered NEET preparation platform under active development.**

TALOS is the platform; **NEET** is the first exam product. Architecture is
exam-agnostic by design (see `docs/decisions/`). This repository is a
**modular monolith MVP** — not a finished, production-certified NEET product.

> **Feature readiness ≠ production readiness.** Much of SP0–SP9 is implemented
> in code and local verification, but production deploy, SMTP, MFA UI, E2E,
> and published content volume are not yet at “serious aspirant / go-live”
> maturity. See `docs/product/` for the authoritative audit.

---

## Who it is for

| Audience | Use |
|----------|-----|
| **NEET aspirants** (target users) | Practice, mocks, mastery, study plan, tutor (when content + AI keys allow) |
| **Content / admin operators** | ECAEP CMS, ingestion, coverage, users, audit |
| **Engineers** | Extend the modular monolith using ADRs + product roadmap |

---

## Current capabilities (honest summary)

### Implemented (functional in local/dev; not automatically production-verified)

- Identity: register, login, logout, refresh, CSRF cookies, Argon2, RBAC, lockout
- Academic hierarchy browse (exam → subject → chapter → topic → concept)
- ECAEP CMS (draft → review → publish → archive) + admin portal
- Assessment engine: practice, mock, full-mock generation, timed attempts, scoring, review UI
- Learning: concept/micro/KU mastery, rule-based recommendations, revision-due (concept schedule)
- AI Gateway + four agents: Tutor, Question Generator, Study Planner, Evaluator (Claude when keyed; otherwise deterministic fallback)
- Flashcard browse/flip (published items only)
- Search over published questions (PostgreSQL FTS)
- Commerce: Razorpay order create + signature verify (no fake success without keys)
- Security Waves A–C at **backend/API** level (rate limits, error IDs, redaction, OTP/TOTP APIs, alert hooks)

### Partial

- Password reset / email verify / OTP — code paths exist; **SMTP production delivery pending**
- TOTP MFA / recovery codes — **APIs + tests exist; student/admin UI for MFA not productized**
- Bookmarks — toggle on questions; **no bookmark library page/API list**
- Knowledge units / ingestion — pipeline present; Phase A/B **not DoD-complete**; grounding is lexical, **not vector RAG**
- Premium purchase — payment works; **`is_premium` does not yet gate features**
- Student analytics — useful scorecard from attempts/mastery; not a full BI suite
- AI Study Coach — dock + study-plan pages wired; not a full multi-session tutor OS

### Basic / MVP

- Admin analytics (assessment + AI usage aggregates)
- Student settings (e.g. preferred language)
- Security alert email (needs `ALERT_EMAIL` + SMTP)
- Marketing landing page copy (see known inconsistency below)

### Advanced / future (not current priority)

- Flashcard SRS decks, vector RAG, adaptive item selection, rank/percentile, in-app/push notifications, Digital Twin, 12-agent OS, multi-tenancy, native mobile

### Explicitly out of scope for now

See “What we are not prioritizing” below and ADR-0007.

---

## Critical product limitation — content

Verified against local database `trinetra_db` on **2026-08-31** (re-checked for this wave):

| Content | DRAFT | IN_REVIEW | PUBLISHED |
|---------|------:|----------:|----------:|
| Questions | 78 | 1 | **11** |
| Flashcards | 12 | — | **2** |
| Concept notes | 7 | — | **6** |

Published questions by subject (same snapshot): Physics 6, Zoology 3, Botany 1, Chemistry 1. Knowledge units: **69**. Attempts: **26**.

**Implication:** The exam UX and CMS are real, but published inventory is **insufficient** for daily multi-chapter practice or a credible full NEET mock (~180 items). Treat demos accordingly.

---

## Architecture

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui + NEET AI Design System |
| Backend | FastAPI + SQLAlchemy 2.x (async) + Alembic + Pydantic v2 |
| Database | PostgreSQL 17+ (schemas: `identity`, `academic`, `cms`, `assessment`, `ai`, `analytics`, `commerce`, `system`) |
| Cache | Redis |
| AI | AI Gateway → Claude (primary); FallbackProvider when unset |
| Architecture | **Modular monolith** — one FastAPI app, one Next.js app |

```
apps/
  backend/          FastAPI modular monolith
  web/              Next.js (student + admin route groups)
database/           Bootstrap SQL, optional RLS notes
docs/
  decisions/        ADRs (normative)
  architecture/     Historical SP0–SP9 + ECAEP + ingestion notes
  product/          Authoritative feature audit + forward roadmap (start here for status)
  deploy/           Coolify / CI runbooks (execution often unverified)
infrastructure/
  docker/           Local + prod-shaped compose
```

**Conflict order:** working code → Accepted ADRs → deploy docs → `docs/product/` → blueprint → BRD.docx (vision only).

---

## Security status

| Area | Status |
|------|--------|
| JWT cookies, CSRF, Argon2, lockout, RBAC | Implemented |
| Rate limits, error IDs, log redaction, headers | Implemented (Waves A–C) |
| OTP / TOTP APIs | Implemented; **UI incomplete** |
| SMTP / `ENCRYPTION_KEY` / `ALERT_EMAIL` in real deploy | **Pending verification** |
| PostgreSQL RLS runtime enforcement | **Pending** (documented only) |
| Overall posture | **YELLOW** — see `docs/security-audit.md` |

---

## Deployment status

- Local: Docker Compose (Postgres, Redis, Mailpit) + native backend/web — supported.
- CI: GitHub Actions workflows exist (`ci`, `security`, `deploy`, …).
- Production (Coolify / Hetzner): **documented, not proven production-ready in-repo.**

Do **not** describe TALOS as a fully production-ready NEET platform unless staging/production verification evidence exists.

---

## Development setup

Per-app READMEs:

- [`apps/backend/README.md`](apps/backend/README.md) — Python 3.11 venv, Alembic, uvicorn `:8000`
- [`apps/web/README.md`](apps/web/README.md) — `npm install` / `npm run dev` `:3000`
- [`database/setup.md`](database/setup.md) — roles + databases
- [`infrastructure/docker/docker-compose.yml`](infrastructure/docker/docker-compose.yml) — Postgres + Redis + Mailpit

Typical local flow: start Postgres/Redis → `alembic upgrade head` → uvicorn → Next.js → open `/login`.

---

## Testing

| Layer | Reality |
|-------|---------|
| Backend | Pytest integration suite (auth, CMS, assessment, ingestion, security waves, …) |
| Frontend | Vitest — limited component coverage |
| E2E | **Not release-grade** (no Playwright suite as of audit) |
| AI evaluation | **Not production-grade** (unit/fallback tests ≠ hallucination harness) |

---

## Current roadmap (forward)

Authoritative sequence: [`docs/product/MASTER_ROADMAP.md`](docs/product/MASTER_ROADMAP.md)

1. Product/documentation truth ← *this wave (WAVE-P0-1)*
2. Content readiness (ECAEP publish)
3. Core exam reliability under real inventory
4. Staging / E2E
5. Personalization / mastery
6. AI quality / evaluation
7. Analytics depth
8. Notifications / engagement
9. Advanced SRS / RAG / adaptive (later)
10. Production hardening

Historical engineering sprints SP0–SP9: [`docs/architecture/roadmap.md`](docs/architecture/roadmap.md) (substantially **done** as engineering scope).

Cursor execution waves: [`docs/product/CURSOR_IMPLEMENTATION_PLAN.md`](docs/product/CURSOR_IMPLEMENTATION_PLAN.md).

---

## What we are not prioritizing

Until core readiness improves, do **not** prioritize:

- 12-agent AI OS, Mentor, Digital Twin
- Multi-tenancy / org threading
- Native mobile apps
- Vector RAG platform
- Flashcard SRS before sufficient published card volume
- Rank/percentile before meaningful cohort data
- SMS OTP before email/MFA UX is mature
- Microservices migration
- Blind framework upgrades
- Competitor feature sprawl

---

## Known documentation / UI inconsistency (WAVE-P0-1)

The public landing page at `apps/web/src/app/(public)/page.tsx` still shows outdated module badges (e.g. CMS/Assessment/AI as planned). **This WAVE does not modify frontend application code.** Tracked in `docs/product/MARKETING_TRUTHFULNESS.md` for a later UI-copy wave.

---

## Naming

Always **Trinetra AI Learning OS (TALOS)**. Prefer “TALOS” / “NEET product on TALOS” over obsolete working titles from the BRD.
