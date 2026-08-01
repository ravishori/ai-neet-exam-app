import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.modules.identity.models.login_history import LoginHistory
from app.modules.identity.models.refresh_token import RefreshToken
from app.modules.identity.models.user import User
from app.modules.identity.repositories.refresh_token_repository import RefreshTokenRepository
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.identity.services.password_service import (
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.modules.identity.services.token_service import (
    create_access_token,
    generate_csrf_token,
    generate_refresh_token,
    generate_verification_token,
    hash_opaque_token,
)

logger = get_logger("auth")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
DEFAULT_ROLE_CODE = "STUDENT"


class AuthError(AppError):
    def __init__(self, message: str, *, code: str = "AUTH_ERROR"):
        super().__init__(message, code=code, status_code=401)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.tokens = RefreshTokenRepository(session)

    async def register(
        self, *, email: str, password: str, first_name: str | None, last_name: str | None
    ) -> User:
        email = email.lower().strip()
        validate_password_policy(password)

        existing = await self.users.get_by_email(email)
        if existing:
            raise AppError("An account with this email already exists", code="EMAIL_TAKEN", status_code=409)

        student_role = await self.roles.get_by_code(DEFAULT_ROLE_CODE)
        if not student_role:
            raise AppError("Default role not seeded — run the identity seed script", code="ROLE_NOT_FOUND", status_code=500)

        user = User(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            display_name=first_name or email.split("@")[0],
        )
        self.users.add(user)
        await self.users.flush()

        self.roles.assign_role(user.id, student_role.id)
        await self.session.commit()

        logger.info("user_registered", user_id=str(user.id), email=email)
        # Re-fetch with roles eager-loaded — `user` above has an unloaded
        # `.roles` collection, and lazy-loading it later (e.g. during
        # response serialization) raises MissingGreenlet outside an
        # explicit await.
        return await self.users.get_by_id(user.id)

    async def authenticate(
        self, *, email: str, password: str, ip_address: str | None, user_agent: str | None
    ) -> User:
        email = email.lower().strip()
        user = await self.users.get_by_email(email)

        if user and user.locked_until and user.locked_until > datetime.now(UTC):
            await self._record_login_attempt(user.id, email, False, "account_locked", ip_address, user_agent)
            raise AuthError("Account temporarily locked due to repeated failed attempts", code="ACCOUNT_LOCKED")

        if not user or not verify_password(password, user.password_hash):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_MINUTES)
                await self.session.commit()
            await self._record_login_attempt(
                user.id if user else None, email, False, "invalid_credentials", ip_address, user_agent
            )
            raise AuthError("Invalid email or password", code="INVALID_CREDENTIALS")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        await self.session.commit()

        await self._record_login_attempt(user.id, email, True, None, ip_address, user_agent)
        logger.info("user_logged_in", user_id=str(user.id))
        return user

    async def _record_login_attempt(
        self,
        user_id: uuid.UUID | None,
        email: str,
        success: bool,
        reason: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self.session.add(
            LoginHistory(
                id=uuid.uuid4(),
                user_id=user_id,
                attempted_email=email,
                success=success,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.commit()

    def issue_tokens(self, user: User) -> tuple[str, str, str]:
        """Returns (access_token, refresh_token_plaintext, csrf_token)."""
        access_token = create_access_token(user_id=user.id, role_codes=user.role_codes)
        csrf_token = generate_csrf_token()
        return access_token, csrf_token

    async def issue_refresh_token(
        self, user: User, *, ip_address: str | None, user_agent: str | None
    ) -> str:
        plaintext, token_hash, expires_at = generate_refresh_token()
        record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            issued_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.tokens.add(record)
        await self.session.commit()
        return plaintext

    async def rotate_refresh_token(
        self, plaintext_token: str, *, ip_address: str | None, user_agent: str | None
    ) -> tuple[User, str]:
        token_hash = hash_opaque_token(plaintext_token)
        existing = await self.tokens.get_by_hash(token_hash)

        if not existing:
            raise AuthError("Invalid refresh token", code="INVALID_REFRESH_TOKEN")

        if existing.revoked_at is not None:
            # Presented an already-used token — possible theft. Revoke the
            # whole family defensively rather than silently ignoring it.
            await self.tokens.revoke_all_for_user(existing.user_id)
            await self.session.commit()
            raise AuthError("Refresh token reuse detected — all sessions revoked", code="TOKEN_REUSE_DETECTED")

        if existing.expires_at <= datetime.now(UTC):
            raise AuthError("Refresh token expired", code="REFRESH_TOKEN_EXPIRED")

        user = await self.users.get_by_id(existing.user_id)
        if not user:
            raise AuthError("User not found", code="USER_NOT_FOUND")

        new_plaintext, new_hash, new_expires_at = generate_refresh_token()
        new_record = RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            issued_at=datetime.now(UTC),
            expires_at=new_expires_at,
        )
        self.tokens.add(new_record)
        await self.session.flush()

        await self.tokens.revoke(existing, replaced_by=new_record.id)
        existing.last_used_at = datetime.now(UTC)
        await self.session.commit()

        return user, new_plaintext

    async def revoke_refresh_token(self, plaintext_token: str) -> None:
        token_hash = hash_opaque_token(plaintext_token)
        existing = await self.tokens.get_by_hash(token_hash)
        if existing and existing.revoked_at is None:
            await self.tokens.revoke(existing)
            await self.session.commit()

    async def request_password_reset(self, email: str) -> str | None:
        user = await self.users.get_by_email(email.lower().strip())
        if not user:
            return None  # never reveal whether the email exists
        plaintext, token_hash, expires_at = generate_verification_token()
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at
        await self.session.commit()
        return plaintext

    async def reset_password(self, token: str, new_password: str) -> None:
        validate_password_policy(new_password)
        token_hash = hash_opaque_token(token)

        from sqlalchemy import select

        result = await self.session.execute(
            select(User).where(User.password_reset_token_hash == token_hash)
        )
        user = result.scalar_one_or_none()

        if not user or not user.password_reset_expires_at or user.password_reset_expires_at <= datetime.now(UTC):
            raise AppError("Invalid or expired reset link", code="INVALID_RESET_TOKEN", status_code=400)

        user.password_hash = hash_password(new_password)
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        await self.tokens.revoke_all_for_user(user.id)
        await self.session.commit()
        logger.info("password_reset", user_id=str(user.id))

    async def request_email_verification(self, user: User) -> str:
        plaintext, token_hash, expires_at = generate_verification_token()
        user.email_verification_token_hash = token_hash
        user.email_verification_expires_at = expires_at
        await self.session.commit()
        return plaintext

    async def verify_email(self, token: str) -> User:
        from sqlalchemy import select

        token_hash = hash_opaque_token(token)
        result = await self.session.execute(
            select(User.id).where(User.email_verification_token_hash == token_hash)
        )
        user_id = result.scalar_one_or_none()
        user = await self.users.get_by_id(user_id) if user_id else None

        if not user or not user.email_verification_expires_at or user.email_verification_expires_at <= datetime.now(UTC):
            raise AppError("Invalid or expired verification link", code="INVALID_VERIFICATION_TOKEN", status_code=400)

        user.email_verified = True
        user.email_verification_token_hash = None
        user.email_verification_expires_at = None
        await self.session.commit()
        logger.info("email_verified", user_id=str(user.id))
        return user
