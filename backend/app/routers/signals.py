"""只读接口：批次列表 / 批次通道 / 降采样时序曲线。

数据源：cmc_rd.raw_rd_usp_lucullus.signal_timeseries（+ process_src）。
只读，绝不写入。所有查询走参数绑定，避免 SQL 注入。
"""
from fastapi import APIRouter, Query
from sqlalchemy import text

from ..db import engine

router = APIRouter(prefix="/api", tags=["signals"])

SCHEMA = "raw_rd_usp_lucullus"


@router.get("/batches")
async def list_batches(
    source_instance: str | None = Query(None, description="按工作站过滤，如 rd_ws01_usp_lucullus_01"),
    year: str | None = Query(None, description="按批次开始年过滤，如 2025"),
    limit: int = Query(200, ge=1, le=1000),
):
    """有时序数据的批次列表（含批次名、反应器、起止时间）。"""
    sql = text(f"""
        SELECT
            p.source_instance,
            p.procid,
            p.procname,
            p.starttime,
            p.endtime,
            (SELECT s.reactor_name FROM {SCHEMA}.signal_timeseries s
              WHERE s.source_instance = p.source_instance AND s.procid = p.procid
              LIMIT 1) AS reactor_name
        FROM {SCHEMA}.process_src p
        WHERE (cast(:si AS text) IS NULL OR p.source_instance = cast(:si AS text))
          AND (cast(:yr AS text) IS NULL OR to_char(p.starttime, 'YYYY') = cast(:yr AS text))
          AND EXISTS (
              SELECT 1 FROM {SCHEMA}.signal_timeseries s
              WHERE s.source_instance = p.source_instance AND s.procid = p.procid
          )
        ORDER BY p.starttime DESC NULLS LAST
        LIMIT :lim
    """)
    async with engine().connect() as conn:
        rows = (await conn.execute(sql, {"si": source_instance, "yr": year, "lim": limit})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/batches/{source_instance}/{procid}/channels")
async def list_channels(source_instance: str, procid: int):
    """某批次有哪些通道，以及每个通道的点数、时间范围。"""
    sql = text(f"""
        SELECT channel_code, channel_name, unitsymbol,
               count(*) AS n_points,
               min(time_hours) AS t_min_h, max(time_hours) AS t_max_h
        FROM {SCHEMA}.signal_timeseries
        WHERE source_instance = :si AND procid = :pid
        GROUP BY channel_code, channel_name, unitsymbol
        ORDER BY channel_code
    """)
    async with engine().connect() as conn:
        rows = (await conn.execute(sql, {"si": source_instance, "pid": procid})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/series")
async def get_series(
    source_instance: str = Query(...),
    procid: int = Query(...),
    channel: str = Query(..., description="通道短名，如 m_temp"),
    max_points: int = Query(2000, ge=50, le=20000, description="降采样后最多返回点数"),
    t_min: float | None = Query(None, description="只取该相对小时数之后的点（放大查看时用）"),
    t_max: float | None = Query(None, description="只取该相对小时数之前的点（放大查看时用）"),
):
    """某批次某通道的曲线，按时间分桶取平均降采样（画图友好）。

    传 t_min/t_max 可只取某个时间窗口 → 放大时后端只对可见段抽稀，
    始终最多返回 max_points 个点，前端渲染量恒定、不会越放大越卡。
    """
    sql = text(f"""
        WITH win AS (
            SELECT time_hours, timestamp_from_starttime, value
            FROM {SCHEMA}.signal_timeseries
            WHERE source_instance = :si AND procid = :pid AND channel_code = :ch
              AND (cast(:tmin AS double precision) IS NULL OR time_hours >= cast(:tmin AS double precision))
              AND (cast(:tmax AS double precision) IS NULL OR time_hours <= cast(:tmax AS double precision))
        ),
        base AS (
            SELECT time_hours, timestamp_from_starttime, value,
                   ntile(:maxp) OVER (ORDER BY time_hours) AS bkt
            FROM win
        )
        SELECT min(time_hours) AS time_hours,
               min(timestamp_from_starttime) AS ts,
               avg(value) AS value,
               count(*) AS n
        FROM base
        GROUP BY bkt
        ORDER BY bkt
    """)
    async with engine().connect() as conn:
        rows = (await conn.execute(
            sql,
            {
                "si": source_instance, "pid": procid, "ch": channel,
                "maxp": max_points, "tmin": t_min, "tmax": t_max,
            },
        )).mappings().all()
    points = [
        {"time_hours": float(r["time_hours"]), "ts": r["ts"], "value": float(r["value"])}
        for r in rows if r["value"] is not None
    ]
    raw_count = sum(int(r["n"]) for r in rows)
    return {
        "source_instance": source_instance,
        "procid": procid,
        "channel": channel,
        "raw_count": raw_count,        # 该窗口内的原始采集点数
        "returned": len(points),        # 抽稀后实际返回的点数
        "points": points,
    }
