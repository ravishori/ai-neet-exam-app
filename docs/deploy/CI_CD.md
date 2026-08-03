# CI/CD pipeline

Three GitHub Actions workflows, added on top of the existing application
without touching business logic (per the standing architecture freeze —
the only application-code edits in this change were 7 mechanical,
zero-behavior-change lint fixes: unused imports and import ordering,
verified against the full test suite before and after).

**Nothing here has executed yet.** This repository has no Git remote
configured (`git remote -v` is empty) — these workflow files are complete
and valid, but GitHub Actions has nothing to run against until the repo is
pushed to GitHub. Treat the first real push as a dry run and watch it,
the same way `docs/deploy/RUNBOOK.md` already treats the first Coolify
deploy.

## Workflows

### `.github/workflows/ci.yml` — on every push/PR to `main`
| Job | What it does | Blocking? |
|---|---|---|
| `backend-lint` | `ruff check app/` against the curated config in `apps/backend/pyproject.toml` | Yes |
| `backend-lint` (ASYNC) | Reports 5 pre-existing blocking-I/O-in-async findings | No — informational, see Test Report |
| `backend-test` | Spins up real `postgres:17` + `redis:7` service containers, creates `trinetra_test_db` per ADR-0020, runs `alembic upgrade head`, then `pytest --cov` | Yes |
| `frontend-lint-typecheck` | `eslint` + `tsc --noEmit` | Yes |
| `frontend-test` | `vitest run` (new — see below) | Yes |
| `docker-build` | Builds both Dockerfiles (validation only, not pushed), scans with Trivy | Yes (build) / No (scan) |

### `.github/workflows/security.yml` — on push/PR to `main`, plus a weekly Monday 03:00 UTC sweep
| Job | What it does | Blocking? |
|---|---|---|
| `codeql` | CodeQL SAST for Python + JS/TS, results in the repo's Security tab | No (informational — first-ever run on this codebase) |
| `secret-scan` | gitleaks across full git history | No |
| `backend-dependency-scan` | `pip-audit` against `requirements.txt` | No |
| `frontend-dependency-scan` | `npm audit` | No |

None of these are hard gates yet because this is the first time any of
them have run against this codebase — see `docs/deploy/TEST_REPORT.md` for
what they currently find. Once a baseline is triaged, tightening any of
these to `exit-code: 1` / removing the `|| true` is a one-line change per
job, not a redesign.

### `.github/workflows/deploy.yml` — after CI succeeds on `main`, or manually
Builds and pushes both images to GHCR (`ghcr.io/<owner>/<repo>/trinetra-backend`
and `.../trinetra-web`), scans them with Trivy, then calls Coolify's deploy
webhook. **Coolify's own deploy model is unchanged** — it still pulls git
source and builds its own images per `docs/deploy/RUNBOOK.md`; the GHCR
images exist for traceability, CVE history, and rollback reference, not as
something Coolify pulls from.

Also usable manually (`workflow_dispatch` with a `ref` input) to rebuild
and redeploy an arbitrary prior commit — see `docs/deploy/ROLLBACK.md`.

### `.github/dependabot.yml`
Weekly update PRs for pip (`apps/backend`), npm (`apps/web`), GitHub
Actions, and both Dockerfiles' base images.

## Configuration reference

Variable **names** only — no real secret values are recorded anywhere in
this repo, matching the existing convention in `docs/deploy/RUNBOOK.md`.

### GitHub Actions secrets (Settings → Secrets and variables → Actions)
| Name | Required | Used by |
|---|---|---|
| `COOLIFY_DEPLOY_WEBHOOK_URL` | No (deploy step no-ops with a warning if unset) | `deploy.yml` |
| `COOLIFY_API_TOKEN` | Only if the webhook above requires auth | `deploy.yml` |
| `GITHUB_TOKEN` | Automatic — provided by Actions | `ci.yml`, `security.yml`, `deploy.yml` (GHCR push) |

### GitHub Actions repository variables (Settings → Secrets and variables → Actions → Variables)
| Name | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes, before the first real deploy build | Baked into the `web` image at build time, same constraint as in `RUNBOOK.md` |

### Backend test environment (set inline in `ci.yml`, not secrets — test-only values)
`DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, `JWT_SECRET`, `ENVIRONMENT=test`.
These point only at the ephemeral service containers created for that CI
run and are never valid outside it.

## Why some things were deliberately left alone
- **No `ruff format` gate.** The codebase has never had a formatter
  applied — `ruff format --check` currently flags 50 files. Reformatting
  all of them is out of scope for a CI/CD-only change ("do not modify
  business logic" / do not redesign the architecture) and would produce a
  50-file diff with no functional change. Left as a fast-follow decision
  for the team, not made unilaterally here.
- **ASYNC lint findings, CodeQL, gitleaks, pip-audit, npm audit are all
  non-blocking.** This is the first time any of them have run against
  this codebase. Making them hard gates on day one would fail the very
  first CI run on pre-existing findings this task was not scoped to fix.
  See `docs/deploy/TEST_REPORT.md` for the current baseline and what's
  recommended as a fast-follow.
