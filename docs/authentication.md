# Authentication architecture — TALOS

## Overview

Custom JWT access tokens + rotating opaque refresh tokens stored as SHA-256 hashes.
Passwords hashed with Argon2. CSRF double-submit on cookie-authenticated mutations.
Optional TOTP MFA. Optional email OTP challenges (hashed at rest).

## Flows

### Register / login
- `POST /api/v1/auth/register` — creates STUDENT, issues cookies, sends verification email when SMTP configured.
- `POST /api/v1/auth/login` — lockout after 5 failures / 15 minutes; rate limited.
  - If `totp_enabled`: returns `{ mfaRequired, mfaToken }` **without** session cookies.
  - `POST /api/v1/auth/mfa/verify` — TOTP or recovery code + `mfaToken` → session cookies.
- Email verification is **informational in v1** (not a login gate) until SMTP is reliable in production.

### Password recovery
- `POST /api/v1/auth/forgot-password` — enumeration-safe; rate limited (fail-closed).
- `POST /api/v1/auth/reset-password` — hashed token; revokes refresh sessions; clears lockout.
- `POST /api/v1/auth/change-password` — authenticated + CSRF; revokes sessions; clears cookies.

### Email OTP
- `POST /api/v1/auth/otp/request` — purposes: `login_stepup`, `email_verify`, `sensitive_action`.
- `POST /api/v1/auth/otp/verify` — codes hashed (SHA-256), TTL 10m, max 5 attempts; never returned in API JSON.
- SMS channel reserved in schema; gateway not wired (REQUIRES INFRASTRUCTURE).

### TOTP 2FA (optional)
- `POST /api/v1/auth/totp/setup` — returns secret + otpauth URL once; secret encrypted with `ENCRYPTION_KEY` (Fernet).
- `POST /api/v1/auth/totp/confirm` — enables MFA; returns one-time recovery codes (hashed at rest).
- `POST /api/v1/auth/totp/disable` — requires valid TOTP or recovery code.

### Email / alerts
- Settings: `SMTP_*`, `WEB_APP_URL`, `ALERT_EMAIL`, `ENCRYPTION_KEY`.
- Without SMTP in production: logs `email_not_configured` (no tokens in prod logs).
- Critical unhandled errors may email `ALERT_EMAIL` (deduped; no secrets/PII).

## Sessions
- Access cookie ~15m; refresh rotates on use; reuse detection revokes all user refresh tokens.
- Cookies: HttpOnly; Secure in production; SameSite=Lax.
- MFA pending JWT: 5 minutes, type `mfa_pending` — not an access token.
