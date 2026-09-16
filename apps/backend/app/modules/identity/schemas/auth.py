from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Public registration payload.

    The user chooses their password at registration; ``validate_password_
    policy`` enforces the full 12-char / upper / lower / digit / special
    rule in the service layer. must_change_password is set to false and
    password_changed_at is stamped with the account creation time.
    """

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    mobile: str = Field(min_length=10, max_length=20)
    state_code: str = Field(min_length=2, max_length=64)
    city: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


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
    must_change_password: bool = False
    mobile_e164: str | None = None
    state_code: str | None = None
    city_name: str | None = None
    # Non-blocking 90-day password-age recommendation. `password_age_days`
    # is None when password_changed_at is unknown (legacy rows) — clients
    # must NOT nag in that case. `password_reminder_due` is derived
    # server-side so the client does not have to know the policy value.
    password_age_days: int | None = None
    password_reminder_due: bool = False


class MobileOtpSendRequest(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)


class MobileOtpVerifyRequest(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    code: str = Field(min_length=4, max_length=10)


class ProfileUpdateRequest(BaseModel):
    """PATCH /users/me payload for mobile/state/city + profile fields."""

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=150)
    mobile: str | None = Field(default=None, min_length=10, max_length=20)
    state_code: str | None = Field(default=None, min_length=2, max_length=64)
    city: str | None = Field(default=None, min_length=1, max_length=120)
