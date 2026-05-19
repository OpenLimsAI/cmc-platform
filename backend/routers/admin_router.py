"""
文件: backend/routers/admin_router.py
用途: 管理员专属：审计日志查询
路径前缀: /api/audit
鉴权: require_admin（用户管理已移至 MDM Portal）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from auth import CurrentUser, require_admin
from database import get_db
from models import AuditLog
from schemas import AuditLogOut

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/audit/logs", response_model=List[AuditLogOut])
def list_audit_logs(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    since = datetime.now() - timedelta(days=days)
    stmt = select(AuditLog).where(AuditLog.created_at >= since)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if username:
        stmt = stmt.where(AuditLog.username == username)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == str(entity_id))
    stmt = stmt.order_by(desc(AuditLog.id)).limit(limit)
    return list(db.execute(stmt).scalars().all())
