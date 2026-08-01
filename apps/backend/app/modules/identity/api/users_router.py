import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.identity.schemas.user import AdminUserUpdateRequest, UserCreateRequest, UserResponse, UserUpdateRequest
from app.modules.identity.services.password_service import hash_password, validate_password_policy
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_response(user: User) -> dict:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        phone=user.phone,
        status=user.status,
        email_verified=user.email_verified,
        roles=user.role_codes,
        preferred_language=user.preferred_language,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    ).model_dump()


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return envelope(success=True, data=_to_response(user))


@router.patch("/me", dependencies=[Depends(verify_csrf)])
async def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return envelope(success=True, data=_to_response(user))


@router.get("", dependencies=[Depends(require_permission("users.manage"))])
async def list_users(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    users = await repo.list(limit=limit, offset=offset)
    return envelope(success=True, data=[_to_response(u) for u in users], meta={"limit": limit, "offset": offset})


@router.get("/{user_id}", dependencies=[Depends(require_permission("users.manage"))])
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if not target:
        raise NotFoundError("User not found")
    return envelope(success=True, data=_to_response(target))


@router.post("", dependencies=[Depends(require_permission("users.manage")), Depends(verify_csrf)])
async def create_user(payload: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    validate_password_policy(payload.password)
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)

    from app.core.exceptions import AppError

    if await user_repo.get_by_email(payload.email):
        raise AppError("An account with this email already exists", code="EMAIL_TAKEN", status_code=409)

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        display_name=payload.first_name or payload.email.split("@")[0],
        email_verified=True,  # admin-created accounts skip self-verification
    )
    user_repo.add(user)
    await user_repo.flush()

    for code in payload.role_codes:
        role = await role_repo.get_by_code(code)
        if role:
            role_repo.assign_role(user.id, role.id)

    await db.commit()
    created = await user_repo.get_by_id(user.id)  # re-fetch with roles eager-loaded
    return envelope(success=True, data=_to_response(created), status_code=201)


@router.patch("/{user_id}", dependencies=[Depends(require_permission("users.manage")), Depends(verify_csrf)])
async def update_user(user_id: uuid.UUID, payload: AdminUserUpdateRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if not target:
        raise NotFoundError("User not found")

    fields = payload.model_dump(exclude_unset=True, exclude={"role_codes"})
    for field, value in fields.items():
        setattr(target, field, value)

    if payload.role_codes is not None:
        role_repo = RoleRepository(db)
        await role_repo.replace_roles(user_id, payload.role_codes)
        # replace_roles does a bulk DELETE, which the ORM's identity map doesn't
        # know invalidates `target.roles` — expire it so the re-fetch below
        # actually reloads the relationship instead of returning the stale
        # in-memory collection (session is expire_on_commit=False).
        db.expire(target, ["roles"])

    await db.commit()
    updated = await repo.get_by_id(user_id)  # re-fetch with roles eager-loaded
    return envelope(success=True, data=_to_response(updated))
