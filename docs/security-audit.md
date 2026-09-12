# Security audit — Trinetra AI Learning OS (TALOS)

**Date:** 2026-08-31  
**Scope:** Waves A + B + C hardening  
**Environment under review:** Local modular monolith (FastAPI + Next.js 15 + PostgreSQL + Redis)  
**Readiness rating:** **YELLOW** — code shipped; SMTP / ENCRYPTION_KEY / alert path / RLS cutover still need real-env verification.

## Current architecture

- **Frontend:** Next.js 15 App Router (`apps/web`) — student + admin route groups; cookie-auth API client with CSRF header echo.
- **Backend:** FastAPI modular monolith (`apps/backend`) — JWT access + rotating refresh cookies; Argon2; RBAC permissions; optional TOTP MFA.
- **Data:** PostgreSQL multi-schema; SQLAlchemy 2.x async; Alembic migrations.
- **Cache:** Redis (rate limits, alert dedupe, readiness).

## Current security mechanisms

| Control | Status |
|---------|--------|
| HTTP-only auth cookies | IMPLEMENTED |
| CSRF double-submit | IMPLEMENTED |
| Argon2 password hashing | IMPLEMENTED |
| Login lockout | IMPLEMENTED |
| Redis rate limit (login/register/refresh) | IMPLEMENTED (fail-open) |
| Rate limit forgot/reset/verify/otp/mfa | IMPLEMENTED (fail-closed) |
| Generic INTERNAL_ERROR envelope + errorId | IMPLEMENTED |
| Correlation (`traceId` / `X-Request-Id`) | IMPLEMENTED |
| Log redaction processor | IMPLEMENTED |
| SQLAlchemy IntegrityError mapping | IMPLEMENTED |
| Security headers + prod HSTS + API CSP | IMPLEMENTED |
| Email abstraction (`SMTP_*`, `WEB_APP_URL`) | IMPLEMENTED (delivery REQUIRES INFRASTRUCTURE) |
| Change-password + lockout clear on reset | IMPLEMENTED |
| Email OTP (hashed, TTL, attempt cap) | IMPLEMENTED |
| TOTP 2FA + recovery codes + MFA login step-up | IMPLEMENTED (needs `ENCRYPTION_KEY`) |
| Critical error alert email + Redis dedupe | IMPLEMENTED (needs `ALERT_EMAIL` + SMTP) |
| PostgreSQL RLS / least-privilege runtime | PARTIAL / REQUIRES INFRASTRUCTURE (`docs/database-security.md`) |
| SMS OTP | NOT IMPLEMENTED (REQUIRES INFRASTRUCTURE) |
| OpenTelemetry exporters | NOT IMPLEMENTED (correlation IDs only) |

## Residual risks

1. Production email delivery depends on configured SMTP (abstraction ready).
2. App DB role still typically owns schemas — RLS not enforced at runtime.
3. Email verification still not a login gate.
4. Register still reveals `EMAIL_TAKEN`.
5. Next.js version tracking separate from this hardening (no blind upgrade).

## Docs

- `docs/authentication.md`
- `docs/error-handling.md`
- `docs/database-security.md`
- `docs/security-test-plan.md`
- `docs/incident-response.md`
