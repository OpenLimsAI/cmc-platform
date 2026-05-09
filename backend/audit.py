"""
文件: backend/audit.py
用途: 审计日志写入 helper
原则:
    - 调用方提供 before / after dict;helper 自动 sanitize 敏感字段
    - 与业务事务**同 session**,业务回滚的话审计也回滚(避免假记录)
    - 写入失败不应让业务接口 500;仅 log.exception
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from models import AppUser, AuditLog

log = logging.getLogger("cmc-inventory.audit")

SENSITIVE_KEYS = {"password", "password_hash", "old_password", "new_password", "token", "access_token"}


def _to_jsonable(v: Any) -> Any:
    """SQLAlchemy ORM 对象 / Decimal / date / datetime → JSON-safe。"""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _to_jsonable(val) for k, val in v.items() if k not in SENSITIVE_KEYS}
    if isinstance(v, (list, tuple, set)):
        return [_to_jsonable(x) for x in v]
    # ORM 对象:取所有 column 值
    if hasattr(v, "__table__"):
        return {
            col.name: _to_jsonable(getattr(v, col.name, None))
            for col in v.__table__.columns
            if col.name not in SENSITIVE_KEYS
        }
    return str(v)


def model_snapshot(obj) -> dict:
    """业务对象的"前/后"快照,用于 audit_log。"""
    return _to_jsonable(obj) or {}


def write_audit(
    db: Session,
    user: Optional[AppUser],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    source_ip: Optional[str] = None,
    flush: bool = True,
) -> None:
    """写一条审计日志。
    flush=True 时只 flush 不 commit,跟随业务事务一起 commit 才落盘
    (业务方一般在调用 helper 后再 db.commit())。
    """
    try:
        entry = AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before_json=_to_jsonable(before) if before is not None else None,
            after_json=_to_jsonable(after) if after is not None else None,
            source_ip=source_ip,
        )
        db.add(entry)
        if flush:
            db.flush()
    except Exception:
        # 审计失败不应阻塞业务;但要记 log
        log.exception("审计日志写入失败 action=%s entity=%s/%s",
                      action, entity_type, entity_id)
