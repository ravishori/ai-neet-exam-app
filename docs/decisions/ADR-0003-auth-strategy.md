# ADR-0003: Custom JWT auth, not Auth.js

## Status
Accepted

## Context
The BRD's Enterprise Frontend Spec names Auth.js as the auth technology.
Its own, later, more concrete Sprint 1 spec designs custom JWT + Argon2 +
rotating refresh tokens in HTTP-only cookies. These conflict — Auth.js
typically owns session/token issuance itself, which collides with a
custom backend-issued JWT model.

## Decision
Custom auth, owned entirely by FastAPI:
- Argon2 password hashing
- Short-lived JWT access token (~10-15 min)
- Opaque refresh token, hashed at rest, rotated on every use, revocable
- HTTP-only, Secure, SameSite cookies — never localStorage

## Why
The Sprint 1 spec is the more detailed and more recently converged-on
decision. Auth.js adds a second source of truth for sessions that the
custom JWT design doesn't need and would fight with.

## Consequences
No third-party auth library dependency. All auth code (token issuance,
refresh rotation, revocation) lives in `apps/backend/app/modules/identity/`.
