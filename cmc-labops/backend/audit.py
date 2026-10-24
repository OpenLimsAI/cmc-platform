"""
文件: backend/audit.py
用途: 审计日志写入 helper
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING

from fastapi import Request
from sqlalchemy.orm import Session

from models import AuditLog

if TYPE_CHECKING:
    from auth import CurrentUser

log = logging.getLogger("cmc-labops.audit")

SENSITIVE_KEYS = {"password", "password_hash", "old_password", "new_password", "token", "access_token"}


def _to_jsonable(v: Any) -> Any:
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
    if hasattr(v, "__table__"):
        return {
            col.name: _to_jsonable(getattr(v, col.name, None))
            for col in v.__table__.columns
            if col.name not in SENSITIVE_KEYS
        }
    return str(v)


def model_snapshot(obj) -> dict:
    return _to_jsonable(obj) or {}


def get_request_ip(request: Request) -> Optional[str]:
    ip = request.headers.get("X-Client-IP")
    if ip:
        return ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def write_audit(
    db: Session,
    user: Optional["CurrentUser"],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    source_ip: Optional[str] = None,
    fallback_username: Optional[str] = None,
    flush: bool = True,
) -> None:
    try:
        entry = AuditLog(
            user_id=user.user_id if user else None,
            username=user.username if user else fallback_username,
            full_name=(user.full_name or None) if user else None,
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
        log.exception("审计日志写入失败 action=%s entity=%s/%s",
                      action, entity_type, entity_id)
        raise
