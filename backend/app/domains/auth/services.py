"""
认证服务
"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    InvalidCredentialsError,
    OldPasswordWrongError,
    TokenExpiredError,
    TokenInvalidError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domains.audit.models import ESignature
from app.domains.audit.schemas import ESignatureItem
from app.domains.auth.models import (
    LoginHistory,
    Permission,
    RefreshToken,
    RolePermission,
    User,
)
from app.domains.auth.schemas import (
    LoginHistoryItem,
    LoginResponse,
    LoginResponseUser,
    RefreshTokenResponse,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 内部辅助 -----------
    async def _get_user_permissions(self, user: User) -> list[str]:
        if not user.roles:
            return []
        # SYS_ADMIN 全权限
        if any(r.role_code == "SYS_ADMIN" for r in user.roles):
            result = await self.db.execute(select(Permission.permission_code))
            return sorted({c for (c,) in result.all()})

        role_ids = [r.role_id for r in user.roles]
        result = await self.db.execute(
            select(Permission.permission_code)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .where(RolePermission.role_id.in_(role_ids))
        )
        return sorted({c for (c,) in result.all()})

    async def _record_login(
        self,
        username: str,
        success: bool,
        ip: str | None,
        ua: str | None,
        user_id: int | None = None,
        failure_reason: str | None = None,
    ):
        history = LoginHistory(
            user_id=user_id,
            username_input=username,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip,
            user_agent=ua,
        )
        self.db.add(history)
        await self.db.flush()

    @staticmethod
    async def _persist_login_failure(
        *,
        user_id: int | None,
        username: str,
        ip: str | None,
        ua: str | None,
        failure_reason: str,
        increment_count_for_user_id: int | None = None,
    ) -> tuple[bool, bool]:
        """旁路 session 持久化登录失败：login_history + failed_login_count++ + 自动锁定。

        必须独立 commit，否则外层 raise InvalidCredentialsError/AccountLockedError 会触发
        get_db 的 rollback，把 failure_count 和 login_history 一起丢失（暴力破解防护失效）。

        返回 (locked_now, _)：locked_now 表示本次是否触发了锁定（让 caller 决定抛哪个异常）。
        """
        locked_now = False
        async with AsyncSessionLocal() as side:
            side.add(
                LoginHistory(
                    user_id=user_id,
                    username_input=username,
                    success=False,
                    failure_reason=failure_reason,
                    ip_address=ip,
                    user_agent=ua,
                )
            )
            if increment_count_for_user_id is not None:
                u = (
                    await side.execute(
                        select(User).where(User.user_id == increment_count_for_user_id)
                    )
                ).scalar_one_or_none()
                if u is not None and u.status == "active":
                    u.failed_login_count = (u.failed_login_count or 0) + 1
                    if u.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
                        u.status = "locked"
                        u.locked_at = datetime.now(UTC)
                        locked_now = True
            await side.commit()
        return locked_now, False

    # ----------- 内部：refresh token 持久化 -----------
    async def _issue_refresh_token(
        self,
        user_id: int,
        ip: str | None,
        ua: str | None,
    ) -> str:
        """生成新 refresh token + 落库；返回原始 JWT 字符串"""
        jti = str(uuid4())
        token = create_refresh_token(subject=user_id, jti=jti)
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        self.db.add(RefreshToken(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            ip_address=ip,
            user_agent=(ua or "")[:512] if ua else None,
        ))
        await self.db.flush()
        return token

    # ----------- 公共方法 -----------
    async def login(
        self, username: str, password: str, ip: str | None, ua: str | None
    ) -> tuple[LoginResponse, str]:
        """返回 (LoginResponse, refresh_token)。refresh 由路由层写 HttpOnly Cookie。"""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.username == username, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()

        if not user:
            # 旁路独立 session 记录失败（主事务后续 raise 会 rollback）
            await self._persist_login_failure(
                user_id=None, username=username, ip=ip, ua=ua,
                failure_reason="user_not_found",
            )
            raise InvalidCredentialsError()

        # 锁定检查：超过 LOGIN_LOCK_DURATION_MINUTES 自动解锁
        if user.status == "locked":
            if user.locked_at is not None:
                unlock_after = user.locked_at + timedelta(
                    minutes=settings.LOGIN_LOCK_DURATION_MINUTES
                )
                if datetime.now(UTC) >= unlock_after:
                    logger.info(
                        f"用户 {username} 锁定时长已过（{settings.LOGIN_LOCK_DURATION_MINUTES} 分钟），自动解锁"
                    )
                    user.status = "active"
                    user.failed_login_count = 0
                    user.locked_at = None
                    # H-01：解锁是既成事实，立即独立提交——否则随后密码错误
                    # raise 后 get_db rollback 会丢失解锁，旁路计数读到 locked
                    # 被 status=='active' 守卫跳过，账户永不再锁（暴力破解防护失效）
                    await self.db.commit()
                    # 继续走密码校验流程
                else:
                    await self._persist_login_failure(
                        user_id=user.user_id, username=username, ip=ip, ua=ua,
                        failure_reason="locked",
                    )
                    raise AccountLockedError()
            else:
                # 没有 locked_at（旧数据或管理员手动锁定）：仍按硬锁处理
                await self._persist_login_failure(
                    user_id=user.user_id, username=username, ip=ip, ua=ua,
                    failure_reason="locked",
                )
                raise AccountLockedError()

        if user.status == "disabled":
            await self._persist_login_failure(
                user_id=user.user_id, username=username, ip=ip, ua=ua,
                failure_reason="disabled",
            )
            raise AccountDisabledError()

        # 密码校验
        if not verify_password(password, user.password_hash):
            locked_now, _ = await self._persist_login_failure(
                user_id=user.user_id, username=username, ip=ip, ua=ua,
                failure_reason="wrong_password",
                increment_count_for_user_id=user.user_id,
            )
            if locked_now:
                logger.warning(f"用户 {username} 因连续失败被锁定")
                raise AccountLockedError()
            raise InvalidCredentialsError()

        # 登录成功
        user.failed_login_count = 0
        user.locked_at = None
        user.last_login_at = datetime.now(UTC)
        await self._record_login(username, True, ip, ua, user.user_id)
        await self.db.flush()

        # 加载权限并构造 token
        permissions = await self._get_user_permissions(user)
        roles = [r.role_code for r in user.roles]

        access_token = create_access_token(
            subject=user.user_id,
            extra_claims={"username": user.username, "full_name": user.full_name, "roles": roles},
        )

        refresh_token = await self._issue_refresh_token(user.user_id, ip, ua)

        return (
            LoginResponse(
                access_token=access_token,
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=LoginResponseUser(
                    user_id=user.user_id,
                    username=user.username,
                    full_name=user.full_name,
                    department=user.department,
                    title=user.title,
                    must_change_password=user.force_password_change,
                    roles=roles,
                    permissions=permissions,
                ),
            ),
            refresh_token,
        )

    async def get_me(self, user: User) -> dict:
        """获取当前用户完整信息"""
        permissions = await self._get_user_permissions(user)
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "full_name_en": user.full_name_en,
            "department": user.department,
            "title": user.title,
            "phone": user.phone,
            "status": user.status,
            "mfa_enabled": user.mfa_enabled,
            "force_password_change": user.force_password_change,
            "last_login_at": user.last_login_at,
            "roles": [
                {"role_id": r.role_id, "role_code": r.role_code, "role_name": r.role_name}
                for r in user.roles
            ],
            "permissions": permissions,
        }

    async def change_password(self, user: User, old_password: str, new_password: str):
        if not verify_password(old_password, user.password_hash):
            raise OldPasswordWrongError()
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.password_expires_at = datetime.now(UTC) + timedelta(days=90)
        # 管理员重置密码后用户首次改密，清空强制改密标记
        user.force_password_change = False
        # 撤销该用户全部活跃 refresh token（同 access token 黑名单语义）
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(UTC),
                revoked_reason="password_changed",
            )
        )
        await self.db.flush()

    # ----------- Refresh / Logout -----------
    async def refresh(
        self,
        refresh_token: str,
        ip: str | None,
        ua: str | None,
    ) -> tuple[RefreshTokenResponse, str]:
        """旋转 refresh token：校验 → 撤销旧 jti → 签发新 access+refresh。

        返回 (RefreshTokenResponse, new_refresh_token)。新 refresh 由路由层
        写回 HttpOnly Cookie 覆盖旧值。

        失败场景：
        - JWT 解码失败 / 不是 refresh 类型 → TokenInvalidError(40103)
        - JWT 已过期 → TokenExpiredError(40102)（decode_token 自抛）
        - 数据库找不到 jti → TokenInvalidError（极少见，可能伪造）
        - jti 已被撤销 → TokenInvalidError + 写审计：可能是 refresh 重放
        - 关联用户已删/disabled → TokenInvalidError
        """
        payload = decode_token(refresh_token)  # 过期/无效会抛
        if payload.get("type") != "refresh":
            raise TokenInvalidError("token_type 不是 refresh")

        jti = payload.get("jti")
        if not jti:
            raise TokenInvalidError("refresh token 缺少 jti")

        # 查 DB：jti 必须存在 + 未撤销 + 未过期（DB 表的 expires_at 与 JWT exp 双校验）
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        rt = result.scalar_one_or_none()
        if rt is None:
            raise TokenInvalidError("refresh token 不存在")
        now = datetime.now(UTC)
        if rt.revoked_at is not None:
            # 已撤销但仍被用——可能是 refresh 重放攻击；记录 warn
            logger.warning(
                f"refresh token 重放尝试：jti={jti} user_id={rt.user_id} "
                f"revoked_reason={rt.revoked_reason}"
            )
            raise TokenInvalidError("refresh token 已被撤销")
        if rt.expires_at <= now:
            raise TokenExpiredError("refresh token 已过期")

        # 拉用户 + roles
        user_result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.user_id == rt.user_id, User.deleted_at.is_(None))
        )
        user = user_result.scalar_one_or_none()
        if user is None or user.status != "active":
            raise TokenInvalidError("用户不存在或已禁用")

        # 旋转：撤销旧 jti
        new_jti = str(uuid4())
        rt.revoked_at = now
        rt.revoked_reason = "rotated"
        rt.rotated_to_jti = new_jti

        # 签发新 refresh
        new_refresh = create_refresh_token(subject=user.user_id, jti=new_jti)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        self.db.add(RefreshToken(
            jti=new_jti,
            user_id=user.user_id,
            expires_at=new_expires_at,
            ip_address=ip,
            user_agent=(ua or "")[:512] if ua else None,
        ))

        # 签发新 access
        roles = [r.role_code for r in user.roles]
        new_access = create_access_token(
            subject=user.user_id,
            extra_claims={"username": user.username, "full_name": user.full_name, "roles": roles},
        )

        # 强一致：refresh 端点必须 commit 后才返回（避免 yield 依赖 commit 时机坑）
        await self.db.flush()
        await self.db.commit()

        return (
            RefreshTokenResponse(
                access_token=new_access,
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            ),
            new_refresh,
        )

    async def logout(self, refresh_token: str | None) -> None:
        """登出：撤销 cookie 中携带的 refresh token（如果有效则 revoke；无则静默）"""
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token)
        except (TokenInvalidError, TokenExpiredError):
            return
        if payload.get("type") != "refresh":
            return
        jti = payload.get("jti")
        if not jti:
            return
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.jti == jti,
                RefreshToken.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.now(UTC),
                revoked_reason="logout",
            )
        )
        await self.db.flush()
        await self.db.commit()

    # ----------- Phase 5.A / M5.4：个人中心（只看自己）-----------

    async def get_my_login_history(
        self,
        user: User,
        page: int,
        page_size: int,
    ) -> tuple[list[LoginHistoryItem], int]:
        """当前用户的登录历史（成功 + 失败均显示，按 login_at 倒序）。

        合规：审计层面用户应可见自己的登录历史以便发现被盗号迹象（NIST 800-63B §5.2.6）。
        过滤强制 user_id == 当前用户，不允许传 username 看别人的（admin 想看别人走
        /audit-logs 走 audit:read 权限路径）。
        """
        base_stmt = select(LoginHistory).where(LoginHistory.user_id == user.user_id)
        count_stmt = (
            select(func.count(LoginHistory.login_id))
            .where(LoginHistory.user_id == user.user_id)
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        result = await self.db.execute(
            base_stmt
            .order_by(LoginHistory.login_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(result.scalars())
        items = [
            LoginHistoryItem(
                login_id=r.login_id,
                username_input=r.username_input,
                success=r.success,
                failure_reason=r.failure_reason,
                ip_address=str(r.ip_address) if r.ip_address else None,
                user_agent=r.user_agent,
                login_at=r.login_at,
            )
            for r in rows
        ]
        return items, total

    async def get_my_signatures(
        self,
        user: User,
        page: int,
        page_size: int,
    ) -> tuple[list[ESignatureItem], int]:
        """当前用户的电子签名历史（21 CFR Part 11 §11.10(e) 用户自查权）"""
        base_stmt = select(ESignature).where(ESignature.user_id == user.user_id)
        count_stmt = (
            select(func.count(ESignature.signature_id))
            .where(ESignature.user_id == user.user_id)
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        result = await self.db.execute(
            base_stmt
            .order_by(ESignature.signature_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(result.scalars())
        items = [ESignatureItem.model_validate(r) for r in rows]
        return items, total
