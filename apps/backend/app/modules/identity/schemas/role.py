from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str | None


class RoleCreateRequest(BaseModel):
    code: str = Field(max_length=50)
    name: str = Field(max_length=100)
    description: str | None = None


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
