from fastapi import Response

from app.core.config import get_settings
from app.modules.identity.dependencies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE

settings = get_settings()


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str, csrf_token: str) -> None:
    secure = settings.is_production
    domain = settings.cookie_domain or None
    response.set_cookie(
        ACCESS_COOKIE, access_token, httponly=True, secure=secure, samesite="lax",
        max_age=settings.jwt_access_token_minutes * 60, path="/", domain=domain,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, httponly=True, secure=secure, samesite="lax",
        max_age=settings.jwt_refresh_token_days * 86400, path="/api/v1/auth", domain=domain,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, httponly=False, secure=secure, samesite="lax",
        max_age=settings.jwt_refresh_token_days * 86400, path="/", domain=domain,
    )


def clear_auth_cookies(response: Response) -> None:
    domain = settings.cookie_domain or None
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", domain=domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)
