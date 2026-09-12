# Error handling — TALOS

## API envelope

All responses use `{ success, data, meta, errors, traceId, timestamp }`.

On errors:
- `errors[].code` — machine code (`INTERNAL_ERROR`, `RATE_LIMITED`, …)
- `errors[].message` — safe user-facing text
- `errors[].errorId` / `meta.errorId` — short support reference
- `traceId` / headers `X-Trace-Id`, `X-Request-Id` — correlation

Clients never receive stack traces, SQL, or filesystem paths.

## Handlers

| Exception | Behavior |
|-----------|----------|
| `AppError` | Business code + message |
| `RequestValidationError` | Field-level validation |
| `IntegrityError` | Mapped to CONFLICT / INVALID_REFERENCE / … |
| `OperationalError` | 503 SERVICE_UNAVAILABLE |
| Other `Exception` | 500 INTERNAL_ERROR + logged with errorId |

## Frontend

- `app/error.tsx` / `global-error.tsx` show a polished message with Next.js `digest` as Reference ID.
- Development may still show Next overlay; production must not expose stack traces to users.
