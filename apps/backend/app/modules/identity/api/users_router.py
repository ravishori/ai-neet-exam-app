import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.user import User
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.identity.schemas.user import AdminUserUpdateRequest, UserCreateRequest, UserResponse, UserUpdateRequest
from app.modules.identity.services.password_service import hash_password, validate_password_policy
from app.modules.system.services.audit_service import AuditService, request_context
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
async def list_users(
    search: str | None = None,
    status: str | None = None,
    role: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    users, total = await repo.list_paginated(search=search, status=status, role_code=role, limit=limit, offset=offset)
    return envelope(success=True, data=[_to_response(u) for u in users], meta={"total": total, "limit": limit, "offset": offset})


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
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    request: Request,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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

    await AuditService(db).log(
        actor_user_id=actor.id,
        action="user.update",
        entity_type="user",
        entity_id=user_id,
        metadata={k: v for k, v in payload.model_dump(exclude_unset=True).items()},
        **request_context(request),
    )
    return envelope(success=True, data=_to_response(updated))


BULK_USER_ACTIONS = {"suspend", "activate"}


class BulkUserActionRequest(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=200)
    action: str  # suspend | activate


@router.post("/bulk", dependencies=[Depends(require_permission("users.manage")), Depends(verify_csrf)])
async def bulk_user_action(
    payload: BulkUserActionRequest, request: Request, actor: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Admin Portal (PR11) Module 9 — bulk suspend/activate, same
    per-item-independent pattern as Question Management's bulk publish/
    archive (cms_router.py)."""
    if payload.action not in BULK_USER_ACTIONS:
        from app.core.exceptions import AppError

        raise AppError(f"Unknown bulk action: {payload.action}", code="INVALID_BULK_ACTION", status_code=400)

    new_status = "active" if payload.action == "activate" else "suspended"
    repo = UserRepository(db)
    audit = AuditService(db)
    ctx = request_context(request)
    results = []
    for raw_id in payload.user_ids:
        user_id = uuid.UUID(raw_id)
        target = await repo.get_by_id(user_id)
        if not target:
            results.append({"id": raw_id, "success": False, "error": "User not found"})
            continue
        target.status = new_status
        await db.commit()
        await audit.log(
            actor_user_id=actor.id,
            action="user.bulk_status_change",
            entity_type="user",
            entity_id=user_id,
            metadata={"status": new_status},
            **ctx,
        )
        results.append({"id": raw_id, "success": True})
    return envelope(success=True, data=results)
