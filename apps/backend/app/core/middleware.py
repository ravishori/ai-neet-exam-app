import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

logger = structlog.get_logger("http")

# Both middlewares below are plain ASGI callables, not starlette.middleware.base.
# BaseHTTPMiddleware — that base class runs the downstream app in a separate
# anyio task per request, which trips up asyncpg's per-connection event-loop
# affinity check ("attached to a different loop") when the app is exercised
# through an in-process ASGITransport, as the integration test suite does
# (see ADR-0020). Plain ASGI middleware has no such task-group indirection.


class RequestContextMiddleware:
    """Attaches a trace/correlation id to every request and logs method/path/status/duration."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        incoming = headers.get("x-request-id") or headers.get("x-correlation-id")
        trace_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        # Bound length to avoid header abuse.
        if len(trace_id) > 128:
            trace_id = trace_id[:128]

        scope.setdefault("state", {})["trace_id"] = trace_id
        start = time.perf_counter()
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Trace-Id"] = trace_id
                response_headers["X-Request-Id"] = trace_id
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request",
            method=scope.get("method"),
            path=scope.get("path"),
            status=status_holder.get("status"),
            duration_ms=duration_ms,
            trace_id=trace_id,
        )


class SecurityHeadersMiddleware:
    """Baseline security headers — see ADR-0018.

    HSTS only in production (avoid breaking local HTTP). CSP is report-friendly
    and intentionally permissive for Next.js inline/dev needs on the API host
    (API returns JSON; the Next app should set its own CSP separately).
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                if settings.is_production:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)
