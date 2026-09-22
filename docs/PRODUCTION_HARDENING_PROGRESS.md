# Production Hardening Progress (B1–B9)

See `docs/RELEASE_AUDIT_STAGING_SERVER_PRODUCTION_READINESS.md` § "B1–B9 Closure Matrix" for the full
evidence table. This file is the change log.

Branch: `chore/production-hardening-b1-b9` (off `origin/main`, not merged/pushed this round).

## Changes made

| File | Reason | Risk | Test | Result |
|---|---|---|---|---|
| GitHub branch protection on `main` (API, not a file) | B1 — enforce required checks before merge | Low — additive, `enforce_admins: false`, does not block existing work | Fresh `GET .../protection` | Verified live |
| `apps/backend/Dockerfile` | B3 — pick up OS-package security patches | Low — `apt-get upgrade`, no version pins broken | Not build-tested locally (no Docker) | Not verified this round |
| `apps/web/Dockerfile` | B3 — same, for the node:22-slim runner stage | Low | Not build-tested locally (no Docker) | Not verified this round |
| `apps/backend/requirements.txt`, `requirements-dev.txt` | B4 — remove pytest CVE from the production image | Low — pytest never imported by `app/` runtime code (verified via grep) | `pytest tests/test_auth.py app/modules/identity app/modules/commerce` | 32/32 pass |
| `docs/deploy/RAILWAY_ROLLBACK.md` (new) | B2 — accurate rollback procedure | None (docs only) | `railway redeploy` tested live on staging | Verified: SUCCESS, healthy |
| `docs/deploy/RUNBOOK.md` | B2 — flag as historical/Coolify-only | None (docs only) | — | — |
| `apps/backend/app/modules/identity/api/auth_router.py` | B8 — fix `emailOtp` flag to check the real (Resend) send path instead of stale SMTP signal | Low — read-only computed field, no behavior change to any write path | `pytest tests/test_auth.py` | 9/9 pass |
| `apps/web/e2e/auth-critical-paths.spec.ts` (new) | B6 — auth/session/authorization E2E coverage | None (test-only) | `tsc --noEmit` | Compiles clean; not executed live |
| `apps/web/e2e/accessibility.spec.ts` (new) | B9 — axe-core accessibility coverage | None (test-only) | `tsc --noEmit` | Compiles clean; not executed live |
| `.github/workflows/ci.yml` | B9 — wire axe-core + Lighthouse into CI (informational, `continue-on-error`) | Low — new job, does not touch existing required jobs | `yaml.safe_load` | Valid YAML; not run live |
| `docs/BACKEND_TEST_FAILURE_TRIAGE.md` (new) | B7 — classify all 104 backend failures/errors | None (docs only) | — | — |
| `apps/web/e2e/global-setup.ts` | B6 — fix pre-existing broken registration payload (missing `mobile`/`state_code`/`city`), blocked every Playwright spec, not just new ones | Low — fixes a real bug, no behavior change to app code | Full Playwright suite | No regression |
| `apps/web/e2e/auth-critical-paths.spec.ts` (rewritten) | B6 — fixed test design (shared identities instead of 8 self-colliding registrations) so the suite passes without touching the real rate limiter | None (test-only) | `npx playwright test e2e/auth-critical-paths.spec.ts --project=laptop-1366` | **10/10 PASS, live** |
| `apps/web/e2e/accessibility.spec.ts` | B9 — re-run with the fixed `global-setup.ts`, now covering 5 routes including auth-gated ones | None (test-only) | `npx playwright test e2e/accessibility.spec.ts` | **5/5 PASS, zero critical/serious violations** |
| `apps/web/package.json` / `package-lock.json` | B3 — `npm update next` (15.5.22→15.5.26) + `npm audit fix` to close 10 of 12 real Trivy findings | Low — safe/non-forcing updates only | Frontend unit tests | 191/191 pass, no regression |
| `docs/SECURITY_EXCEPTIONS.md` (new) | B3 — formal risk exception for the 2 remaining HIGH `postcss` findings bundled inside `next`, no non-major fix available, confirmed non-reachable | None (docs only) | — | — |
| `docs/BACKEND_TEST_FAILURE_TRIAGE.md` (updated) | B7 — reproduced and classified the final 2 undetermined items (content-lineage fixture, mcq_p2_3 IndexError), both confirmed ENVIRONMENT ISSUE | None (docs only) | `pytest` direct reproduction | Confirmed `2 failed` matching predicted root cause; 104/104 now fully classified |
| Lighthouse (`scripts/run-lighthouse-mobile.mjs`) | B9 — actually executed (not just wired) against a real local dev server | None (measurement only) | `node scripts/run-lighthouse-mobile.mjs` | Login/register: Perf 0.70, A11y/BP/SEO 1.0 (dev-server caveat noted) |

No cosmetic changes. No unrelated refactoring. No test deleted, skipped without justification, or
weakened. No production secret printed or modified. No production DB touched. No force-push, no
destructive git operation. Nothing committed or pushed, per instructions.
