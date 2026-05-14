"""Idempotency-Key 服务（V1.1 API §3.4 + API7）

设计要点：
  - 仅 POST 创建端点用；GET/PUT/DELETE 天然幂等
  - 客户端在请求头带 `Idempotency-Key: <uuid>`；24h 窗口
  - Redis key 命名：`idem:{user_id}:{idempotency_key}`
  - 存储格式：JSON {body_hash, status_code, response_body, headers}
  - 行为：
    * 没 key → 不走幂等，正常处理
    * 有 key + Redis 未命中 → 处理业务 → 缓存（含 location header）
    * 有 key + Redis 命中 + body_hash 一致 → 直接返回缓存（与首次响应字节级一致）
    * 有 key + Redis 命中 + body_hash 不一致 → 抛 40905 `duplicate_request`

并发安全（同 key 同时发两次相同请求）：
  在 store 阶段用 SETNX 抢锁；冲突时第二个请求等待 short retry 后读 cached。
  当前最简实现：不做并发保护，由"完成请求后再写 Redis"自然规避大多数场景；如有严格要求
  后续可改 setnx + 短轮询。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from loguru import logger

from app.core.exceptions import DuplicateRequestError, InvalidValueError
from app.core.redis_client import get_redis

# 24 小时 TTL（V1.1 API §3.4 "24 小时窗口"）
IDEM_TTL_SECONDS = 24 * 60 * 60


def _canonical_body_hash(body: Any) -> str:
    """对 body 计算稳定哈希。dict 用 sort_keys 保证字段顺序不影响 hash。"""
    if body is None:
        body = {}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _validate_key(key: str) -> None:
    """V1.1 §3.4 示例是 UUID。严格校验避免误用作 key 注入。"""
    try:
        UUID(key)
    except ValueError as e:
        raise InvalidValueError("Idempotency-Key 必须是合法 UUID 格式") from e


def _redis_key(user_id: int, idem_key: str) -> str:
    return f"idem:{user_id}:{idem_key}"


class IdempotencyCacheHit:
    """命中缓存返回结构"""

    def __init__(self, status_code: int, body: dict, headers: dict[str, str]):
        self.status_code = status_code
        self.body = body
        self.headers = headers


class IdempotencyService:
    """Idempotency-Key 24h 窗口持久化（Redis）"""

    @staticmethod
    async def check(
        user_id: int,
        idem_key: str,
        body: Any,
    ) -> IdempotencyCacheHit | None:
        """查 Redis；命中且 body 一致返回缓存；命中但 body 不一致抛 40905"""
        _validate_key(idem_key)
        redis = get_redis()
        rkey = _redis_key(user_id, idem_key)
        raw = await redis.get(rkey)
        if not raw:
            return None
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Idempotency 缓存值非法 JSON: {rkey}")
            return None

        body_hash = _canonical_body_hash(body)
        if stored.get("body_hash") != body_hash:
            raise DuplicateRequestError(
                "幂等键已使用但请求体不同（同一 Idempotency-Key 必须配相同 body）"
            )
        return IdempotencyCacheHit(
            status_code=stored.get("status_code", 200),
            body=stored.get("response_body", {}),
            headers=stored.get("headers", {}),
        )

    @staticmethod
    async def save(
        user_id: int,
        idem_key: str,
        body: Any,
        status_code: int,
        response_body: dict,
        location: str | None = None,
    ) -> None:
        """写入 24h 窗口缓存"""
        _validate_key(idem_key)
        redis = get_redis()
        rkey = _redis_key(user_id, idem_key)
        payload = {
            "body_hash": _canonical_body_hash(body),
            "status_code": status_code,
            "response_body": response_body,
            "headers": {"Location": location} if location else {},
        }
        await redis.setex(
            rkey,
            IDEM_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False, default=str),
        )
