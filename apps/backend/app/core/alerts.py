"""Critical error / security alert emails with Redis dedupe + cooldown."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.modules.identity.services.email_service import send_security_alert_email

logger = get_logger("alerts")

DEFAULT_COOLDOWN_SECONDS = 300


def build_incident_email_body(
    *,
    incident_id: str,
    request_id: str | None,
    method: str,
    route: str,
    status_code: int,
    error_type: str,
    safe_message: str,
    environment: str,
    service: str = "talos-api",
    duration_ms: float | None = None,
    stack_trace: str | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Ops-facing body — never include passwords, tokens, or raw auth headers."""
    lines = [
        "NEET Exam Preparation Webapp",
        "Error Incident Report",
        "",
        f"Incident ID: {incident_id}",
        f"Request ID: {request_id or 'n/a'}",
        f"Trace ID: {request_id or 'n/a'}",
        f"Timestamp: {datetime.now(UTC).isoformat()}",
        f"Environment: {environment}",
        f"Service: {service}",
        f"HTTP Method: {method}",
        f"Route: {route}",
        f"Status Code: {status_code}",
        f"Error Type: {error_type}",
        f"Safe Error Message: {safe_message}",
        f"Duration: {duration_ms if duration_ms is not None else 'n/a'} ms",
        "",
        "Stack Trace:",
        stack_trace or "(not captured)",
        "",
        "Relevant Context:",
        str({k: v for k, v in (context or {}).items() if k.lower() not in {"password", "token", "authorization", "cookie"}}),
        "",
        "Suggested Investigation:",
        "1. Search application logs for the Request ID / Incident ID.",
        "2. Confirm database connectivity and recent deploys.",
        "3. Reproduce with the controlled failure endpoint in non-production if needed.",
    ]
    return "\n".join(lines)


def format_exception_stack(exc: BaseException | None = None) -> str:
    if exc is not None:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return traceback.format_exc()


async def maybe_send_critical_alert(
    *,
    subject: str,
    body: str,
    dedupe_key: str,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
) -> bool:
    """Return True if an alert email was attempted (not necessarily delivered).

    Email failures are logged and never raised — they must not replace the original error.
    """
    settings = get_settings()
    if not settings.error_reporting_enabled:
        logger.info("alert_skipped_disabled", dedupe_key=dedupe_key)
        return False
    if not settings.ops_alert_email:
        logger.warning("alert_email_not_configured", dedupe_key=dedupe_key, subject=subject)
        return False

    redis_client = get_redis()
    cache_key = f"alert:dedupe:{dedupe_key}"
    if redis_client is not None:
        try:
            was_set = await redis_client.set(cache_key, "1", nx=True, ex=cooldown_seconds)
            if not was_set:
                logger.info("alert_deduped", dedupe_key=dedupe_key)
                return False
        except Exception:
            logger.warning("alert_dedupe_redis_error", dedupe_key=dedupe_key, exc_info=True)

    try:
        await send_security_alert_email(subject=subject, body=body)
    except Exception:
        logger.error("alert_email_send_failed", dedupe_key=dedupe_key, exc_info=True)
        return False
    return True


async def report_unexpected_incident(
    *,
    method: str,
    route: str,
    status_code: int,
    exc: BaseException,
    request_id: str | None,
    error_id: str,
    safe_message: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Build + send a sanitized incident email for unexpected failures (never raises)."""
    settings = get_settings()
    error_type = type(exc).__name__
    subject = f"[NEET APP ERROR] {error_type} — {request_id or error_id}"
    body = build_incident_email_body(
        incident_id=error_id,
        request_id=request_id,
        method=method,
        route=route,
        status_code=status_code,
        error_type=error_type,
        safe_message=safe_message,
        environment=settings.environment,
        stack_trace=format_exception_stack(exc),
        context=context,
    )
    try:
        await maybe_send_critical_alert(
            subject=subject,
            body=body,
            dedupe_key=f"unexpected:{route}:{error_type}",
        )
    except Exception:
        logger.error("report_unexpected_incident_failed", error_id=error_id, exc_info=True)


def schedule_unexpected_incident(**kwargs: Any) -> None:
    """Fire-and-forget wrapper so SMTP latency never blocks the API response."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("incident_schedule_no_loop", error_id=kwargs.get("error_id"))
        return

    task = loop.create_task(report_unexpected_incident(**kwargs))

    def _done(t: asyncio.Task[None]) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.error("incident_task_failed", error=str(exc))

    task.add_done_callback(_done)
