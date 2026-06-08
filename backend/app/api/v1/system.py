"""
/api/v1/system/info 系统元信息端点（V1.2 评审 API11:B 部分立即做）

返回：应用名 / 版本 / 环境 / 数据库连接状态 / 主要功能开关状态。
供前端 footer / 系统状态页 / 监控聚合调用。无需鉴权。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.responses import success

router = APIRouter()


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
