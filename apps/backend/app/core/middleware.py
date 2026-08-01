import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger("http")

# Both middlewares below are plain ASGI callables, not starlette.middleware.base.
# BaseHTTPMiddleware — that base class runs the downstream app in a separate
# anyio task per request, which trips up asyncpg's per-connection event-loop
# affinity check ("attached to a different loop") when the app is exercised
# through an in-process ASGITransport, as the integration test suite does
# (see ADR-0020). Plain ASGI middleware has no such task-group indirection.


class RequestContextMiddleware:
    """Attaches a trace id to every request and logs method/path/status/duration."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = str(uuid.uuid4())
        scope.setdefault("state", {})["trace_id"] = trace_id
        start = time.perf_counter()
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Trace-Id"] = trace_id
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
    """Baseline security headers — see ADR-0018. Nothing in this app needs
    camera/mic/geolocation, and every response is JSON or same-origin, so
    these are safe defaults rather than something requiring per-route tuning.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            await send(message)

        await self.app(scope, receive, send_wrapper)
