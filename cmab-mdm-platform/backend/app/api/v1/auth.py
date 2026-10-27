"""
/api/v1/auth 路由
"""
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_mode import require_native_auth_enabled
from app.core.config import settings
from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
)
from app.domains.auth.services import AuthService
from app.domains.auth.session_policy import (
    DISPLAY_MODE_ROLE,
    SessionPolicy,
    load_session_policy,
)
from app.shared.permissions import get_current_user
from app.shared.rate_limit import login_rate_limit, public_rate_limit

router = APIRouter()

# HttpOnly Cookie 名（API §2.2 / ARCH §7.2.1）
REFRESH_COOKIE_NAME = "cmab_refresh_token"
# 限定 cookie 只发送到 /api/v1/auth/* 路径下，减少非必要传输面
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _refresh_cookie_path():
    if settings.MDM_OIDC_ENABLED and settings.MDM_PUBLIC_URL:
        try:
            return urlsplit(settings.MDM_PUBLIC_URL).path.rstrip("/") + REFRESH_COOKIE_PATH
        except ValueError:
            # A malformed optional SSO URL must not block explicit password recovery.
            return REFRESH_COOKIE_PATH
    return REFRESH_COOKIE_PATH


def _set_refresh_cookie(response: Response, token: str, policy: SessionPolicy) -> None:
    """写入 HttpOnly Cookie。是否带 Secure 由 settings.cookie_secure 决定（内网 HTTP 须为 false）。

    max_age 取硬上限（cookie 可以活得比 refresh 久，真正到期以服务端 DB 为准）。"""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=policy.absolute_max_hours * 3600,
        path=_refresh_cookie_path(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    for path in {REFRESH_COOKIE_PATH, _refresh_cookie_path()}:
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path=path)


@router.post("/login", summary="用户登录")
@login_rate_limit()  # V1.1 §3.5：未认证端点 10/min/IP
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    require_native_auth_enabled()
    oidc_config = None
    if settings.MDM_OIDC_ENABLED:
        from app.domains.auth.oidc.config import configured
        from app.domains.auth.oidc.protocol import OIDCError
        from app.domains.auth.oidc.service import require_origin
        try:
            oidc_config = configured()
        except OIDCError:
            # Explicit password recovery is independent of OIDC completeness.
            origin = request.headers.get("origin")
            if origin and origin not in settings.cors_origins_list:
                from app.core.exceptions import PermissionDeniedError
                raise PermissionDeniedError("请求来源不匹配") from None
        else:
            require_origin(request, oidc_config, allow_missing=True)
    service = AuthService(db)
    result, refresh_token, policy = await service.login(
        username=payload.username,
        password=payload.password,
        ip=getattr(request.state, "ip_address", None),
        ua=getattr(request.state, "user_agent", None),
    )
    _set_refresh_cookie(response, refresh_token, policy)
    from app.domains.auth.oidc.service import (
        LOGIN_COOKIE,
        SESSION_COOKIE,
        cancel_login,
        revoke_session,
    )
    if settings.MDM_OIDC_ENABLED or request.cookies.get(LOGIN_COOKIE) or request.cookies.get(SESSION_COOKIE):
        from app.api.v1.oidc import clear_login_cookie, clear_session_cookie
        await cancel_login(db, request.cookies.get(LOGIN_COOKIE))
        await revoke_session(db, request.cookies.get(SESSION_COOKIE))
        if oidc_config:
            clear_session_cookie(response, oidc_config)
            clear_login_cookie(response, oidc_config)
        else:
            response.delete_cookie(SESSION_COOKIE, path="/mdm/")
            response.delete_cookie(LOGIN_COOKIE, path="/mdm/")
    return success(
        data=result.model_dump(),
        message="登录成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/refresh", summary="刷新 Access Token（使用 Cookie 中的 Refresh Token）")
@public_rate_limit()  # access 已过期取不到 user_id，按 IP 兜底
async def refresh(
    request: Request,
    response: Response,
    cmab_refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    require_native_auth_enabled()
    service = AuthService(db)
    if not cmab_refresh_token:
        # 没有 cookie 直接 401 — 让前端跳登录
        from app.core.exceptions import TokenMissingError
        raise TokenMissingError("refresh token 缺失")
    result, new_refresh, policy = await service.refresh(
        refresh_token=cmab_refresh_token,
        ip=getattr(request.state, "ip_address", None),
        ua=getattr(request.state, "user_agent", None),
    )
    _set_refresh_cookie(response, new_refresh, policy)
    return success(
        data=result.model_dump(),
        message="OK",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/logout", summary="登出（撤销 Refresh Token + 清除 Cookie）")
async def logout(
    request: Request,
    response: Response,
    cmab_refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """V1.1 §2.2：204 No Content。即使没带 cookie 也返回 204（幂等登出）。"""
    service = AuthService(db)
    await service.logout(
        cmab_refresh_token,
        ip=getattr(request.state, "ip_address", None),
        ua=getattr(request.state, "user_agent", None),
    )
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me", summary="当前用户信息")
async def get_me(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    data = await service.get_me(user)
    return success(
        data=data,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/session-policy", summary="当前用户生效的会话策略（供各子系统前端做空闲登出/续期）")
async def my_session_policy(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全公司各前端（门户/LabOps/批号/看板…）登录后调一次，按返回值做：
    - 快到 access_token_minutes 且最近有操作 → 静默 refresh
    - 超过 idle_timeout_minutes 无操作 → 清令牌回登录页
    display_mode=true 表示当前账号是展示模式（DISPLAY_MODE 角色），idle 已按展示模式放宽。"""
    policy = await load_session_policy(db)
    roles = [r.role_code for r in user.roles]
    display_mode = DISPLAY_MODE_ROLE in roles
    return success(
        data={
            "access_token_minutes": policy.access_token_minutes,
            "idle_timeout_minutes": policy.idle_minutes_for(roles),
            "absolute_max_hours": policy.absolute_max_hours,
            "display_mode": display_mode,
        },
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/change-password", summary="修改密码")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.change_password(user, payload.old_password, payload.new_password)
    # 改密同时撤销所有 refresh token + 清前端 cookie
    _clear_refresh_cookie(response)
    return success(
        data=None,
        message="密码修改成功，请重新登录",
        request_id=getattr(request.state, "request_id", None),
    )


# =============================================================================
# Phase 5.A / M5.4：个人中心（用户看自己）
# =============================================================================


@router.get("/me/login-history", summary="我的登录历史")
async def my_login_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    items, total = await service.get_my_login_history(user, page, page_size)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.get("/me/signatures", summary="我的电子签名记录")
async def my_signatures(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    items, total = await service.get_my_signatures(user, page, page_size)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )
