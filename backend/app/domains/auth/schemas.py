"""
auth 域 Pydantic schemas
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: int
    role_code: str
    role_name: str


class UserMe(BaseModel):
    """当前用户信息（GET /auth/me）"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: str
    full_name: str
    full_name_en: str | None = None
    department: str | None = None
    title: str | None = None
    phone: str | None = None
    status: str
    mfa_enabled: bool
    last_login_at: datetime | None = None

    roles: list[RoleBrief] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class LoginResponseUser(BaseModel):
    user_id: int
    username: str
    full_name: str
    department: str | None = None
    title: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: LoginResponseUser


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=12, max_length=128)
