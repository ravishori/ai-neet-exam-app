# Reliability Audit — Phase 0 (Read-Only)

**Companion JSON:** `reliability_audit.json` · **Date:** 2026-09-12

## Findings

| Area | Status | Notes |
|------|--------|-------|
| Backend global exception handlers | **IMPLEMENTED** | `app/core/exceptions.py` — safe client messages, server `exc_info` |
| Readiness/health | **IMPLEMENTED** | `/health`, `/ready` (Redis ping) |
| Frontend route error UI | **IMPLEMENTED** | `app/error.tsx`, student/attempt `error.tsx` |
| Practice save/submit failures | **PARTIALLY IMPLEMENTED** | Documented silent save gap in CH01 pilot UX review; mutations often lack user-visible `onError` |
| Retry / backoff / circuit breaker | **PARTIALLY IMPLEMENTED** | AI provider fallback chain; no tenacity/circuit-breaker library |
| Alembic migrations | **IMPLEMENTED** | Schema changes via Alembic; production drill **UNVERIFIED** |
| Backup / restore / PITR | **MISSING** | Docker volumes ≠ backup; no `pg_dump` runbook/evidence |
| Idempotency of retried writes | **UNVERIFIED** | Assessment/payment paths need explicit audit in remediation |

## P0 reliability blockers

- Backup + restore drill evidence  
- Surface practice save/submit errors  
- Production alert delivery on unhandled 500s  

## Mandatory stop

Read-only; no resilience features added.
