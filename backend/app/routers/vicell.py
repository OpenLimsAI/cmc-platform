"""只读接口：Vi-CELL 细胞计数生长曲线。

数据源：cmc_analytics.mart.fact_vicell（Beckman Vi-CELL XR 细胞计数，rd-vicell-etl 入库）。
一行 = 某批次某罐在某培养天的一次取样（活细胞密度、活率、直径…）。
只读，绝不写入。所有查询走参数绑定。

术语（给非技术同事）：
- 批次（batch_key）= 项目编号_批号_罐号，如 0071_R2601_B2，是一条生长曲线的唯一身份。
- 培养天（culture_day）= 接种后第几天，做生长曲线的横轴。
- 活细胞密度（viable_per_ml，×10⁶/ml）、活率（viability_pct，%）= 两条纵轴。
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from ..db import analytics_engine

router = APIRouter(prefix="/api/vicell", tags=["vicell"])

SCHEMA = "mart"
VIEW = f"{SCHEMA}.fact_vicell"

# 批次年份从批号解析（与 signals.py 同规则）：R2601 -> 26 -> 2026。
# 大多数 Vi-CELL 批次没关联到工艺维度 dim_batch，其 batch_year 列为空，
# 所以优先按批号算，回退 dim_batch.batch_year，再回退取样日期年份。
_YEAR_EXPR = """
    coalesce(
        CASE WHEN min(batch_number) ~* '^R[0-9]{4}$'
             THEN 2000 + substring(min(batch_number) from 2 for 2)::int END,
        min(batch_year),
        extract(year FROM min(run_date))::int
    )
"""


@router.get("/batches")
async def list_batches(limit: int = Query(5000, ge=1, le=20000)):
    """能画生长曲线的批次列表（有 culture_day 且能拆出 batch_key 的那部分）。

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
            min(run_date)      AS first_run_date,
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


@router.get("/growth")
async def get_growth(batch_key: str = Query(..., description="批次身份，如 0071_R2601_B2")):
    """某批次按培养天的生长曲线：活细胞密度 + 活率（+ 总密度、直径）。

    同一培养天若有多次取样则取平均，得到干净的一天一点曲线。
    """
    sql = text(f"""
        SELECT
            culture_day,
            avg(viable_per_ml)   AS viable_per_ml,
            avg(viability_pct)   AS viability_pct,
            avg(total_per_ml)    AS total_per_ml,
            avg(avg_diameter_um) AS avg_diameter_um,
            count(*)             AS n
        FROM {VIEW}
        WHERE batch_key = :bk
          AND culture_day IS NOT NULL
        GROUP BY culture_day
        ORDER BY culture_day
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
        raise HTTPException(status_code=404, detail=f"没有该批次的生长曲线数据：{batch_key}")

    def num(v):
        return float(v) if v is not None else None

    points = [
        {
            "culture_day": int(r["culture_day"]),
            "viable_per_ml": num(r["viable_per_ml"]),
            "viability_pct": num(r["viability_pct"]),
            "total_per_ml": num(r["total_per_ml"]),
            "avg_diameter_um": num(r["avg_diameter_um"]),
            "n": int(r["n"]),
        }
        for r in rows
    ]
    return {
        "batch_key": batch_key,
        "project_id": meta["project_id"] if meta else None,
        "batch_number": meta["batch_number"] if meta else None,
        "bioreactor_id": meta["bioreactor_id"] if meta else None,
        "n_samples": int(meta["n_samples"]) if meta else 0,
        "points": points,
    }


@router.get("/growth-by-procid")
async def get_growth_by_procid(
    source_instance: str = Query(..., description="Lucullus 工作站编码，如 rd_ws01_usp_lucullus_01"),
    procid: int = Query(..., description="工艺批次编号（Lucullus procid）"),
):
    """按工艺批次（Lucullus 工作站 + procid）取该批次关联的细胞生长曲线。

    用于工艺曲线视图里把细胞指标叠到工艺趋势图上。
    关联链：dim_batch 按 batch_key 关联 fact_vicell，dim_batch 里记着工艺侧的
    (source_instance, procid)。⚠️ procid 会跨工作站撞号（ws01 / ws02 都有 procid 1,2,3…），
    所以必须带 Lucullus 工作站 source_instance 消歧——注意这是工艺侧编码，
    不是 fact_vicell.source_instance（那是 Vi-CELL 仪器编码，恒为 rd_ws01_usp_vicell_01）。
    没关联到细胞数据时返回空 points（前端做空态提示），不报错。
    """
    sql = text(f"""
        SELECT
            fv.culture_day,
            avg(fv.viable_per_ml)   AS viable_per_ml,
            avg(fv.viability_pct)   AS viability_pct,
            avg(fv.total_per_ml)    AS total_per_ml,
            avg(fv.avg_diameter_um) AS avg_diameter_um,
            count(*)                AS n
        FROM {VIEW} fv
        JOIN {SCHEMA}.dim_batch b ON b.batch_key = fv.batch_key
        WHERE b.procid = :procid
          AND b.source_instance = :si
          AND fv.culture_day IS NOT NULL
        GROUP BY fv.culture_day
        ORDER BY fv.culture_day
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"procid": procid, "si": source_instance})).mappings().all()

    def num(v):
        return float(v) if v is not None else None

    points = [
        {
            "culture_day": int(r["culture_day"]),
            "viable_per_ml": num(r["viable_per_ml"]),
            "viability_pct": num(r["viability_pct"]),
            "total_per_ml": num(r["total_per_ml"]),
            "avg_diameter_um": num(r["avg_diameter_um"]),
            "n": int(r["n"]),
        }
        for r in rows
    ]
    return {
        "source_instance": source_instance,
        "procid": procid,
        "points": points,
    }
