from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    phone: str | None
    status: str
    email_verified: bool
    roles: list[str]
    last_login_at: datetime | None
    created_at: datetime


class UserUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    preferred_language: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=50)


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None
    role_codes: list[str] = Field(default_factory=lambda: ["STUDENT"])


class AdminUserUpdateRequest(BaseModel):
    """Admin-only fields for PATCH /users/{id} — never accepted on the self-service /users/me route."""

    status: str | None = Field(default=None, max_length=20)
    role_codes: list[str] | None = None
