"""
文件: backend/routers/auth_router.py
用途: 登录 / 登出 / 当前用户 / 改密
路径前缀: /api/auth + /api/users/me

注意:
    - 登录是匿名接口,不依赖 get_current_user
    - /me 与 /change-password 仅依赖 get_current_user,不要求 require_password_not_pending,
      让首次登录用户能自查与改密
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    hash_password,
    issue_session,
    revoke_all_user_sessions,
    revoke_session,
    verify_password,
)
from database import get_db
from models import AppUser
from schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """用户名密码登录,返回 token。"""
    user = db.execute(
        select(AppUser).where(AppUser.username == payload.username)
    ).scalar_one_or_none()

    # 用户不存在 / 密码不对 → 同样的错误信息,避免账号枚举
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用,请联系管理员")

    source_ip = request.client.host if request.client else None
    sess = issue_session(db, user, source_ip=source_ip)

    return TokenResponse(
        access_token=sess.token,
        expires_at=sess.expires_at,
        user=UserOut.model_validate(user),
    )


@router.post("/auth/logout", status_code=204)
def logout(
    current: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    authorization: Optional[str] = None,
):
    """登出当前 session(token 主动失效)。
    取 token 用 get_current_user 已经验证过,这里再调一次解析比较麻烦;
    简化做法:从 user 角度,撤销其所有 session(等价于"在所有设备上登出")。
    多设备需求小,先这样;后续再做单 session 撤销。
    """
    revoke_all_user_sessions(db, current.id)


@router.get("/users/me", response_model=UserOut)
def me(current: AppUser = Depends(get_current_user)):
    return current


@router.post("/auth/change-password", response_model=UserOut)
def change_password(
    payload: ChangePasswordRequest,
    current: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, current.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    current.password_hash = hash_password(payload.new_password)
    current.must_change_password = False
    db.commit()
    # 改密后撤销其他 session,但保留当前(刚刚 commit 的 token 还有效)。
    # 简化:把所有 session 都撤销,前端用返回值重新登录即可。
    revoke_all_user_sessions(db, current.id)
    db.refresh(current)
    return current
