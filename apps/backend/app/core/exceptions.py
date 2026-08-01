from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.responses import envelope


class AppError(Exception):
    """Base for business errors. Every module-specific error inherits this."""

    def __init__(self, message: str, *, code: str = "APP_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403)


async def app_error_handler(request: Request, exc: AppError):
    trace_id = getattr(request.state, "trace_id", None)
    return envelope(
        success=False,
        errors=[{"code": exc.code, "message": exc.message}],
        trace_id=trace_id,
        status_code=exc.status_code,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = getattr(request.state, "trace_id", None)
    return envelope(
        success=False,
        errors=[{"code": "HTTP_ERROR", "message": str(exc.detail)}],
        trace_id=trace_id,
        status_code=exc.status_code,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", None)
    errors = [
        {"code": "VALIDATION_ERROR", "message": err["msg"], "field": ".".join(str(p) for p in err["loc"])}
        for err in exc.errors()
    ]
    return envelope(success=False, errors=errors, trace_id=trace_id, status_code=422)


async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", None)
    return envelope(
        success=False,
        errors=[{"code": "INTERNAL_ERROR", "message": "Something went wrong. Try again shortly."}],
        trace_id=trace_id,
        status_code=500,
    )
