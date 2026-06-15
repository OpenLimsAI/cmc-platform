"""
文件: backend/routers/auth_router.py
用途: 登录 / 登出 / 当前用户 — 代理 MDM Portal 认证
路径前缀: /api/auth + /api/users/me
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from audit import get_request_ip, write_audit
from auth import (
    MDM_JWT_ALGORITHM,
    MDM_SECRET_KEY,
    CurrentUser,
    get_current_user,
)
from database import get_db
from schemas import LoginRequest

MDM_BASE_URL = os.getenv("MDM_BASE_URL", "http://127.0.0.1:18000/api/v1")
MDM_TIMEOUT = float(os.getenv("MDM_TIMEOUT", "5"))

router = APIRouter(prefix="/api", tags=["auth"])


def _user_from_token(token: str | None) -> CurrentUser | None:
    """从 MDM 返回的 access_token 解出登录用户（仅用于审计记录）。"""
    if not token:
        return None
    try:
        claims = jwt.decode(token, MDM_SECRET_KEY, algorithms=[MDM_JWT_ALGORITHM])
        return CurrentUser(
            user_id=int(claims["sub"]),
            username=claims.get("username", ""),
            roles=claims.get("roles", []),
        )
    except (JWTError, KeyError, ValueError, TypeError):
        return None


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """代理 MDM 登录，返回 JWT access_token。"""
    try:
        with httpx.Client(timeout=MDM_TIMEOUT, trust_env=False) as c:
            resp = c.post(
                f"{MDM_BASE_URL}/auth/login",
                json={"username": payload.username, "password": payload.password},
            )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="认证服务不可用，请稍后重试")

    if resp.status_code != 200:
        detail = "用户名或密码错误"
        try:
            body = resp.json()
            detail = body.get("detail") or body.get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)

    body = resp.json()
    data = body.get("data", body)

    user = _user_from_token(data.get("access_token") if isinstance(data, dict) else None)
    try:
        write_audit(
            db,
            user,
            "auth.login",
            entity_type="user",
            entity_id=user.user_id if user else None,
            source_ip=get_request_ip(request),
            fallback_username=payload.username,
        )
        db.commit()
    except Exception:
        db.rollback()

    return data


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """JWT 无状态，客户端丢弃 token 即可；此处仅记录审计。"""
    try:
        write_audit(
            db,
            current,
            "auth.logout",
            entity_type="user",
            entity_id=current.user_id,
            source_ip=get_request_ip(request),
        )
        db.commit()
    except Exception:
        db.rollback()
    return


@router.get("/users/me")
def me(current: CurrentUser = Depends(get_current_user)):
    return {
        "user_id": current.user_id,
        "username": current.username,
        "roles": current.roles,
    }
