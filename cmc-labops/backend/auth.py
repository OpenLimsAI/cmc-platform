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

import httpx
from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt

MDM_SECRET_KEY = os.getenv(
    "MDM_SECRET_KEY",
    "dev-secret-key-CHANGE-ME-IN-PRODUCTION-please-32-chars",
)
MDM_JWT_ALGORITHM = os.getenv("MDM_JWT_ALGORITHM", "HS256")
# 2026-09-10 负责人：LabOps 是实验室系统，只对部门以 TT / CMC 开头的员工开放（SYS_ADMIN 例外）。
# 部门来自 MDM access token 的 department 字段（MDM 2026-09-10 起下发）。逗号分隔，不分大小写。
LAB_DEPARTMENT_PREFIXES = tuple(
    p.strip().upper() for p in os.getenv("LAB_DEPARTMENT_PREFIXES", "TT,CMC").split(",") if p.strip()
)
MDM_BASE_URL = os.getenv("MDM_BASE_URL", "http://127.0.0.1:18000/api/v1")
MDM_TIMEOUT = float(os.getenv("MDM_TIMEOUT", "5"))


@dataclass
class CurrentUser:
    user_id: int
    username: str
    full_name: str = ""
    roles: list[str] = field(default_factory=list)
    department: Optional[str] = None
    # 令牌里到底有没有 department 这个键：MDM 2026-09-10 之前签发的旧令牌没有该键，
    # 而「部门为空的用户」新令牌里键存在、值是 null——两者都取到 None，必须靠这个标志区分，
    # 否则部门没填的人会被当成旧令牌无限 401 → 换证 → 还是 401 → 被强制登出（无法看到 403 说明）。
    has_department_claim: bool = False

    @property
    def id(self) -> int:
        return self.user_id

    @property
    def is_lab_member(self) -> bool:
        """部门以 LAB_DEPARTMENT_PREFIXES 之一开头（不分大小写）；SYS_ADMIN 视同成员"""
        if "SYS_ADMIN" in self.roles:
            return True
        dept = (self.department or "").strip().upper()
        return any(dept.startswith(p) for p in LAB_DEPARTMENT_PREFIXES)


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

    # 2026-09-11：拿临时密码（管理员重置后）的人只能先去 MDM 改密码。
    # MDM 自己早就拦了，但下游本地验签、不回调 MDM，所以靠令牌里的 must_change_password 标记。
    # 用 403 不用 401：401 会被前端当成会话过期去续期，续出来的新令牌照样带这个标记，会转圈。
    if payload.get("must_change_password"):
        raise HTTPException(status_code=403, detail="请先到主数据平台（MDM）修改临时密码，再使用本系统")

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
        full_name=payload.get("full_name", ""),
        roles=payload.get("roles", []),
        department=payload.get("department"),
        has_department_claim="department" in payload,
    )


def require_lab_member(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """LabOps 全部业务接口的准入：实验室部门（TT*/CMC*）员工或 SYS_ADMIN。

    旧令牌（没有 department 字段）回 401 而不是 403：前端拦截器收到 401 会去 MDM 换一张新令牌
    并重放请求，新令牌带部门，用户无感；真正不符合部门的才回 403。
    """
    if not current.has_department_claim and "SYS_ADMIN" not in current.roles:
        raise HTTPException(status_code=401, detail="登录凭证版本过旧，请刷新页面重新登录")
    if not current.is_lab_member:
        raise HTTPException(
            status_code=403,
            detail="LabOps 仅对实验室部门（TT / CMC）员工开放；部门信息在 MDM 维护，如有疑问请联系管理员",
        )
    return current


def verify_reviewer(username: str, password: str) -> CurrentUser:
    """用账号密码向 MDM 验证一个复核人身份,返回其 CurrentUser(含 roles)。
    用于双人复核电子签名:第二位库管员/管理员当场输入凭据证明本人。
    注意 httpx 须 trust_env=False(本机有 SOCKS 代理)。"""
    try:
        with httpx.Client(timeout=MDM_TIMEOUT, trust_env=False) as c:
            resp = c.post(
                f"{MDM_BASE_URL}/auth/login",
                json={"username": username, "password": password},
            )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="认证服务不可用,无法完成复核签名")
    if resp.status_code != 200:
        # 必须用 400 而非 401:复核人凭据错误是"业务校验失败",
        # 前端对 401 会统一清登录态并跳登录页(client.ts),用 401 会把
        # 正在操作的修改人误踢回登录页。复核失败只应在弹窗里提示。
        raise HTTPException(status_code=400, detail="复核人账号或密码错误")
    body = resp.json()
    data = body.get("data", body)
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise HTTPException(status_code=502, detail="复核认证返回异常")
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
        raise HTTPException(status_code=502, detail="复核认证令牌解析失败")


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
