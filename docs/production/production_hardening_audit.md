# TALOS Production Hardening Audit — Phase 0 (Read-Only)

**Date:** 2026-09-12  
**Repository:** `ai-neet-exam-app`  
**Branch:** `phase2-question-bank`  
**Scope:** Security · Reliability · Observability · Caching · Payments  
**Mode:** READ-ONLY — no application code, schema, config, or deployment changes  

**Overall verdict: AMBER — HARDENING REQUIRED**  
(Not GREEN: local/feature readiness ≠ production-verified controls. Not RED: core auth/CSRF/envelope/ECAEP exist in code with tests.)

Aligned with existing `docs/security-audit.md` (YELLOW, 2026-08-31) and `docs/product/MASTER_FEATURE_AUDIT.md`.

---

## Classification legend

| Label | Meaning |
|-------|---------|
| **IMPLEMENTED** | Working implementation with code (+ usually tests) evidence |
| **PARTIALLY IMPLEMENTED** | Meaningful code exists; important controls missing or fail-open |
| **MISSING** | No implementation |
| **UNVERIFIED** | Code/docs suggest capability; production/env evidence absent |

Scorecard colours: **GREEN** / **AMBER** / **RED** / **GREY** / **UNVERIFIED**

---

## Executive summary

| Bucket | Assessment |
|--------|------------|
| AuthN/AuthZ (app layer) | Strong code evidence (Argon2, cookies, CSRF, RBAC, attempt ownership) |
| Injection / XSS (API path) | Generally controlled; residual SVG/data-URI + Next CSP gap |
| Ops production gates | SMTP, alerts, ENCRYPTION_KEY, RLS, TLS, backups largely **UNVERIFIED** or **MISSING** |
| Observability | Correlation IDs yes; OTel/metrics/SLOs **MISSING** |
| Caching | Redis for rate-limit/alerts only; practice-pool & AI tutor cache **MISSING** |
| Payments | Razorpay client verify **IMPLEMENTED**; webhooks/reconciliation **MISSING** |
| Frontend reliability | Route `error.tsx` yes; practice save/submit silent failures **PARTIAL** |

---

## 1. What is already IMPLEMENTED

- HTTP-only JWT access + rotating refresh cookies; Argon2 hashing; login lockout  
- CSRF double-submit on most mutating APIs; frontend CSRF header echo  
- Structured logging + secret redaction; request `traceId` / `X-Request-Id`  
- Safe API error envelope (generic `INTERNAL_ERROR` + `errorId`; no stack to client)  
- Backend security headers (nosniff, frame deny, referrer, permissions, API CSP, prod HSTS)  
- Redis rate limiting (auth/AI/commerce); fail-closed on recovery/OTP paths  
- Attempt ownership checks (anti-IDOR) in assessment services  
- ECAEP content workflow + publication gates (AI output ≠ auto-publish)  
- PDF upload magic/size/path jail (ingestion)  
- Razorpay order create + HMAC signature verify (client-driven)  
- Wave A/C security tests under `apps/backend/tests/`  
- Coolify/Hetzner compose + deploy runbooks (documented)

## 2. What is PARTIALLY IMPLEMENTED

- Login/register rate limit **fail-open** if Redis unavailable  
- CSRF missing on `/logout`  
- MFA/OTP **API without product MFA UI**  
- Email verification not a login gate; register can reveal `EMAIL_TAKEN`  
- PostgreSQL RLS / least-privilege app role (docs + optional SQL; not runtime)  
- Critical alert email (code ready; needs SMTP + `ALERT_EMAIL`)  
- AI gateway fallback chain (no circuit breaker / tenacity)  
- Factory prompt-injection gates (not runtime tutor prompt firewall)  
- Frontend practice save: mutations often lack user-visible `onError`  
- Payment path: no webhook; relies on client verify  
- FULL practice pool: PUBLISHED filter yes; Seq Scan / load-all-IDs at scale (documented debt)  
- Next.js security headers / CSP (backend only)

## 3. What is MISSING

- OpenTelemetry exporters / distributed spans  
- Prometheus/metrics endpoints & practice latency SLOs  
- Redis (or other) cache for FULL practice pool ID sets  
- AI tutor/explain response cache (cross-user isolation design required)  
- Stripe; payment webhooks; automated reconciliation jobs  
- In-repo nginx TLS config (edge assumed at Coolify)  
- Documented scheduled `pg_dump` / restore drill / PITR evidence  
- Organizations / `tenant_id` threading (deferred by ADR — table reservation incomplete)

## 4. What is UNVERIFIED (production)

- Live Coolify TLS/certs/HSTS at edge  
- Production SMTP delivery + alert receipt  
- Production `ENCRYPTION_KEY` / Razorpay live keys  
- Runtime DB role is non-owner / RLS enabled  
- Backup retention, encryption, offsite restore success  
- Staging load behaviour of FULL pool at ≫1k PUBLISHED items  

---

## Scorecard (condensed)

| Area | Status | Priority | Evidence (paths) |
|------|--------|----------|------------------|
| SQL injection (app path) | GREEN | P0 | Parameterized `text()` in cms/ingestion; ORM elsewhere |
| XSS (markdown) | AMBER | P0 | `markdown-renderer.tsx` no raw HTML; SVG data-URI in `question-panel.tsx` |
| CSRF | AMBER | P0 | `verify_csrf` ubiquitous except logout |
| CORS | AMBER | P0 | Explicit origins + credentials; methods/headers `*` |
| AuthN | GREEN | P0 | `password_service`, `auth_service`, cookies |
| AuthZ / IDOR | AMBER | P0 | `require_permission`, `_get_owned_attempt`; CMS ownership uneven |
| Secrets hygiene | AMBER | P0 | `.gitignore` + examples; local `.env` UNVERIFIED ops |
| Rate limiting | AMBER | P0 | `rate_limit.py`; login fail-open |
| Exception leakage | GREEN | P0 | `exceptions.py` envelope |
| Security headers (API) | GREEN | P0 | `SecurityHeadersMiddleware` |
| Security headers (web) | RED | P0 | No Next CSP/headers found |
| Logging | GREEN | P0 | `logging.py` structlog + redaction |
| Correlation IDs | GREEN | P0 | `RequestContextMiddleware` |
| OpenTelemetry | RED | P1 | Documented NOT IMPLEMENTED |
| Metrics / SLOs | RED | P1 | No `/metrics`; pilot notes no SLO |
| Admin alerting | AMBER | P0 | `alerts.py` + env UNVERIFIED |
| Redis general cache | AMBER | P1 | Rate limit / alert only |
| Practice pool cache | RED | P1 | Live SQL load-all IDs |
| AI response cache | RED | P1 | Tutor always hits gateway |
| HTTPS/TLS prod | UNVERIFIED | P0 | Coolify docs; not proven live |
| Backups/DR | RED | P0 | Volumes ≠ backup runbook |
| Payments Razorpay | AMBER | P1 | Client verify; no webhook |
| ECAEP / content trust | GREEN | P0 | Workflow + publication gates |
| Frontend practice errors | AMBER | P0 | Silent save gap |
| Multi-tenant RLS | AMBER | P2 | Deferred; app-layer ownership |

Full structured data: `production_hardening_audit.json`. Domain deep-dives: sibling `*_audit.md` files.

---

## P0 blockers (must clear before calling production “ready”)

1. **Production TLS/HTTPS + secure cookies** — prove Coolify/edge termination, redirect, HSTS (app HSTS alone insufficient).  
2. **SMTP + `ALERT_EMAIL` verified** — critical 500 alerts must actually deliver.  
3. **`ENCRYPTION_KEY` in prod** if MFA/TOTP secrets used.  
4. **Next.js security headers / CSP** — student XSS surface currently API-side only.  
5. **DB least-privilege / RLS cutover plan executed** or accepted residual with compensating controls.  
6. **Backup + restore drill documented and evidenced** (not only Docker volumes).  
7. **Login rate-limit fail-open policy** accepted with Redis HA, or fail-closed for auth.  
8. **Practice save/submit error UX** — no silent failures under load/network blips.  
9. **Secrets management** — confirm no prod secrets in git; rotate any exposed local copies.  
10. **Payment webhook / reconciliation** before real money (or explicitly keep payments disabled).

---

## P1 improvements

- OpenTelemetry + metrics + practice latency SLOs  
- Redis/index strategy for FULL pool selection  
- AI tutor cache with strict user/tenant isolation + prompt/version keys  
- CSRF on logout; tighten CORS methods/headers  
- Razorpay webhooks + idempotent state machine  
- MFA product UI; email-verify login gate  
- Circuit breakers / bounded retries for AI providers  

---

## Recommended remediation order

1. Ops verify: TLS, SMTP/alerts, secrets, backups/restore  
2. Frontend: CSP/headers + practice error surfacing  
3. Auth hardening: fail-closed auth limits (or Redis HA), logout CSRF, register enumeration  
4. DB role / RLS staging experiment  
5. Observability: OTel + metrics + alert routing  
6. Scale: practice-pool indexes/cache  
7. Payments: webhook + reconciliation before go-live commerce  
8. AI cache (only with isolation design)  

---

## Mandatory stop

Phase 0 audit only. **No code, schema, Redis feature, payment account, HTTPS enablement, or deploy changes** were performed in this task.

See also:

- `security_audit.md` / `.json`  
- `reliability_audit.md` / `.json`  
- `observability_audit.md` / `.json`  
- `caching_audit.md` / `.json`  
- `payments_readiness_audit.md` / `.json`  
- `production_hardening_roadmap.md`  
- `production_hardening_audit.json`  
