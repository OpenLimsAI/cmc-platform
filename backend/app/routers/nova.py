"""只读接口：Nova FLEX2 生化分析仪趋势曲线。

数据源：cmc_analytics.mart.fact_nova（Nova Biomedical BioProfile FLEX2 生化分析，
rd-nova-etl 入库）。一行 = 某批次某罐在某培养天的一次取样（葡萄糖、乳酸、氨…）。
只读，绝不写入。所有查询走参数绑定。

术语（给非技术同事）：
- 批次（batch_key）= 项目编号_批号_罐号，如 0071_R2601_B2，与细胞生长曲线同一套身份。
- 培养天（culture_day）= 接种后第几天，趋势曲线的横轴。
- 指标：gluc 葡萄糖(g/L)、lac 乳酸(g/L)、gln 谷氨酰胺、glu 谷氨酸、nh4 氨(mmol/L)、
  na/k/ca 钠钾钙(mmol/L)、ph、po2/pco2 氧/二氧化碳分压(mmHg)。
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from ..db import analytics_engine

router = APIRouter(prefix="/api/nova", tags=["nova"])

SCHEMA = "mart"
VIEW = f"{SCHEMA}.fact_nova"

# 全部生化指标列（fact_nova 里的数值列），列表接口/序列接口共用。
METRICS = ["gluc", "lac", "gln", "glu", "nh4", "na", "k", "ca", "ph", "po2", "pco2"]

# 批次年份从批号解析（与 vicell.py 同规则）：R2601 -> 26 -> 2026。
# 多数批次没关联 dim_batch（batch_year 空），优先按批号算，回退 dim_batch，再回退取样时间年份。
_YEAR_EXPR = """
    coalesce(
        CASE WHEN min(batch_number) ~* '^R[0-9]{4}$'
             THEN 2000 + substring(min(batch_number) from 2 for 2)::int
             WHEN min(batch_number) ~ '^[0-9]{5}$'
             THEN 2000 + substring(min(batch_number) from 1 for 2)::int END,
        min(batch_year),
        extract(year FROM min(measured_at))::int
    )
"""


@router.get("/batches")
async def list_batches(limit: int = Query(5000, ge=1, le=20000)):
    """能画生化趋势的批次列表（有 culture_day 且能拆出 batch_key 的那部分）。

    每个 batch_key 聚合成一行，供前端级联筛选（项目→年份→罐）与列表使用。
    """
    sql = text(f"""
        SELECT
            batch_key,
            min(project_id)    AS project_id,
            min(batch_number)  AS batch_number,
            min(bioreactor_id) AS bioreactor_id,
            {_YEAR_EXPR}       AS batch_year,
            count(*)           AS n_samples,
            min(culture_day)   AS day_min,
            max(culture_day)   AS day_max,
            min(measured_at)   AS first_measured_at,
            bool_or(lucullus_procid IS NOT NULL) AS has_process_link
        FROM {VIEW}
        WHERE batch_key IS NOT NULL
          AND culture_day IS NOT NULL
        GROUP BY batch_key
        ORDER BY min(project_id), batch_year DESC NULLS LAST, min(bioreactor_id)
        LIMIT :lim
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"lim": limit})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["batch_year"] = int(d["batch_year"]) if d["batch_year"] is not None else None
        d["n_samples"] = int(d["n_samples"])
        d["day_min"] = int(d["day_min"]) if d["day_min"] is not None else None
        d["day_max"] = int(d["day_max"]) if d["day_max"] is not None else None
        out.append(d)
    return out


# 取样点在横轴上的位置：培养天 + 当天时刻占一天的比例（北京时间）。同一天两次取样 = 两个点，不平均。
_T_DAY = "culture_day + extract(epoch FROM (measured_at AT TIME ZONE 'Asia/Shanghai')::time) / 86400.0"


@router.get("/series")
async def get_series(batch_key: str = Query(..., description="批次身份，如 0071_R2601_B2")):
    """某批次的生化趋势：每次取样一个点，全部指标一次返回，前端勾选展示。

    t_day = 该点在横轴上的位置（培养天 + 当天时刻）。渗透压来自人工录入（只有"天"没有时刻），
    挂在当天第一次取样的点上；那天仪器没测、只录了渗透压的，单独出一个点放在当天中午（day + 0.5）。
    """
    cols = ", ".join(METRICS)
    sql = text(f"""
        WITH n AS (
            SELECT culture_day, {_T_DAY} AS t_day, {cols},
                   row_number() OVER (PARTITION BY culture_day ORDER BY measured_at, sample_result_id) AS rn
            FROM {VIEW}
            WHERE batch_key = :bk AND culture_day IS NOT NULL
        ),
        o AS (
            SELECT culture_day, value AS osmolality
            FROM mart.fact_manual_latest
            WHERE batch_key = :bk AND metric_code = 'osmolality'
        )
        SELECT n.culture_day, n.t_day, {", ".join("n." + m for m in METRICS)},
               CASE WHEN n.rn = 1 THEN o.osmolality END AS osmolality
        FROM n LEFT JOIN o ON o.culture_day = n.culture_day
        UNION ALL
        SELECT o.culture_day, o.culture_day + 0.5, {", ".join("NULL::double precision" for _ in METRICS)}, o.osmolality
        FROM o
        WHERE NOT EXISTS (SELECT 1 FROM n WHERE n.culture_day = o.culture_day)
        ORDER BY 2
    """)
    meta_sql = text(f"""
        SELECT
            min(project_id)    AS project_id,
            min(batch_number)  AS batch_number,
            min(bioreactor_id) AS bioreactor_id,
            count(*)           AS n_samples
        FROM {VIEW}
        WHERE batch_key = :bk
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"bk": batch_key})).mappings().all()
        meta = (await conn.execute(meta_sql, {"bk": batch_key})).mappings().first()

    if not rows:
        raise HTTPException(status_code=404, detail=f"没有该批次的生化数据：{batch_key}")

    def num(v):
        return float(v) if v is not None else None

    points = [
        {
            "culture_day": int(r["culture_day"]),
            "t_day": float(r["t_day"]),
            **{m: num(r[m]) for m in METRICS},
            "osmolality": num(r["osmolality"]),  # 人工录入，mOsm/kg
            "n": 1,
        }
        for r in rows
    ]
    return {
        "batch_key": batch_key,
        "project_id": meta["project_id"] if meta else None,
        "batch_number": meta["batch_number"] if meta else None,
        "bioreactor_id": meta["bioreactor_id"] if meta else None,
        "n_samples": int(meta["n_samples"]) if meta else 0,
        "metrics": METRICS + ["osmolality"],
        "points": points,
    }


@router.get("/samples")
async def get_samples(batch_key: str = Query(..., description="批次身份，如 0071_R2601_B2")):
    """某批次的取样记录明细（总览页明细表用）：每次取样一行，不按天聚合。"""
    cols = ",\n            ".join(METRICS)
    sql = text(f"""
        SELECT
            sample_result_id,
            sample_id,
            culture_day,
            measured_at,
            {cols},
            parse_status
        FROM {VIEW}
        WHERE batch_key = :bk
        ORDER BY measured_at
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"bk": batch_key})).mappings().all()

    def num(v):
        return float(v) if v is not None else None

    return [
        {
            "sample_result_id": int(r["sample_result_id"]),
            "sample_id": r["sample_id"],
            "culture_day": int(r["culture_day"]) if r["culture_day"] is not None else None,
            "measured_at": r["measured_at"].isoformat() if r["measured_at"] else None,
            **{m: num(r[m]) for m in METRICS},
            "parse_status": r["parse_status"],
        }
        for r in rows
    ]
