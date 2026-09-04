"""
/api/v1/system/info 系统元信息端点（V1.2 评审 API11:B 部分立即做）

返回：应用名 / 版本 / 环境 / 数据库连接状态 / 主要功能开关状态。
供前端 footer / 系统状态页 / 监控聚合调用。无需鉴权。
"""
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.responses import success
from app.domains.audit.models import AuditLog, ChangeHistory
from app.domains.auth.models import User
from app.domains.auth.schemas import SessionPolicyUpdate
from app.domains.auth.session_policy import (
    LIMITS,
    SessionPolicy,
    load_session_policy,
    save_session_policy,
)
from app.shared.audit_context import audit_request_id
from app.shared.permissions import require_permission

router = APIRouter()


# =============================================================================
# 会话策略（2026-09-04；migration 0054）—— 权限 system:config（SYS_ADMIN 短路）
# =============================================================================


@router.get("/session-policy", summary="会话策略（admin）")
async def get_session_policy(
    request: Request,
    user: User = Depends(require_permission("system:config")),
    db: AsyncSession = Depends(get_db),
):
    policy = await load_session_policy(db)
    return success(
        data={**policy.to_dict(), "limits": {k: list(v) for k, v in LIMITS.items()}},
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/session-policy", summary="修改会话策略（admin，立即生效）")
async def update_session_policy(
    payload: SessionPolicyUpdate,
    request: Request,
    user: User = Depends(require_permission("system:config")),
    db: AsyncSession = Depends(get_db),
):
    """四个时长整体提交（表单一次保存）。变更进 audit_log（UPDATE meta.system_config）。"""
    new = SessionPolicy(
        access_token_minutes=payload.access_token_minutes,
        idle_timeout_minutes=payload.idle_timeout_minutes,
        absolute_max_hours=payload.absolute_max_hours,
        display_mode_idle_minutes=payload.display_mode_idle_minutes,
    )
    saved, changes = await save_session_policy(db, new, updated_by=user.user_id)
    if changes:
        log = AuditLog(
            user_id=user.user_id,
            username=user.username,
            action="UPDATE",
            entity_schema="meta",
            entity_table="system_config",
            entity_code="session_policy",
            change_summary="; ".join(f"{f}: {o} → {n}" for f, o, n in changes),
            reason=payload.reason,
            ip_address=getattr(request.state, "ip_address", None),
            user_agent=getattr(request.state, "user_agent", None),
            request_id=audit_request_id.get(),
        )
        db.add(log)
        await db.flush()
        # 字段级 diff（与 audit trigger 写法一致：old/new 存 JSON 标量），审计页直接显示
        for field, old_v, new_v in changes:
            db.add(
                ChangeHistory(
                    audit_log_id=log.log_id,
                    field_name=field,
                    old_value=cast(Any, old_v),
                    new_value=cast(Any, new_v),
                )
            )
        await db.flush()
    # 强一致：策略改完必须落库后才返回（下一次登录/换证立即按新值）
    await db.commit()
    return success(
        data={**saved.to_dict(), "limits": {k: list(v) for k, v in LIMITS.items()}},
        message="会话策略已更新" if changes else "无变更",
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/info", summary="系统元信息")
async def get_system_info(request: Request, db: AsyncSession = Depends(get_db)):
    """系统元信息（version / env / 数据库连接 / config 摘要）"""
    # DB 健康（用 meta.system_config 简单 SELECT 验证）
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # 加载 system_config 几个公开项作为摘要（is_sensitive=FALSE）
    cfg_result = await db.execute(
        text(
            """
            SELECT config_key, config_value, value_type
              FROM meta.system_config
             WHERE is_sensitive = FALSE
             ORDER BY config_key
            """
        )
    )
    config_summary = {
        row.config_key: row.config_value for row in cfg_result.all()
    }

    return success(
        data={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": "development" if settings.APP_DEBUG else "production",
            "database": "ok" if db_ok else "error",
            "config_summary": config_summary,
        },
        request_id=getattr(request.state, "request_id", None),
    )
