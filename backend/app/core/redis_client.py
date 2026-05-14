"""Redis async client（P4.B 仅用于限流计数器 + Idempotency-Key 24h 窗口）

V1.1 ARCH §7.2.1 line 912 / 1030 / 1381 把 Redis 完整应用层接入定为 Phase 5（缓存层 +
JWT 黑名单等）。Phase 4.B 仅为下面两个用例提前接入 redis-py client，**不引入业务缓存**：

  1. slowapi rate-limit storage（key: `LIMITER/...`，slowapi 自管）
  2. IdempotencyService 的 24h 窗口（key: `idem:{user_id}:{idempotency_key}`）

后续 Phase 5 上业务缓存时，可继续复用此 client；如改 Redis Cluster / Sentinel，只
需在 redis_from_url 处替换。
"""
from typing import Optional

import redis.asyncio as redis_async
from loguru import logger

from app.core.config import settings

_client: Optional[redis_async.Redis] = None


def get_redis() -> redis_async.Redis:
    """获取全局 redis client（lifespan 已初始化）"""
    if _client is None:
        raise RuntimeError("Redis client not initialized. Did lifespan run?")
    return _client


async def init_redis() -> None:
    """应用启动时建立 Redis 连接并 PING 验证"""
    global _client
    if _client is not None:
        return
    _client = redis_async.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    try:
        pong = await _client.ping()
        if pong is not True:
            raise RuntimeError(f"Redis PING 返回异常值: {pong}")
        logger.info(f"✓ Redis 连接已就绪 → {settings.REDIS_URL}")
    except Exception as e:
        logger.error(f"Redis 连接失败: {e}")
        # 不直接抛出 — 让应用继续启动；限流/幂等会在调用点降级（fail-open）
        # 但 dev 阶段为快速暴露问题，仍 raise
        raise


async def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception as e:
            logger.warning(f"Redis close 异常: {e}")
        finally:
            _client = None
