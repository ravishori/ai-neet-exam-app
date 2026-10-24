# CLAUDE.md — Trinetra AI Learning OS (TALOS)

Read this before touching any code in this repo. It exists so every session
starts with the same frozen decisions instead of re-deriving them.

## What this is

An AI-first learning platform, NEET as the first product — **under active
development**. Full brainstorm is in `BRD.docx` (treat as backlog/vision, not a
build spec) and `Trinetra AI Learning OS (TALOS).docx`. The actual build target
is the phased product plan in `docs/product/MASTER_ROADMAP.md` and the frozen
ADRs — not the BRD's enterprise-scale vision (280 tables, 12 AI agents, full
knowledge graph — deferred, see ADR-0007).

**Feature readiness ≠ production readiness.** SP0–SP9 are substantially
implemented in code; production deploy, SMTP, MFA UI, E2E, AI eval harness, and
published content volume are separate gates. See `docs/product/MASTER_FEATURE_AUDIT.md`.

## Frozen decisions (do not re-litigate — see docs/decisions/ for the "why")

- **Architecture**: modular monolith. One FastAPI app, one Next.js app. No
  microservices, no separate admin frontend app.
- **Stack**: Next.js 15 + TS + Tailwind + shadcn/ui · FastAPI + SQLAlchemy 2.x
  (async) + Alembic + Pydantic v2 · PostgreSQL 17+ · Redis.
- **Auth**: custom JWT (access + rotating refresh tokens), Argon2 password
  hashing, HTTP-only cookies. Not Auth.js. OTP/TOTP APIs exist (Wave C);
  product MFA UI is incomplete.
- **AI**: AI Gateway abstraction from day one, Claude as the only wired
  provider for now. Four agents in v1: Tutor, Question Generator, Study
  Planner, Evaluator. Nothing else (Mentor, Digital Twin, Diagram Agent,
  12-agent orchestrator) until a later explicit decision.
- **Content**: NCERT-aligned + originally authored content only. No
  ingestion of Aakash/Allen/PW/Unacademy material without explicit
  licensing. Content moves through the ECAEP workflow
  (`docs/architecture/ecaep.md`) — never a CRUD path that skips review.
- **Commerce**: Razorpay. **Hosting**: Coolify on a Hetzner VPS for MVP
  (documented; production verification separate).
- **Multi-tenancy**: not in MVP. Reserve an `organizations` table; don't
  thread `tenant_id` through anything yet.
- **Naming**: always "Trinetra AI Learning OS (TALOS)", never "AI Learning
  OS" (an earlier working title that appears throughout the BRD).

## Repo conventions

- Backend modules live under `apps/backend/app/modules/<name>/` with
  identical internal shape: `api/ services/ repositories/ models/ schemas/
  tests/`. Use `apps/backend/app/modules/identity/` as the template for
  every module after it.
- Every table: `id UUID PK`, `created_at/updated_at TIMESTAMPTZ`,
  `created_by/updated_by`, `deleted_at` (soft delete), `version INT`.
- PostgreSQL schemas, not everything in `public`: `identity`, `academic`,
  `cms`, `assessment`, `ai`, `analytics`, `commerce`, `system`.
- Alembic migrations are the only way schema changes happen. Never hand-edit
  a deployed schema.
- API responses follow one envelope: `{ success, data, meta, errors,
  traceId, timestamp }`.

## Frontend dev-server invariant (agent rule)

Before running `npm run build` (or `npx next build`) inside `apps/web/`,
verify no `npm run dev` / `next dev` is already running against the same
working tree. Both write into `apps/web/.next/` — running them
concurrently corrupts the dev server's on-disk CSS/JS chunks while it
keeps serving HTML that references them, producing an entirely unstyled
app locally.

Cheap check before any build:

```bash
netstat -ano | grep ':3000.*LISTENING'
```

If a process is listening on 3000, ask the operator to stop the dev
server first. Do **not** kill it yourself — dev-server node processes
launched from another shell/session may be un-killable from your shell,
and even if killable, arbitrary `taskkill //IM node.exe` will nuke
editor/tsserver nodes too. Wait for a clean tree.

Recovery when a local dev already shows unstyled pages: stop the dev
server, `rm -rf apps/web/.next`, `npm run dev`. No source change needed.

The invariant is also documented for humans in `apps/web/README.md`
under "Dev-server invariant"; the static guard is
`apps/web/src/app/layout.stylesheet.test.ts`.

## Audit documentation protocol (agent rule — always follow, never ask first)

`docs/audits/` is the permanent, living record of every audit, investigation,
fix, and test run on this repo. Start at `docs/audits/README.md`.

- **Before any audit/investigation**: read the relevant report in
  `docs/audits/` first (and `findings-register.md` for that module's open
  items). Reuse valid findings; investigate only what has changed or what's
  flagged STALE. Never re-derive from scratch what's already documented and
  still valid.
- **After any audit, investigation, fix, or test run** — update the
  relevant `docs/audits/*.md` report automatically, without being asked.
  Record: scope, date, status, findings with severity, exact file:line,
  reproduction steps, exact commands run, actual results (never estimated),
  limitations, fixes, next actions. Then update `findings-register.md` and
  `README.md`'s status table if the module's overall status changed.
- **Evidence tiers** — label every claim one of: Implemented / Tested /
  Independently verified / Sandbox-tested / Production-verified / STALE.
  Never claim a tier you didn't actually establish (e.g. don't call
  something "tested" if you only read the code).
- **Never overwrite a report blindly** — read it first, then edit/append;
  preserve prior findings as historical record unless they're confirmed
  superseded.
- **Never put secrets, password hashes, tokens, or unmasked PII in these
  reports** — mask emails, never record hash/token values, counts and
  structure only for anything sensitive.
- This protocol itself lives here so every future session follows it
  automatically — do not ask the user whether to maintain this system, just
  maintain it.

## Where to look

- `docs/product/` — **authoritative current product status**, gaps, forward
  roadmap, Cursor waves.
- `docs/decisions/` — ADRs for frozen decisions above.
- `docs/architecture/roadmap.md` — historical SP0–SP9 engineering log +
  StudyMaterial phases.
- `docs/architecture/ecaep.md` — content editorial workflow spec.
- `docs/security-audit.md` — security posture (YELLOW until ops verified).
- Root `README.md` — onboarding summary for humans and agents.
