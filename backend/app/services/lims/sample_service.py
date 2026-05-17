# 样品服务层：所有数据库查询在此，route 层只调用服务方法
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lims.views import SampleOverview


async def get_sample_overview(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> tuple[int, list[SampleOverview]]:
    """分页查询 mart.v_sample_overview"""
    offset = (page - 1) * size

    total_result = await db.execute(select(func.count()).select_from(SampleOverview))
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(SampleOverview)
        .order_by(SampleOverview.received_dt.desc())
        .offset(offset)
        .limit(size)
    )
    rows = list(rows_result.scalars().all())

    return total, rows
