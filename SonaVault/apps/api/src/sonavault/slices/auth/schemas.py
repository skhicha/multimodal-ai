from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    invite_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    status: str  # "authenticated" | "mfa_required"
    access_token: str | None = None
    mfa_ticket: str | None = None
    methods: list[str] | None = None
    mfa_setup_required: bool = False


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=128)


class SessionOut(BaseModel):
    id: str
    ip_addr: str | None
    user_agent: str | None
    amr: list[str]
    created_current: bool = False
