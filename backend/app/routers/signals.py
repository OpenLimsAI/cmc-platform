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
        WHERE (:si IS NULL OR p.source_instance = :si)
          AND (:yr IS NULL OR to_char(p.starttime, 'YYYY') = :yr)
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
):
    """某批次某通道的曲线，按时间分桶取平均降采样（画图友好）。"""
    sql = text(f"""
        WITH base AS (
            SELECT time_hours, timestamp_from_starttime, value,
                   ntile(:maxp) OVER (ORDER BY time_hours) AS bkt
            FROM {SCHEMA}.signal_timeseries
            WHERE source_instance = :si AND procid = :pid AND channel_code = :ch
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
            sql, {"si": source_instance, "pid": procid, "ch": channel, "maxp": max_points}
        )).mappings().all()
    return {
        "source_instance": source_instance,
        "procid": procid,
        "channel": channel,
        "points": [
            {"time_hours": float(r["time_hours"]), "ts": r["ts"], "value": float(r["value"])}
            for r in rows if r["value"] is not None
        ],
    }
