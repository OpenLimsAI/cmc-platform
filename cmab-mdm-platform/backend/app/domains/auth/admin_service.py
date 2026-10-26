"""
管理员侧：用户/角色/权限管理服务（Phase 5.A / M5.1）

权限：user:manage（用户管理）；role:manage（角色管理，M5.2 启用）。
合规：
- 不做物理删除（用户拍板：lock = 软停用），保留全部审计链
- 管理员不能 lock/disable/reset-password 自己（GxP 误操作防护）
- reset-password 返回 16 位临时密码且 force_password_change=TRUE，用户首次登录强制改密

部门管理员（2026-09-10；见 dept_admin.py）：
- list/get/assign_roles/lock/unlock 接收 UserAdminScope；scope 限定部门时只能碰同部门用户
  （跨部门 → DataAccessDeniedError 40303），挂/摘角色只能动白名单角色（其余 → 40301），
  不能锁定持有 SYS_ADMIN / DEPT_ADMIN 的账号
- 用户管理的成功变更**无论谁做**都写一条应用层 audit_log + 字段明细
  （auth 表没有触发器审计；谁、对谁、加了/去了什么角色、何时 + extra 明细）
"""
from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    CannotOperateSelfError,
    DataAccessDeniedError,
    EmailExistsError,
    OperationNotAllowedError,
    PermissionDeniedError,
    UsernameExistsError,
    UserNotFoundError,
    ValidationError,
)
from app.core.security import hash_password
from app.domains.auth.admin_guard import ensure_admin_remains, lock_admin_management
from app.domains.auth.audit_service import record_auth_change, user_state
from app.domains.auth.dept_admin import (
    PROTECTED_ROLES,
    UserAdminScope,
    load_dept_admin_policy,
)
from app.domains.auth.models import (
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.domains.auth.password_policy import (
    ensure_current_password_recorded,
    load_password_policy,
    record_password,
    validate_new_password,
)
from app.domains.auth.schemas import (
    ResetPasswordResponse,
    RoleBrief,
    UserCreate,
    UserDetail,
    UserListItem,
    UserUpdate,
)

# 16 位临时密码字符集（去掉易混淆字符 O/0/I/l）
_TEMP_PW_ALPHABET = string.ascii_letters.replace("O", "").replace("I", "").replace("l", "")
_TEMP_PW_DIGITS = "23456789"
_TEMP_PW_SYMBOLS = "!@#$%&*+-_"


def _generate_temp_password(length: int = 16) -> str:
    """生成指定长度的临时密码，保证大写、小写、数字、符号各至少一个。"""
    rng = secrets.SystemRandom()
    chars = (
        [rng.choice(string.ascii_uppercase)]
        + [rng.choice(string.ascii_lowercase)]
        + [rng.choice(_TEMP_PW_DIGITS)]
        + [rng.choice(_TEMP_PW_SYMBOLS)]
        + [rng.choice(_TEMP_PW_ALPHABET + _TEMP_PW_DIGITS) for _ in range(length - 4)]
    )
    rng.shuffle(chars)
    return "".join(chars)


def _to_role_brief(role: Role) -> RoleBrief:
    return RoleBrief(role_id=role.role_id, role_code=role.role_code, role_name=role.role_name)


async def _load_user(
    db: AsyncSession, username: str, *, with_roles: bool = True, for_update: bool = False,
) -> User:
    stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
    if for_update:
        # 认证依赖可能已加载该对象；锁定后重新读取，避免前值仍来自旧身份快照。
        stmt = stmt.with_for_update(of=User).execution_options(populate_existing=True)
    if with_roles:
        stmt = stmt.options(selectinload(User.roles))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundError(f"用户 {username} 不存在")
    return user


class UserAdminService:
    """管理员侧用户管理"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 内部 -----------
    @staticmethod
    def _ensure_in_scope(target: User, scope: UserAdminScope | None) -> None:
        """部门管理员只能碰同部门用户；scope=None 表示内部调用/全权限，不限制"""
        if scope is not None and not scope.covers(target):
            raise DataAccessDeniedError(
                f"只能管理本部门（{scope.department}）的用户，{target.username} 不在本部门"
            )

    @staticmethod
    def _ensure_not_protected(target: User, scope: UserAdminScope | None, verb: str) -> None:
        """部门管理员不能锁定/解锁持有 SYS_ADMIN / DEPT_ADMIN 的账号"""
        if scope is None or not scope.dept_scoped:
            return
        held = sorted({r.role_code for r in target.roles} & PROTECTED_ROLES)
        if held:
            raise PermissionDeniedError(
                f"部门管理员不能{verb}持有 {', '.join(held)} 角色的账号"
            )

    async def _audit(
        self,
        actor: User,
        scope: UserAdminScope | None,
        *,
        action: str,
        target: User,
        summary: str,
        extra: dict | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        """应用层审计：auth.user / auth.user_role 没有触发器审计，管理动作在这里落 audit_log。
        与主事务同 session，业务失败则一起回滚（成功才有审计，不产生半条记录）。"""
        payload = {
            "actor_scope": "department" if (scope and scope.dept_scoped) else "all",
            "actor_department": scope.department if scope and scope.dept_scoped else None,
            "target_department": target.department,
            **(extra or {}),
        }
        await record_auth_change(
            self.db, actor, target=target, action=action, summary=summary,
            before=before, after=after, extra=payload,
        )

    async def _resolve_role_ids(self, role_codes: list[str]) -> list[int]:
        if not role_codes:
            return []
        result = await self.db.execute(
            select(Role).where(Role.role_code.in_(role_codes), Role.deleted_at.is_(None))
        )
        roles = result.scalars().all()
        found = {r.role_code for r in roles}
        missing = [c for c in role_codes if c not in found]
        if missing:
            raise ValidationError(f"角色不存在: {', '.join(missing)}")
        return [r.role_id for r in roles]

    async def _user_permissions(self, user: User) -> list[str]:
        if any(r.role_code == "SYS_ADMIN" for r in user.roles):
            result = await self.db.execute(select(Permission.permission_code))
            return sorted({c for (c,) in result.all()})
        if not user.roles:
            return []
        role_ids = [r.role_id for r in user.roles]
        result = await self.db.execute(
            select(Permission.permission_code)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .where(RolePermission.role_id.in_(role_ids))
        )
        return sorted({c for (c,) in result.all()})

    # ----------- 列表 / 详情 -----------
    async def list_users(
        self,
        q: str | None,
        role_code: str | None,
        status: str | None,
        page: int,
        page_size: int,
        scope: UserAdminScope | None = None,
        department: str | None = None,
    ) -> tuple[list[UserListItem], int]:
        stmt = select(User).where(User.deleted_at.is_(None)).options(selectinload(User.roles))
        count_stmt = select(func.count(User.user_id)).where(User.deleted_at.is_(None))

        if scope is not None and scope.dept_scoped:
            dept_cond = func.trim(User.department) == scope.department
            stmt = stmt.where(dept_cond)
            count_stmt = count_stmt.where(dept_cond)
        if q:
            pattern = f"%{q}%"
            cond = or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if department:
            # 包含匹配（不分大小写）：下拉里选 TT5 精确命中，手输 TT 则 TT1/TT5/TT7 全出
            dept_pattern = f"%{department.strip()}%"
            stmt = stmt.where(User.department.ilike(dept_pattern))
            count_stmt = count_stmt.where(User.department.ilike(dept_pattern))
        if status:
            stmt = stmt.where(User.status == status)
            count_stmt = count_stmt.where(User.status == status)
        if role_code:
            role_subq = (
                select(UserRole.user_id)
                .join(Role, Role.role_id == UserRole.role_id)
                .where(Role.role_code == role_code)
            )
            stmt = stmt.where(User.user_id.in_(role_subq))
            count_stmt = count_stmt.where(User.user_id.in_(role_subq))

        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(User.username).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        users = result.scalars().unique().all()

        items = [
            UserListItem(
                user_id=u.user_id,
                username=u.username,
                email=u.email,
                full_name=u.full_name,
                department=u.department,
                title=u.title,
                status=u.status,
                last_login_at=u.last_login_at,
                created_at=u.created_at,
                roles=[_to_role_brief(r) for r in u.roles],
            )
            for u in users
        ]
        return items, total

    async def list_departments(self, scope: UserAdminScope | None = None) -> list[str]:
        """用户表里实际出现过的部门清单（去空白、去重、排序），供筛选下拉使用。

        部门是自由文本（与 auth.user.department 同口径），没有独立字典表，所以从现有数据里取。
        部门管理员只会看到自己那一个部门。"""
        stmt = select(func.trim(User.department)).where(
            User.deleted_at.is_(None),
            User.department.isnot(None),
            func.trim(User.department) != "",
        )
        if scope is not None and scope.dept_scoped:
            stmt = stmt.where(func.trim(User.department) == scope.department)
        result = await self.db.execute(stmt.distinct().order_by(func.trim(User.department)))
        return [d for (d,) in result.all()]

    async def get_user(self, username: str, scope: UserAdminScope | None = None) -> UserDetail:
        user = await _load_user(self.db, username)
        self._ensure_in_scope(user, scope)
        permissions = await self._user_permissions(user)
        return UserDetail(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            full_name_en=user.full_name_en,
            department=user.department,
            title=user.title,
            phone=user.phone,
            status=user.status,
            failed_login_count=user.failed_login_count,
            locked_at=user.locked_at,
            last_login_at=user.last_login_at,
            password_changed_at=user.password_changed_at,
            password_expires_at=user.password_expires_at,
            force_password_change=user.force_password_change,
            mfa_enabled=user.mfa_enabled,
            created_at=user.created_at,
            created_by=user.created_by,
            updated_at=user.updated_at,
            updated_by=user.updated_by,
            roles=[_to_role_brief(r) for r in user.roles],
            permissions=permissions,
        )

    # ----------- 创建 / 更新 -----------
    async def create_user(self, payload: UserCreate, actor: User) -> UserDetail:
        password_policy = await validate_new_password(self.db, payload.password)
        # 预检：username / email 唯一（pre-check 避免 IntegrityError）
        exist = await self.db.execute(
            select(User).where(User.username == payload.username, User.deleted_at.is_(None))
        )
        if exist.scalar_one_or_none():
            raise UsernameExistsError(f"用户名 {payload.username} 已存在")

        exist = await self.db.execute(
            select(User).where(User.email == payload.email, User.deleted_at.is_(None))
        )
        if exist.scalar_one_or_none():
            raise EmailExistsError(f"邮箱 {payload.email} 已被使用")

        role_ids = await self._resolve_role_ids(payload.role_codes)

        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            full_name_en=payload.full_name_en,
            department=payload.department,
            title=payload.title,
            phone=payload.phone,
            status="active",
            password_changed_at=datetime.now(UTC),
            password_expires_at=datetime.now(UTC) + timedelta(days=password_policy.expire_days),
            force_password_change=False,
            created_by=actor.user_id,
            updated_by=actor.user_id,
        )
        self.db.add(user)
        await self.db.flush()

        for rid in role_ids:
            self.db.add(UserRole(user_id=user.user_id, role_id=rid, granted_by=actor.user_id))
        await self.db.flush()
        await self.db.refresh(user, ["roles"])

        await record_password(self.db, user)
        await self._audit(
            actor, None, action="CREATE", target=user,
            summary=f"创建用户 {user.username}",
            after=user_state(user, roles=[r.role_code for r in user.roles]),
        )
        await self.db.commit()
        logger.info(
            f"管理员 {actor.username} 创建用户 {user.username}（角色={payload.role_codes}）"
        )
        return await self.get_user(user.username)

    async def update_user(
        self, username: str, payload: UserUpdate, actor: User
    ) -> UserDetail:
        user = await _load_user(self.db, username, for_update=True)
        before = user_state(user)

        if payload.email is not None and payload.email != user.email:
            exist = await self.db.execute(
                select(User).where(
                    User.email == payload.email,
                    User.user_id != user.user_id,
                    User.deleted_at.is_(None),
                )
            )
            if exist.scalar_one_or_none():
                raise EmailExistsError(f"邮箱 {payload.email} 已被使用")
            user.email = payload.email
        for field in ("full_name", "full_name_en", "department", "title", "phone"):
            val = getattr(payload, field)
            if val is not None:
                setattr(user, field, val)
        user.updated_by = actor.user_id
        await self.db.flush()
        after = user_state(user)
        if before != after:
            await self._audit(
                actor, None, action="UPDATE", target=user,
                summary=f"修改用户 {username} 资料", before=before, after=after,
            )
        await self.db.commit()
        return await self.get_user(user.username)

    async def assign_roles(
        self,
        username: str,
        role_codes: list[str],
        actor: User,
        scope: UserAdminScope | None = None,
    ) -> UserDetail:
        await lock_admin_management(self.db)
        user = await _load_user(self.db, username, for_update=True)
        self._ensure_in_scope(user, scope)
        current = {r.role_code for r in user.roles}

        if scope is not None and scope.dept_scoped:
            # 不能给自己挂角色：否则一旦白名单里混进带管理权限的角色即可自我提权
            if user.user_id == scope.actor.user_id:
                raise PermissionDeniedError("部门管理员不能修改自己的角色，请联系系统管理员")
            self._ensure_not_protected(user, scope, "调整角色")
            # 部门管理员：提交的每个角色都必须在白名单内；目标已持有的非白名单角色原样保留
            # （前端下拉只出白名单角色，提交的就是「白名单部分」的完整集合）
            policy = await load_dept_admin_policy(self.db)
            denied = sorted({c for c in role_codes if not policy.is_delegable(c)})
            if denied:
                raise PermissionDeniedError(
                    f"部门管理员不能下放角色: {', '.join(denied)}"
                    f"（当前允许前缀: {', '.join(policy.delegable_role_prefixes) or '无'}）"
                )
            keep = [c for c in sorted(current) if not policy.is_delegable(c)]
            role_codes = keep + [c for c in role_codes if c not in keep]

        if "SYS_ADMIN" not in role_codes:
            await ensure_admin_remains(self.db, user, removing_role=True)

        role_ids = await self._resolve_role_ids(role_codes)

        # 全替换：先清，再加
        await self.db.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user.user_id)
        )
        for rid in role_ids:
            self.db.add(UserRole(user_id=user.user_id, role_id=rid, granted_by=actor.user_id))
        user.updated_by = actor.user_id

        final = set(role_codes)
        added, removed = sorted(final - current), sorted(current - final)
        parts = []
        if added:
            parts.append("+" + ", +".join(added))
        if removed:
            parts.append("-" + ", -".join(removed))
        await self._audit(
            actor, scope,
            action="PERMISSION_CHANGE",
            target=user,
            summary=f"调整用户 {user.username} 角色：{'; '.join(parts) or '无变化'}",
            before={"roles": sorted(current)}, after={"roles": sorted(final)},
            extra={
                "roles_before": sorted(current),
                "roles_after": sorted(final),
                "added": added,
                "removed": removed,
            },
        )
        await self.db.flush()
        await self.db.refresh(user, ["roles"])
        await self.db.commit()
        logger.info(f"{actor.username} 调整用户 {username} 角色：+{added} -{removed}")
        return await self.get_user(user.username)

    # ----------- 动作端点 -----------
    async def lock_user(
        self, username: str, actor: User, scope: UserAdminScope | None = None
    ) -> UserDetail:
        if username == actor.username:
            raise CannotOperateSelfError("不能锁定自己")
        await lock_admin_management(self.db)
        user = await _load_user(self.db, username, for_update=True)
        self._ensure_in_scope(user, scope)
        self._ensure_not_protected(user, scope, "锁定")
        if user.status == "locked":
            raise OperationNotAllowedError("用户已处于锁定状态")
        await ensure_admin_remains(self.db, user)
        before = user_state(user)
        user.status = "locked"
        user.locked_at = datetime.now(UTC)
        user.updated_by = actor.user_id
        # 同步撤销所有活跃 refresh token（让其无法续期）
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoked_reason="admin")
        )
        await self._audit(
            actor, scope,
            action="UPDATE",
            target=user,
            summary=f"锁定用户 {user.username}（status: {before['status']} → locked，活跃会话已撤销）",
            before=before, after=user_state(user),
            extra={"field": "status", "old": before["status"], "new": "locked"},
        )
        await self.db.flush()
        await self.db.commit()
        logger.info(f"管理员 {actor.username} 锁定用户 {username}")
        return await self.get_user(username)

    async def unlock_user(
        self, username: str, actor: User, scope: UserAdminScope | None = None
    ) -> UserDetail:
        user = await _load_user(self.db, username, for_update=True)
        self._ensure_in_scope(user, scope)
        self._ensure_not_protected(user, scope, "解锁")
        if user.status != "locked":
            raise OperationNotAllowedError("用户当前不是锁定状态")
        before = user_state(user)
        user.status = "active"
        user.locked_at = None
        user.failed_login_count = 0
        user.updated_by = actor.user_id
        await self._audit(
            actor, scope,
            action="UPDATE",
            target=user,
            summary=f"解锁用户 {user.username}（status: locked → active，失败计数清零）",
            before=before, after=user_state(user),
            extra={"field": "status", "old": "locked", "new": "active"},
        )
        await self.db.flush()
        await self.db.commit()
        logger.info(f"管理员 {actor.username} 解锁用户 {username}")
        return await self.get_user(username)

    async def reset_password(
        self, username: str, actor: User
    ) -> ResetPasswordResponse:
        if username == actor.username:
            raise CannotOperateSelfError("不能重置自己的密码，请走 /auth/change-password")
        user = await _load_user(self.db, username, with_roles=False, for_update=True)
        before = user_state(user)

        password_policy = await load_password_policy(self.db)
        temp_pw = _generate_temp_password(max(16, password_policy.min_length))
        await validate_new_password(self.db, temp_pw, user)
        await ensure_current_password_recorded(self.db, user)
        user.password_hash = hash_password(temp_pw)
        user.password_changed_at = datetime.now(UTC)
        # 临时密码保留发放窗口；有效期内也只允许进入改密闭环。
        user.password_expires_at = datetime.now(UTC) + timedelta(days=settings.PASSWORD_TEMP_DAYS)
        user.force_password_change = True
        user.failed_login_count = 0
        # 若用户处于 locked 状态，重置时一并解锁
        if user.status == "locked":
            user.status = "active"
            user.locked_at = None
        user.updated_by = actor.user_id
        # 撤销该用户所有活跃 refresh token（旧会话无法续期）
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoked_reason="admin")
        )
        await self.db.flush()
        await record_password(self.db, user)
        await self._audit(
            actor, None, action="UPDATE", target=user,
            summary=f"管理员重置用户 {username} 密码，须首次改密，活跃会话已撤销",
            before=before, after=user_state(user), extra={"operation": "reset_password"},
        )
        await self.db.commit()
        logger.warning(
            f"管理员 {actor.username} 重置了用户 {username} 的密码（force_password_change=True）"
        )
        return ResetPasswordResponse(
            username=username,
            temp_password=temp_pw,
            force_password_change=True,
        )
