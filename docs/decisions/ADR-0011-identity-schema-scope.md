# ADR-0011: Identity schema — consolidated, not the BRD's 13-table spread

## Status
Accepted

## Context
The BRD's Sprint 1 spec lists 13 identity tables across three groups (core,
authentication, profile): `users, roles, permissions, user_roles,
role_permissions, refresh_tokens, sessions, devices, password_history,
login_history, user_profiles, preferences, addresses`. Consistent with
ADR-0007's MVP scope cut, several of these are consolidated or deferred —
same reasoning applied one level down.

## Decision
**Built now:**
- `identity.users` — includes profile fields directly (first/last name,
  phone, avatar_url, preferred_language, timezone) rather than a separate
  `user_profiles` table. Also carries `email_verification_token_hash` and
  `password_reset_token_hash` (+ expiry columns) directly — single-use,
  short-lived tokens don't need their own table.
- `identity.roles`, `identity.permissions`, `identity.user_roles`,
  `identity.role_permissions`
- `identity.refresh_tokens` — doubles as the session record (device label,
  IP, user agent, last-used timestamp all live here). No separate
  `identity.sessions` table: a refresh token *is* a session in every way
  that matters for v1.
- `identity.login_history` — audit trail of login attempts
- `system.audit_logs` — general-purpose, cross-cutting (not identity-only)

**Deferred:**
- `identity.devices` — redundant with refresh_token metadata until device
  management becomes its own feature (e.g. "log out this device by name"
  beyond what session listing already gives you)
- `identity.password_history` — reused-password prevention; real but not
  load-bearing for MVP
- `identity.preferences`, `identity.addresses` — no feature consumes these
  yet

## Consequences
Fewer joins for the common paths (login, refresh, "who am I"). Splitting
`user_profiles` back out, or adding `devices`/`password_history`, is an
additive migration whenever a feature actually needs them — not a
redesign.
