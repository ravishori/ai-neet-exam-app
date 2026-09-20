# Production Hardening Roadmap (Post Phase-0)

Derived from Phase 0 read-only audit (2026-09-12).  
**Do not start work without a separate authorized remediation task.**

## Wave H1 — Production ops truth (P0)

| # | Work | Proof tests |
|---|------|-------------|
| H1.1 | Verify Coolify TLS, HTTP→HTTPS, HSTS at edge | External SSL labs / curl redirects; secure cookie flags |
| H1.2 | Configure & test SMTP + `ALERT_EMAIL` | Trigger test 500; alert received ≤5 min; dedupe works |
| H1.3 | Confirm `ENCRYPTION_KEY` / JWT secrets in prod vault | Secret scan CI; boot fails on weak JWT |
| H1.4 | Backup schedule + restore drill | Restore to staging; checksum row counts |
| H1.5 | Document go/no-go if payments disabled | Commerce 503 without keys |

**Exit:** Ops checklist signed; no silent alert path.

## Wave H2 — App security closures (P0)

| # | Work | Files (indicative) | Proof |
|---|------|--------------------|-------|
| H2.1 | Next.js CSP + security headers | `apps/web` middleware/next.config | Header integration tests |
| H2.2 | CSRF on logout | `auth_router.py`, web logout | Wave test |
| H2.3 | Auth rate-limit fail-closed or Redis HA | `rate_limit.py` | Chaos: Redis down |
| H2.4 | Reduce register enumeration | `auth_service` | Security test |
| H2.5 | Practice save/submit error UI | attempt page mutations | Playwright failure injection |
| H2.6 | SVG/markdown XSS threat model | `question-panel`, CSP | XSS fixtures |

**Exit:** Security regression suite green; web headers present.

## Wave H3 — Data plane (P0/P2)

| # | Work | Proof |
|---|------|-------|
| H3.1 | Non-owner app DB role staging | Cannot DDL; app still works |
| H3.2 | Optional RLS experiment | `docs/database-security.md` plan |

## Wave H4 — Observability (P1)

| # | Work | Proof |
|---|------|-------|
| H4.1 | OpenTelemetry traces | Trace ID spans FE→BE→AI |
| H4.2 | Metrics + practice latency SLO | Dashboard + alert on burn |
| H4.3 | Propagate `X-Request-Id` from web | FE sets header |

## Wave H5 — Scale & cache (P1)

| # | Work | Proof |
|---|------|-------|
| H5.1 | Indexes / EXPLAIN for PUBLISHED pool | No Seq Scan at target N |
| H5.2 | Optional Redis ID-set cache + invalidation | Hit ratio; publish invalidates |
| H5.3 | AI cache design (isolation-first) | Cross-user negative test |

## Wave H6 — Payments go-live (P1)

| # | Work | Proof |
|---|------|-------|
| H6.1 | Webhooks + idempotency | Replay test |
| H6.2 | Reconciliation job | Daily parity report |
| H6.3 | Entitlement enforcement E2E | Unpaid blocked |

---

## Suggested sequence

`H1 → H2 → H3 → H4 → H5 → H6`

Do not enable live Razorpay (H6) before H1 secrets/TLS and H2 CSRF/headers.

## Explicit non-goals of Phase 0

- No code changes  
- No Redis feature adds  
- No payment account creation  
- No production deploy enablement  
