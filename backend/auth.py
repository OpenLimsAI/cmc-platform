"""
文件: backend/auth.py
用途: 认证与鉴权基础设施
    - 密码 hash / 校验(bcrypt)
    - 随机 token 生成 + DB 落库
    - FastAPI 依赖:current_user / require_admin
    - 首次启动用 ADMIN_INITIAL_PASSWORD 自动建 admin

约束:
    - token 走 Authorization: Bearer <token> header
    - session 10 分钟"无操作"过期(滑动):每次鉴权调用刷新 last_seen_at +
      expires_at;前端把 token 存在浏览器 localStorage 里,刷新页面不会
      重新登录,但 10 分钟没有任何 API 调用 → 后端 401 → 前端弹登录框
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import get_request_ip
from database import get_db
from models import AppUser, AuthSession

SESSION_DURATION = timedelta(minutes=10)
TOKEN_BYTES = 32  # 32 bytes → 64 hex chars,与 schema 匹配


# ---------------------------------------------------------------------------
# 密码 hash
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """bcrypt hash;cost 默认 12 轮。"""
    if not plain:
        raise ValueError("密码不能为空")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Token 生成 / 校验
# ---------------------------------------------------------------------------
def issue_session(db: Session, user: AppUser, source_ip: Optional[str] = None) -> AuthSession:
    """为登录用户签发新 session token,落库。"""
    token = secrets.token_hex(TOKEN_BYTES)
    now = datetime.now()
    sess = AuthSession(
        token=token,
        user_id=user.id,
        created_at=now,
        expires_at=now + SESSION_DURATION,
        last_seen_at=now,
        source_ip=source_ip,
    )
    db.add(sess)
    user.last_login_at = now
    db.commit()
    db.refresh(sess)
    return sess


def revoke_session(db: Session, token: str) -> None:
    """主动失效(用户登出 / 管理员强退)。"""
    sess = db.get(AuthSession, token)
    if sess:
        db.delete(sess)
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: int) -> int:
    """踢掉某用户所有会话(改密 / 停用 / 强退)。返回删除条数。"""
    rows = db.execute(
        select(AuthSession).where(AuthSession.user_id == user_id)
    ).scalars().all()
    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return n


def cleanup_expired_sessions(db: Session) -> int:
    """删过期 session(可由定时任务/管理页触发,不是必须)。"""
    now = datetime.now()
    rows = db.execute(
        select(AuthSession).where(AuthSession.expires_at < now)
    ).scalars().all()
    for r in rows:
        db.delete(r)
    db.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# FastAPI 依赖:从 Authorization header 解析 token,返回 AppUser
# ---------------------------------------------------------------------------
def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> AppUser:
    """需要登录的接口都依赖这个。token 失效 → 401。"""
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="未登录,请提供 Authorization: Bearer <token>")
    sess = db.get(AuthSession, token)
    if not sess:
        raise HTTPException(status_code=401, detail="会话不存在或已登出,请重新登录")
    now = datetime.now()
    if sess.expires_at < now:
        # 顺手清掉
        db.delete(sess)
        db.commit()
        raise HTTPException(status_code=401, detail="会话已过期,请重新登录")
    user = db.get(AppUser, sess.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="账号已停用")

    # 续期:每次成功鉴权刷新 last_seen_at 与 expires_at
    sess.last_seen_at = now
    sess.expires_at = now + SESSION_DURATION
    db.commit()

    # 把 source_ip 在首次见到时记录(中途变化不动,用作粗略审计)
    if not sess.source_ip:
        ip = get_request_ip(request)
        if ip:
            sess.source_ip = ip
            db.commit()

    return user


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[AppUser]:
    """匿名也允许的场景使用(目前没有,但留口子)。"""
    token = _extract_token(authorization)
    if not token:
        return None
    sess = db.get(AuthSession, token)
    if not sess or sess.expires_at < datetime.now():
        return None
    user = db.get(AppUser, sess.user_id)
    return user if user and user.is_active else None


def require_admin(current: AppUser = Depends(get_current_user)) -> AppUser:
    """需要 admin 角色的接口依赖这个。"""
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="此操作仅管理员可执行")
    return current


def require_password_not_pending(current: AppUser = Depends(get_current_user)) -> AppUser:
    """要求用户已完成首次改密。除 /api/auth/change-password 与 /me 外其他接口都依赖这个,
    防止 must_change_password=True 的用户绕开强制改密流程。"""
    if current.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="首次登录需修改密码,请调用 /api/auth/change-password",
        )
    return current


# ---------------------------------------------------------------------------
# 启动时初始化 admin
# ---------------------------------------------------------------------------
def ensure_initial_admin(db: Session) -> Optional[AppUser]:
    """app_user 为空时,用 ADMIN_INITIAL_PASSWORD 自动建 admin。
    若 .env 没设这个变量,跳过(此时部署者必须自己在数据库里建第一个 admin)。
    """
    if db.execute(select(AppUser).limit(1)).first():
        return None
    init_pwd = os.getenv("ADMIN_INITIAL_PASSWORD")
    if not init_pwd:
        return None
    admin = AppUser(
        username="admin",
        password_hash=hash_password(init_pwd),
        role="admin",
        is_active=True,
        must_change_password=True,  # 首次登录强制改密
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
