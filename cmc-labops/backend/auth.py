"""
文件: backend/auth.py
用途: JWT 认证 — 信任 MDM Portal 签发的 access token
说明:
    - 解码 MDM JWT，从 claims 中提取 user_id / username / roles
    - 不再维护本地用户表和 session 表
    - token 走 Authorization: Bearer <jwt> header
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx
from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt

DEV_DEFAULT_MDM_SECRET_KEY = "dev-secret-key-CHANGE-ME-IN-PRODUCTION-please-32-chars"
DEV_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5100",
    "http://127.0.0.1:5100",
)
CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Authorization", "Content-Type", "Accept", "X-Requested-With"]
_INSECURE_SECRET_MARKERS = (
    "change-me",
    "change_me",
    "dev-secret",
    "__redacted",
    "placeholder",
    "default-secret",
)
_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def is_production_env(environ: Mapping[str, str] | None = None) -> bool:
    """判断当前是否处于生产环境（APP_ENV=production 或 CMC_ENV=production）。"""
    source = os.environ if environ is None else environ
    for key in ("APP_ENV", "CMC_ENV"):
        if source.get(key, "").strip().lower() == "production":
            return True
    return False


def resolve_cors_origins(environ: Mapping[str, str] | None = None) -> list[str]:
    """解析并校验允许跨域访问的前端 Origin 列表；生产环境缺失或含通配符 '*' 时立即 fail-closed。"""
    source = os.environ if environ is None else environ
    raw_origins = source.get("LABOPS_CORS_ORIGINS", "")
    origins = [item.strip() for item in raw_origins.split(",") if item.strip()]

    if is_production_env(source):
        if not origins or "*" in origins:
            raise RuntimeError(
                "安全配置错误：生产环境（APP_ENV/CMC_ENV=production）必须显式配置 "
                "LABOPS_CORS_ORIGINS（禁止缺省、为空或包含通配符 '*'）"
            )
        return origins

    if not origins:
        return list(DEV_DEFAULT_CORS_ORIGINS)
    return origins


def validate_cors_startup(environ: Mapping[str, str] | None = None) -> list[str]:
    """应用启动时的 CORS 安全基线检查。"""
    return resolve_cors_origins(environ)


def resolve_mdm_signing_config(environ: Mapping[str, str] | None = None) -> tuple[str, str]:
    """解析并校验 JWT 验签配置；生产环境下缺失或使用弱默认密钥时立即 fail-closed。"""
    source = os.environ if environ is None else environ
    algorithm = source.get("MDM_JWT_ALGORITHM", "HS256").strip() or "HS256"
    if algorithm not in {"HS256", "RS256"}:
        raise RuntimeError(f"安全配置错误：不支持的 MDM_JWT_ALGORITHM={algorithm!r}")

    raw_secret = source.get("MDM_SECRET_KEY")
    if is_production_env(source):
        secret = (raw_secret or "").strip()
        lowered = secret.lower()
        if (
            not secret
            or len(secret) < 32
            or secret == DEV_DEFAULT_MDM_SECRET_KEY
            or any(marker in lowered for marker in _INSECURE_SECRET_MARKERS)
        ):
            raise RuntimeError(
                "安全配置错误：生产环境（APP_ENV/CMC_ENV=production）必须显式配置高强度 "
                "MDM_SECRET_KEY（至少 32 字符，禁止缺省或使用开发默认密钥）"
            )
        return secret, algorithm

    return (raw_secret if raw_secret else DEV_DEFAULT_MDM_SECRET_KEY), algorithm


def validate_auth_startup(environ: Mapping[str, str] | None = None) -> None:
    """应用启动与请求验签前的安全基线检查。"""
    resolve_mdm_signing_config(environ)


def is_legacy_password_proxy_disabled(environ: Mapping[str, str] | None = None) -> bool:
    """判断是否已禁用向 MDM 转发用户明文账号密码（启用 OIDC / oidc_fresh 后开启）。"""
    source = os.environ if environ is None else environ
    if source.get("LABOPS_DISABLE_LEGACY_PASSWORD_PROXY", "").strip().lower() in _TRUTHY_VALUES:
        return True
    if source.get("LABOPS_SIGNATURE_MODE", "").strip().lower() == "oidc_fresh":
        return True
    return False


def ensure_legacy_password_proxy_enabled(*, context: str = "login") -> None:
    """当明文密码代理被停用时，在发起任何外部 HTTP 调用前直接拦截。"""
    if not is_legacy_password_proxy_disabled():
        return
    if context == "reviewer":
        raise HTTPException(
            status_code=403,
            detail="明文密码复核代理已停用，请使用统一身份二次认证（oidc_fresh）完成复核签名",
        )
    raise HTTPException(
        status_code=403,
        detail="明文密码代理登录已停用，请使用统一身份（Casdoor OIDC）登录",
    )


MDM_SECRET_KEY, MDM_JWT_ALGORITHM = resolve_mdm_signing_config()
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
    secret_key, jwt_algorithm = resolve_mdm_signing_config()
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请提供 Authorization: Bearer <token>")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 头格式错误")

    try:
        payload = jwt.decode(parts[1], secret_key, algorithms=[jwt_algorithm])
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
    当启用统一身份二次认证（LABOPS_DISABLE_LEGACY_PASSWORD_PROXY=true / oidc_fresh）时直接拦截。
    注意 httpx 须 trust_env=False(本机有 SOCKS 代理)。"""
    secret_key, jwt_algorithm = resolve_mdm_signing_config()
    ensure_legacy_password_proxy_enabled(context="reviewer")
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
        claims = jwt.decode(token, secret_key, algorithms=[jwt_algorithm])
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
