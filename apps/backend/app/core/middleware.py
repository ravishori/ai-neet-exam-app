import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a trace id to every request and logs method/path/status/duration."""

    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline security headers — see ADR-0018. Nothing in this app needs
    camera/mic/geolocation, and every response is JSON or same-origin, so
    these are safe defaults rather than something requiring per-route tuning.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
