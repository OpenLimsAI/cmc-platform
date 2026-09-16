"""验证 MDM access token；不签发令牌、不建立账号、不提供开放写权限。"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.config import Settings, get_auth_settings
from app.core.envelope import BusinessError


class _AuthConfigurationError(Exception):
    """仅包含适合展示的配置错误，不附带密钥、路径或底层异常。"""


def _verification_key(auth_settings: Settings) -> str | RSAPublicKey:
    if auth_settings.jwt_algorithm == "HS256":
        secret = auth_settings.jwt_secret_key
        if secret is None or not secret.get_secret_value().strip():
            raise _AuthConfigurationError("未配置 MDM 令牌验签")
        key = secret.get_secret_value()
        try:
            jwt.get_algorithm_by_name("HS256").prepare_key(key)
        except (jwt.exceptions.InvalidKeyError, TypeError, ValueError):
            raise _AuthConfigurationError("MDM 令牌验签配置无效") from None
        return key
    if auth_settings.jwt_algorithm == "RS256":
        if not auth_settings.jwt_public_key_path:
            raise _AuthConfigurationError("未配置 MDM 令牌验签")
        try:
            path = Path(auth_settings.jwt_public_key_path)
            if path.stat().st_size > 64 * 1024:
                raise ValueError("public key file too large")
            key = serialization.load_pem_public_key(path.read_bytes())
            if not isinstance(key, RSAPublicKey):
                raise ValueError("RSA public key required")
        except (OSError, ValueError, TypeError, UnsupportedAlgorithm):
            raise _AuthConfigurationError("MDM 令牌验签配置无效") from None
        return key
    raise _AuthConfigurationError("MDM 令牌验签算法不受支持")


def auth_configured(auth_settings: Settings | None = None) -> bool:
    """只暴露是否具备可用验签配置，不暴露验签材料。"""
    try:
        _verification_key(auth_settings or get_auth_settings())
    except _AuthConfigurationError:
        return False
    return True


def authentication_required(auth_settings: Settings) -> bool:
    """只有明确的、本机未配置身份的开发只读模式允许匿名。"""
    return (
        auth_settings.auth_required
        or auth_settings.environment != "development"
        or auth_settings.jwt_secret_key is not None
        or bool(auth_settings.jwt_public_key_path)
    )


def validate_auth_configuration(auth_settings: Settings | None = None) -> None:
    """由 lifespan 调用；生产、要求认证或已提供但无效的配置均须启动失败。"""
    config = auth_settings or get_auth_settings()
    if authentication_required(config):
        try:
            _verification_key(config)
        except _AuthConfigurationError as exc:
            raise RuntimeError(str(exc)) from None


def verify_access_token(token: str, auth_settings: Settings | None = None) -> dict[str, Any]:
    """验签并检查必需 claims；身份缺失或畸形不降级为 system。"""
    config = auth_settings or get_auth_settings()
    try:
        key = _verification_key(config)
    except _AuthConfigurationError as exc:
        raise BusinessError("auth_not_configured", str(exc), http_status=503) from None
    try:
        claims = jwt.decode(
            token, key, algorithms=[config.jwt_algorithm],
            options={
                "require": ["exp", "sub", "username", "type", "roles"],
                # 当前 MDM 没有 iss/aud 契约，不能自行要求这两个 claim。
                "verify_aud": False, "verify_iss": False,
            },
        )
        if claims["type"] != "access":
            raise ValueError("access token required")
        expiration = claims["exp"]
        if isinstance(expiration, bool) or not isinstance(expiration, (int, float)) or not math.isfinite(expiration):
            raise ValueError("numeric expiration required")
        for name in ("sub", "username"):
            value = claims[name]
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError("identity required")
        roles = claims["roles"]
        if not isinstance(roles, list) or any(
            not isinstance(role, str) or not role or role != role.strip() for role in roles
        ):
            raise ValueError("role list required")
        if claims.get("full_name") is not None and not isinstance(claims["full_name"], str):
            raise ValueError("invalid display name")
        if "must_change_password" in claims and not isinstance(claims["must_change_password"], bool):
            raise ValueError("invalid password status")
    except (jwt.exceptions.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise BusinessError("invalid_token", "登录令牌无效或已过期，请重新登录", http_status=401) from None
    if claims.get("must_change_password") is True:
        raise BusinessError(
            "password_change_required", "请先到主数据平台（MDM）修改临时密码，再使用本系统", http_status=403
        )
    return claims
