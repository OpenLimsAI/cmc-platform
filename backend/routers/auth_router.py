"""
文件: backend/routers/auth_router.py
用途: 登录 / 登出 / 当前用户 — 代理 MDM Portal 认证
路径前缀: /api/auth + /api/users/me
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import CurrentUser, get_current_user
from schemas import LoginRequest

MDM_BASE_URL = os.getenv("MDM_BASE_URL", "http://127.0.0.1:18000/api/v1")
MDM_TIMEOUT = float(os.getenv("MDM_TIMEOUT", "5"))

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login")
def login(payload: LoginRequest):
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
    return data


@router.post("/auth/logout", status_code=204)
def logout(_: CurrentUser = Depends(get_current_user)):
    """JWT 无状态，客户端丢弃 token 即可。"""
    return


@router.get("/users/me")
def me(current: CurrentUser = Depends(get_current_user)):
    return {
        "user_id": current.user_id,
        "username": current.username,
        "roles": current.roles,
    }
