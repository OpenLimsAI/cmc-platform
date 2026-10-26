"""24 小时重复新增保护：成功结果与业务同事务保存，事务锁覆盖创建过程。"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, DuplicateRequestError, InvalidValueError
from app.core.redis_client import get_redis
from app.shared.idempotency_models import IdempotencyResult

IDEM_TTL_SECONDS = 24 * 60 * 60


def _canonical_body_hash(body: Any) -> str:
    blob = json.dumps(body or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _validate_key(key: str) -> UUID:
    try:
        return UUID(key)
    except ValueError as exc:
        raise InvalidValueError("Idempotency-Key 必须是合法 UUID 格式") from exc


class IdempotencyUnavailableError(AppError):
    code = 50301
    http_status = 503
    error_type = "service_unavailable"
    default_message = "提交结果暂时无法核对，请稍后使用同一提交编号重试"


class IdempotencyCacheHit:
    def __init__(self, status_code: int, body: dict, headers: dict[str, str]):
        self.status_code = status_code
        self.body = body
        self.headers = headers


class IdempotencyService:
    @staticmethod
    async def check(db: AsyncSession, user_id: int, idem_key: str, body: Any,
                    operation: str) -> IdempotencyCacheHit | None:
        key = _validate_key(idem_key)
        digest = hashlib.sha256(f"mdm:create:{user_id}:{key}".encode()).digest()
        lock_id = int.from_bytes(digest[:8], "big", signed=True)
        # 只等待保存中的同一提交；不是编辑占用锁。连接关闭/失败时自动释放。
        try:
            async with asyncio.timeout(5):
                while not (await db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id})).scalar_one():
                    await asyncio.sleep(0.05)
        except TimeoutError as exc:
            raise DuplicateRequestError("该提交正在处理中，请稍后使用同一提交编号重试") from exc
        row = (await db.execute(select(IdempotencyResult).where(
            IdempotencyResult.user_id == user_id, IdempotencyResult.request_key == key,
        ).execution_options(populate_existing=True))).scalar_one_or_none()
        if row is not None:
            if row.expires_at > datetime.now(UTC):
                if row.operation != operation or row.body_hash != _canonical_body_hash(body):
                    raise DuplicateRequestError("同一提交编号不能修改内容或用于另一种新增操作")
                return IdempotencyCacheHit(row.status_code, row.response_body, row.headers)
            # 已过固定窗口不再查旧缓存，也不因重复请求延长原窗口。
            return None
        # 兼容旧版 Redis 成功结果。无法读取时，在业务写入前明确失败。
        try:
            redis = get_redis()
            raw = await redis.get(f"idem:{user_id}:{idem_key}")
            if not raw:
                return None
            stored = json.loads(raw)
            location = (stored.get("headers") or {}).get("Location", "")
            if (stored.get("body_hash") != _canonical_body_hash(body)
                    or not location.startswith(f"/api/v1/{operation.split(':')[0]}/")):
                raise DuplicateRequestError("同一提交编号不能修改内容或用于另一种新增操作")
            ttl = await redis.ttl(f"idem:{user_id}:{idem_key}")
            if ttl <= 0:
                raise IdempotencyUnavailableError()
            await IdempotencyService.save(db, user_id, idem_key, body, operation,
                stored["status_code"], stored["response_body"], location,
                expires_at=datetime.now(UTC) + timedelta(seconds=min(ttl, IDEM_TTL_SECONDS)))
            return IdempotencyCacheHit(stored["status_code"], stored["response_body"], stored["headers"])
        except DuplicateRequestError:
            raise
        except Exception as exc:
            raise IdempotencyUnavailableError() from exc

    @staticmethod
    async def save(db: AsyncSession, user_id: int, idem_key: str, body: Any, operation: str,
                   status_code: int, response_body: dict, location: str | None = None,
                   *, expires_at: datetime | None = None) -> None:
        key = _validate_key(idem_key)
        row = await db.get(IdempotencyResult, (user_id, key))
        if row is None:
            row = IdempotencyResult(user_id=user_id, request_key=key)
            db.add(row)
        now = datetime.now(UTC)
        row.operation = operation
        row.body_hash = _canonical_body_hash(body)
        row.status_code = status_code
        row.response_body = json.loads(json.dumps(response_body, ensure_ascii=False, default=str))
        row.headers = {"Location": location} if location else {}
        row.created_at = now
        row.expires_at = expires_at or now + timedelta(seconds=IDEM_TTL_SECONDS)
        await db.flush()
