"""
管理员侧：用户/角色/权限管理服务（Phase 5.A / M5.1）

权限：user:manage（用户管理）；role:manage（角色管理，M5.2 启用）。
合规：
- 不做物理删除（用户拍板：lock = 软停用），保留全部审计链
- 管理员不能 lock/disable/reset-password 自己（GxP 误操作防护）
- reset-password 返回 16 位临时密码且 force_password_change=TRUE，用户首次登录强制改密
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
    EmailExistsError,
    OperationNotAllowedError,
    UserNotFoundError,
    UsernameExistsError,
    ValidationError,
)
from app.core.security import hash_password
from app.domains.auth.models import (
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserRole,
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
    """生成 16 位临时密码：保证至少 1 大写、1 小写、1 数字、1 符号（满足 12 位 + 复杂度策略）"""
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


async def _load_user(db: AsyncSession, username: str, *, with_roles: bool = True) -> User:
    stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
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
    ) -> tuple[list[UserListItem], int]:
        stmt = select(User).where(User.deleted_at.is_(None)).options(selectinload(User.roles))
        count_stmt = select(func.count(User.user_id)).where(User.deleted_at.is_(None))

        if q:
            pattern = f"%{q}%"
            cond = or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
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

    async def get_user(self, username: str) -> UserDetail:
        user = await _load_user(self.db, username)
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
            password_expires_at=datetime.now(UTC) + timedelta(days=90),
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

        logger.info(
            f"管理员 {actor.username} 创建用户 {user.username}（角色={payload.role_codes}）"
        )
        return await self.get_user(user.username)

    async def update_user(
        self, username: str, payload: UserUpdate, actor: User
    ) -> UserDetail:
        user = await _load_user(self.db, username)

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
        return await self.get_user(user.username)

    async def assign_roles(
        self, username: str, role_codes: list[str], actor: User
    ) -> UserDetail:
        user = await _load_user(self.db, username)

        # SYS_ADMIN 防呆：管理员不能取消自己最后一个 SYS_ADMIN（避免锁死）
        if user.user_id == actor.user_id and "SYS_ADMIN" not in role_codes:
            current = {r.role_code for r in user.roles}
            if "SYS_ADMIN" in current:
                # 检查是否是最后一个 SYS_ADMIN
                count_result = await self.db.execute(
                    select(func.count(UserRole.user_id.distinct()))
                    .join(Role, Role.role_id == UserRole.role_id)
                    .join(User, User.user_id == UserRole.user_id)
                    .where(
                        Role.role_code == "SYS_ADMIN",
                        User.deleted_at.is_(None),
                        User.status == "active",
                    )
                )
                count = count_result.scalar_one()
                if count <= 1:
                    raise OperationNotAllowedError(
                        "不能取消最后一个 SYS_ADMIN 的角色"
                    )

        role_ids = await self._resolve_role_ids(role_codes)

        # 全替换：先清，再加
        await self.db.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user.user_id)
        )
        for rid in role_ids:
            self.db.add(UserRole(user_id=user.user_id, role_id=rid, granted_by=actor.user_id))
        user.updated_by = actor.user_id
        await self.db.flush()
        await self.db.refresh(user, ["roles"])
        return await self.get_user(user.username)

    # ----------- 动作端点 -----------
    async def lock_user(self, username: str, actor: User) -> UserDetail:
        if username == actor.username:
            raise CannotOperateSelfError("不能锁定自己")
        user = await _load_user(self.db, username, with_roles=False)
        if user.status == "locked":
            raise OperationNotAllowedError("用户已处于锁定状态")
        user.status = "locked"
        user.locked_at = datetime.now(UTC)
        user.updated_by = actor.user_id
        # 同步撤销所有活跃 refresh token（让其无法续期）
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoked_reason="admin")
        )
        await self.db.flush()
        logger.info(f"管理员 {actor.username} 锁定用户 {username}")
        return await self.get_user(username)

    async def unlock_user(self, username: str, actor: User) -> UserDetail:
        user = await _load_user(self.db, username, with_roles=False)
        if user.status != "locked":
            raise OperationNotAllowedError("用户当前不是锁定状态")
        user.status = "active"
        user.locked_at = None
        user.failed_login_count = 0
        user.updated_by = actor.user_id
        await self.db.flush()
        logger.info(f"管理员 {actor.username} 解锁用户 {username}")
        return await self.get_user(username)

    async def reset_password(
        self, username: str, actor: User
    ) -> ResetPasswordResponse:
        if username == actor.username:
            raise CannotOperateSelfError("不能重置自己的密码，请走 /auth/change-password")
        user = await _load_user(self.db, username, with_roles=False)

        temp_pw = _generate_temp_password(16)
        user.password_hash = hash_password(temp_pw)
        user.password_changed_at = datetime.now(UTC)
        # 临时密码立即过期视角：不设 password_expires_at 短窗口，而是用 force_password_change
        # 强制走改密流程；用户改密后正常进入 90 天有效期
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
        logger.warning(
            f"管理员 {actor.username} 重置了用户 {username} 的密码（force_password_change=True）"
        )
        return ResetPasswordResponse(
            username=username,
            temp_password=temp_pw,
            force_password_change=True,
        )
