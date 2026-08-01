from fastapi import Response

from app.core.config import get_settings
from app.modules.identity.dependencies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE

settings = get_settings()


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = settings.is_production
    response.set_cookie(
        ACCESS_COOKIE, access_token, httponly=True, secure=secure, samesite="lax",
        max_age=settings.jwt_access_token_minutes * 60, path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, httponly=True, secure=secure, samesite="lax",
        max_age=settings.jwt_refresh_token_days * 86400, path="/api/v1/auth",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, httponly=False, secure=secure, samesite="lax",
        max_age=settings.jwt_refresh_token_days * 86400, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")
