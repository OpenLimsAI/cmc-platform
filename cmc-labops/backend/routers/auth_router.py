"""
文件: backend/routers/auth_router.py
用途: 登录 / 登出 / 当前用户 — 代理 MDM Portal 认证
路径前缀: /api/auth + /api/users/me
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
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

# refresh token 以 HttpOnly Cookie 中转(与 MDM 同名);LabOps 不把它放进 JSON/JS 可读区。
# 当前生产为内网 http,COOKIE_SECURE 默认 false;上 HTTPS 后置 true 即可(无需改码)。
REFRESH_COOKIE_NAME = "cmab_refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"
REFRESH_COOKIE_MAX_AGE = 7 * 86400
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


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
            full_name=claims.get("full_name", ""),
            roles=claims.get("roles", []),
            department=claims.get("department"),
            has_department_claim="department" in claims,
        )
    except (JWTError, KeyError, ValueError, TypeError):
        return None


@router.post("/auth/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """代理 MDM 登录，返回 JWT access_token；并把 MDM 下发的 refresh Cookie
    中转为 LabOps 域的 HttpOnly Cookie，供后续 /auth/refresh 无感续期。"""
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

    # 中转 MDM 的 refresh Cookie(HttpOnly,7天);access_token 仍照常 body 返回
    mdm_refresh = resp.cookies.get(REFRESH_COOKIE_NAME)
    if mdm_refresh:
        _set_refresh_cookie(response, mdm_refresh)

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


@router.post("/auth/refresh")
def refresh(
    request: Request,
    response: Response,
    cmab_refresh_token: str | None = Cookie(default=None),
):
    """用 HttpOnly Cookie 中的 refresh token 向 MDM 换取新 access_token。
    成功则透传轮换后的新 Cookie;refresh 失效则清 Cookie 并返回 401。
    续期为高频操作,不写审计(避免污染 audit_log)。"""
    if not cmab_refresh_token:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    try:
        with httpx.Client(timeout=MDM_TIMEOUT, trust_env=False) as c:
            resp = c.post(
                f"{MDM_BASE_URL}/auth/refresh",
                cookies={REFRESH_COOKIE_NAME: cmab_refresh_token},
            )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="认证服务不可用，请稍后重试")

    if resp.status_code != 200:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    # MDM 轮换了 refresh,透传新 Cookie 给浏览器
    new_refresh = resp.cookies.get(REFRESH_COOKIE_NAME)
    if new_refresh:
        _set_refresh_cookie(response, new_refresh)

    body = resp.json()
    return body.get("data", body)


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    current: CurrentUser = Depends(get_current_user),
    cmab_refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    """登出:撤销 MDM refresh token(best-effort) + 清 LabOps refresh Cookie + 记审计。"""
    if cmab_refresh_token:
        try:
            with httpx.Client(timeout=MDM_TIMEOUT, trust_env=False) as c:
                c.post(
                    f"{MDM_BASE_URL}/auth/logout",
                    cookies={REFRESH_COOKIE_NAME: cmab_refresh_token},
                )
        except httpx.RequestError:
            pass
    _clear_refresh_cookie(response)
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
