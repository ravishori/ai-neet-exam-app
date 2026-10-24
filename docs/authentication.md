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

### Admin-initiated password reset
- `POST /api/v1/users/{user_id}/reset-password` — `users.manage` + CSRF + per-admin rate limit
  (`admin_reset_password`, 5/300s). Reuses `AuthService.request_password_reset` and
  `send_password_reset_email` verbatim (same token generation/hashing/expiry/email template as
  self-service forgot-password) — no separate mechanism. Audit-logged as
  `user.password_reset_initiated` (actor = calling admin, entity = target user). Always returns a
  generic success message regardless of email-delivery outcome, to avoid creating a new
  enumeration vector; 404 only if the target `user_id` itself does not exist (the caller is
  already permissioned, so this doesn't leak anything beyond "this user id exists").

## Sessions
- Access cookie ~15m; refresh rotates on use; reuse detection revokes all user refresh tokens.
- Cookies: HttpOnly; Secure in production; SameSite=Lax.
- MFA pending JWT: 5 minutes, type `mfa_pending` — not an access token.

## MFA enforcement for privileged accounts (SUPER_ADMIN / ADMIN)

**Current state (2026-10-24):** zero privileged accounts in production have TOTP enabled
(`totp_confirmed_at IS NULL` for all SUPER_ADMIN/ADMIN rows — confirmed via read-only query).
A hard login-time MFA requirement would therefore lock out every admin, including the sole
SUPER_ADMIN, with no recovery path. **Do not hard-enforce until step 3 below is confirmed.**

### Soft-gate (implemented this session)
`_mfa_setup_required(user)` in `apps/backend/app/modules/identity/api/auth_router.py` adds an
additive `mfa_setup_required: bool` field to every `_user_to_me()` payload (login response, `/me`,
register, refresh). It is `true` when the user's role intersects `{SUPER_ADMIN, ADMIN}` and
`totp_enabled` is `false`; otherwise `false`. It never blocks login or the MFA-challenge branch
(`mfaRequired`) — it only gives the frontend a signal to redirect the user to the existing TOTP
setup screen after a normal login. No new DB column was needed; this derives purely from the
existing `User.totp_enabled` column and the existing role-code relationship.

### Safe migration path to mandatory MFA (planned, NOT implemented)
1. **Soft-gate rollout** (done): ship `mfa_setup_required` and have the admin-portal frontend
   redirect to `/admin/mfa-setup` (or wherever the existing TOTP setup page lives) when the flag
   is `true` after login. Reversible — purely additive, nobody is locked out.
2. **Grace-period reminder banner**: for a defined window (e.g. 2-4 weeks), show a persistent but
   dismissible banner on every admin-portal page for users with `mfa_setup_required: true`,
   escalating in visibility as the deadline approaches. Still non-blocking.
3. **Verification gate before hard enforcement**: run the read-only query
   `SELECT id, email, r.code FROM identity.users u JOIN identity.user_roles ur ON ur.user_id = u.id
   JOIN identity.roles r ON r.id = ur.role_id WHERE r.code IN ('SUPER_ADMIN','ADMIN') AND
   u.totp_confirmed_at IS NULL;` and confirm it returns **zero rows**. Do this immediately before
   flipping the setting in step 4 — not days before, since new admins can be created at any time.
4. **Hard enforcement**: only after step 3 returns zero rows, add a settings flag (e.g.
   `ENFORCE_MFA_FOR_PRIVILEGED_ROLES`) and, when set, reject login for a SUPER_ADMIN/ADMIN user
   whose `totp_enabled` is `false` with a distinct error code (e.g. `MFA_SETUP_REQUIRED`, HTTP 403)
   instead of issuing session cookies — forcing setup through a short-lived, MFA-setup-only token
   rather than a full session. Re-run the step-3 query as a pre-flight check inside the login path
   itself (not just at rollout time) so a newly-created, not-yet-MFA'd admin account fails safely
   with a clear setup-required error rather than a silent lockout.
