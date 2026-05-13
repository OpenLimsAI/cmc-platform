"""
/api/v1/lookups/{type} 字典查询端点

V1.2 评审 API11:B（部分立即做）：从 meta.lookup_value 表读 enum 字典；
返回某个 lookup_type 的所有活跃条目（is_active = TRUE，按 sort_order 升序）。

供前端表单 / 列表 select 选项使用。无需鉴权（只读字典）。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import success

router = APIRouter()


@router.get("/{lookup_type}", summary="字典查询 (lookup_value)")
async def get_lookup_values(
    lookup_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """按 lookup_type 返回活跃字典项（is_active=TRUE）"""
    result = await db.execute(
        text(
            """
            SELECT lookup_code, lookup_name, lookup_name_en, sort_order, description
              FROM meta.lookup_value
             WHERE lookup_type = :lt AND is_active = TRUE
             ORDER BY sort_order ASC, lookup_id ASC
            """
        ),
        {"lt": lookup_type},
    )
    items = [
        {
            "code": row.lookup_code,
            "name": row.lookup_name,
            "name_en": row.lookup_name_en,
            "sort_order": row.sort_order,
            "description": row.description,
        }
        for row in result.all()
    ]
    return success(
        data=items,
        message=f"lookup_type={lookup_type} 共 {len(items)} 项",
        request_id=getattr(request.state, "request_id", None),
    )
