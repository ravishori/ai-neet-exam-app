# Incident: Gemini API Key Exposed in Production Logs

**Status:** Code remediated and tested. **Production key rotation NOT performed — pending authorized operator action.**
**Discovered:** 2026-10-01, during a post-merge production-readiness audit of an unrelated feature (WhatsApp M2-A), via `railway logs`.
**Severity:** High (live, usable credential exposed in plaintext in centrally-retained logs).

## Finding and Impact

The production Gemini API key (`GEMINI_API_KEY`, used for PYQ answer resolution and MCQ generation) appeared in plaintext inside Railway production logs, embedded in lines of the form:

```
HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<REDACTED> "HTTP/1.1 200 OK"
```

This is a real, live secret recorded in a log store with retention and access policies separate from the application's own secret management — anyone with Railway log access (beyond those with Railway variable/secret access) could read and reuse the key. Impact: unauthorized Gemini API usage/billing, and potential need to treat the key as compromised regardless of code fix, since it was already exposed before this fix landed.

## Root Cause

This was **not** an application-level `logger.*` call leaking the key. Two independent factors combined:

1. **Key placement:** `GeminiProvider.generate_request()` and both functions in `gemini_batch.py` (`submit_batch`, `get_batch_status`) built the Gemini API URL with the key as a `?key=...` query parameter, per one of Google's two supported auth methods (the other being the `x-goog-api-key` header).
2. **httpx's own logging:** `httpx` logs every outbound request at `INFO` level via Python's stdlib `logging` module (logger name `httpx`), independent of and invisible to this codebase's `structlog`-based pipeline. `app/core/logging.py`'s `configure_logging()` calls `logging.basicConfig(level=logging.INFO, ...)`, which gives the root logger a stdout handler at INFO — so httpx's internal "HTTP Request: ..." record propagates straight to stdout. Because this is a stdlib `logging.LogRecord`, not a structlog event dict, the app's existing redaction (`redact_event_dict` in `app/core/logging.py`, which only inspects event-dict **keys** against `SENSITIVE_KEY_PATTERN`) never runs on it — there is no key named `api_key` to redact; the secret is embedded inside the message string httpx builds for the request line.

Any secret placed in a request URL in this codebase would have been exposed this way, regardless of how carefully `logger.*` calls elsewhere were written.

### Secondary exposure path (not yet triggered, but real)

Two generic `except Exception` catch-alls — `ai_gateway.py` (outer handler around `router.execute`) and `router.py` (`ProviderRouter.execute`, the non-`ProviderError` branch) — stored `str(exc)[:N]` as `error_message`, both logged via structlog (`logger.error("ai_request_failed", ...)`) **and persisted to the `ai.ai_requests` database table** (`AIRequestLog.error_message`). `str(exc)` on an `httpx.HTTPStatusError`/`RequestError` embeds the exception's triggering request URL. For Gemini specifically this path was not actually reachable in practice (the provider's own `try/except` already converts httpx exceptions into sanitized `ProviderError`s before they escape), but it is a structural gap: any future provider that does not locally wrap its HTTP exceptions would leak request URLs — and any credentials in them — into both logs and a database column that already had no redaction applied.

## Affected Components

| File | Issue |
|---|---|
| `apps/backend/app/modules/ai/gateway/gemini_provider.py` | Key in URL query string |
| `apps/backend/app/modules/ai/gateway/gemini_batch.py` | Key in URL query string (2 call sites: `submit_batch`, `get_batch_status`) |
| `apps/backend/app/core/logging.py` | httpx/httpcore stdlib loggers not level-capped; no shared sanitizer for raw exception text |
| `apps/backend/app/modules/ai/gateway/router.py` | Generic exception handler stored unsanitized `str(exc)` |
| `apps/backend/app/modules/ai/gateway/ai_gateway.py` | Generic exception handler stored/logged unsanitized `str(exc)` |

## Code Changes

1. **`gemini_provider.py`, `gemini_batch.py`** — API key moved from the `?key=` URL query parameter to the `x-goog-api-key` HTTP header (Gemini's officially supported alternative). The key is now structurally absent from every URL these modules construct, so it cannot appear in httpx's request-line log or in any exception string that embeds the request URL.
2. **`app/core/logging.py`** — `configure_logging()` now sets `logging.getLogger("httpx")` and `logging.getLogger("httpcore")` to `WARNING`, so routine per-request INFO lines are no longer emitted at all (defense-in-depth: this holds even if a future call site puts something sensitive in a URL). Also adds `sanitize_error_text(text, limit)`, a shared helper that redacts credential-shaped query parameters (`key=`, `api_key=`, `token=`, `secret=`, `access_token=`, …) and `Authorization: Bearer ...` headers found inside free-form exception text.
3. **`router.py`, `ai_gateway.py`** — the two generic `except Exception` catch-alls now pass `str(exc)` through `sanitize_error_text()` before it is logged or stored, closing the secondary path described above.

No behavioral change to the Gemini integration itself: request/response payload shape, retry/fallback policy, cost estimation, and error classification are all unchanged — only how the key is transmitted and how raw exception text is sanitized.

## Regression Test Evidence

File: `apps/backend/tests/test_credential_redaction.py` (new), plus additions to `apps/backend/tests/test_gemini_provider_response_handling.py`.

Command run and result (actually executed, `.venv/Scripts/python.exe -m pytest`, 2026-10-01):

```
tests/test_credential_redaction.py .......... (10 passed)
tests/test_gemini_provider_response_handling.py .................. (18 passed)
tests/test_ai_gateway_multi_provider.py, test_mcq_provider_abstraction_001.py, test_openai_adapter_fix_001.py — all passing, unaffected
80 passed, 26 warnings (warnings pre-exist in unrelated files, unaffected by this change)
```

Coverage:
- `test_api_key_never_appears_in_request_url` / `test_api_key_sent_via_header_not_query_string` / `test_api_key_never_appears_in_safe_metadata_or_response` — `GeminiProvider.generate_request` (sync path).
- `test_batch_submit_key_never_in_url` / `test_batch_poll_key_never_in_url` — both `gemini_batch.py` call sites.
- `test_configure_logging_silences_httpx_request_logging` — httpx/httpcore loggers capped at WARNING.
- `test_sanitize_error_text_redacts_credentials` (4 parametrized cases: query-string key, batch URL key, Bearer header, access_token) and two edge-case tests (non-sensitive text preserved, `None`/truncation handled).
- `test_router_sanitizes_unwrapped_exception_before_storing` — end-to-end: a fake provider raises a raw `RuntimeError` whose message embeds a credential-bearing URL exactly as an unwrapped httpx exception would; asserts the resulting `ProviderAttempt.error_message` (what would be persisted to `AIRequestLog`) and `RoutingResult.error` are both scrubbed.

Lint: `ruff check` on all 7 touched/added files — clean (`All checks passed!`) after two auto-fixes (import ordering, an unnecessary quoted type annotation) applied and re-verified.

Type check: **not run** — `mypy` is not installed in this environment's `.venv`. Not claimed as passed.

## Outstanding Operational Risks

- **The exposed key has not been rotated.** Until an authorized operator rotates it, it must be treated as compromised — this code fix prevents *future* leakage but does not undo the existing exposure.
- Log retention/access on Railway for the window the key was exposed has not been reviewed — unknown how many log readers had access to it.
- Other providers' integrations (OpenAI via SDK, Claude via SDK, Mistral, Sarvam) were not found to place credentials in URLs (SDKs/header-based auth), but were not exhaustively re-audited beyond the grep performed during this investigation; worth a follow-up pass if any new raw-HTTP provider integration is added.
- No `/version`/build-SHA endpoint exists in production, so there's no way to externally confirm exactly when this fix reaches the running deployment — covered separately in the M2-A post-merge audit, unrelated to this incident.

## Production Rotation & Verification Checklist (for an authorized operator — not performed by this session)

1. **Revoke/rotate** the exposed `GEMINI_API_KEY` in Google AI Studio / Google Cloud Console (whichever issued it) — generate a new key; do not just disable without replacing, to avoid an outage window longer than necessary.
2. **Update the production secret** via the existing approved process (Railway variable `GEMINI_API_KEY` on the `ai-neet-exam-app` service) — set the new value through Railway's own secret UI/CLI; never paste it into chat, a log, or a file.
3. **Deploy/restart** the service so the new credential is picked up (Railway services pick up variable changes on redeploy — confirm via Railway's own deployment mechanism, not by reading the value).
4. **Verify the application uses the replacement credential** — trigger one real, low-cost Gemini call in a controlled way (e.g. one PYQ resolver request) and confirm `success=true` in the `ai_request` log line / `ai.ai_requests` table, without ever printing the key itself.
5. **Confirm the old credential is revoked** — attempt (from a non-production tool, e.g. `curl` with the old key) a call and confirm it is rejected (401/403); do this only with the old, already-compromised key, never with the new one.
6. **Review Gemini/Google Cloud usage, billing, and audit logs** for the exposure window for any requests you cannot attribute to this application's own traffic — look for anomalous volume, unfamiliar source IPs/regions, or unexpected models being called.
7. **Review Railway log access and retention** — who can read `railway logs` for this service/project, whether logs are exported anywhere else (e.g. a log drain), and whether retroactive redaction or deletion of the already-exposed log lines is possible/needed.
8. **Post-rotation health check** — `GET /health` and `GET /ready` both `ok`/`true`, and one controlled end-to-end Gemini-backed feature exercised successfully (e.g. one PYQ answer resolution), confirming no regression from the header-based auth change.

## Distinguishing Code Remediation from Pending Operational Remediation

**Done (code):** key moved out of URLs into the `x-goog-api-key` header (2 files, 4 call sites); httpx/httpcore stdlib request logging capped to WARNING; shared `sanitize_error_text` added and wired into both generic exception paths that previously stored raw `str(exc)`; 10 new + 3 extended regression tests, all passing; lint clean.

**Not done, requires an authorized operator (production actions, explicitly out of scope for this session):** rotating the exposed key, revoking the old one, reviewing usage/billing/audit logs for the exposure window, reviewing log retention/access, and the post-rotation health check. **The exposure is not fully resolved until these production steps are completed** — the code fix only stops the leak going forward.
