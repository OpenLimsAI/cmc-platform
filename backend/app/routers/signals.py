"""只读接口：批次列表 / 批次通道 / 降采样时序曲线。

数据源：cmc_rd.raw_rd_usp_lucullus.signal_timeseries（+ process_src）。
只读，绝不写入。所有查询走参数绑定，避免 SQL 注入。
"""
import re

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..channel_dict import get_channel_dict
from ..db import engine

router = APIRouter(prefix="/api", tags=["signals"])

SCHEMA = "raw_rd_usp_lucullus"

# 批次名（procname）解析规则（负责人 2026-07 确认）。
# 分隔符 `_` 或空格都可能；字段从左到右：项目编号 / 批号 R+4位 / 实验目的(可选) / 罐号。
# 这里只解析看板筛选要用的两项：项目编号、批次年份。罐号一律以 reactor_name 列为权威。
_TOKEN_SPLIT = re.compile(r"[_\s]+")
_BATCH_NUMBER = re.compile(r"^R(\d{2})(\d{2})$", re.IGNORECASE)  # R2605 -> 年26 流水05


def parse_batch_name(
    procname: str | None, starttime
) -> tuple[str | None, int | None, str | None]:
    """从批次名解析 (项目编号, 批次年份, 批号)。

    - 项目编号：批次名第一段，纯数字才算，保留前导零当字符串（"016"≠"16"）；否则 None。
    - 批号：批次名里 R+4位 的那段（R2605），统一大写；没有则 None。
    - 批次年份：批号 R2605 的前两位 → 2026；批次名里没有 R+4位时，回退用开始时间的年份。
    解析不出来的批次（如 test610）项目编号 / 批号为 None，前端归入"未识别"。
    """
    project_code: str | None = None
    batch_year: int | None = None
    batch_number: str | None = None
    if procname:
        tokens = [t for t in _TOKEN_SPLIT.split(procname.strip()) if t]
        if tokens and tokens[0].isdigit():
            project_code = tokens[0]
        for t in tokens:
            m = _BATCH_NUMBER.match(t)
            if m:
                batch_number = t.upper()
                batch_year = 2000 + int(m.group(1))
                break
    if batch_year is None and starttime is not None:
        batch_year = starttime.year
    return project_code, batch_year, batch_number


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
    out = []
    for r in rows:
        d = dict(r)
        project_code, batch_year, batch_number = parse_batch_name(
            d.get("procname"), d.get("starttime")
        )
        d["project_code"] = project_code      # 项目编号（字符串，保留前导零），解析不出为 None
        d["batch_year"] = batch_year          # 批次年份（int）
        d["batch_number"] = batch_number      # 批号（R+4位，大写），解析不出为 None
        d["reactor"] = d.get("reactor_name")  # 罐号（以 reactor_name 列为权威）
        out.append(d)
    return out


@router.get("/batches/{source_instance}/{procid}/channels")
async def list_channels(source_instance: str, procid: int):
    """某批次有哪些通道，以及每个通道的点数、时间范围。

    并合并通道字典（cmc_analytics.dim.channel_dict）：display_name / category / sort_order 等。
    字典缺行或读不到时，display_name 回退为 channel_code，其余为 None——前端照常显示原始代号。
    """
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
    cdict = await get_channel_dict()
    out = []
    for r in rows:
        d = dict(r)
        meta = cdict.get(d["channel_code"])
        d["display_name"] = meta.display_name if meta else d["channel_code"]
        d["category"] = meta.category if meta else None
        d["canonical_key"] = meta.canonical_key if meta else None
        d["is_preferred"] = meta.is_preferred if meta else True
        d["sort_order"] = meta.sort_order if meta else 9999
        d["notes"] = meta.notes if meta else None
        out.append(d)
    out.sort(key=lambda d: (d["sort_order"], d["channel_code"]))
    return out


@router.get("/channel-dict")
async def channel_dict():
    """通道字典全表（cmc_analytics.dim.channel_dict）。未配置 analytics 连接时返回空列表。"""
    cdict = await get_channel_dict()
    return sorted((m.__dict__ for m in cdict.values()), key=lambda m: (m["sort_order"], m["channel_code"]))


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
