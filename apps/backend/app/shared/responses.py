from datetime import UTC, datetime
from typing import Any

from fastapi.responses import JSONResponse


def envelope(
    *,
    success: bool,
    data: Any = None,
    meta: dict | None = None,
    errors: list[dict] | None = None,
    trace_id: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    """Every API response — success or error — uses this one shape."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "data": data,
            "meta": meta or {},
            "errors": errors or [],
            "traceId": trace_id,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
