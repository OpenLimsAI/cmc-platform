"""
文件: backend/routers/admin_router.py
用途: 管理员专属:用户 CRUD + 审计日志查询
路径前缀: /api/users + /api/audit
鉴权: 所有 endpoint require_admin
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit import model_snapshot, write_audit
from auth import (
    hash_password,
    require_admin,
    revoke_all_user_sessions,
)
from database import get_db
from models import AppUser, AuditLog
from schemas import (
    AdminResetPasswordRequest,
    AuditLogOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/api", tags=["admin"])


# ---------------------------------------------------------------------------
# 用户管理
# ---------------------------------------------------------------------------
@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_admin),
):
    return db.execute(select(AppUser).order_by(AppUser.id)).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.execute(select(AppUser).where(AppUser.username == payload.username)).first():
        raise HTTPException(status_code=400, detail=f"用户名 {payload.username} 已存在")
    obj = AppUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        must_change_password=True,  # 新建用户首次登录强制改密
    )
    db.add(obj)
    db.flush()
    write_audit(
        db, current, "user.create",
        entity_type="app_user", entity_id=obj.id,
        before=None,
        after={"username": obj.username, "role": obj.role, "must_change_password": True},
        source_ip=request.client.host if request.client else None,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="用户名冲突")
    db.refresh(obj)
    return obj


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(AppUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == current.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="不能停用自己当前登录的账号")
    if target.username == "admin" and payload.role == "user" and current.id == target.id:
        # 防止把自己从 admin 降级导致没人能管
        raise HTTPException(status_code=400, detail="不能把自己从 admin 降级")

    before = {
        "username": target.username,
        "role": target.role,
        "is_active": target.is_active,
    }
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active

    write_audit(
        db, current, "user.update",
        entity_type="app_user", entity_id=user_id,
        before=before,
        after={"role": target.role, "is_active": target.is_active},
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    # 改了 role / is_active 后,踢掉该用户已有 session,强制重新登录加载新权限
    revoke_all_user_sessions(db, user_id)
    db.refresh(target)
    return target


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def admin_reset_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    request: Request,
    current: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员重置某用户密码;默认勾选首次登录强制改密。"""
    target = db.get(AppUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    target.password_hash = hash_password(payload.new_password)
    target.must_change_password = bool(payload.require_change_on_login)
    write_audit(
        db, current, "user.reset_password",
        entity_type="app_user", entity_id=user_id,
        before=None,
        after={
            "username": target.username,
            "must_change_password": target.must_change_password,
        },
        source_ip=request.client.host if request.client else None,
    )
    db.commit()
    # 撤销该用户所有 session
    revoke_all_user_sessions(db, user_id)
    db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# 审计日志查询
# ---------------------------------------------------------------------------
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
    _: AppUser = Depends(require_admin),
):
    """近 days 天的审计日志;过滤维度:用户、动作、实体。"""
    since = datetime.utcnow() - timedelta(days=days)
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
