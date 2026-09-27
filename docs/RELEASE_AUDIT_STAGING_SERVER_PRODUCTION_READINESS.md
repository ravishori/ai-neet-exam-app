# Release Audit — Staging/Server/Production Readiness

**App:** ai-neet-exam-app (NEET exam prep platform)
**Audit date:** 2026-09-22
**Auditor:** Claude (Principal Architect / DevSecOps / QA / Release Auditor role)
**Method:** Evidence-based, read-only. No deploys, commits, pushes, resets, or production/DB writes were performed during this audit.

> Note on scope: the audit brief's example feature list (patient registration, appointments, psychology portal) does not match this application. This report uses ai-neet-exam-app's actual feature set (auth/OTP/MFA, exam content, question bank, assessments, admin/CMS) — confirmed with the user before starting.

---

## B1–B9 Closure Matrix (final pass, 2026-09-23, hardening branch `chore/production-hardening-b1-b9`)

| Blocker | Final Status | Evidence |
|---|---|---|
| B1 | **PARTIALLY RESOLVED** | GitHub branch protection on `main` verified real via fresh `GET` (required contexts: Backend Tests, Backend Lint, Frontend Tests, Frontend Lint+Typecheck, Enterprise Security Checks, docker). Railway confirmed structurally incapable of being gated through any exposed config surface — `railway status --json` service object's full key set enumerated (`activeDeployments, cronSchedule, domains, environmentId, id, latestDeployment, nextCronRunAt, numReplicas, serviceId, serviceName, source, startCommand`) contains no CI-gating field. Railway's native GitHub integration deploys on every push to `main` independent of Actions status. Real fix requires switching to Actions-triggered `railway up` (a deployment-architecture change) — not implemented, requires separate authorization. Residual risk: a commit that fails required checks can still reach production via Railway's own push-triggered deploy. |
| B2 | **RESOLVED** (unchanged, not revisited per instruction) | `docs/deploy/RAILWAY_ROLLBACK.md` / `RUNBOOK.md`; `railway redeploy` verified live on staging in a prior pass. |
| B3 | **ACCEPTED RISK** | Real Trivy v0.74.0 `fs`-mode scan (no Docker) this round: Backend 0 CRITICAL/0 HIGH. Frontend: 0 CRITICAL, 2 HIGH remaining after `npm update next` + `npm audit fix` (resolved 10 of 12 original findings). Remaining 2 HIGH (`CVE-2026-45623`, `CVE-2026-73646`, `postcss@8.4.31`) are bundled inside `next@15.5.26`'s own `node_modules`; no non-major fix exists (`next@16.3.6` is the first release carrying patched postcss `8.5.23`); confirmed non-reachable — both CVEs require attacker-controlled CSS input, and this app has no CSS-upload/theming feature. Formal exception documented in [`docs/SECURITY_EXCEPTIONS.md`](docs/SECURITY_EXCEPTIONS.md). Frontend tests re-confirmed 191/191 after dependency bumps. |
| B4 | **RESOLVED** (unchanged, not revisited per instruction) | `pip-audit -r requirements.txt`: "No known vulnerabilities found". `requirements-dev.txt` pytest CVE confirmed scoped to dev/CI-only, never in the production Docker image. |
| B5 | **RESOLVED** (verify-only, not revisited per instruction) | Production `EMAIL_FROM=noreply@trinetralab.net`, Resend domain `trinetralab.net` Verified, real production forgot-password test returned 200 with confirmed `email_sent kind=password_reset provider=resend` in production logs. |
| B6 | **RESOLVED** | Rewrote `apps/web/e2e/auth-critical-paths.spec.ts` to fix TEST DESIGN (not the rate limiter): reduced from 8 self-colliding registrations to 3 shared identities registered once in `beforeAll`, reusing `primaryEmail` across tests that don't need a distinct identity. Also fixed a real pre-existing bug in `e2e/global-setup.ts` (registration payload missing `mobile`/`state_code`/`city`, broke every Playwright spec) and a Playwright config gotcha (project-wide `storageState` leaking into manually-created `APIRequestContext`s, fixed via explicit `storageState: undefined`). **Result: 10/10 PASS**, executed live against a real local backend+frontend+Postgres+Redis stack (`npx playwright test e2e/auth-critical-paths.spec.ts --project=laptop-1366 --reporter=list`). No regression in the rest of the Playwright suite. |
| B7 | **RESOLVED** | Reconciled and reproduced the final 2 previously-undetermined items directly: (1) `test_content_draft_supersession.py::test_load_biology_replacement_lineage` — `AssertionError` on `BIO_LINEAGE.is_file()`, a missing content-team fixture file, same root-cause family as bucket #5 (ENVIRONMENT ISSUE). (2) `test_mcq_p2_3.py::test_dry_run_preflight` — `IndexError: Cannot choose from an empty sequence` at `plan.py:97`, traced to an empty `concepts` list from the same missing-NCERT-corpus dependency chain (ENVIRONMENT ISSUE). Both confirmed via direct pytest reproduction (`2 failed`, matching predicted root cause exactly). **104/104 backend triage items now fully classified with a confirmed, reproduced root cause** — see closing note in [`docs/BACKEND_TEST_FAILURE_TRIAGE.md`](docs/BACKEND_TEST_FAILURE_TRIAGE.md). Zero items remain undetermined. |
| B8 | **RESOLVED** (unchanged, not revisited per instruction) | `emailOtp` flag fix verified in a prior pass (`tests/test_auth.py` 9/9). |
| B9 | **RESOLVED** | Actually executed (not just inspected): `e2e/accessibility.spec.ts` (axe-core, `wcag2a/2aa/21a/21aa`) against the real local frontend, now covering 5 routes (landing, login, register, student-dashboard, practice — the latter two newly reachable after the B6 `global-setup.ts` fix). **5/5 PASS, zero critical/serious violations** — re-confirmed against a genuine production build (`next build` + `next start`) in the 2026-09-23 final pass. Lighthouse actually executed via `node scripts/run-lighthouse-mobile.mjs` twice: first against `next dev` (Performance 0.70, Accessibility/BP/SEO 1.0 — noted as not representative of production); then, in the final pass, against a genuine production build (`next build` + `next start -p 3001`): **login — Performance 0.94, Accessibility 1.0, Best Practices 1.0, SEO 1.0, LCP 3.1s, CLS 0, TBT 30ms, FCP 1.1s; register — Performance 0.99, Accessibility 1.0, Best Practices 1.0, SEO 1.0, LCP 2.3s, CLS 0, TBT 10ms, FCP 1.1s.** No thresholds invented; production-build numbers supersede the earlier dev-server measurement as the representative baseline. |

### Residual risk carried forward
- Railway auto-deploy still not gated by any CI check (B1) — real platform limitation, no CLI/API/dashboard toggle exists; fixing requires switching to Actions-triggered deploys, a separate authorized change.
- 2 HIGH vulnerabilities remain in `next`'s bundled `postcss`, formally accepted as non-reachable risk pending a future major Next.js upgrade (B3, see `docs/SECURITY_EXCEPTIONS.md`).
- Lighthouse re-measured against a genuine production build on 2026-09-23 (Performance 0.94 login / 0.99 register — supersedes the earlier 0.70 dev-server number). Local-machine measurement only, not staging/production infra; treat as directional, not a guaranteed production number under real network/CDN conditions.

---

## 1. Executive Summary

Staging and production are running the **exact same commit** (`e4f19fa0`), which is also the current tip of `origin/main`. Runtime health/readiness endpoints respond correctly on both. Database schema (Alembic) is in sync with the repo on production. However, **the GitHub Actions CI pipeline for this exact commit reports FAILURE on 3 of 4 required jobs** (backend test suite, dependency security scan, Docker image security scan) — and the deploy pipeline still pushed/activated this commit anyway, because Railway auto-deploys independently of the GitHub Actions gate. The backend test failures are a large, previously-triaged pre-existing baseline (83 failed / 21 errors, unrelated to recent changes — documented below), but the **dependency-vulnerability and container-image scan failures are new, unaddressed, real findings** (pytest CVE, nltk CVE, and 10 container vulnerabilities including 1 CRITICAL and 5 HIGH). No E2E suite has been run against staging or production in this audit. Frontend unit tests (191/191) and lint/typecheck pass cleanly.

**Decision: READY WITH CONDITIONS** (see §22).

---

## 2. Audit Scope

Backend (`apps/backend`, FastAPI/Python), frontend (`apps/web`, Next.js/TypeScript), Railway-hosted staging (`railpack-validation` / `ai-neet-exam-app-test`) and production (`production` / `ai-neet-exam-app`), PostgreSQL + Redis per environment, GitHub Actions CI/CD, Cloudflare DNS/Email Routing (audited in prior sessions), Resend transactional email (in progress, not yet fully verified).

---

## 3. Repository Baseline

```
Branch (local working copy): feat/https-email-provider
Local HEAD:                  f095e093f85a94aa630c6211c07f6a58f37cb515
origin/main HEAD:             e4f19fa028bc40bd08e278132526db4c00d4e1d8
f095e09 is an ancestor of main: YES (already merged via PR #44)
Working tree:                 clean (git status --short: no output)
Staged files:                 none
Untracked files:               none
```

Recent history on `main` (top 10):
```
e4f19fa Merge pull request #44 from ravishori/feat/https-email-provider
f095e09 fix(email): wire provider failure/misconfiguration into admin alert mechanism
2ad84f4 feat(email): replace production SMTP with HTTPS transactional-email provider
e2c4072 Merge pull request #43 from ravishori/feat/auth-observability-test-coverage
aa51bd3 fix(tests): stub Twilio in the negative-alert test to avoid an unrelated 503
3a5f339 test(auth): add forgot/reset-password, session-semantics, and MFA/CSRF/alert coverage
e61e495 Merge pull request #39 from ravishori/fix/otp-rate-limit-mobile
50ec8a8 ci: retrigger PR #39 checks against updated main (post PR #40 merge)
8e21185 Merge pull request #40 from ravishori/chore/ci-infra-fixes
ed07760 fix(tests): accept log_key in test_mobile_otp_login's rate-limit bypass mock
```

**Finding — local working copy is not on `main`.** The local checkout used for recent work sits on the now-merged feature branch `feat/https-email-provider`, not `main`. Not a release blocker (main is up to date and matches deployment), but worth switching back for future work to avoid confusion.

---

## 4. Git State

No modified, staged, or untracked files at audit time. No commits, pushes, resets, or rebases were performed.

---

## 5. Application Feature Inventory (IMPLEMENTED — code-level, not deployment claim)

| ID | Feature | Source Location | Implemented |
|----|---------|------------------|-------------|
| F01 | Email/password auth (register/login/logout) | `app/modules/identity/api/auth_router.py`, `services/auth_service.py` | IMPLEMENTED |
| F02 | Mobile OTP login (Twilio Verify) | `services/twilio_verify_service.py`, `auth_router.py` | IMPLEMENTED |
| F03 | Email OTP login | `services/otp_service.py` | IMPLEMENTED |
| F04 | TOTP MFA (enroll/verify/recovery codes/disable) | `auth_router.py`, `services/` (MFA) | IMPLEMENTED |
| F05 | Forgot/reset password | `auth_router.py::forgot_password/reset_password`, `email_service.py` | IMPLEMENTED |
| F06 | Refresh-token session management, per-session logout | `services/token_service.py`, `identity.refresh_tokens` | IMPLEMENTED |
| F07 | Rate limiting (IP, per-user, per-mobile) | `app/core/rate_limit.py` | IMPLEMENTED |
| F08 | Admin incident alerting (email, Redis-deduped) | `app/core/alerts.py` | IMPLEMENTED |
| F09 | Transactional email via Resend (HTTPS) | `services/email_service.py` | IMPLEMENTED |
| F10 | Geo master data (states/cities) for registration | `identity.states`/`identity.cities`, geo-seed | IMPLEMENTED |
| F11 | Academic structure (subjects/chapters/topics/concepts) | `app/modules/academic/` | IMPLEMENTED |
| F12 | Question bank / CMS content factory | `app/modules/cms/` | IMPLEMENTED |
| F13 | Assessment/mock-test engine | `app/modules/assessment/` | IMPLEMENTED |
| F14 | Learning/practice module, scope preferences | `app/modules/learning/` | IMPLEMENTED |
| F15 | Ingestion pipeline (NCERT source, PDF/visual assets) | `app/modules/ingestion/` | IMPLEMENTED |
| F16 | Knowledge/fact-pack & deterministic MCQ generation | `app/modules/knowledge/`, `cms/services/deterministic_fact_pack_loader.py` | IMPLEMENTED |
| F17 | Analytics module | `app/modules/analytics/` | IMPLEMENTED |
| F18 | Commerce module | `app/modules/commerce/` | IMPLEMENTED |
| F19 | AI module | `app/modules/ai/` | IMPLEMENTED |
| F20 | System/audit-log module | `app/modules/system/` (`AuditLog`/`AuditService`) | IMPLEMENTED (admin-portal scoped only, not wired into auth flows) |
| F21 | Frontend: auth UI (email/mobile OTP tabs, MFA step-up) | `apps/web/src/features/auth/` | IMPLEMENTED |
| F22 | Frontend: student dashboard, practice, mock tests | `apps/web/src/app/student/` | IMPLEMENTED |
| F23 | Frontend: admin/CMS UI | `apps/web/src/features/admin/`, `cms/` | IMPLEMENTED |
| F24 | Frontend: search, flashcards, weekly assessments | `apps/web/src/features/search/`, `flashcards/`, `weekly-assessments/` | IMPLEMENTED |

Enumeration is based on directory/module presence and prior-session functional verification (auth/OTP/MFA/email flows were E2E-tested against real staging/production earlier this engagement). Content-heavy modules (CMS, ingestion, assessment internals) were **not** re-verified at runtime in this audit — see §9 Code-to-Runtime Verification.

---

## 6. Staging Environment

```
Provider:        Railway
Project env:     railpack-validation
Service:         ai-neet-exam-app-test
URL:             https://ai-neet-exam-app-test-railpack-validation.up.railway.app
Deployed commit: e4f19fa028bc40bd08e278132526db4c00d4e1d8
Deployed branch: main
Instance status: RUNNING
Health (/health):                200 {"status":"ok"}
/api/v1/auth/methods:            200 {"emailPassword":true,"mobileOtp":true,"emailOtp":false,"google":false,"microsoft":false}
```

---

## 7. Server / Production Environment

```
Provider:        Railway
Project env:     production
Service:         ai-neet-exam-app
Public URL:      https://api.neet.trinetralab.net
Deployed commit: e4f19fa028bc40bd08e278132526db4c00d4e1d8
Deployed branch: main
Instance status: RUNNING
Health (/health):                200 {"status":"ok"}
/api/v1/auth/methods:            200 {"emailPassword":true,"mobileOtp":true,"emailOtp":true,"google":false,"microsoft":false}
Frontend (neet.trinetralab.net): 200 OK
```

**Finding — staging/production feature-flag divergence.** `emailOtp` reports `false` on staging and `true` on production for the same deployed commit — meaning this is driven by an environment variable, not code. Not necessarily a bug, but an unreconciled config difference that should be confirmed as intentional.

---

## 8. Deployment Reconciliation

| Component | Git SHA | Staging SHA | Server SHA | Match | Runtime Verified |
|---|---|---|---|---|---|
| Backend | e4f19fa0 (origin/main) | e4f19fa0 | e4f19fa0 | **EXACT MATCH** | VERIFIED (health + auth/methods respond, correct commit per Railway API) |
| Frontend | e4f19fa0 (origin/main) | not independently checked (Vercel not queried this pass) | not independently checked | NOT VERIFIED THIS PASS | Frontend root loads (200) only |

**CI/CD documentation-vs-reality mismatch (Finding).** `.github/workflows/deploy.yml` documents Coolify as the deployment target ("Coolify still builds its own images straight from this repo's git source... this workflow adds... triggering Coolify's own redeploy via its webhook"). Runtime evidence conclusively shows **Railway**, not Coolify, is the actual live host for both staging and production (`railway status` returns RUNNING instances with matching commit SHAs; the public domains resolve to Railway-issued/Cloudflare-proxied endpoints per earlier DNS audit). Per the governance rule "never infer deployment from documentation," this doc is either stale or describes a parallel/legacy path — it must not be treated as authoritative for how this app actually ships. **This needs a maintainer decision, not an assumption.**

**Deploy gate bypass (Finding, P1).** The most recent CI run on `main` (commit e4f19fa0) shows `CI`, `Security Pipeline`, and `Docker Build & Security Scan` all **FAILURE**, and the `Deploy` workflow run for the same push is marked **skipped**. Yet Railway is independently running this exact commit in both staging and production. This means **Railway deployment is not actually gated on GitHub Actions CI passing** — a broken CI run does not block or roll back a live deployment. This is a structural CI/CD gap, not a one-off incident.

---

## 9. Code-to-Runtime Verification

| Feature | Code | Build | Staging | Server | Runtime | Result |
|---|---|---|---|---|---|---|
| `/health` | EXISTS | INCLUDED | DEPLOYED | DEPLOYED | VERIFIED (200) | PASS |
| `/api/v1/auth/methods` | EXISTS | INCLUDED | DEPLOYED | DEPLOYED | VERIFIED (200, correct JSON) | PASS |
| Forgot password (email dispatch via Resend) | EXISTS | INCLUDED | DEPLOYED | DEPLOYED | PARTIALLY VERIFIED — staging test showed correct generic 200 response and confirmed Resend attempt in logs, but delivery itself is **BLOCKED** (Resend domain not yet verified — see prior session's DNS work; status was `Pending` at last check) | BLOCKED |
| Mobile OTP send/verify | EXISTS | INCLUDED | DEPLOYED | DEPLOYED | VERIFIED in a prior session (real Twilio SMS E2E against production, explicit user authorization) | PASS (historical evidence, not re-run this pass) |
| Mobile-keyed rate limiting | EXISTS | INCLUDED | DEPLOYED | DEPLOYED | VERIFIED in a prior session (real staging E2E: 11th attempt → 429) | PASS (historical evidence, not re-run this pass) |
| Admin incident alert wiring for email-provider failure | EXISTS | INCLUDED | DEPLOYED | DEPLOYED | VERIFIED via unit/mocked tests only; **not exercised against a real production failure** | NOT VERIFIED (runtime) |
| CMS/content factory, assessment engine, learning module | EXISTS | INCLUDED | DEPLOYED (assumed by same deployed commit) | DEPLOYED (assumed) | **NOT RUN this audit** — no smoke test executed | NOT VERIFIED |
| Frontend student dashboard / practice / mock tests | EXISTS | INCLUDED | NOT VERIFIED THIS PASS | NOT VERIFIED THIS PASS | frontend root returns 200; no authenticated smoke test run | NOT VERIFIED |
| Admin/CMS frontend UI | EXISTS | INCLUDED | NOT VERIFIED THIS PASS | NOT VERIFIED THIS PASS | not exercised | NOT VERIFIED |

**Explicit statement per governance rule:** existence of source files for F11–F19, F22–F24 in §5 is not treated as "deployed and working" — it is IMPLEMENTED only, pending the runtime checks above.

---

## 10. Database Reconciliation

```
Repo Alembic head (apps/backend/alembic/versions):        c1d2e3f4b5a6
Production DB alembic_version (read via railway ssh):     c1d2e3f4b5a6
Match:                                                     EXACT MATCH
```
Staging DB schema version was not independently re-queried in this pass (verified in a prior session as part of the geo-seed migration work; no schema-changing commits have landed since). Total migration files in repo: 45.

**No migration was run, and no schema was modified, during this audit.**

---

## 11. Environment Variable Reconciliation (names only — no values)

| Variable | Code Uses | Staging | Production | Required | Secret |
|---|---|---|---|---|---|
| `DATABASE_URL` | `app/core/config.py` | present | present | yes | yes |
| `JWT_SECRET` | `app/core/config.py` | present | present | yes | yes |
| `ENCRYPTION_KEY` | `app/core/config.py` | present | present | yes | yes |
| `EMAIL_PROVIDER` | `email_service.py` | present (`resend`) | present (`resend`) | yes | no |
| `EMAIL_API_KEY` | `email_service.py` | present | present | yes | yes |
| `EMAIL_FROM` | `email_service.py` | present (`ravishori@gmail.com` — **known misconfiguration**, remediation in progress via Resend domain verification) | present (same value) | yes | no |
| `EMAIL_FROM_NAME` | `email_service.py` | present | present | yes | no |
| `WEB_APP_URL` | `email_service.py::_app_base_url` | present (confirmed earlier session) | present | yes | no |
| `ALERT_EMAIL` / `ERROR_REPORT_EMAIL` | `app/core/alerts.py` (`ops_alert_email`) | not confirmed staging | present (production) | yes for alerting | no |
| `TWILIO_*` (Verify SID/token) | `twilio_verify_service.py` | present | present | yes | yes |

**Finding — `EMAIL_FROM` is a `gmail.com` address in both environments,** which cannot be verified as a Resend sending domain (root-caused and being remediated across the prior two sessions: `trinetralab.net` was added to Resend, DKIM/CNAME records published to Cloudflare, status was `Pending` at last check — **not yet `Verified`**). Until Resend shows `Verified` and `EMAIL_FROM` is switched to a `trinetralab.net` address, **outbound transactional email (registration verification, password reset) is not reliably deliverable in either environment.**

No client-exposed secrets were found in the frontend bundle audit performed in prior sessions (not re-checked this pass).

---

## 12. Security Audit

Carried over from extensive prior-session, evidence-based work (not re-run from scratch this pass, but summarized since it is load-bearing for this decision):

| Control | Status | Evidence |
|---|---|---|
| Auth (password + mobile/email OTP + TOTP MFA) | VERIFIED | Real E2E against staging/production in prior sessions |
| Session handling (refresh-token rotation, per-session logout) | VERIFIED (semantics), documented not changed | `test_logout_session_semantics.py` |
| Rate limiting (IP, mobile) | VERIFIED | Real edge-IP-rotation staging test proved IP-only limiting was ineffective; mobile-keyed fix verified |
| PII/secret log redaction | VERIFIED | `structlog` field-based redaction + dedicated tests (`capture_logs()`, not vacuous `caplog`) |
| Non-enumeration on forgot-password | VERIFIED | Generic response regardless of account existence, tested |
| Admin incident alerting, recursion-safety | VERIFIED (unit/mocked only) | `test_email_provider.py` new tests this session |
| CSRF | VERIFIED (tested) | `test_mfa_recovery_csrf_alerts.py` |
| Dependency vulnerabilities (Python: pip-audit) | **FAIL** | CI: 3 known vulns — `nltk 3.10.3` (PYSEC-2026-3740), `pytest 8.3.4` (PYSEC-2026-1845, fixed in 9.0.3) |
| Dependency vulnerabilities (frontend: npm audit) | **FAIL** (exit code from Security Pipeline job) | CI log: "npm audit fix" suggested; exact count not captured in this pass — **requires follow-up** |
| Container image vulnerabilities (Trivy scan) | **FAIL** | CI: "10 vulnerabilities (4 moderate, 5 high, 1 critical)"; job gated on CRITICAL/HIGH severity |
| Container health check during CI build | **FAIL** | CI: "Backend image failed to become healthy within 15s" |
| Secrets never printed | VERIFIED (this session) | All credential checks throughout this audit used presence-only booleans |

No destructive/exploitative penetration testing was performed, per instructions.

---

## 13. Test Audit (results as observed on CI for commit e4f19fa0)

```
Backend unit/integration (pytest): FAIL — 1319 passed, 83 failed, 21 errors, 52 skipped
Frontend unit (vitest):            PASS — 191/191 tests, 43/43 files
Frontend lint + typecheck:         PASS (0 errors, 10 warnings — no-img-element)
Backend lint (ruff):               FAIL — 203 pre-existing findings (established baseline, unrelated to any change made this session)
Build (Docker, backend + web):     FAIL — backend image failed health check within 15s during CI build validation
Security (pip-audit):              FAIL — 3 known CVEs (nltk, pytest x2)
Security (Trivy container scan):   FAIL — 10 vulnerabilities (1 critical, 5 high, 4 moderate)
CodeQL:                            PASS
E2E (Playwright):                  NOT RUN this audit (suite exists — see §15)
Accessibility:                     NOT RUN this audit (no dedicated a11y CI job found; some ad-hoc scripts exist under apps/web/scripts, not integrated into CI)
```

The 83 backend test failures / 21 errors are a **previously triaged, pre-existing baseline** unrelated to recent PRs (confirmed across sessions: `test_trusted_factory_submission.py`, `test_visual_asset_pipeline.py`, `test_python_mcq_engine_00{5,6,7}.py` fail on missing/misconfigured NCERT source paths and pilot PDF fixtures not present in the CI environment — an environment/fixture-availability issue, not an application defect). This baseline count has been stable and explicitly re-confirmed identical (1319/83/21) across the last several PRs in this engagement. **It is a real, unresolved gap in CI hygiene** (a red pipeline is easy to become numb to) even though it is not evidence of new breakage.

The **security/build failures are separate from this baseline and are new findings for this audit** — they were not previously triaged or accepted as baseline.

---

## 14. Complete Test Case Inventory

See companion file: `docs/TEST_CASES_MASTER.csv`.

Given the size of the implemented surface (24 features across identity, academic, CMS, assessment, ingestion, analytics, commerce, and the corresponding frontend), the CSV enumerates a representative, prioritized set of test cases per feature (happy path, validation, unauthorized/unauthenticated access, boundary, error/network/DB-failure, session expiry, duplicate submission, mobile viewport, and security-abuse cases per §13/Phase 13 rules), rather than an exhaustive combinatorial set — prioritizing high-risk auth/payment/PII-adjacent flows per the instructions ("prioritize high-risk business functionality," "do not create meaningless duplicate tests").

---

## 15. E2E Coverage

Playwright **is** already set up (`apps/web/playwright.config.ts`, `apps/web/e2e/`). Existing spec files:

```
home-hero-viewports.spec.ts
practice-now.spec.ts
practice-physics-topic-isolation.spec.ts
practice-t6f2-publication.spec.ts
seed-v2-practice.spec.ts
viewport-smoke.spec.ts
```

Plus a number of `.cjs` "audit" scripts (`seed-v1-*`, `seed-v2-*`) that appear to be ad-hoc browser-driven regression/audit scripts rather than a formal Playwright suite — their current pass/fail status was **NOT RUN** in this audit (not wired into CI per `.github/workflows/ci.yml` inspection — Frontend CI job runs `npm test` (vitest) and lint/typecheck only, no `test:e2e` step observed).

**Gap:** No auth (login/logout/session-expiry), MFA, registration-gate, or admin/authorization-isolation E2E specs exist despite these being the highest-risk flows in the app. Recommended structure (per Phase 14):

```
e2e/auth/login.spec.ts              — email+password, mobile OTP, wrong-password, lockout/rate-limit
e2e/auth/logout-session.spec.ts     — single-session logout, other sessions still valid (per documented semantics)
e2e/auth/mfa.spec.ts                — enroll, verify, recovery code, disable
e2e/auth/forgot-reset-password.spec.ts — non-enumeration, single-use token, no auto-login
e2e/dashboard/student-dashboard.spec.ts
e2e/practice/mock-test-flow.spec.ts
e2e/admin/authorization-isolation.spec.ts — student cannot reach admin routes
e2e/registration/registration-gate.spec.ts
e2e/search/search.spec.ts
e2e/error-states/network-failure.spec.ts
e2e/accessibility/keyboard-nav.spec.ts
e2e/responsive/mobile-viewport.spec.ts
```

Per instructions, this structure is **proposed, not implemented**, in this audit.

---

## 16. Accessibility

No dedicated automated accessibility test (axe-core, Lighthouse-CI accessibility category, or Playwright + `@axe-core/playwright`) was found wired into CI. `apps/web/scripts/run-lighthouse-mobile.mjs` exists but its CI integration and last-run results were **NOT RUN/NOT VERIFIED** in this audit. **NOT RUN.**

---

## 17. Performance

No CI job runs bundle-size budgets, Lighthouse CI, or API latency checks. `apps/web/scripts/run-lighthouse-mobile.mjs` exists as a manual script only. Build sizes and API latencies were **not measured** in this audit — fabricating numbers would violate the audit's own governance rules. **NOT RUN.**

---

## 18. Observability

Structured JSON logging (`structlog`) with field-based secret redaction — VERIFIED (used throughout prior sessions, including this one, to safely check config presence and diagnose the SMTP network-block incident). Admin incident alerting via email — IMPLEMENTED, Redis-deduped, **wired into genuine-exception handlers only** (not into ordinary 4xx/validation errors — verified by dedicated tests). No APM/metrics/tracing platform (Datadog, Sentry, OpenTelemetry) was found configured. **Gap.**

---

## 19. CI/CD

```
GitHub → PR → Tests → Lint → Typecheck → Security → Build → Staging → Verification → Approval → Production
```

| Stage | Implemented? | Evidence |
|---|---|---|
| PR-triggered tests/lint/typecheck | YES | `.github/workflows/ci.yml` |
| Security scanning (pip-audit, npm audit) | YES (but currently failing, ungated from deploy) | `security.yml` |
| CodeQL | YES, passing | `codeql.yml` |
| Container build + Trivy scan | YES (but currently failing, ungated from deploy) | `docker.yml` |
| Dependency review | YES (separate workflow) | `dependency-review.yml` |
| Deploy gated on CI success | **DOCUMENTED but NOT ENFORCED IN PRACTICE** — Railway deployed e4f19fa0 despite CI/Security/Docker jobs failing on that exact commit | §8 |
| Staging → production promotion gate / manual approval | NOT FOUND | Both environments appear to auto-deploy from `main` independently |
| Automated deployment verification (post-deploy smoke) | NOT FOUND in CI | Verification has so far been performed manually in this engagement (curl health checks), not automated |
| Rollback automation | PARTIAL | `deploy.yml` supports `workflow_dispatch` with a `ref` input to redeploy a prior commit via the Coolify webhook — but this targets Coolify, which conflicts with the Railway-is-actually-live finding in §8; **rollback mechanism reliability is unverified** |

---

## 20. Rollback

No verified, tested rollback procedure exists for the Railway deployment path actually in use. The documented rollback (`deploy.yml` `workflow_dispatch`) targets Coolify. **This is a release blocker for confident incident response** — if production needs to be rolled back today, the documented mechanism may not affect the system that is actually serving traffic.

---

## 21. Release Blockers

| ID | Severity | Blocker | Evidence | Release Impact | Required Fix |
|---|---|---|---|---|---|
| B1 | **P1** | Deploy pipeline is not gated on CI success; Railway deployed a commit with 3 failing required CI jobs | §8, run 35709778244/35709777559/35709777583 | Any future regression in tests/security/build will not block a bad deploy | Wire Railway deploys to only trigger after GitHub Actions `CI`+`Security Pipeline`+`Docker Build` succeed, or adopt branch protection requiring these checks before merge |
| B2 | **P1** | Rollback mechanism (`deploy.yml`) targets Coolify, not the Railway environment actually serving traffic | §8, §20 | Rollback may not work when needed | Reconcile deploy docs/workflow with actual Railway-based deployment, and test a real rollback in staging |
| B3 | **P1** | Container image has 1 CRITICAL + 5 HIGH vulnerabilities per Trivy scan | §12, run 35709777583 | Known exploitable vulnerabilities in the running production image | Identify and patch/upgrade the flagged packages; re-scan |
| B4 | **P2** | `pytest` and `nltk` have known CVEs per pip-audit (pytest fix available: 9.0.3) | §12, run 35709777559 | Supply-chain risk | Bump pytest to ≥9.0.3; assess nltk usage and available fix/mitigation |
| B5 | **P2** | Outbound transactional email (registration verification, password reset) not reliably deliverable — `EMAIL_FROM` on an unverifiable `gmail.com` address; Resend domain verification for `trinetralab.net` was `Pending`, not `Verified`, at last check | prior-session audit + this session's DNS work | New user registration / password reset likely fails silently for end users right now | Confirm Resend shows `Verified` for `trinetralab.net`, then switch `EMAIL_FROM` to a `trinetralab.net` address in both environments |
| B6 | **P2** | No E2E coverage for auth, MFA, registration gating, or admin authorization isolation despite Playwright being set up | §15 | Highest-risk flows have no regression safety net beyond backend unit tests | Implement the proposed E2E structure in §15, starting with auth/session/MFA |
| B7 | **P2** | Backend test suite has an 83-failed/21-error pre-existing baseline that is not resolved, only tracked | §13 | CI signal is noisy; new regressions are harder to spot against a red baseline | Fix or explicitly skip-and-ticket the NCERT/pilot-PDF-fixture-dependent tests so CI is green-by-default |
| B8 | **P3** | Staging vs production feature-flag divergence (`emailOtp`) not documented as intentional | §7 | Staging does not fully represent production behavior for this flow | Confirm intent; document in environment runbook |
| B9 | **P3** | No automated accessibility or performance testing in CI | §16, §17 | Regressions in a11y/performance ship undetected | Add axe-core/Lighthouse-CI jobs, at minimum on critical pages |
| B10 | **P3** | No APM/tracing/error-monitoring platform configured | §18 | Slower incident detection/diagnosis beyond structured logs + email alerts | Evaluate adding Sentry or equivalent |

---

## 22. Production Readiness

| Area | Status | Evidence | Risk | Required Action |
|---|---|---|---|---|
| Architecture | READY WITH CONDITIONS | Modular FastAPI/Next.js, clean module boundaries | Low | — |
| Authentication | READY | Multi-method auth, MFA, verified E2E | Low | — |
| Authorization | READY WITH CONDITIONS | RBAC exists; no E2E isolation test | Medium | Add E2E isolation tests (B6) |
| Database | READY | Schema in sync prod/repo, migrations clean | Low | — |
| API | READY WITH CONDITIONS | Functional, but CI test suite has unresolved failures | Medium | B7 |
| Frontend | READY WITH CONDITIONS | Unit tests green, no E2E for critical flows | Medium | B6 |
| Error handling | READY | Sanitized error responses, verified via tests | Low | — |
| Security | **NOT READY** | Container CRITICAL/HIGH vulns, dependency CVEs, CI security gate not enforced | **High** | B1, B3, B4 |
| Privacy | READY WITH CONDITIONS | PII redaction verified; email delivery currently broken affects account-recovery privacy flows indirectly | Medium | B5 |
| Accessibility | NOT VERIFIED | No automated coverage | Unknown | B9 |
| Performance | NOT VERIFIED | No measurement | Unknown | B9 |
| Observability | READY WITH CONDITIONS | Structured logs + admin alerts; no APM | Medium | B10 |
| Backups | NOT VERIFIED THIS AUDIT | Prior session used `pg_dump` manually for a migration; no confirmed automated backup schedule found | Unknown | Follow-up audit |
| Disaster recovery / Rollback | **NOT READY** | Documented mechanism targets the wrong platform | High | B2 |
| CI/CD | **NOT READY** | Deploy not gated on CI; CI itself currently red | High | B1, B7 |
| Documentation | READY WITH CONDITIONS | `docs/deploy/RUNBOOK.md` exists but appears stale re: Coolify | Medium | Update to reflect Railway |
| External providers | READY WITH CONDITIONS | Twilio verified working; Resend pending verification | Medium | B5 |
| E2E testing | **NOT READY** | No coverage of critical flows | High | B6 |
| Deployment verification | READY WITH CONDITIONS | Manual, not automated | Medium | Add automated post-deploy smoke (Phase 15 style) |

---

## 23. Evidence

All evidence in this report was gathered via: `git` commands against the local clone, `railway status --json` / `railway ssh` (read-only), direct `curl` against public staging/production endpoints, `gh run view --log` against the real GitHub Actions run for commit `e4f19fa0`, and Alembic `heads` command (offline) cross-checked against the production DB's `alembic_version` table (read-only query via `railway ssh`). No values of any secret were printed; presence-only booleans were used throughout. Full CI logs are available via the linked run IDs for independent verification: `35709778244` (CI), `35709777559` (Security Pipeline), `35709777583` (Docker Build & Security Scan).

---

## 24. Recommended Remediation Sequence

1. **B1** — Make Railway deploys conditional on GitHub Actions CI success (or add branch protection requiring the 3 failing checks before merge to `main`).
2. **B3** — Patch the CRITICAL/HIGH container vulnerabilities; re-run Trivy.
3. **B4** — Bump `pytest` to ≥9.0.3; assess `nltk`.
4. **B5** — Confirm Resend `Verified` status for `trinetralab.net`; switch `EMAIL_FROM`.
5. **B2** — Reconcile/replace the Coolify-targeted rollback workflow with a Railway-accurate one; test a real rollback in staging.
6. **B6** — Implement auth/MFA/session/authorization-isolation E2E specs first.
7. **B7** — Triage and either fix or properly skip-with-ticket the 83/21 pre-existing backend test failures so CI is green-by-default.
8. **B8** — Document/confirm the staging-vs-production `emailOtp` flag difference.
9. **B9** — Add automated accessibility (axe-core) and performance (Lighthouse-CI) checks to CI.
10. **B10** — Evaluate an APM/error-monitoring platform.

---

## 25. Final Decision

## READY WITH CONDITIONS

The application is functionally deployed, healthy, and schema-consistent across staging and production, with strong evidence of correct behavior for its highest-risk feature (authentication) from real E2E testing in prior sessions. It is **not** unconditionally ready because: (a) the deployment pipeline does not actually enforce its own CI/security gates (B1), (b) the container currently serving production traffic has known CRITICAL/HIGH vulnerabilities (B3), (c) the documented rollback mechanism appears to target a platform other than the one actually serving traffic (B2), and (d) a core user-facing flow (registration/password-reset email) is presently unreliable pending Resend domain verification (B5).

**Conditions for unconditional READY:** B1, B2, B3, B5 resolved and re-verified with evidence (not documentation).
