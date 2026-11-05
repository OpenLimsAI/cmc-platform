"""
认证与权限依赖
"""
from datetime import UTC

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_mode import require_native_auth_enabled
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    AccountDisabledError,
    PasswordChangeRequiredError,
    PermissionDeniedError,
    TemporaryPasswordExpiredError,
    TokenInvalidError,
    TokenMissingError,
)
from app.core.security import decode_token
from app.domains.auth.models import User
from app.domains.auth.password_policy import requires_password_change, temporary_password_expired
from app.shared.audit_context import (
    audit_user_id,
    audit_username,
    set_audit_session_vars,
)

# 强制改密期间仅放行改密闭环必要接口（refresh/logout 当前不依赖
# get_current_user，列入以防御未来加依赖）
FORCE_PASSWORD_CHANGE_ALLOWED_PATHS = frozenset({
    "/api/v1/auth/change-password",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/auth/refresh",
    "/api/v1/auth/session-policy",
    "/api/v1/auth/oidc/session",
    "/api/v1/auth/oidc/logout",
})


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Authorization 头解析 JWT 并加载当前用户"""
    from app.domains.auth.oidc.service import SESSION_COOKIE, OIDCService, require_origin
    opaque = request.cookies.get(SESSION_COOKIE) if settings.MDM_OIDC_ENABLED else None
    if authorization:
        require_native_auth_enabled()
        if opaque:
            raise TokenInvalidError("不能混用原生令牌和统一登录会话，请重新选择登录方式")
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise TokenInvalidError("Authorization 头格式错误")
        payload = decode_token(parts[1])
        if payload.get("type") != "access":
            raise TokenInvalidError("Token 类型错误")
    elif opaque:
        service = OIDCService(db)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_origin(request, service.config)
        cookie_user, session = await service.current_session(opaque)
        request.state.oidc_session = session
        db.info["oidc_session_id"] = session.id
        payload = {"sub": str(cookie_user.user_id), "type": "access",
                   "iat": int(session.issued_at.timestamp()), "password_changed_at": session.password_version}
    else:
        raise TokenMissingError()

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise TokenInvalidError("Token 缺少 subject")

    try:
        user_id = int(user_id_str)
    except ValueError as e:
        raise TokenInvalidError() from e

    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.user_id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise TokenInvalidError("用户不存在")

    if user.status != "active":
        raise AccountDisabledError(f"账户状态: {user.status}")

    # 改密后旧 token 失效（21 CFR Part 11 §11.300 标识码/密码生命周期管理）
    # JWT.iat 是秒级整数；password_changed_at 是微秒级 timestamptz。
    # 必须把 password_changed_at 也截到整秒比较，否则改密后立即重登的 token（iat=秒）
    # 会被误判（fromtimestamp(秒) < 同一秒.123 → True）。
    if user.password_changed_at is not None:
        changed_at_claim = payload.get("password_changed_at")
        if changed_at_claim is not None and changed_at_claim != user.password_changed_at.astimezone(UTC).isoformat():
            raise TokenInvalidError("密码已变更，请重新登录")
        token_iat = payload.get("iat")
        if token_iat is not None:
            pwd_changed_sec = int(user.password_changed_at.timestamp())
            if int(token_iat) < pwd_changed_sec:
                raise TokenInvalidError("密码已变更，请重新登录")

    # 强制改密拦截：临时密码仅可走改密闭环，其余接口 403
    # （403 而非 401：避免前端拦截器按会话失效登出）
    from app.domains.auth.oidc.config import fresh_signing_enabled
    from app.domains.auth.oidc.protocol import OIDCError
    from app.domains.auth.oidc.service import OIDCUnavailableError
    fresh_oidc = False
    if opaque:
        try:
            fresh_oidc = fresh_signing_enabled()
        except OIDCError:
            raise OIDCUnavailableError() from None
    if not fresh_oidc and temporary_password_expired(user):
        raise TemporaryPasswordExpiredError()
    if not fresh_oidc and requires_password_change(user) and request.url.path not in FORCE_PASSWORD_CHANGE_ALLOWED_PATHS:
        raise PasswordChangeRequiredError()

    # 认证通过后把 user 写入 ContextVar 并回灌当前事务的 PG session 变量，
    # 后续业务 SQL 触发的 audit trigger 才能取到正确的 user_id/username
    audit_user_id.set(user.user_id)
    audit_username.set(user.username)
    await set_audit_session_vars(db)

    # P4.B：限流按已认证用户分桶（slowapi key_func 读 request.state.rate_limit_user_id）
    request.state.rate_limit_user_id = user.user_id

    return user


async def get_user_permissions(user: User, db: AsyncSession) -> set[str]:
    """获取用户全部权限码集合（通过角色聚合）"""
    from app.domains.auth.models import Permission, RolePermission

    if not user.roles:
        return set()

    role_ids = [r.role_id for r in user.roles]
    result = await db.execute(
        select(Permission.permission_code)
        .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
        .where(RolePermission.role_id.in_(role_ids))
    )
    return {code for (code,) in result.all()}


def require_permission(permission_code: str):
    """权限依赖工厂"""

    async def checker(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        permissions = await get_user_permissions(user, db)
        # SYS_ADMIN 角色拥有所有权限
        if any(r.role_code == "SYS_ADMIN" for r in user.roles):
            return user
        if permission_code not in permissions:
            raise PermissionDeniedError(f"缺少权限: {permission_code}")
        return user

    return checker


def require_all_permissions(*permission_codes: str):
    """要求当前用户同时具备多个权限码（GxP 双权限场景，如 substance:approve + substance:sign）"""

    async def checker(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if any(r.role_code == "SYS_ADMIN" for r in user.roles):
            return user
        permissions = await get_user_permissions(user, db)
        missing = [p for p in permission_codes if p not in permissions]
        if missing:
            raise PermissionDeniedError(f"缺少权限: {', '.join(missing)}")
        return user

    return checker
