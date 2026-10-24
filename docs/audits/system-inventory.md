# System Inventory

Refresh the relevant section whenever an audit touches that part of the
system. This is a snapshot of what exists, not a findings log (see
`findings-register.md` for that).

**Last refreshed:** 2026-10-24 (this session's audits)

## Deployment targets

- **Repo**: `ravishori/ai-neet-exam-app`, default branch `main`.
- **Backend production**: Railway, project `sincere-happiness`, environment
  `production`, service `ai-neet-exam-app`, reachable at
  `https://api.neet.trinetralab.net`. Confirmed via live HTTP response
  headers (`Server: railway-hikari`, `x-railway-edge`) and `railway status`.
  (CLAUDE.md's "Hosting: Coolify on Hetzner" line is the *documented intent*
  for MVP but does not match what's actually live — `docs/deploy/RUNBOOK.md`
  self-documents as never executed against a real server. Treat the Railway
  facts above as ground truth over that doc until reconciled.)
- **Database production**: Railway service `NEET-Postgres`, same project/environment.
  Access pattern: `railway run --service NEET-Postgres -- bash -c 'psql "$DATABASE_PUBLIC_URL" ...'`.
- **Frontend production**: Vercel, `https://neet.trinetralab.net` (confirmed via `Server: Vercel` headers).
- **Deployed backend commit** (as of 2026-10-22 check): `677724ab7f0a0714b60bdc8a16c01fb9aa4d1d59`,
  confirmed via `railway status --json`'s deployment metadata (`commitHash` field) —
  **9 commits behind local `main` at that time.** Re-check this before trusting
  "is X deployed" claims; it changes whenever someone redeploys.

## Backend module map (`apps/backend/app/modules/`)

Standard internal shape per `CLAUDE.md`: `api/ services/ repositories/ models/ schemas/ tests/`.

| Module | Routers registered in `app/main.py` | Audited this session |
|---|---|---|
| `identity` | `auth_router`, `users_router`, `roles_router`, `locations_router` | Yes — see `admin-security.md` |
| `commerce` | `commerce_router`, new `commerce_webhook_router` (uncommitted) | Yes — see `payments.md` |
| `cms` (incl. `cms/pyq/`) | `cms_router`, `content_factory_router`, `human_gold_sandbox_router`, `search_router`, `pyq_gemini_backfill_router`, `pyq_answer_review_router` | Yes — see `pyq-answer-quality.md` |
| `assessment` | `assessment_router`, `weekly_assessment_router` | Partially (practice/mock-test test coverage checked) |
| `whatsapp` | `whatsapp_webhook_router`, `whatsapp_link_router` | Spot-checked (111 tests passing) |
| `ai`, `analytics`, `academic`, `knowledge`, `ingestion`, `system` | various | Not independently audited this session beyond incidental contact |

## Key migrations relevant to active audits (Alembic head chain)

- `d2e3f4a5b6c7` — `pyq.answer_assertions` reviewer-identity columns (PYQ Answer Review feature). On `main`, **not applied to production** as of last check.
- `c7d8e9f0a1b2` — `commerce.webhook_events` dedup table. **Uncommitted**, local-only verification.
- `d4f5a6b7c8d9` — index on `commerce.orders.razorpay_order_id`. **Uncommitted**, local-only verification.
- Production's actual `alembic_version` as of last check: `62aa0447d463` — 5 migrations behind local head at that time (`f8a1b2c3d4e5 → c45cfde6bfcf → d8e9f0a1b2c3 → ee40bf25d73d → d2e3f4a5b6c7`), before the two commerce migrations above even existed. Re-verify before relying on this.

## Known permission codes relevant to active audits

- `pyq.answer_review` — gates the PYQ Answer Review feature. Seeded in `app/modules/identity/seed.py`, granted to `ADMIN`/`CONTENT_MANAGER`. Seeding is **manual-only** — not run automatically on deploy (confirmed: no call in `app/main.py` lifespan, Dockerfile, or deploy workflow).
- `users.manage` — gates admin user-management endpoints including the new admin-initiated password-reset endpoint.

## Admin accounts (production, counts only — see admin-security.md for the masked inventory and the privacy rule for this data)

As of last read-only query: 1 `SUPER_ADMIN`, 3 `ADMIN`, 5 `CONTENT_MANAGER`. Zero have MFA (`totp_confirmed_at`) set up.

## PYQ content cohort (production, counts only — see pyq-answer-quality.md for the full breakdown)

`NEET_PYQ_OFFICIAL` source: `ANSWER_PENDING` 8,928, `ANSWER_VERIFIED` 3,081, `ANSWER_CONFLICT` 387 (as of last re-query, confirmed stable/no drift across two checks this session).
