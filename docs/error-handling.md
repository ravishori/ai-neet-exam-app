# Error handling & observability — TALOS

## Principle

| Audience | Experience |
|----------|------------|
| Student | Calm message + reference ID. No stacks, SQL, paths, secrets. |
| Ops / developers | Structured logs + optional incident email with traceback. |

## API envelope

All responses use `{ success, data, meta, errors, traceId, timestamp }`.

On errors:
- `errors[].code` — machine code (`INTERNAL_SERVER_ERROR`, `VALIDATION_ERROR`, `AUTHENTICATION_FAILED`, …)
- `errors[].message` — safe user-facing text (may include `Reference: <id>`)
- `errors[].errorId` / `meta.errorId` — short support reference
- `traceId` / headers `X-Trace-Id`, `X-Request-Id` — correlation

Clients never receive stack traces, SQL, or filesystem paths.

## Request / correlation ID flow

```text
Browser (api-client generates X-Request-Id)
        ↓
Next.js (proxies fetch to API)
        ↓
FastAPI RequestContextMiddleware (accept or mint ID)
        ↓
Handlers / DB / logs / incident email
```

Frontend: `apps/web/src/lib/api-client.ts` always sends `X-Request-Id` and attaches `requestId` / `errorId` on `ApiError`.

Backend: `apps/backend/app/core/middleware.py` echoes `X-Request-Id` and `X-Trace-Id`.

## Handlers

| Exception | Behavior |
|-----------|----------|
| `AppError` | Business code + message (expected — no critical email) |
| `RequestValidationError` | Field-level validation |
| HTTP 401/403/404/429 | Mapped codes (`AUTHENTICATION_FAILED`, …) |
| `IntegrityError` | Mapped to CONFLICT / INVALID_REFERENCE / … |
| `OperationalError` | 503 SERVICE_UNAVAILABLE + incident email |
| Other `SQLAlchemyError` | 500 + incident email |
| Other `Exception` | 500 INTERNAL_SERVER_ERROR + incident email |

## Incident email

Configured via environment (never hard-code SMTP secrets):

```text
ERROR_REPORTING_ENABLED=true
ALERT_EMAIL=ravishori@gmail.com
ERROR_REPORT_EMAIL=          # alias if ALERT_EMAIL unset
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
```

- Deduped in Redis for 300s per `(route, exception_type)`.
- Email failure is logged and never replaces the original API error.
- Body includes incident/request IDs, route, status, stack trace, sanitized context.

## Frontend

- Shared UI: `StudentFriendlyError`
- Route boundaries: `app/error.tsx`, `app/student/error.tsx`, `app/global-error.tsx`
- Development may still show the Next.js overlay; production must not expose stacks to users.

## Controlled failure (non-production)

```http
POST /api/v1/admin/diagnostics/controlled-failure?confirm=yes
```

Returns a safe 500 envelope and triggers incident reporting. Hidden (404) in production or without `confirm=yes`.

## Distributed tracing

```text
Distributed tracing:
NOT IMPLEMENTED
Reason:
Request correlation IDs provide current observability requirements without introducing unnecessary infrastructure.
```

OpenTelemetry is not a first-party TALOS dependency. Correlation uses `X-Request-Id` / `traceId` / `errorId` across browser → FastAPI → logs → incident email.

## Troubleshooting

```text
Student reports error
       ↓
Reference / Request ID from UI or ApiError
       ↓
Application logs (structlog, filter by trace_id / error_id)
       ↓
Incident email (if unexpected + reporting enabled)
       ↓
Root cause → fix → regression test
```

## Webpack / Next.js `Cannot find module './NNNN.js'`

Usually a **stale or mixed `.next` build** (e.g. long-lived `next start`/`next dev` after `next build`, or HMR rewriting `webpack-runtime.js` while chunks live under `server/chunks/`). Fix: stop the Node process serving the app, delete `apps/web/.next`, start a single clean `npm run dev` (or rebuild then `next start`). Do not mix production and development servers on the same `.next` directory.
