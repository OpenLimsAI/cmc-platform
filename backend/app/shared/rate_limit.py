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
from typing import Callable

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


# 普通用户档：生产 300/min/user，开发 10000/min/user（避免测试 fixture 高频调用被打爆）
# 生产环境严守 V1.1 §3.5 第 2 档；nginx 层兜底
_DEFAULT_LIMIT = "300/minute" if settings.is_production else "10000/minute"

limiter = Limiter(
    key_func=_key_user_or_ip,
    default_limits=[_DEFAULT_LIMIT],
    storage_uri=settings.REDIS_URL,
    headers_enabled=True,  # 自动写 X-RateLimit-Limit / Remaining / Reset 三个 header
    strategy="fixed-window",
    enabled=settings.RATE_LIMIT_ENABLED,
)


# 开发环境放宽：测试 fixture 每个用例都 login，10/min/IP 会被打爆
# 生产仍严守 V1.1 §3.5 第 1 档（10/min/IP）— nginx 层兜底
_LOGIN_LIMIT = "10/minute" if settings.is_production else "1000/minute"
_PUBLIC_LIMIT = "10/minute" if settings.is_production else "1000/minute"


def login_rate_limit() -> Callable:
    """登录端点专用（V1.1 API §3.5 第 1 档）

    生产：10/min/IP；开发：1000/min/IP（测试 fixture 高频 login）
    """
    return limiter.limit(_LOGIN_LIMIT, key_func=_key_ip)


def public_rate_limit() -> Callable:
    """公开端点（refresh / 健康 / metrics 等）— 同登录档"""
    return limiter.limit(_PUBLIC_LIMIT, key_func=_key_ip)


__all__ = [
    "limiter",
    "login_rate_limit",
    "public_rate_limit",
    "SlowAPIMiddleware",
    "RateLimitExceeded",
]
