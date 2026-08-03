import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.role import Role
from app.modules.identity.models.user import User
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.schemas.role import (
    PermissionResponse,
    RoleCreateRequest,
    RolePermissionsUpdateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from app.modules.system.services.audit_service import AuditService, request_context
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


def _to_response(role: Role, permission_codes: list[str] | None = None) -> dict:
    return RoleResponse(
        id=str(role.id), code=role.code, name=role.name, description=role.description
    ).model_dump() | {"permission_codes": permission_codes}


@router.get("", dependencies=[Depends(get_current_user)])
async def list_roles(db: AsyncSession = Depends(get_db)):
    repo = RoleRepository(db)
    roles = await repo.list()
    result = []
    for r in roles:
        codes = sorted(await repo.get_permission_codes_for_roles([r.id]))
        result.append(_to_response(r, codes))
    return envelope(success=True, data=result)


@router.get("/permissions", dependencies=[Depends(require_permission("users.manage"))])
async def list_permissions(db: AsyncSession = Depends(get_db)):
    """Admin Portal (PR11) Module 9 — every permission code that exists, for
    the role permission-editor checklist UI."""
    repo = RoleRepository(db)
    permissions = await repo.list_all_permissions()
    return envelope(
        success=True,
        data=[PermissionResponse(code=p.code, description=p.description).model_dump() for p in permissions],
    )


@router.patch(
    "/{role_id}/permissions", dependencies=[Depends(require_permission("users.manage")), Depends(verify_csrf)]
)
async def update_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsUpdateRequest,
    request: Request,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = RoleRepository(db)
    role = await db.get(Role, role_id)
    if not role:
        raise NotFoundError("Role not found")
    if role.code == "SUPER_ADMIN":
        raise AppError("SUPER_ADMIN's permissions cannot be edited — it bypasses permission checks entirely", code="ROLE_IMMUTABLE", status_code=400)

    await repo.replace_permissions(role_id, payload.permission_codes)
    await db.commit()

    await AuditService(db).log(
        actor_user_id=actor.id,
        action="role.update_permissions",
        entity_type="role",
        entity_id=role_id,
        metadata={"permission_codes": payload.permission_codes},
        **request_context(request),
    )
    codes = sorted(await repo.get_permission_codes_for_roles([role_id]))
    return envelope(success=True, data=_to_response(role, codes))


@router.post("", dependencies=[Depends(require_permission("users.manage")), Depends(verify_csrf)])
async def create_role(payload: RoleCreateRequest, db: AsyncSession = Depends(get_db)):
    repo = RoleRepository(db)
    if await repo.get_by_code(payload.code):
        raise AppError("A role with this code already exists", code="ROLE_EXISTS", status_code=409)
    role = Role(code=payload.code.upper(), name=payload.name, description=payload.description)
    db.add(role)
    await db.commit()
    return envelope(success=True, data=_to_response(role), status_code=201)


@router.patch("/{role_id}", dependencies=[Depends(require_permission("users.manage")), Depends(verify_csrf)])
async def update_role(role_id: uuid.UUID, payload: RoleUpdateRequest, db: AsyncSession = Depends(get_db)):
    role = await db.get(Role, role_id)
    if not role:
        raise NotFoundError("Role not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.commit()
    return envelope(success=True, data=_to_response(role))
