import uuid

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError, PermissionDeniedError
from app.modules.identity.models.user import User
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.identity.services.token_service import decode_access_token

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


class AuthenticationError(AppError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(message, code="NOT_AUTHENTICATED", status_code=401)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise AuthenticationError()

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Session expired, please log in again") from exc

    user_repo = UserRepository(db)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError() from exc
    user = await user_repo.get_by_id(user_id)
    if not user or user.status != "active":
        raise AuthenticationError()
    return user


async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    try:
        return await get_current_user(request, db)
    except AppError:
        return None


def require_permission(permission_code: str):
    async def _check(
        user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
    ) -> User:
        if "SUPER_ADMIN" in user.role_codes:
            return user

        role_repo = RoleRepository(db)
        role_ids = [ur.role_id for ur in user.roles]
        permissions = await role_repo.get_permission_codes_for_roles(role_ids)
        if permission_code not in permissions:
            raise PermissionDeniedError(f"Missing permission: {permission_code}")
        return user

    return _check


def verify_csrf(request: Request) -> None:
    """Double-submit cookie check for cookie-authenticated mutating requests."""
    header_token = request.headers.get(CSRF_HEADER)
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if not header_token or not cookie_token or header_token != cookie_token:
        raise AppError("CSRF check failed", code="CSRF_INVALID", status_code=403)
