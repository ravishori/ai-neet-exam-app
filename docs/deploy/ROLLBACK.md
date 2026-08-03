# Rollback procedure

Two complementary paths. Neither has been exercised against a real
deployment yet — no live Coolify instance is reachable from this
environment, consistent with `docs/deploy/RUNBOOK.md`'s existing "treat
first use as a dry run" framing.

## Path A — Coolify-native redeploy (fastest, application-only)

Use this when the current `main` is broken and there is no accompanying
database migration to undo.

**Automated, via GitHub Actions:**
1. Go to Actions → **Deploy** → Run workflow.
2. Set `ref` to the last known-good commit SHA or tag.
3. This rebuilds and pushes GHCR images for that commit, then calls the
   Coolify deploy webhook — Coolify pulls git source at that ref and
   rebuilds, exactly like any other deploy (`RUNBOOK.md` section 4).

**Manual fallback, directly in Coolify** (if the webhook secret isn't
configured, or Actions is unavailable): Coolify's UI keeps previous
builds — select the resource → redeploy a prior commit. This is the same
procedure `RUNBOOK.md` section 5 already documented before this CI/CD
work existed; nothing about it changed.

Either way: **this only rolls back the application code**, not the
database schema.

## Path B — Git revert (when the bad change must not exist on `main` at all)

Use this when the broken commit should be permanently undone in history —
e.g. it shipped a real bug and letting people build on top of `main`
in the meantime would compound it.

```bash
git revert <bad-commit-sha>
git push origin main
```

Pushing the revert to `main` triggers `ci.yml`, and on success
`deploy.yml` automatically redeploys the reverted state — no manual
Coolify step needed. Prefer this over `git reset --hard` + force-push:
a revert preserves history and doesn't rewrite commits other people may
have already pulled.

## Database migrations are never rolled back automatically

Neither path above touches the database. If the bad deploy included a new
Alembic migration:

1. Decide deliberately whether the migration itself is the problem, or
   just the application code that used it.
2. If the migration must be undone: `alembic downgrade -1` (or a specific
   revision), run by hand against the production database — never as an
   automatic CI/CD step. This repo's migrations are additive-only by
   convention (see the ADRs in `docs/decisions/`), so a downgrade is rare
   and should be treated as a deliberate, reviewed action, not routine.
3. If only the application code is at fault, Path A or B above is
   sufficient on its own — the schema stays as-is.

## Verifying a rollback worked
Same checks as a normal deploy (`RUNBOOK.md` section 3):
`https://<domain>/health`, `https://<domain>/ready`, and a real
login round-trip through the frontend.
