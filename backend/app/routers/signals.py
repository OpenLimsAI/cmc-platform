"""只读接口：批次列表 / 批次通道 / 降采样时序曲线。

数据源：cmc_rd.raw_rd_usp_lucullus.signal_timeseries（+ process_src）。
只读，绝不写入。所有查询走参数绑定，避免 SQL 注入。
"""
import re

from fastapi import APIRouter, Query
from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY

from ..channel_dict import get_channel_dict
from ..db import engine

router = APIRouter(prefix="/api", tags=["signals"])

SCHEMA = "raw_rd_usp_lucullus"

# 批次名（procname）解析规则（负责人 2026-07 确认）。
# 分隔符 `_` 或空格都可能；字段从左到右：项目编号 / 批号 R+4位 / 实验目的(可选) / 罐号。
# 这里只解析看板筛选要用的两项：项目编号、批次年份。罐号一律以 reactor_name 列为权威。
_TOKEN_SPLIT = re.compile(r"[-_\s]+")  # 登记系统新规则批次名用 - 分隔（016-26003-A8）
_BATCH_NUMBER = re.compile(r"^R(\d{2})(\d{2})$", re.IGNORECASE)  # R2605 -> 年26 流水05
# 登记系统新批号 YYSEQ：年 2 位 + 全实验室年流水 3 位，如 26003 -> 年26 流水003
_BATCH_NUMBER_V2 = re.compile(r"^(\d{2})(\d{3})$")


def parse_batch_name(
    procname: str | None, starttime
) -> tuple[str | None, int | None, str | None]:
    """从批次名解析 (项目编号, 批次年份, 批号)。

    - 项目编号：批次名第一段，纯数字才算，保留前导零当字符串（"016"≠"16"）；否则 None。
    - 批号：批次名里 R+4位 的那段（R2605）或登记系统新批号 5 位 YYSEQ（26003）；没有则 None。
    - 批次年份：R2605 取第 2~3 位 → 2026；26003 取前两位 → 2026；都没有时回退用开始时间的年份。
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
            m = _BATCH_NUMBER.match(t) or _BATCH_NUMBER_V2.match(t)
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
        d["is_active"] = meta.is_active if meta else True  # false = 字典标记为看板不列（冗余通道）
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


# ---------------------------------------------------------------------------
# 工艺参数按时段汇总（看板「工艺参数（按时段）」板块，2026-09-08 起）
# ---------------------------------------------------------------------------
# 直接从原始时序按「每 N 小时一格」算平均 / 最低 / 末值，不依赖 ETL 的日均表
# （mart.fact_process_daily 只有一天一个点且只认 ws01 的通道名）。
# 指标 → 通道的对应关系按通道字典的 canonical_key（同一物理量跨工作站归并）；
# 字典读不到时退回到写死的兜底通道名。
_BUCKET_METRICS: list[dict] = [
    # code：前端指标键；name/unit：显示；key：字典 canonical_key；agg：时段内怎么汇总
    {"code": "temp_c", "name": "温度", "unit": "°C", "key": "temp", "agg": "avg", "fallback": ["m_temp"]},
    {"code": "ph", "name": "pH", "unit": "", "key": "ph", "agg": "avg", "fallback": ["m_ph"]},
    {"code": "do_pct", "name": "溶氧", "unit": "%", "key": "do", "agg": "avg", "fallback": ["m_do"]},
    {"code": "do_pct_min", "name": "溶氧最低", "unit": "%", "key": "do", "agg": "min", "fallback": ["m_do"]},
    {"code": "stirrer_rpm", "name": "搅拌", "unit": "rpm", "key": "stirrer", "agg": "avg", "fallback": ["m_stirrer"]},
    {"code": "air_surface", "name": "空气(表层)", "unit": "mL/min", "key": "mfc1_flow", "agg": "avg", "fallback": ["m_mfc1"]},
    {"code": "air_sparge", "name": "空气(深层)", "unit": "mL/min", "key": "mfc2_flow", "agg": "avg", "fallback": ["m_mfc2", "m_air2", "m_air"]},
    {"code": "o2", "name": "O₂(0-1000)", "unit": "mL/min", "key": "mfc3_flow", "agg": "avg", "fallback": ["m_mfc3", "m_o2"]},
    {"code": "o2_low", "name": "O₂(0-100)", "unit": "mL/min", "key": "mfc5_flow", "agg": "avg", "fallback": ["m_mfc5"]},
    {"code": "co2", "name": "CO₂", "unit": "mL/min", "key": "mfc4_flow", "agg": "avg", "fallback": ["m_mfc4", "m_co2"]},
    {"code": "alkali_cum", "name": "加碱累计", "unit": "mL", "key": "dpump2_total", "agg": "last", "fallback": ["dm_dpump2", "dm_alkali"]},
    {"code": "acid_cum", "name": "加酸累计", "unit": "mL", "key": None, "agg": "last", "fallback": ["dm_acid"]},
]


def _metric_codes(cdict) -> dict[str, list[str]]:
    """每个指标可用的通道名列表（首选通道排前面）。"""
    out: dict[str, list[str]] = {}
    for m in _BUCKET_METRICS:
        codes: list[str] = []
        if m["key"] and cdict:
            hits = [c for c in cdict.values() if c.canonical_key == m["key"] and c.is_active]
            hits.sort(key=lambda c: (not c.is_preferred, c.sort_order))
            codes = [c.channel_code for c in hits]
        for fb in m["fallback"]:
            if fb not in codes:
                codes.append(fb)
        out[m["code"]] = codes
    return out


@router.get("/process-bucketed")
async def get_process_bucketed(
    source_instance: str = Query(..., description="Lucullus 工作站编码，如 rd_ws01_usp_lucullus_01"),
    procid: int = Query(..., description="工艺批次编号（Lucullus procid）"),
    bucket_hours: float = Query(6, gt=0, le=24, description="每格几小时：24 / 12 / 6 / 3 / 1"),
):
    """某工艺批次的常用工艺参数，按「每 bucket_hours 小时一格」汇总。

    返回 points：每格一行，culture_day = 该格起点换算成的培养天（6h 一格就是 0、0.25、0.5…），
    好和生长 / 生化曲线（按培养天）叠在同一横轴上。
    平均类指标取格内平均；溶氧最低取格内最低；加碱 / 加酸累计取格内末值（累计量本身单调）。
    没数据返回空 points，不报错。
    """
    cdict = await get_channel_dict()
    codes_by_metric = _metric_codes(cdict)
    all_codes = sorted({c for cs in codes_by_metric.values() for c in cs})
    sql = text(f"""
        SELECT channel_code,
               floor(time_hours / :bh)::int AS bkt,
               avg(value) AS v_avg,
               min(value) AS v_min,
               max(value) AS v_max,
               count(*)   AS n
        FROM {SCHEMA}.signal_timeseries
        WHERE source_instance = :si AND procid = :pid
          AND channel_code = ANY(:codes)
          AND time_hours >= 0
        GROUP BY channel_code, bkt
        ORDER BY bkt
    """).bindparams(bindparam("codes", type_=ARRAY(String())))
    async with engine().connect() as conn:
        rows = (await conn.execute(
            sql, {"si": source_instance, "pid": procid, "bh": bucket_hours, "codes": all_codes}
        )).mappings().all()

    # 按通道分桶：{channel_code: {bkt: row}}
    by_code: dict[str, dict[int, dict]] = {}
    for r in rows:
        by_code.setdefault(r["channel_code"], {})[int(r["bkt"])] = r

    # 每个指标挑一个实际存在的通道（首选在前）
    chosen: dict[str, str] = {}
    for m in _BUCKET_METRICS:
        for c in codes_by_metric[m["code"]]:
            if c in by_code:
                chosen[m["code"]] = c
                break

    buckets = sorted({b for c in chosen.values() for b in by_code[c]})
    points = []
    for b in buckets:
        p: dict = {
            "bucket": b,
            "time_hours": b * bucket_hours,
            "culture_day": b * bucket_hours / 24,
        }
        for m in _BUCKET_METRICS:
            c = chosen.get(m["code"])
            r = by_code[c].get(b) if c else None
            if r is None:
                p[m["code"]] = None
                continue
            v = {"avg": r["v_avg"], "min": r["v_min"], "last": r["v_max"]}[m["agg"]]
            p[m["code"]] = float(v) if v is not None else None
        points.append(p)

    return {
        "source_instance": source_instance,
        "procid": procid,
        "bucket_hours": bucket_hours,
        "metrics": [
            {"code": m["code"], "name": m["name"], "unit": m["unit"], "agg": m["agg"], "channel": chosen.get(m["code"])}
            for m in _BUCKET_METRICS
        ],
        "points": points,
    }
