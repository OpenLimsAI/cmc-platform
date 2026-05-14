"""
/api/v1/auth 路由
"""
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.responses import success
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
)
from app.domains.auth.services import AuthService
from app.shared.permissions import get_current_user
from app.shared.rate_limit import login_rate_limit, public_rate_limit

router = APIRouter()

# HttpOnly Cookie 名（API §2.2 / ARCH §7.2.1）
REFRESH_COOKIE_NAME = "cmab_refresh_token"
# 限定 cookie 只发送到 /api/v1/auth/* 路径下，减少非必要传输面
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """写入 HttpOnly Cookie。生产环境强制 Secure。"""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/login", summary="用户登录")
@login_rate_limit()  # V1.1 §3.5：未认证端点 10/min/IP
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result, refresh_token = await service.login(
        username=payload.username,
        password=payload.password,
        ip=getattr(request.state, "ip_address", None),
        ua=getattr(request.state, "user_agent", None),
    )
    _set_refresh_cookie(response, refresh_token)
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
    service = AuthService(db)
    if not cmab_refresh_token:
        # 没有 cookie 直接 401 — 让前端跳登录
        from app.core.exceptions import TokenMissingError
        raise TokenMissingError("refresh token 缺失")
    result, new_refresh = await service.refresh(
        refresh_token=cmab_refresh_token,
        ip=getattr(request.state, "ip_address", None),
        ua=getattr(request.state, "user_agent", None),
    )
    _set_refresh_cookie(response, new_refresh)
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
    await service.logout(cmab_refresh_token)
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
