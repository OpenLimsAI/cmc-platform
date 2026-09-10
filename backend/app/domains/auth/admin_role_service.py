"""
Phase 5.A / M5.2：角色 & 权限管理服务

规则：
- 系统角色（is_system=TRUE）不可修改/删除（SystemRoleProtectedError）
- 自定义角色删除前必须确保无用户持有（复用 ReferenceInUseError 42202）
- 创建/更新时 permission_codes 必须全部存在（PermissionNotFoundError 40409）
- 角色编码全大写 + 下划线（schema 校验）
"""
from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    PermissionNotFoundError,
    ReferenceInUseError,
    RoleCodeExistsError,
    RoleNotFoundError,
    SystemRoleProtectedError,
)
from app.domains.auth.dept_admin import load_dept_admin_policy
from app.domains.auth.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.domains.auth.schemas import (
    PermissionItem,
    RoleCreate,
    RoleDetail,
    RoleListItem,
    RoleUpdate,
)


def _permission_to_item(p: Permission) -> PermissionItem:
    return PermissionItem(
        permission_id=p.permission_id,
        permission_code=p.permission_code,
        resource=p.resource,
        action=p.action,
        description=p.description,
        is_system=p.is_system,
    )


class RoleAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 内部 -----------
    async def _resolve_permission_ids(self, permission_codes: list[str]) -> list[int]:
        if not permission_codes:
            return []
        result = await self.db.execute(
            select(Permission).where(Permission.permission_code.in_(permission_codes))
        )
        perms = result.scalars().all()
        found = {p.permission_code for p in perms}
        missing = [c for c in permission_codes if c not in found]
        if missing:
            raise PermissionNotFoundError(
                f"权限不存在: {', '.join(missing)}"
            )
        return [p.permission_id for p in perms]

    async def _load_role(self, role_code: str) -> Role:
        result = await self.db.execute(
            select(Role).where(Role.role_code == role_code, Role.deleted_at.is_(None))
        )
        role = result.scalar_one_or_none()
        if not role:
            raise RoleNotFoundError(f"角色 {role_code} 不存在")
        return role

    async def _count_users(self, role_id: int) -> int:
        result = await self.db.execute(
            select(func.count(UserRole.user_id))
            .join(User, User.user_id == UserRole.user_id)
            .where(UserRole.role_id == role_id, User.deleted_at.is_(None))
        )
        return result.scalar_one()

    async def _count_permissions(self, role_id: int) -> int:
        result = await self.db.execute(
            select(func.count(RolePermission.permission_id)).where(
                RolePermission.role_id == role_id
            )
        )
        return result.scalar_one()

    async def _load_permissions(self, role_id: int) -> list[Permission]:
        result = await self.db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.resource, Permission.action)
        )
        return list(result.scalars().all())

    # ----------- 公共方法 -----------
    async def list_roles(self, *, delegable_only: bool = False) -> list[RoleListItem]:
        """delegable_only=True：部门管理员视角，只返回白名单（可下放）角色"""
        # 单次查询取角色 + 聚合计数；无分页，角色数量极少（实施现状 6 系统 + N 自定义）
        result = await self.db.execute(
            select(Role).where(Role.deleted_at.is_(None)).order_by(
                Role.is_system.desc(), Role.role_code
            )
        )
        roles = list(result.scalars().all())
        if delegable_only:
            policy = await load_dept_admin_policy(self.db)
            roles = [r for r in roles if policy.is_delegable(r.role_code)]

        items: list[RoleListItem] = []
        for r in roles:
            items.append(
                RoleListItem(
                    role_id=r.role_id,
                    role_code=r.role_code,
                    role_name=r.role_name,
                    description=r.description,
                    is_system=r.is_system,
                    permission_count=await self._count_permissions(r.role_id),
                    user_count=await self._count_users(r.role_id),
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
            )
        return items

    async def get_role(self, role_code: str) -> RoleDetail:
        role = await self._load_role(role_code)
        perms = await self._load_permissions(role.role_id)
        return RoleDetail(
            role_id=role.role_id,
            role_code=role.role_code,
            role_name=role.role_name,
            description=role.description,
            is_system=role.is_system,
            permission_count=len(perms),
            user_count=await self._count_users(role.role_id),
            permissions=[_permission_to_item(p) for p in perms],
            created_at=role.created_at,
            updated_at=role.updated_at,
        )

    async def create_role(self, payload: RoleCreate, actor: User) -> RoleDetail:
        # 预检 role_code 唯一
        exist = await self.db.execute(
            select(Role).where(Role.role_code == payload.role_code, Role.deleted_at.is_(None))
        )
        if exist.scalar_one_or_none():
            raise RoleCodeExistsError(f"角色编码 {payload.role_code} 已存在")

        perm_ids = await self._resolve_permission_ids(payload.permission_codes)

        role = Role(
            role_code=payload.role_code,
            role_name=payload.role_name,
            description=payload.description,
            is_system=False,  # 自定义角色
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        self.db.add(role)
        await self.db.flush()

        for pid in perm_ids:
            self.db.add(RolePermission(role_id=role.role_id, permission_id=pid, granted_by=actor.user_id))
        await self.db.flush()

        logger.info(
            f"管理员 {actor.username} 创建自定义角色 {payload.role_code}（权限={payload.permission_codes}）"
        )
        return await self.get_role(role.role_code)

    async def update_role(
        self, role_code: str, payload: RoleUpdate, actor: User
    ) -> RoleDetail:
        role = await self._load_role(role_code)
        if role.is_system:
            raise SystemRoleProtectedError(
                f"系统内置角色 {role_code} 不可修改"
            )

        if payload.role_name is not None:
            role.role_name = payload.role_name
        if payload.description is not None:
            role.description = payload.description

        # 权限集合替换（None 表示不动）
        if payload.permission_codes is not None:
            perm_ids = await self._resolve_permission_ids(payload.permission_codes)
            await self.db.execute(
                RolePermission.__table__.delete().where(
                    RolePermission.role_id == role.role_id
                )
            )
            for pid in perm_ids:
                self.db.add(
                    RolePermission(
                        role_id=role.role_id,
                        permission_id=pid,
                        granted_by=actor.user_id,
                    )
                )

        role.updated_by = actor.user_id
        await self.db.flush()
        logger.info(f"管理员 {actor.username} 更新自定义角色 {role_code}")
        return await self.get_role(role.role_code)

    async def delete_role(self, role_code: str, actor: User) -> None:
        role = await self._load_role(role_code)
        if role.is_system:
            raise SystemRoleProtectedError(
                f"系统内置角色 {role_code} 不可删除"
            )
        user_count = await self._count_users(role.role_id)
        if user_count > 0:
            raise ReferenceInUseError(
                f"角色 {role_code} 仍有 {user_count} 个用户持有，无法删除"
            )

        # 先删 role_permission 行，再软删 role
        await self.db.execute(
            RolePermission.__table__.delete().where(
                RolePermission.role_id == role.role_id
            )
        )
        role.deleted_at = datetime.now(UTC)
        role.deleted_by = actor.user_id
        await self.db.flush()
        logger.info(f"管理员 {actor.username} 删除自定义角色 {role_code}")


class PermissionAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_permissions(self) -> list[PermissionItem]:
        result = await self.db.execute(
            select(Permission).order_by(Permission.resource, Permission.action)
        )
        return [_permission_to_item(p) for p in result.scalars().all()]
