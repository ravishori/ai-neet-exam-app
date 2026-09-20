# Observability Audit — Phase 0 (Read-Only)

**Companion JSON:** `observability_audit.json` · **Date:** 2026-09-12

## Findings

| Capability | Status | Evidence |
|------------|--------|----------|
| Structured logging | **IMPLEMENTED** | `app/core/logging.py` (structlog, redaction) |
| Request correlation | **IMPLEMENTED** | `RequestContextMiddleware` → `X-Trace-Id` / envelope `traceId` |
| Audit log persistence | **PARTIALLY IMPLEMENTED** | System audit logs store `trace_id` |
| OpenTelemetry / distributed spans | **MISSING** | Confirmed in `docs/security-audit.md` |
| Metrics (Prometheus etc.) | **MISSING** | No `/metrics` in app |
| Practice latency SLO dashboards | **MISSING** | Pilot review: no formal SLO |
| Critical admin email alerts | **PARTIALLY IMPLEMENTED** | `app/core/alerts.py` + Redis dedupe; SMTP/`ALERT_EMAIL` **UNVERIFIED** |
| AI latency tracking | **PARTIALLY IMPLEMENTED** | Gateway logs `latency_ms` (not scraped metrics) |

## Gap vs prior pilot review

Still true:

- Thin formal practice observability (logs duration only)  
- No codified practice API latency SLO  

## Traceability question

Can one failed student action be traced Frontend → API → DB → AI?

| Hop | Status |
|-----|--------|
| Frontend → API | **PARTIAL** — browser Network; may not propagate `X-Request-Id` unless set |
| API → logs | **IMPLEMENTED** — `trace_id` |
| API → AI provider | **PARTIAL** — latency logged; no OTel span |
| Cross-service search | **MISSING** without centralized log/OTel backend |

## Mandatory stop

No exporters or dashboards added.
