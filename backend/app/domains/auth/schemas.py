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
    force_password_change: bool = False
    last_login_at: datetime | None = None

    roles: list[RoleBrief] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class LoginResponseUser(BaseModel):
    user_id: int
    username: str
    full_name: str
    department: str | None = None
    title: str | None = None
    must_change_password: bool = False
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


# =============================================================================
# Phase 5.A / M5.1：管理员侧用户管理 schemas（user:manage）
# =============================================================================


class UserCreate(BaseModel):
    """POST /api/v1/users — 管理员创建用户"""

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=128)
    full_name_en: str | None = Field(None, max_length=128)
    department: str | None = Field(None, max_length=64)
    title: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=32)
    role_codes: list[str] = Field(default_factory=list, max_length=20)


class UserUpdate(BaseModel):
    """PUT /api/v1/users/{username} — 仅允许编辑 profile 字段（username/password 走专用动作）"""

    email: EmailStr | None = None
    full_name: str | None = Field(None, min_length=1, max_length=128)
    full_name_en: str | None = Field(None, max_length=128)
    department: str | None = Field(None, max_length=64)
    title: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=32)


class UserRoleAssignment(BaseModel):
    """PUT /api/v1/users/{username}/roles — 替换式角色分配"""

    role_codes: list[str] = Field(..., max_length=20)


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: str
    full_name: str
    department: str | None = None
    title: str | None = None
    status: str
    last_login_at: datetime | None = None
    created_at: datetime
    roles: list[RoleBrief] = Field(default_factory=list)


class UserDetail(BaseModel):
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
    failed_login_count: int = 0
    locked_at: datetime | None = None
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    password_expires_at: datetime | None = None
    force_password_change: bool = False
    mfa_enabled: bool
    created_at: datetime
    created_by: int | None = None
    updated_at: datetime
    updated_by: int | None = None
    roles: list[RoleBrief] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class ResetPasswordResponse(BaseModel):
    """POST /api/v1/users/{username}:reset-password — 临时密码一次性返回给管理员"""

    username: str
    temp_password: str
    force_password_change: bool = True


# =============================================================================
# Phase 5.A / M5.2：角色 & 权限管理 schemas
# =============================================================================


class PermissionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permission_id: int
    permission_code: str
    resource: str
    action: str
    description: str | None = None
    is_system: bool = True


class RoleListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: int
    role_code: str
    role_name: str
    description: str | None = None
    is_system: bool
    permission_count: int = 0
    user_count: int = 0
    created_at: datetime
    updated_at: datetime


class RoleDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: int
    role_code: str
    role_name: str
    description: str | None = None
    is_system: bool
    permission_count: int = 0
    user_count: int = 0
    permissions: list[PermissionItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    """POST /api/v1/roles — 创建自定义角色"""

    role_code: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Z][A-Z0-9_]+$")
    role_name: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(None, max_length=1024)
    permission_codes: list[str] = Field(default_factory=list, max_length=200)


class RoleUpdate(BaseModel):
    """PUT /api/v1/roles/{role_code} — 更新自定义角色（不可改 role_code）"""

    role_name: str | None = Field(None, min_length=1, max_length=64)
    description: str | None = Field(None, max_length=1024)
    permission_codes: list[str] | None = Field(None, max_length=200)


# =============================================================================
# Phase 5.A / M5.4：个人中心 schemas（GET /auth/me/login-history 等）
# =============================================================================


class LoginHistoryItem(BaseModel):
    """登录历史条目"""

    model_config = ConfigDict(from_attributes=True)

    login_id: int
    username_input: str
    success: bool
    failure_reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    login_at: datetime
