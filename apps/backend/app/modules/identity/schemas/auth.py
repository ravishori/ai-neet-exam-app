from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class OtpRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(min_length=3, max_length=40)


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(min_length=3, max_length=40)
    code: str = Field(min_length=6, max_length=6)


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=4, max_length=64)


class TotpConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class TotpDisableRequest(BaseModel):
    code: str = Field(min_length=4, max_length=64)


class MeResponse(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    email_verified: bool
    roles: list[str]
    totp_enabled: bool = False
