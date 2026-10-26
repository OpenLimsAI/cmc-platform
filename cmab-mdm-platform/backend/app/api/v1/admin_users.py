"""/api/v1/users 路由（管理员侧：API10 用户管理）

权限：user:manage（SYS_ADMIN 自动通过）
合规：用户只能 lock（软停用），不可物理/软删除（GxP 审计链完整性）；
管理员不能对自己执行 lock/reset-password（CannotOperateSelfError）。

部门管理员（DEPT_ADMIN，2026-09-10）：list / detail / roles / lock / unlock 五个端点改用
user_admin_scope() 依赖——SYS_ADMIN 或持 user:manage 为全公司范围（行为不变），
DEPT_ADMIN 为本部门范围（service 内做部门过滤 + 角色白名单校验）。
create / update / reset-password 仍只认 user:manage，部门管理员 403。
"""
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.auth.admin_service import UserAdminService
from app.domains.auth.dept_admin import UserAdminScope, user_admin_scope
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    UserCreate,
    UserDetail,
    UserRoleAssignment,
    UserUpdate,
)
from app.shared.permissions import require_permission

router = APIRouter()


@router.get("", summary="用户列表（admin）")
async def list_users(
    request: Request,
    q: str | None = None,
    role_code: str | None = None,
    department: str | None = Query(None, max_length=64, description="部门，包含匹配、不分大小写"),
    status: str | None = Query(None, pattern="^(active|locked|disabled)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scope: UserAdminScope = Depends(user_admin_scope()),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    items, total = await service.list_users(
        q, role_code, status, page, page_size, scope=scope, department=department
    )
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建用户（admin）")
async def create_user(
    payload: UserCreate,
    request: Request,
    user: User = Depends(require_permission("user:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    detail: UserDetail = await service.create_user(payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="用户创建成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/departments", summary="部门清单（admin，供筛选下拉）")
async def list_departments(
    request: Request,
    scope: UserAdminScope = Depends(user_admin_scope()),
    db: AsyncSession = Depends(get_db),
):
    """用户表里实际出现过的部门（自由文本，无字典表）。

    ⚠️ 必须注册在 /{username} 之前，否则会被当成 username="departments" 去查用户。
    """
    service = UserAdminService(db)
    return success(
        data=await service.list_departments(scope=scope),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{username}", summary="用户详情（admin）")
async def get_user_detail(
    username: str,
    request: Request,
    scope: UserAdminScope = Depends(user_admin_scope()),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    detail = await service.get_user(username, scope=scope)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{username}", summary="更新用户 profile（admin）")
async def update_user(
    username: str,
    payload: UserUpdate,
    request: Request,
    user: User = Depends(require_permission("user:manage")),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    detail = await service.update_user(username, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="用户已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{username}/roles", summary="分配/替换用户角色（admin）")
async def assign_user_roles(
    username: str,
    payload: UserRoleAssignment,
    request: Request,
    scope: UserAdminScope = Depends(user_admin_scope()),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    detail = await service.assign_roles(username, payload.role_codes, scope.actor, scope=scope)
    return success(
        data=detail.model_dump(mode="json"),
        message="角色已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{username}:lock", summary="锁定用户（admin）")
async def lock_user(
    username: str,
    request: Request,
    scope: UserAdminScope = Depends(user_admin_scope()),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    detail = await service.lock_user(username, scope.actor, scope=scope)
    return success(
        data=detail.model_dump(mode="json"),
        message="用户已锁定",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{username}:unlock", summary="解锁用户（admin）")
async def unlock_user(
    username: str,
    request: Request,
    scope: UserAdminScope = Depends(user_admin_scope()),
    db: AsyncSession = Depends(get_db),
):
    service = UserAdminService(db)
    detail = await service.unlock_user(username, scope.actor, scope=scope)
    return success(
        data=detail.model_dump(mode="json"),
        message="用户已解锁",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{username}:reset-password", summary="重置用户密码（admin）")
async def reset_password(
    username: str,
    request: Request,
    user: User = Depends(require_permission("user:manage")),
    db: AsyncSession = Depends(get_db),
):
    """返回一次性临时密码 + force_password_change=TRUE，用户首次登录强制改密。"""
    service = UserAdminService(db)
    result = await service.reset_password(username, user)
    return success(
        data=result.model_dump(mode="json"),
        message="密码已重置，请将临时密码安全告知用户（一次性显示）",
        request_id=getattr(request.state, "request_id", None),
    )
