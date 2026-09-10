"""/api/v1/roles 与 /api/v1/permissions 路由（Phase 5.A / M5.2）

权限：role:manage（SYS_ADMIN 自动通过）
- GET    /api/v1/roles                — 角色列表（含 user_count / permission_count）
- POST   /api/v1/roles                — 创建自定义角色
- GET    /api/v1/roles/{role_code}    — 角色详情（含 permissions 列表）
- PUT    /api/v1/roles/{role_code}    — 更新自定义角色（系统角色 40306）
- DELETE /api/v1/roles/{role_code}    — 删除自定义角色（用户在用 42202；系统角色 40306）
- GET    /api/v1/permissions          — 权限列表（只读）

部门管理员（DEPT_ADMIN，2026-09-10）：仅 GET /roles 放行，且只返回白名单（可下放）角色，
供前端角色下拉使用；其余端点仍只认 role:manage。
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import success
from app.domains.auth.admin_role_service import (
    PermissionAdminService,
    RoleAdminService,
)
from app.domains.auth.dept_admin import UserAdminScope, user_admin_scope
from app.domains.auth.models import User
from app.domains.auth.schemas import RoleCreate, RoleUpdate
from app.shared.permissions import require_permission

roles_router = APIRouter()
permissions_router = APIRouter()


@roles_router.get("", summary="角色列表（admin）")
async def list_roles(
    request: Request,
    scope: UserAdminScope = Depends(user_admin_scope("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = RoleAdminService(db)
    items = await service.list_roles(delegable_only=scope.dept_scoped)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@roles_router.post("", status_code=status.HTTP_201_CREATED, summary="创建自定义角色（admin）")
async def create_role(
    payload: RoleCreate,
    request: Request,
    user: User = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = RoleAdminService(db)
    detail = await service.create_role(payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="角色已创建",
        request_id=getattr(request.state, "request_id", None),
    )


@roles_router.get("/{role_code}", summary="角色详情（admin）")
async def get_role(
    role_code: str,
    request: Request,
    user: User = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = RoleAdminService(db)
    detail = await service.get_role(role_code)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@roles_router.put("/{role_code}", summary="更新自定义角色（admin）")
async def update_role(
    role_code: str,
    payload: RoleUpdate,
    request: Request,
    user: User = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = RoleAdminService(db)
    detail = await service.update_role(role_code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="角色已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@roles_router.delete("/{role_code}", summary="删除自定义角色（admin）")
async def delete_role(
    role_code: str,
    request: Request,
    user: User = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = RoleAdminService(db)
    await service.delete_role(role_code, user)
    return success(
        data=None,
        message="角色已删除",
        request_id=getattr(request.state, "request_id", None),
    )


@permissions_router.get("", summary="权限列表（admin）")
async def list_permissions(
    request: Request,
    user: User = Depends(require_permission("role:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PermissionAdminService(db)
    items = await service.list_permissions()
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )
