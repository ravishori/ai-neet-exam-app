from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.rate_limit import rate_limit
from app.modules.identity.cookies import clear_auth_cookies, set_auth_cookies
from app.modules.identity.dependencies import REFRESH_COOKIE, get_current_user
from app.modules.identity.models.user import User
from app.modules.identity.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.modules.identity.services.auth_service import AuthService
from app.modules.identity.services.email_service import send_password_reset_email, send_verification_email
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str, str]:
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return ip, user_agent


def _user_to_me(user: User) -> dict:
    return MeResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        email_verified=user.email_verified,
        roles=user.role_codes,
    ).model_dump()


@router.post("/register", dependencies=[Depends(rate_limit("register", limit=5, window_seconds=60))])
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.register(
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    verification_token = await service.request_email_verification(user)
    send_verification_email(to=user.email, token=verification_token)

    # Auto-login on registration — email verification is informational in
    # v1, not a login gate (no SMTP wired up yet, see email_service.py), so
    # gating login on it here would just lock every new user out.
    ip, user_agent = _client_meta(request)
    access_token, csrf_token = service.issue_tokens(user)
    refresh_token = await service.issue_refresh_token(user, ip_address=ip, user_agent=user_agent)

    result = envelope(success=True, data=_user_to_me(user), status_code=201)
    set_auth_cookies(result, access_token=access_token, refresh_token=refresh_token, csrf_token=csrf_token)
    return result


@router.post("/login", dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60))])
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip, user_agent = _client_meta(request)
    service = AuthService(db)
    user = await service.authenticate(email=payload.email, password=payload.password, ip_address=ip, user_agent=user_agent)

    access_token, csrf_token = service.issue_tokens(user)
    refresh_token = await service.issue_refresh_token(user, ip_address=ip, user_agent=user_agent)

    # Cookies must be set on the response object actually returned — a
    # separately-injected `Response` dependency's headers are discarded
    # whenever the endpoint returns a Response (like envelope()) directly.
    result = envelope(success=True, data=_user_to_me(user))
    set_auth_cookies(result, access_token=access_token, refresh_token=refresh_token, csrf_token=csrf_token)
    return result


@router.post("/refresh", dependencies=[Depends(rate_limit("refresh", limit=20, window_seconds=60))])
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise AppError("No refresh token presented", code="NO_REFRESH_TOKEN", status_code=401)

    ip, user_agent = _client_meta(request)
    service = AuthService(db)
    user, new_refresh_token = await service.rotate_refresh_token(refresh_token, ip_address=ip, user_agent=user_agent)

    access_token, csrf_token = service.issue_tokens(user)
    result = envelope(success=True, data=_user_to_me(user))
    set_auth_cookies(result, access_token=access_token, refresh_token=new_refresh_token, csrf_token=csrf_token)
    return result


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        service = AuthService(db)
        await service.revoke_refresh_token(refresh_token)
    result = envelope(success=True, data={"loggedOut": True})
    clear_auth_cookies(result)
    return result


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    token = await service.request_password_reset(payload.email)
    if token:
        send_password_reset_email(to=payload.email, token=token)
    # Always return success — never reveal whether the email exists.
    return envelope(success=True, data={"message": "If that email exists, a reset link has been sent."})


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.reset_password(payload.token, payload.new_password)
    return envelope(success=True, data={"message": "Password updated. Please log in again."})


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.verify_email(payload.token)
    return envelope(success=True, data=_user_to_me(user))


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return envelope(success=True, data=_user_to_me(user))
