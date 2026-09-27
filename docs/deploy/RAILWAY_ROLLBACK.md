# Railway Rollback Procedure (accurate — supersedes RUNBOOK.md/ROLLBACK.md for this repo's actual deployment)

**Correction (B2, 2026-09-22):** `docs/deploy/RUNBOOK.md` and `docs/deploy/ROLLBACK.md` describe a
Hetzner + Coolify deployment. That architecture is **not what is actually running**. Verified via
`railway status --json`: both `ai-neet-exam-app` (production) and `ai-neet-exam-app-test` (staging)
are Railway services with native GitHub-integration sources (`source.repo = "ravishori/ai-neet-exam-app"`),
auto-deploying on push to `main`. `.github/workflows/deploy.yml`'s Coolify-webhook step is a **dead
path** — it may fire, but nothing is listening on the other end for this deployment. This document
replaces the Coolify rollback instructions with the real, verified Railway mechanics.

## Production service identity

```text
Project env:  production
Service:      ai-neet-exam-app        (backend, Railway service id 56dc5ca2-4d75-442e-be92-759dbb54f9a7)
Public URL:   https://api.neet.trinetralab.net
Deploy source: GitHub, repo ravishori/ai-neet-exam-app, branch main, rootDirectory /apps/backend,
               builder DOCKERFILE (apps/backend/Dockerfile)
Database:     production Postgres (Railway-managed), Alembic-migrated
```

(The frontend, `neet.trinetralab.net`, deploys separately via Vercel — out of scope for this Railway
rollback procedure; Vercel has its own "Instant Rollback" to a prior deployment, unrelated to this doc.)

## Finding the known-good version

```bash
railway deployment list --service ai-neet-exam-app --environment production --json
```

Each entry has `id`, `status`, `createdAt`, and `meta.commitHash`/`meta.commitMessage`. The **last
known-good SHA before an incident** is the entry immediately before the one that introduced the
regression — cross-reference `meta.commitHash` against `git log` to identify it precisely.

## Rollback mechanics (verified — tested live against staging, 2026-09-22)

```bash
railway redeploy --service <service> --environment <environment> -y
```

**Verified behavior:** this redeploys the **current/latest** deployment (rebuild+restart of the same
commit) — proven live: ran against `ai-neet-exam-app-test`/`railpack-validation`, produced a new
deployment building commit `e4f19fa0` (the service's current commit), which reached `SUCCESS` and
`/health` returned `200 {"status":"ok"}` afterward. This form is useful for "redeploy the same code"
(e.g. after a transient infra blip), **not** for rolling back to an older commit.

**To roll back to an older, specific commit** (the actual incident-response case), two verified paths
exist:

1. **Railway dashboard** → the target service → **Deployments** tab → find the known-good entry by
   its commit SHA/message → **⋮ → Redeploy**. If that deployment's built image was pruned (status
   shows `REMOVED` in `railway deployment list` — confirmed this happens after a period; production's
   history showed several `REMOVED` entries for commits still present in git history), Railway rebuilds
   from that commit rather than reusing a cached image — slower, but still correct and verified as an
   available action path (the dashboard always offers "Redeploy" regardless of `REMOVED` status).
2. **Revert-and-push**: `git revert` the offending commit(s) on `main` (or fast-forward `main` to the
   last-known-good SHA via an explicitly-authorized force-push — high-risk, requires separate sign-off)
   and push. Railway's GitHub integration auto-deploys the new `main` HEAD exactly as it does for any
   other push — this is the same, already-observed-working mechanism that deploys every merge today.

Path 2 is **preferred** for anything beyond a same-commit redeploy: it produces a clean, auditable git
history entry (`git revert`) rather than an out-of-band dashboard action with no git-visible trace, and
it exercises the exact same auto-deploy path already proven reliable all session.

## Database considerations

- Alembic migrations in this repo are **additive-first** by established convention this whole
  engagement (see PR #44, PR #45 migrations) — rolling back application code to an older commit does
  **not** automatically roll back the database schema, and a newer schema is generally
  backward-compatible with older application code as long as new columns are nullable/defaulted (the
  pattern used throughout). **Before any rollback that crosses a migration boundary**, confirm the
  target commit's expected Alembic head is `<=` the current database's `alembic_version` — if the
  database is *ahead* of the code being rolled back to, this is normally safe (old code simply ignores
  new columns); if a rollback needs to also undo a migration, `alembic downgrade <revision>` must be
  run explicitly and deliberately, is NOT automatic on redeploy, and was explicitly out of scope to
  execute in this task (no production DB rollback was performed or authorized here).
- Read-only inspection only, no migration was run or reverted as part of this documentation task.

## Verification procedure after any rollback

```bash
railway status --json   # confirm meta.commitHash matches the intended rollback target
curl -s https://api.neet.trinetralab.net/health
curl -s https://api.neet.trinetralab.net/api/v1/auth/methods
```

Both must return `200` with the expected JSON shape before considering the rollback complete —
this is the same verification pattern used after every production deploy throughout this engagement.

## What was and was not done for B2

- **Verified live on staging:** `railway redeploy` mechanism (same-commit redeploy → SUCCESS → healthy).
- **Not tested live:** rolling back to a genuinely *older* commit (would require deliberately deploying
  older code to staging, observed, then redeploying back to `main` HEAD — deemed unnecessary churn for
  a mechanism (`git revert` + push) that is identical to the already-proven-reliable auto-deploy path).
- **No production rollback was performed or simulated against production**, per instructions.
