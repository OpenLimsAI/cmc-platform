"""只读接口：批次总览（一个批号看全部数据源）。

把细胞（fact_vicell）与生化（fact_nova）两边能画曲线的批次按 batch_key 合并成
一张总表，标出各源的样本数与培养天范围、是否关联工艺批次（Lucullus）。
总览页据此选批次，再分别调 /api/vicell/* 与 /api/nova/* 取曲线和明细。
只读，绝不写入。所有查询走参数绑定。
"""
from fastapi import APIRouter, Query
from sqlalchemy import text

from ..db import analytics_engine

router = APIRouter(prefix="/api/overview", tags=["overview"])

# 批次年份从批号解析（与 vicell.py / nova.py 同规则）：R2601 -> 2026。
_YEAR_EXPR = """
    coalesce(
        CASE WHEN u.batch_number ~* '^R[0-9]{4}$'
             THEN 2000 + substring(u.batch_number from 2 for 2)::int END,
        extract(year FROM u.first_at)::int
    )
"""


@router.get("/batches")
async def list_batches(limit: int = Query(5000, ge=1, le=20000)):
    """两源合并的批次列表：有细胞或生化任一数据（batch_key + culture_day 齐）就上榜。

    n_vicell / n_nova = 各源样本数（0 = 该源没有此批）；
    lucullus_procid / lucullus_source_instance = 工艺关联（dim_batch 去重后取），
    用于总览页跳转工艺曲线视图。
    """
    sql = text(f"""
        WITH v AS (
            SELECT batch_key,
                   min(project_id)    AS project_id,
                   min(batch_number)  AS batch_number,
                   min(bioreactor_id) AS bioreactor_id,
                   count(*)           AS n_samples,
                   min(culture_day)   AS day_min,
                   max(culture_day)   AS day_max,
                   min(run_date)::timestamptz AS first_at
            FROM mart.fact_vicell
            WHERE batch_key IS NOT NULL AND culture_day IS NOT NULL
            GROUP BY batch_key
        ),
        n AS (
            SELECT batch_key,
                   min(project_id)    AS project_id,
                   min(batch_number)  AS batch_number,
                   min(bioreactor_id) AS bioreactor_id,
                   count(*)           AS n_samples,
                   min(culture_day)   AS day_min,
                   max(culture_day)   AS day_max,
                   min(measured_at)   AS first_at
            FROM mart.fact_nova
            WHERE batch_key IS NOT NULL AND culture_day IS NOT NULL
            GROUP BY batch_key
        ),
        b AS (
            SELECT DISTINCT ON (batch_key) batch_key, procid, source_instance
            FROM mart.dim_batch
            WHERE batch_key IS NOT NULL
            ORDER BY batch_key, (procid IS NULL), starttime DESC NULLS LAST
        ),
        u AS (
            SELECT
                coalesce(v.batch_key, n.batch_key)         AS batch_key,
                coalesce(v.project_id, n.project_id)       AS project_id,
                coalesce(v.batch_number, n.batch_number)   AS batch_number,
                coalesce(v.bioreactor_id, n.bioreactor_id) AS bioreactor_id,
                coalesce(v.n_samples, 0)                   AS n_vicell,
                coalesce(n.n_samples, 0)                   AS n_nova,
                least(v.day_min, n.day_min)                AS day_min,
                greatest(v.day_max, n.day_max)             AS day_max,
                least(v.first_at, n.first_at)              AS first_at
            FROM v
            FULL OUTER JOIN n ON n.batch_key = v.batch_key
        )
        SELECT
            u.batch_key,
            u.project_id,
            u.batch_number,
            u.bioreactor_id,
            {_YEAR_EXPR}      AS batch_year,
            u.n_vicell,
            u.n_nova,
            u.day_min,
            u.day_max,
            u.first_at,
            b.procid          AS lucullus_procid,
            b.source_instance AS lucullus_source_instance
        FROM u
        LEFT JOIN b ON b.batch_key = u.batch_key
        ORDER BY u.project_id, batch_year DESC NULLS LAST, u.bioreactor_id
        LIMIT :lim
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"lim": limit})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["batch_year"] = int(d["batch_year"]) if d["batch_year"] is not None else None
        d["n_vicell"] = int(d["n_vicell"])
        d["n_nova"] = int(d["n_nova"])
        d["day_min"] = int(d["day_min"]) if d["day_min"] is not None else None
        d["day_max"] = int(d["day_max"]) if d["day_max"] is not None else None
        d["first_at"] = d["first_at"].isoformat() if d["first_at"] else None
        d["lucullus_procid"] = (
            int(d["lucullus_procid"]) if d["lucullus_procid"] is not None else None
        )
        out.append(d)
    return out
