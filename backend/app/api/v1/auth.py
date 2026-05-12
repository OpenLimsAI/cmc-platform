"""
/api/v1/auth 路由
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import success
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
)
from app.domains.auth.services import AuthService
from app.shared.permissions import get_current_user

router = APIRouter()


@router.post("/login", summary="用户登录")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result = await service.login(
        username=payload.username,
        password=payload.password,
        ip=getattr(request.state, "ip_address", None),
        ua=getattr(request.state, "user_agent", None),
    )
    return success(
        data=result.model_dump(),
        message="登录成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="登出")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
):
    # 简化版：JWT 无状态，前端清除 token 即可
    # 完整版应将 jti 加入 Redis 黑名单
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.change_password(user, payload.old_password, payload.new_password)
    return success(
        data=None,
        message="密码修改成功，请重新登录",
        request_id=getattr(request.state, "request_id", None),
    )
