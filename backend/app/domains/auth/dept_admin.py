"""部门管理员（DEPT_ADMIN）：把「本部门用户管理」委派给部门负责人（2026-09-10；migration 0055）

背景：验证部平台（qv-validation-platform，门户 /qv/）登录与角色都走 MDM，验证部希望自己的
负责人能管本部门的人，而不必每次找 SYS_ADMIN。

规则（负责人 2026-09-10 拍板）：
  - 角色码 DEPT_ADMIN 是身份标签（系统角色，不挂任何 permission）；能力由本模块按角色码判定，
    与 SYS_ADMIN 短路 / DISPLAY_MODE 同一套写法。
  - 范围 = auth.user.department 与自己完全相同的用户（字符串精确匹配）。
  - 可做：看本部门用户列表/详情；挂/摘「允许下放的角色」；锁定/解锁本部门用户。
  - 不可做：新建用户、改资料、改部门、重置密码（这些端点仍只认 user:manage）；
    碰 SYS_ADMIN / DEPT_ADMIN 或任何非白名单角色；锁定持有 SYS_ADMIN / DEPT_ADMIN 的账号。
  - 「允许下放的角色」= 角色码前缀白名单，存 meta.system_config
    键 dept_admin.delegable_role_prefixes（逗号分隔，默认 QV_），SYS_ADMIN 在系统管理页在线改。
  - SYS_ADMIN（或持有 user:manage 权限的账号）行为不变：全公司范围、不受白名单约束。
  - access token 的 roles 里自然带 DEPT_ADMIN，下游不需要理解，token 结构不动。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.domains.auth.models import User
from app.domains.auth.session_policy import SystemConfig
from app.shared.permissions import get_current_user, get_user_permissions

SYS_ADMIN_ROLE = "SYS_ADMIN"
DEPT_ADMIN_ROLE = "DEPT_ADMIN"
# 无论白名单怎么配，这两个角色永远不可由部门管理员下放；持有者也不可被部门管理员锁定
PROTECTED_ROLES = frozenset({SYS_ADMIN_ROLE, DEPT_ADMIN_ROLE})

KEY_DELEGABLE_PREFIXES = "dept_admin.delegable_role_prefixes"
DEFAULT_DELEGABLE_PREFIXES: tuple[str, ...] = ("QV_",)
_PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


# =============================================================================
# 白名单策略（meta.system_config）
# =============================================================================


@dataclass(frozen=True)
class DeptAdminPolicy:
    delegable_role_prefixes: tuple[str, ...]
    updated_at: datetime | None = None

    def is_delegable(self, role_code: str) -> bool:
        if role_code in PROTECTED_ROLES:
            return False
        return any(role_code.startswith(p) for p in self.delegable_role_prefixes)

    def to_dict(self) -> dict:
        return {
            "delegable_role_prefixes": list(self.delegable_role_prefixes),
            "protected_roles": sorted(PROTECTED_ROLES),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def parse_prefixes(raw: str | None) -> tuple[str, ...]:
    """'QV_, CMC_USP_' → ('QV_', 'CMC_USP_')：去空白、去重、保序"""
    if not raw:
        return ()
    out: list[str] = []
    for part in raw.split(","):
        p = part.strip()
        if p and p not in out:
            out.append(p)
    return tuple(out)


def validate_prefixes(prefixes: tuple[str, ...]) -> None:
    """前缀须是合法角色码片段（大写字母开头，大写/数字/下划线）；允许空列表 = 暂停下放"""
    for p in prefixes:
        if len(p) > 32 or not _PREFIX_RE.match(p):
            raise ValidationError(f"角色前缀 {p!r} 不合法：须大写字母开头，仅含大写字母/数字/下划线")
        if any(r.startswith(p) for r in PROTECTED_ROLES):
            raise ValidationError(f"角色前缀 {p!r} 会覆盖受保护角色 SYS_ADMIN / DEPT_ADMIN，不允许")


async def load_dept_admin_policy(db: AsyncSession) -> DeptAdminPolicy:
    row = await db.get(SystemConfig, KEY_DELEGABLE_PREFIXES)
    if row is None:
        return DeptAdminPolicy(delegable_role_prefixes=DEFAULT_DELEGABLE_PREFIXES)
    return DeptAdminPolicy(
        delegable_role_prefixes=parse_prefixes(row.config_value), updated_at=row.updated_at
    )


async def save_dept_admin_policy(
    db: AsyncSession, prefixes: list[str], updated_by: int | None
) -> tuple[DeptAdminPolicy, tuple[str, ...], tuple[str, ...]]:
    """写入并返回 (保存后的策略, 旧前缀, 新前缀)。调用方负责 commit + 审计。"""
    new = parse_prefixes(",".join(prefixes))
    validate_prefixes(new)
    current = await load_dept_admin_policy(db)
    if new != current.delegable_role_prefixes:
        row = await db.get(SystemConfig, KEY_DELEGABLE_PREFIXES)
        if row is None:
            row = SystemConfig(
                config_key=KEY_DELEGABLE_PREFIXES,
                value_type="string",
                description="部门管理员（DEPT_ADMIN）可下放的角色码前缀，逗号分隔",
            )
            db.add(row)
        row.config_value = ",".join(new)
        row.updated_by = updated_by
        row.updated_at = datetime.now(UTC)
        await db.flush()
    return await load_dept_admin_policy(db), current.delegable_role_prefixes, new


# =============================================================================
# 操作范围（FastAPI 依赖）
# =============================================================================


@dataclass(frozen=True)
class UserAdminScope:
    """用户管理端点的操作范围：department=None 表示全公司（SYS_ADMIN / user:manage）"""

    actor: User
    department: str | None = None

    @property
    def dept_scoped(self) -> bool:
        return self.department is not None

    def covers(self, target: User) -> bool:
        return not self.dept_scoped or (target.department or "").strip() == self.department


def user_admin_scope(permission_code: str = "user:manage"):
    """依赖工厂：全权限（SYS_ADMIN 或持 permission_code）→ 全公司；DEPT_ADMIN → 本部门；其余 403。

    permission_code 默认 user:manage（用户端点）；角色列表端点传 role:manage。
    """

    async def checker(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> UserAdminScope:
        codes = {r.role_code for r in user.roles}
        if SYS_ADMIN_ROLE in codes:
            return UserAdminScope(actor=user)
        permissions = await get_user_permissions(user, db)
        if permission_code in permissions:
            return UserAdminScope(actor=user)
        if DEPT_ADMIN_ROLE in codes:
            department = (user.department or "").strip()
            if not department:
                raise PermissionDeniedError("部门管理员账号未填写部门，无法管理用户，请联系系统管理员补齐")
            return UserAdminScope(actor=user, department=department)
        raise PermissionDeniedError(f"缺少权限: {permission_code}")

    return checker
