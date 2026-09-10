"""ARCH11 限流（V1.1 API §3.5）

4 档：
  - 未认证（/auth/login + 公开端点）  10/min/IP
  - 普通用户                        300/min/user
  - 内部服务（service token）       1000/min   ← Phase 5 service token 后接入；当前同普通用户
  - 批量操作                         10/min/user ← Phase 5 batch endpoints；当前无批量端点

实现要点：
  - Redis 作为 distributed counter storage（依赖 settings.REDIS_URL）
  - key_func: 已登录走 user_id, 未登录走 X-Forwarded-For -> client.host
  - 超限统一通过 app_error_handler 走 42901 错误码 + Retry-After + X-RateLimit-* header
"""
from collections.abc import Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings


def _key_user_or_ip(request: Request) -> str:
    """优先按已认证用户分桶；否则按 IP。

    user_id 来源：业务认证中间件已把用户写到 request.state.user_id（若有）。
    若没有（鉴权前的请求），fall back 到 X-Forwarded-For / client.host。
    """
    user_id = getattr(request.state, "rate_limit_user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


def _key_ip(request: Request) -> str:
    """强制按 IP 分桶（用于登录端点 + 公开端点）"""
    return f"ip:{get_remote_address(request)}"


# 阈值集中在 core/config.py 的 rate_limit_* property（可用 RATE_LIMIT_* 环境变量覆盖）
_DEFAULT_LIMIT = settings.rate_limit_default

limiter = Limiter(
    key_func=_key_user_or_ip,
    default_limits=[_DEFAULT_LIMIT],
    storage_uri=settings.REDIS_URL,
    headers_enabled=True,  # 自动写 X-RateLimit-Limit / Remaining / Reset 三个 header
    strategy="fixed-window",
    enabled=settings.RATE_LIMIT_ENABLED,
)


_LOGIN_LIMIT = settings.rate_limit_login
_PUBLIC_LIMIT = settings.rate_limit_public


def login_rate_limit() -> Callable:
    """登录端点专用（V1.1 API §3.5 第 1 档）

    生产 10/min/IP；开发放宽。⚠️ 按 IP 分桶依赖 uvicorn 的 --proxy-headers：
    没开时所有请求的来源都是 nginx 的 127.0.0.1，限流会退化成「全公司共用一个桶」。
    """
    return limiter.limit(_LOGIN_LIMIT, key_func=_key_ip)


def public_rate_limit() -> Callable:
    """公开端点（refresh / 健康 / metrics 等）：生产 60/min/IP"""
    return limiter.limit(_PUBLIC_LIMIT, key_func=_key_ip)


__all__ = [
    "limiter",
    "login_rate_limit",
    "public_rate_limit",
    "SlowAPIMiddleware",
    "RateLimitExceeded",
]
