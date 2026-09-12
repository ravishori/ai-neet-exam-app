from fastapi import Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.shared.responses import envelope

logger = get_logger("exceptions")


class AppError(Exception):
    """Base for business errors. Every module-specific error inherits this."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        status_code: int = 400,
        error_id: str | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.error_id = error_id
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403)


def _new_error_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12].upper()


def _error_payload(*, code: str, message: str, field: str | None = None, error_id: str | None = None) -> dict:
    payload: dict = {"code": code, "message": message}
    if field:
        payload["field"] = field
    if error_id:
        payload["errorId"] = error_id
    return payload


async def app_error_handler(request: Request, exc: AppError):
    trace_id = getattr(request.state, "trace_id", None)
    error_id = exc.error_id or _new_error_id()
    return envelope(
        success=False,
        errors=[_error_payload(code=exc.code, message=exc.message, error_id=error_id)],
        trace_id=trace_id,
        status_code=exc.status_code,
        meta={"errorId": error_id},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = getattr(request.state, "trace_id", None)
    error_id = _new_error_id()
    # Never forward raw server detail that might include internals — keep short.
    message = str(exc.detail) if isinstance(exc.detail, str) else "Request failed"
    return envelope(
        success=False,
        errors=[_error_payload(code="HTTP_ERROR", message=message, error_id=error_id)],
        trace_id=trace_id,
        status_code=exc.status_code,
        meta={"errorId": error_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", None)
    error_id = _new_error_id()
    errors = [
        _error_payload(
            code="VALIDATION_ERROR",
            message=err["msg"],
            field=".".join(str(p) for p in err["loc"]),
            error_id=error_id,
        )
        for err in exc.errors()
    ]
    return envelope(success=False, errors=errors, trace_id=trace_id, status_code=422, meta={"errorId": error_id})


def map_integrity_error(exc: IntegrityError) -> AppError:
    """Translate PostgreSQL/SQLAlchemy integrity failures into safe AppErrors."""
    orig = str(getattr(exc, "orig", exc)).lower()
    if "unique" in orig or "duplicate" in orig:
        return AppError(
            "This record already exists or conflicts with an existing value.",
            code="CONFLICT",
            status_code=409,
        )
    if "foreign key" in orig or "fk_" in orig:
        return AppError(
            "Related record is missing or cannot be modified.",
            code="INVALID_REFERENCE",
            status_code=400,
        )
    if "not-null" in orig or "null value" in orig:
        return AppError(
            "A required field was missing.",
            code="VALIDATION_ERROR",
            status_code=422,
        )
    return AppError(
        "The request could not be completed due to a data constraint.",
        code="DATA_CONSTRAINT",
        status_code=400,
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    trace_id = getattr(request.state, "trace_id", None)
    error_id = _new_error_id()

    if isinstance(exc, IntegrityError):
        mapped = map_integrity_error(exc)
        logger.warning(
            "db_integrity_error",
            method=request.method,
            path=request.url.path,
            trace_id=trace_id,
            error_id=error_id,
            code=mapped.code,
        )
        return envelope(
            success=False,
            errors=[_error_payload(code=mapped.code, message=mapped.message, error_id=error_id)],
            trace_id=trace_id,
            status_code=mapped.status_code,
            meta={"errorId": error_id},
        )

    severity = "error"
    if isinstance(exc, OperationalError):
        severity = "fatal"
    getattr(logger, severity if severity != "fatal" else "error")(
        "db_error",
        method=request.method,
        path=request.url.path,
        trace_id=trace_id,
        error_id=error_id,
        severity=severity,
        exc_info=exc,
    )
    return envelope(
        success=False,
        errors=[
            _error_payload(
                code="SERVICE_UNAVAILABLE" if isinstance(exc, OperationalError) else "INTERNAL_ERROR",
                message="Something went wrong. Try again shortly.",
                error_id=error_id,
            )
        ],
        trace_id=trace_id,
        status_code=503 if isinstance(exc, OperationalError) else 500,
        meta={"errorId": error_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", None)
    error_id = _new_error_id()
    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        trace_id=trace_id,
        error_id=error_id,
        severity="error",
        exc_info=exc,
    )
    try:
        from app.core.alerts import maybe_send_critical_alert

        await maybe_send_critical_alert(
            subject=f"[AI NEET] CRITICAL APPLICATION ERROR — Error ID {error_id}",
            body=(
                f"Application: AI NEET Preparation (TALOS)\n"
                f"Severity: CRITICAL\n"
                f"Route: {request.method} {request.url.path}\n"
                f"Correlation ID: {trace_id}\n"
                f"Error ID: {error_id}\n"
                f"Safe message: Unhandled server exception (details redacted).\n"
            ),
            dedupe_key=f"unhandled:{request.url.path}:{type(exc).__name__}",
        )
    except Exception:
        logger.warning("critical_alert_failed", error_id=error_id, exc_info=True)

    return envelope(
        success=False,
        errors=[
            _error_payload(
                code="INTERNAL_ERROR",
                message="Something went wrong. Try again shortly.",
                error_id=error_id,
            )
        ],
        trace_id=trace_id,
        status_code=500,
        meta={"errorId": error_id},
    )
