import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.modules.identity.dependencies import get_current_user, require_permission, verify_csrf
from app.modules.identity.models.role import Role
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.schemas.role import RoleCreateRequest, RoleResponse, RoleUpdateRequest
from app.shared.responses import envelope

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


def _to_response(role: Role) -> dict:
    return RoleResponse(id=str(role.id), code=role.code, name=role.name, description=role.description).model_dump()


@router.get("", dependencies=[Depends(get_current_user)])
async def list_roles(db: AsyncSession = Depends(get_db)):
    repo = RoleRepository(db)
    roles = await repo.list()
    return envelope(success=True, data=[_to_response(r) for r in roles])


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
