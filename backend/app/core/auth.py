"""从 MDM 已验签身份实施权限检查；没有 system/匿名写入身份。"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header

from app.core.config import Settings, get_auth_settings
from app.core.envelope import BusinessError
from app.core.security import authentication_required, auth_configured, verify_access_token


@dataclass(frozen=True)
class CurrentUser:
    username: str
    full_name: str | None
    subject: str
    roles: tuple[str, ...]

    def has_any_role(self, allowed: list[str]) -> bool:
        # 包括 SYS_ADMIN 在内的任何角色均须由负责人显式纳入本系统白名单。
        return bool(set(self.roles).intersection(allowed))


def _require_user(authorization: str | None, auth_settings: Settings) -> CurrentUser:
    if not auth_configured(auth_settings):
        raise BusinessError("auth_not_configured", "尚未配置 MDM 令牌验签，受控功能不可用", http_status=503)
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 16_384:
        raise BusinessError("authentication_required", "需要有效的 MDM 登录令牌", http_status=401)
    claims = verify_access_token(parts[1], auth_settings)
    return CurrentUser(claims["username"], claims.get("full_name"), claims["sub"], tuple(claims["roles"]))


def require_user(
    authorization: str | None = Header(default=None),
    auth_settings: Settings = Depends(get_auth_settings),
) -> CurrentUser:
    return _require_user(authorization, auth_settings)


def require_read(
    authorization: str | None = Header(default=None),
    auth_settings: Settings = Depends(get_auth_settings),
) -> CurrentUser | None:
    if not authentication_required(auth_settings):
        # 公司统一存储可能带着其他系统的令牌。本机开放读取仍是匿名，
        # 不把未验签内容当身份，也不因此开放任何受控动作。
        return None
    user = _require_user(authorization, auth_settings)
    if not user.has_any_role(auth_settings.read_roles):
        raise BusinessError("read_forbidden", "当前账号没有质量分析浏览权限", http_status=403)
    return user


def require_import_preview(
    user: CurrentUser = Depends(require_user),
    auth_settings: Settings = Depends(get_auth_settings),
) -> CurrentUser:
    if not user.has_any_role(auth_settings.import_preview_roles):
        raise BusinessError("preview_forbidden", "当前账号没有 Excel 预览权限", http_status=403)
    return user
