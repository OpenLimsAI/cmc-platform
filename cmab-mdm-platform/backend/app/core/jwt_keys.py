"""
JWT 密钥管理（HS256 对称 / RS256 非对称）

设计：
- HS256：直接用 settings.SECRET_KEY 对称密钥；最简单，dev 默认。
- RS256：从 JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH 读 PEM，私钥签名 / 公钥验证。
  生产强烈建议（ARCH2 / 21 CFR Part 11 §11.10(b) 系统验证 + §11.300(d) 私钥隔离）。

启动时一次性加载密钥到模块级缓存（避免每次 sign/verify 都读文件）；
配置错误（RS256 但路径未配 / 文件不存在）直接 fail-fast。
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# 模块级缓存：进程启动时加载一次
_signing_key: str | bytes | None = None
_verifying_key: str | bytes | None = None
_loaded_for: str | None = None  # 当前缓存对应的算法（侦测运行时切算法异常）


def _load_keys() -> None:
    """按 settings.JWT_ALGORITHM 装载签名 / 验证密钥"""
    global _signing_key, _verifying_key, _loaded_for

    algo = settings.JWT_ALGORITHM.upper()

    if algo == "HS256":
        # 对称：签名 = 验证 = SECRET_KEY
        _signing_key = settings.SECRET_KEY
        _verifying_key = settings.SECRET_KEY
    elif algo == "RS256":
        if not settings.JWT_PRIVATE_KEY_PATH or not settings.JWT_PUBLIC_KEY_PATH:
            raise RuntimeError(
                "JWT_ALGORITHM=RS256 时必须配置 JWT_PRIVATE_KEY_PATH 与 JWT_PUBLIC_KEY_PATH。"
                " 运行 `make jwt-keys` 生成密钥对。"
            )
        priv = Path(settings.JWT_PRIVATE_KEY_PATH)
        pub = Path(settings.JWT_PUBLIC_KEY_PATH)
        if not priv.is_file():
            raise RuntimeError(f"RS256 私钥文件不存在: {priv}")
        if not pub.is_file():
            raise RuntimeError(f"RS256 公钥文件不存在: {pub}")
        _signing_key = priv.read_bytes()
        _verifying_key = pub.read_bytes()
    else:
        raise RuntimeError(
            f"不支持的 JWT_ALGORITHM: {settings.JWT_ALGORITHM}（仅 HS256/RS256）"
        )

    _loaded_for = algo


def get_signing_key() -> str | bytes:
    if _signing_key is None or _loaded_for != settings.JWT_ALGORITHM.upper():
        _load_keys()
    assert _signing_key is not None  # 由 _load_keys 保证
    return _signing_key


def get_verifying_key() -> str | bytes:
    if _verifying_key is None or _loaded_for != settings.JWT_ALGORITHM.upper():
        _load_keys()
    assert _verifying_key is not None
    return _verifying_key


def get_jwt_header_extras() -> dict:
    """JWT header 附加字段（kid 用于密钥轮换）"""
    extras = {}
    if settings.JWT_KEY_ID:
        extras["kid"] = settings.JWT_KEY_ID
    return extras
