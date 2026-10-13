"""
认证服务
"""
from datetime import UTC, datetime, timedelta
from math import ceil
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
    TemporaryPasswordExpiredError,
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
from app.domains.audit.models import AuditLog, ESignature
from app.domains.audit.schemas import ESignatureItem
from app.domains.auth.audit_service import record_auth_change, user_state
from app.domains.auth.models import (
    LoginHistory,
    Permission,
    RefreshToken,
    RolePermission,
    User,
)
from app.domains.auth.password_policy import (
    access_deadline,
    ensure_current_password_recorded,
    record_password,
    requires_password_change,
    temporary_password_expired,
    validate_new_password,
)
from app.domains.auth.schemas import (
    LoginHistoryItem,
    LoginResponse,
    LoginResponseUser,
    RefreshTokenResponse,
)
from app.domains.auth.session_policy import SessionPolicy, load_session_policy
from app.shared.audit_context import audit_request_id


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
            # 旁路写一条 LOGIN_FAILED 审计：登录失败属安全事件，须在全局审计日志可见，
            # 且与 login_history 一样独立 commit，避免外层 raise 触发的 rollback 丢失。
            side.add(
                AuditLog(
                    user_id=user_id,
                    username=username,
                    action="LOGIN_FAILED",
                    ip_address=ip,
                    user_agent=ua,
                    request_id=audit_request_id.get(),
                    reason=f"登录失败：{failure_reason}",
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
    @staticmethod
    def _refresh_deadline(
        policy: SessionPolicy, roles: list[str], session_started_at: datetime, now: datetime
    ) -> datetime:
        """refresh 到期 = min(现在 + 空闲窗口, 会话开始 + 硬上限)。滑动会话的核心：
        每次换证只往后推一个空闲窗口；没人换证就自然过期 → 空闲登出。"""
        idle_deadline = now + timedelta(minutes=policy.idle_minutes_for(roles))
        absolute_deadline = session_started_at + timedelta(hours=policy.absolute_max_hours)
        return min(idle_deadline, absolute_deadline)

    async def _issue_refresh_token(
        self,
        user_id: int,
        ip: str | None,
        ua: str | None,
        *,
        policy: SessionPolicy,
        roles: list[str],
        session_started_at: datetime,
    ) -> str:
        """生成新 refresh token + 落库；返回原始 JWT 字符串"""
        jti = str(uuid4())
        now = datetime.now(UTC)
        expires_at = self._refresh_deadline(policy, roles, session_started_at, now)
        token = create_refresh_token(subject=user_id, jti=jti, expires_at=expires_at)
        self.db.add(RefreshToken(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            session_started_at=session_started_at,
            ip_address=ip,
            user_agent=(ua or "")[:512] if ua else None,
        ))
        await self.db.flush()
        return token

    # ----------- 公共方法 -----------
    async def login(
        self, username: str, password: str, ip: str | None, ua: str | None
    ) -> tuple[LoginResponse, str, SessionPolicy]:
        """返回 (LoginResponse, refresh_token, 生效的会话策略)。refresh 由路由层写 HttpOnly Cookie。"""
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

        if temporary_password_expired(user):
            await self._persist_login_failure(
                user_id=user.user_id, username=username, ip=ip, ua=ua,
                failure_reason="temporary_password_expired",
            )
            raise TemporaryPasswordExpiredError()

        # 登录成功；普通过期密码只能进入改密闭环，不延长其原到期日期。
        user.failed_login_count = 0
        user.locked_at = None
        user.last_login_at = datetime.now(UTC)
        await self._record_login(username, True, ip, ua, user.user_id)
        # LOGIN 成功审计与 refresh 台账同事务；响应前提交，避免立即换证查不到记录。
        self.db.add(
            AuditLog(
                user_id=user.user_id,
                username=user.username,
                action="LOGIN",
                ip_address=ip,
                user_agent=ua,
                request_id=audit_request_id.get(),
                reason="登录成功",
            )
        )
        await self.db.flush()

        # 加载权限并构造 token
        permissions = await self._get_user_permissions(user)
        roles = [r.role_code for r in user.roles]
        policy = await load_session_policy(self.db)

        must_change = requires_password_change(user)
        deadline = access_deadline(user, policy.access_token_minutes)
        access_token = create_access_token(
            subject=user.user_id,
            extra_claims={
                "username": user.username,
                "full_name": user.full_name,
                "roles": roles,
                # 2026-09-10：部门随令牌下发，供门户/LabOps 按部门前缀（TT/CMC）判定可见性；下游按名取值，多字段无影响
                "department": user.department,
                # 2026-09-11：临时密码状态随令牌下发。MDM 自己早就拦住了（shared/permissions.py），
                # 但下游系统本地验签、不回调 MDM，不下发就不知道 → 拿临时密码的人照样能在
                # LabOps / 批号 / 看板里干活。下游据此一律 403 并提示先去 MDM 改密码。
                "must_change_password": must_change,
                "password_changed_at": user.password_changed_at.astimezone(UTC).isoformat()
                if user.password_changed_at else None,
            },
            expires_minutes=policy.access_token_minutes,
            expires_at=deadline,
        )

        refresh_token = await self._issue_refresh_token(
            user.user_id, ip, ua,
            policy=policy, roles=roles, session_started_at=datetime.now(UTC),
        )
        await self.db.commit()

        return (
            LoginResponse(
                access_token=access_token,
                expires_in=max(1, ceil((deadline - datetime.now(UTC)).total_seconds())),
                user=LoginResponseUser(
                    user_id=user.user_id,
                    username=user.username,
                    full_name=user.full_name,
                    department=user.department,
                    title=user.title,
                    must_change_password=must_change,
                    roles=roles,
                    permissions=permissions,
                ),
            ),
            refresh_token,
            policy,
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
            "force_password_change": requires_password_change(user),
            "last_login_at": user.last_login_at,
            "roles": [
                {"role_id": r.role_id, "role_code": r.role_code, "role_name": r.role_name}
                for r in user.roles
            ],
            "permissions": permissions,
        }

    async def change_password(self, user: User, old_password: str, new_password: str):
        result = await self.db.execute(
            select(User).where(User.user_id == user.user_id)
            .options(selectinload(User.roles))
            .with_for_update(of=User).execution_options(populate_existing=True)
        )
        user = result.scalar_one()
        if not verify_password(old_password, user.password_hash):
            raise OldPasswordWrongError()
        if temporary_password_expired(user):
            raise TemporaryPasswordExpiredError()
        policy = await validate_new_password(self.db, new_password, user)
        before = user_state(user)
        await ensure_current_password_recorded(self.db, user)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.password_expires_at = datetime.now(UTC) + timedelta(days=policy.expire_days)
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
        await record_password(self.db, user)
        await record_auth_change(
            self.db, user, target=user, action="UPDATE",
            summary=f"用户 {user.username} 自行修改密码，活跃会话已撤销",
            before=before, after=user_state(user), extra={"operation": "change_password"},
        )
        await self.db.commit()

    # ----------- Refresh / Logout -----------
    async def refresh(
        self,
        refresh_token: str,
        ip: str | None,
        ua: str | None,
    ) -> tuple[RefreshTokenResponse, str, SessionPolicy]:
        """旋转 refresh token：校验 → 撤销旧 jti → 签发新 access+refresh。

        返回 (RefreshTokenResponse, new_refresh_token, 生效的会话策略)。新 refresh 由路由层
        写回 HttpOnly Cookie 覆盖旧值。

        失败场景：
        - JWT 签名无效 / 不是 refresh 类型 → TokenInvalidError(40103)
        - 空闲超时（DB expires_at 已过）→ TokenExpiredError(40102)「空闲超时」
        - 达到硬上限（session_started_at + absolute_max_hours 已过）→ TokenExpiredError「登录时长上限」
        - 数据库找不到 jti → TokenInvalidError（极少见，可能伪造）
        - jti 已被撤销 → TokenInvalidError + 写审计：可能是 refresh 重放
        - 关联用户已删/disabled → TokenInvalidError

        到期判断以 DB 为准（JWT exp 与 DB expires_at 同值，但只有 DB 能区分两种到期原因），
        故解码时跳过 exp 校验，签名仍校验。
        """
        payload = decode_token(refresh_token, verify_exp=False)  # 签名无效会抛
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
        policy = await load_session_policy(self.db)
        session_started_at = rt.session_started_at or rt.issued_at
        absolute_deadline = session_started_at + timedelta(hours=policy.absolute_max_hours)
        if absolute_deadline <= now:
            raise TokenExpiredError(
                f"本次登录已满 {policy.absolute_max_hours} 小时，请重新登录"
            )
        if rt.expires_at <= now:
            raise TokenExpiredError("长时间未操作，已自动退出，请重新登录")

        # 拉用户 + roles
        user_result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.user_id == rt.user_id, User.deleted_at.is_(None))
        )
        user = user_result.scalar_one_or_none()
        if user is None or user.status != "active":
            raise TokenInvalidError("用户不存在或已禁用")
        if temporary_password_expired(user, now):
            raise TemporaryPasswordExpiredError()

        # 旋转：撤销旧 jti
        new_jti = str(uuid4())
        rt.revoked_at = now
        rt.revoked_reason = "rotated"
        rt.rotated_to_jti = new_jti

        # 签发新 refresh：只续到 min(现在 + 空闲窗口, 会话开始 + 硬上限)
        roles = [r.role_code for r in user.roles]
        new_expires_at = self._refresh_deadline(policy, roles, session_started_at, now)
        new_refresh = create_refresh_token(
            subject=user.user_id, jti=new_jti, expires_at=new_expires_at
        )
        self.db.add(RefreshToken(
            jti=new_jti,
            user_id=user.user_id,
            expires_at=new_expires_at,
            session_started_at=session_started_at,
            ip_address=ip,
            user_agent=(ua or "")[:512] if ua else None,
        ))

        # 签发新 access
        deadline = access_deadline(user, policy.access_token_minutes, now)
        new_access = create_access_token(
            subject=user.user_id,
            extra_claims={
                "username": user.username,
                "full_name": user.full_name,
                "roles": roles,
                # 2026-09-10：部门随令牌下发，供门户/LabOps 按部门前缀（TT/CMC）判定可见性；下游按名取值，多字段无影响
                "department": user.department,
                # 2026-09-11：临时密码状态随令牌下发。MDM 自己早就拦住了（shared/permissions.py），
                # 但下游系统本地验签、不回调 MDM，不下发就不知道 → 拿临时密码的人照样能在
                # LabOps / 批号 / 看板里干活。下游据此一律 403 并提示先去 MDM 改密码。
                "must_change_password": requires_password_change(user, now),
                "password_changed_at": user.password_changed_at.astimezone(UTC).isoformat()
                if user.password_changed_at else None,
            },
            expires_minutes=policy.access_token_minutes,
            expires_at=deadline,
        )

        # 强一致：refresh 端点必须 commit 后才返回（避免 yield 依赖 commit 时机坑）
        await self.db.flush()
        await self.db.commit()

        return (
            RefreshTokenResponse(
                access_token=new_access,
                expires_in=max(1, ceil((deadline - datetime.now(UTC)).total_seconds())),
            ),
            new_refresh,
            policy,
        )

    async def logout(
        self,
        refresh_token: str | None,
        ip: str | None = None,
        ua: str | None = None,
    ) -> None:
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
        # LOGOUT 审计：logout 路由不走 get_current_user，操作人身份从 refresh token 的
        # sub 解析后再查 username（audit_log.username 非空）；解析不出则跳过审计但仍登出。
        sub_raw = payload.get("sub")
        try:
            user_id_int = int(sub_raw) if sub_raw is not None else None
        except (TypeError, ValueError):
            user_id_int = None
        if user_id_int is not None:
            uname = (
                await self.db.execute(
                    select(User.username).where(User.user_id == user_id_int)
                )
            ).scalar_one_or_none()
            if uname is not None:
                self.db.add(
                    AuditLog(
                        user_id=user_id_int,
                        username=uname,
                        action="LOGOUT",
                        ip_address=ip,
                        user_agent=ua,
                        request_id=audit_request_id.get(),
                        reason="登出",
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
