# Admin / Security Audit Report

**Scope:** Administrator accounts, authentication mechanism, password
reset/change/recovery, MFA, admin user-management, audit logging, production
backup readiness.

## Current status (2026-10-24)

Overall: **Partially implemented.** Self-service auth flows are solid and
well-tested. The two real gaps found (admin-initiated reset for another user;
MFA not enforced for privileged accounts) have been **implemented in the
working tree but not committed**. One gap remains genuinely open (recovering
an existing admin's own lost password).

## Admin inventory (production, read-only, masked — never re-print full emails/hashes/tokens)

Last queried: 2026-10-23/24, via `railway run --service NEET-Postgres -- psql ...` (SELECT-only).

| Role | Count |
|---|---|
| SUPER_ADMIN | 1 |
| ADMIN | 3 |
| CONTENT_MANAGER | 5 |

No separate `username` field exists — `identity.users.email` (schema:
`app/modules/identity/models/user.py:16`) is the sole identity field. The
single SUPER_ADMIN account (masked `rav***@gmail.com`) is `email_verified=true`,
`totp_enabled=false`, not locked, `failed_login_attempts=0`. **Zero of the 9
privileged accounts have `totp_confirmed_at` set — nobody has MFA set up.**

This inventory is **STALE after ~2 weeks** or after any account creation/role
change — re-query before relying on exact counts in a future audit.

## Authentication mechanism (Implemented, Verified by code read)

- Argon2 password hashing (`app/modules/identity/services/password_service.py:8`).
- JWT access + rotating refresh tokens, HTTP-only cookies (`app/modules/identity/cookies.py`).
- CSRF protection on mutating endpoints (`Depends(verify_csrf)`).
- Optional TOTP MFA with recovery codes — **fully implemented and tested**,
  confirmed via `tests/test_mfa_recovery_csrf_alerts.py` (recovery-code login,
  single-use enforcement, disable flow, CSRF rejection on MFA endpoints).

## Self-service password flows (Implemented, Tested, Verified)

| Endpoint | File:line | Behavior |
|---|---|---|
| `POST /auth/forgot-password` | `auth_router.py:254-264` | Rate-limited 5/5min, fail-closed; `AuthService.request_password_reset` returns `None` silently for unknown email — enumeration-safe |
| `POST /auth/reset-password` | `auth_router.py:267-273` | Rate-limited 10/5min; token hashed at rest, expiry enforced, single-use |
| `POST /auth/change-password` | `auth_router.py:305-318` | CSRF + 5/5min per-user rate limit; requires current password |
| Revocation | `refresh_token_repository.py:37-42` `revoke_all_for_user` | Called from both reset and change-password paths |

**Tested:** `pytest tests/test_forgot_reset_password.py tests/test_mfa_recovery_csrf_alerts.py app/modules/identity/tests/test_email_service.py tests/test_email_provider.py -v` → **46 passed, 0 failed, 0 skipped** (confirmed 2026-10-23).
**Tested:** `pytest tests/test_security_wave_c.py -k change_password` → **2 passed**.

Specific guarantees independently verified via passing, named tests:
`test_forgot_password_unknown_email_returns_identical_response`,
`test_reset_token_is_single_use`, `test_reset_token_expires_correctly`,
`test_successful_reset_revokes_all_refresh_tokens`,
`test_new_password_works_old_password_rejected`,
`test_reset_token_is_stored_hashed_not_plaintext`.

## F-04 — Admin-initiated reset for ANOTHER user (Implemented, Tested — uncommitted)

**Before this session:** confirmed missing. `users_router.py` had create/update/bulk-suspend
only; no reset-password action; frontend had no such control.

**Fix (in working tree, not committed):**
- `POST /api/v1/users/{user_id}/reset-password` (`app/modules/identity/api/users_router.py`) —
  `require_permission("users.manage")` + `verify_csrf` + rate-limited 5/300s per admin.
  Reuses `AuthService.request_password_reset` and the existing reset email
  verbatim (no new token mechanism). Audit-logs `user.password_reset_initiated`
  via the existing `AuditService` pattern (same call shape as `update_user`'s
  `user.update` log entry, `users_router.py:213-220`). 404 for unknown user.
  Generic response regardless of email-send outcome (no new enumeration vector).
- Frontend: two-step "Reset password → Confirm" control per row in
  `apps/web/src/app/admin/users/page.tsx`, mirroring the confirmation-dialog
  pattern already established in `admin/pyq-answer-review/[questionId]/page.tsx`.
- New test file: `apps/backend/tests/test_admin_password_reset_and_mfa_gate.py`.

**Tested:** `pytest tests/test_admin_password_reset_and_mfa_gate.py tests/test_forgot_reset_password.py tests/test_mfa_recovery_csrf_alerts.py -v` → **26 passed, 0 failed, 0 skipped** (2026-10-24).

**Not yet:** independently re-reviewed by a separate audit pass (implemented
and tested by the same agent) — mark this sub-finding "Independently verified:
NO" until a different pass confirms it. Not committed, not deployed.

## F-05 — MFA not enforced for privileged accounts (Mitigated — uncommitted)

Given **zero** privileged accounts have MFA, a hard login-time gate would
lock out the only SUPER_ADMIN. Implemented instead:

- Soft gate: login/`/me`/register/refresh responses now include
  `mfa_setup_required: true` when the user's role is SUPER_ADMIN/ADMIN and
  `totp_enabled` is false (`auth_router.py`, `_mfa_setup_required()` +
  `_user_to_me()`). Frontend can redirect to MFA setup without blocking login.
- No migration needed — reuses the existing `totp_enabled` column.
- Staged hard-enforcement plan documented in `docs/authentication.md`
  (soft-gate → reminder banner → verify zero gaps via read-only query →
  hard-enforce) — **the hard-enforce step itself is deliberately NOT implemented.**

**Tested:** 3 of the 26 tests above cover this flag's correctness across roles
(true for ADMIN w/o MFA, false for STUDENT, false once `totp_enabled=True`).

## F-06 — No recovery path for an existing admin's own lost password (Open, unresolved)

`scripts/bootstrap_super_admin.py` is the only purpose-built admin-recovery
tool, but it is a **no-op** if the target email already has the SUPER_ADMIN
role (`bootstrap_super_admin.py:66-68`) — it only sets a password on
brand-new-account creation or when promoting a *different*, non-admin account.
There is currently no safe, pre-built way to reset an existing admin's
forgotten password without email access. A manual one-off script (reusing
`hash_password()` directly against the DB) would be the only path today, and
that is not a pre-audited, repeatable tool — treat as a real operational risk,
not a solved problem.

**Minimum safe remediation (not implemented):** extend
`bootstrap_super_admin.py` with an explicit `--force-password-reset` flag that,
for an *existing* SUPER_ADMIN only (never silently for ADMIN/CONTENT_MANAGER),
sets a new password via the same getpass-hidden-input flow already used for
account creation, with the same never-logged/never-echoed guarantee, and an
audit-log entry.

## Audit logging (Implemented, Verified)

`AuditService.log(action=..., actor_user_id=..., entity_type=..., entity_id=...)`
is already wired into `update_user` (`"user.update"`) and the new
`user.password_reset_initiated` action above. No gap found here beyond the
missing endpoint itself (now added).

## Production backup readiness (F-09 — Fixed this session)

No evidence existed of a prior real production backup
(`docs/deploy/BACKUP_RESTORE.md`'s procedure is part of the Coolify/Hetzner
runbook set that self-documents as never executed against a real server; the
only local backup file found was a *local dev DB* dump, not production).

**Fixed:** `database/backups/prod_railway_20261022_042819Z.dump` taken via
`railway run --service NEET-Postgres -- pg_dump --format=custom --dbname="$DATABASE_PUBLIC_URL"`.
Validated: `pg_restore --list` exit 0, 568 TOC entries, `dbname: railway`.
17,817,614 bytes. SHA256 `6dcb8497883393c9427d3d4ef2c542249873379e2bf7b232607cfafc5508bca3`.
This file is git-ignored (`/database/backups/` in `.gitignore`) — it will
never be committed; this report is its only durable record. **This single
backup will itself become STALE** as production data changes — take a fresh
one before any future migration against production.

## Required approvals (none taken)

1. Review and commit (or discard) the uncommitted identity-module changes above.
2. Decide on the `bootstrap_super_admin.py --force-password-reset` addition for F-06.
3. Eventually: flip hard MFA enforcement once all privileged accounts have `totp_confirmed_at` set.
