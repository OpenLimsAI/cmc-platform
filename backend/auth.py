"""
文件: backend/auth.py
用途: JWT 认证 — 信任 MDM Portal 签发的 access token
说明:
    - 解码 MDM JWT，从 claims 中提取 user_id / username / roles
    - 不再维护本地用户表和 session 表
    - token 走 Authorization: Bearer <jwt> header
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt

MDM_SECRET_KEY = os.getenv(
    "MDM_SECRET_KEY",
    "dev-secret-key-CHANGE-ME-IN-PRODUCTION-please-32-chars",
)
MDM_JWT_ALGORITHM = os.getenv("MDM_JWT_ALGORITHM", "HS256")


@dataclass
class CurrentUser:
    user_id: int
    username: str
    roles: list[str] = field(default_factory=list)

    @property
    def id(self) -> int:
        return self.user_id


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> CurrentUser:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请提供 Authorization: Bearer <token>")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 头格式错误")

    try:
        payload = jwt.decode(parts[1], MDM_SECRET_KEY, algorithms=[MDM_JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期，请重新登录")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token 类型错误")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token 缺少 subject")

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Token subject 格式错误")

    return CurrentUser(
        user_id=user_id,
        username=payload.get("username", ""),
        roles=payload.get("roles", []),
    )


def require_admin(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if "SYS_ADMIN" not in current.roles:
        raise HTTPException(status_code=403, detail="此操作仅管理员可执行")
    return current


def require_warehouse(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    allowed = {"SYS_ADMIN", "CMC_WAREHOUSE_ADMIN"}
    if not (set(current.roles) & allowed):
        raise HTTPException(status_code=403, detail="此操作需要管理员或库管理员权限")
    return current


def require_equipment(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    allowed = {"SYS_ADMIN", "CMC_EQUIPMENT_ADMIN"}
    if not (set(current.roles) & allowed):
        raise HTTPException(status_code=403, detail="此操作需要管理员或设备管理员权限")
    return current
