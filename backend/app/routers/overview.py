"""只读接口：批次总览（一个批号看全部数据源）。

把细胞（fact_vicell）与生化（fact_nova）两边能画曲线的批次按 batch_key 合并成
一张总表，标出各源的样本数与培养天范围、是否关联工艺批次（Lucullus）。
总览页据此选批次，再分别调 /api/vicell/* 与 /api/nova/* 取曲线和明细。
只读，绝不写入。所有查询走参数绑定。
"""
import json

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY

from ..db import analytics_engine

router = APIRouter(prefix="/api/overview", tags=["overview"])

# 工艺按天宽表的数值列（mart.fact_process_daily，rd-lucullus-etl 每日物化）
PROCESS_METRICS = [
    "ph_mean",
    "temp_c_mean",
    "do_pct_mean",
    "do_pct_min",
    "stirrer_rpm_mean",
    "o2_mlmin_mean",
    "air_mlmin_mean",
    "co2_mlmin_mean",
    "alkali_cum_ml",
    "acid_cum_ml",
]

# 批次年份从批号解析（与 vicell.py / nova.py 同规则）：R2601 -> 2026；登记系统 26003 -> 2026。
# 拆不出再依次回退：dim_batch 解析的年份 → 细胞/生化首次取样年份 → 工艺开始年份。
_YEAR_EXPR = """
    coalesce(
        CASE WHEN x.batch_number ~* '^R[0-9]{4}$'
             THEN 2000 + substring(x.batch_number from 2 for 2)::int
             WHEN x.batch_number ~ '^[0-9]{5}$'
             THEN 2000 + substring(x.batch_number from 1 for 2)::int END,
        x.dim_year,
        extract(year FROM x.first_at)::int,
        extract(year FROM x.proc_first_at)::int
    )
"""


@router.get("/batches")
async def list_batches(limit: int = Query(5000, ge=1, le=20000)):
    """三源合并的批次总名单：细胞（fact_vicell）、生化（fact_nova）、工艺（dim_batch）任一有数据就上榜。

    每行一个批次身份 batch_key（项目_批号_罐）。字段：
    - n_vicell / n_nova：各源样本数（0 = 该源没有此批）；
    - lucullus_runs：该批次对应的全部工艺记录（同一批次中途重开会有 2~3 段，按开始时间倒序），
      每段 {source_instance, procid, procname, starttime, endtime}；空数组 = 没有工艺数据；
    - lucullus_procid / lucullus_source_instance：主工艺记录（= runs[0]），日均工艺参数板块用；
    - unparsed：true = 工艺批次名不规范（test610 这类），拆不出项目/批号，只能按原始名字选。
      这类批次 batch_key 用 'lucullus:<工作站>#<procid>' 顶替，batch_number 直接放原始名字。

    只算有工艺数据（mart.fact_process_daily 里出现过）的 dim_batch 记录，
    没同步过时序的空登记不列。
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
        runs AS (
            SELECT b.batch_key, b.project_id, b.batch_number, b.batch_year, b.bioreactor_id,
                   b.source_instance, b.procid, b.procname_raw, b.starttime, b.endtime
            FROM mart.dim_batch b
            WHERE EXISTS (
                SELECT 1 FROM mart.fact_process_daily d
                WHERE d.source_instance = b.source_instance AND d.procid = b.procid
            )
        ),
        p AS (
            SELECT
                coalesce(batch_key, 'lucullus:' || source_instance || '#' || procid) AS batch_key,
                (batch_key IS NULL)      AS unparsed,
                min(project_id)          AS project_id,
                min(batch_number)        AS batch_number,
                min(bioreactor_id)       AS bioreactor_id,
                min(batch_year)          AS dim_year,
                min(starttime)           AS proc_first_at,
                jsonb_agg(
                    jsonb_build_object(
                        'source_instance', source_instance,
                        'procid', procid,
                        'procname', procname_raw,
                        'starttime', starttime,
                        'endtime', endtime
                    ) ORDER BY starttime DESC NULLS LAST
                ) AS runs
            FROM runs
            GROUP BY 1, 2
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
        ),
        x AS (
            SELECT
                coalesce(u.batch_key, p.batch_key)         AS batch_key,
                coalesce(u.project_id, p.project_id)       AS project_id,
                coalesce(u.batch_number, p.batch_number)   AS batch_number,
                coalesce(u.bioreactor_id, p.bioreactor_id) AS bioreactor_id,
                coalesce(u.n_vicell, 0)                    AS n_vicell,
                coalesce(u.n_nova, 0)                      AS n_nova,
                u.day_min, u.day_max, u.first_at,
                p.dim_year, p.proc_first_at,
                coalesce(p.unparsed, false)                AS unparsed,
                coalesce(p.runs, '[]'::jsonb)              AS runs
            FROM u
            FULL OUTER JOIN p ON p.batch_key = u.batch_key
        )
        SELECT
            x.batch_key, x.project_id, x.batch_number, x.bioreactor_id,
            {_YEAR_EXPR} AS batch_year,
            x.n_vicell, x.n_nova, x.day_min, x.day_max,
            coalesce(x.first_at, x.proc_first_at) AS first_at,
            x.unparsed, x.runs
        FROM x
        ORDER BY x.project_id NULLS LAST, batch_year DESC NULLS LAST,
                 x.batch_number DESC NULLS LAST, x.bioreactor_id
        LIMIT :lim
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"lim": limit})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        runs = d.pop("runs") or []
        if isinstance(runs, str):
            runs = json.loads(runs)
        d["batch_year"] = int(d["batch_year"]) if d["batch_year"] is not None else None
        d["n_vicell"] = int(d["n_vicell"])
        d["n_nova"] = int(d["n_nova"])
        d["day_min"] = int(d["day_min"]) if d["day_min"] is not None else None
        d["day_max"] = int(d["day_max"]) if d["day_max"] is not None else None
        d["first_at"] = d["first_at"].isoformat() if d["first_at"] else None
        d["unparsed"] = bool(d["unparsed"])
        d["lucullus_runs"] = runs
        primary = runs[0] if runs else None
        d["lucullus_procid"] = int(primary["procid"]) if primary else None
        d["lucullus_source_instance"] = primary["source_instance"] if primary else None
        d["lucullus_procname"] = primary["procname"] if primary else None
        if d["unparsed"]:
            # 不规范名：没有项目/批号可拆，把原始批次名当"批号"展示，前端归入「未识别」项目
            d["project_id"] = None
            d["batch_number"] = primary["procname"] if primary else d["batch_key"]
        out.append(d)
    return out


class DailyTableRequest(BaseModel):
    """数据表板块的请求体：要看哪些批次（batch_key 列表）。

    用 POST + JSON 而不是 GET 查询串，是因为「全选」时可能有上千个批次，
    拼进 URL 会超长。只读查询，不写任何东西。
    """

    batch_keys: list[str] = Field(..., min_length=1, max_length=2000)


# 数据表的数值列（按来源分组；列序对齐《项目第一表》Raw_Data）
_TABLE_PROC_COLS = [
    "ph_mean",
    "do_pct_mean",
    "do_pct_min",
    "temp_c_mean",
    "stirrer_rpm_mean",
    "air_mlmin_mean",
    "o2_mlmin_mean",
    "co2_mlmin_mean",
    "alkali_cum_ml",
    "acid_cum_ml",
]
_TABLE_CELL_COLS = ["density_tcd", "density_vcd", "viability_pct", "avg_diameter_um"]
_TABLE_NOVA_COLS = [
    "gluc",
    "lac",
    "gln",
    "glu",
    "nh4",
    "na",
    "k",
    "ca",
    "ph_nova",
    "po2",
    "pco2",
]


@router.post("/daily-table")
async def get_daily_table(req: DailyTableRequest):
    """《项目第一表》样式的合并数据表：一行 = 某批次某培养天，三源列并排。

    细胞（fact_vicell）、生化（fact_nova）同天多次取样取平均；
    工艺（fact_process_daily）本身就是按天汇总，经 dim_batch 的
    (source_instance, procid) 关联（DISTINCT ON 去重，防批号重复放大）。
    三源按 (batch_key, culture_day) FULL OUTER JOIN——任一源有数就出一行。
    """
    sql = text("""
        WITH v AS (
            SELECT batch_key, culture_day,
                   min(run_date)::date  AS sample_date,
                   avg(total_per_ml)    AS density_tcd,
                   avg(viable_per_ml)   AS density_vcd,
                   avg(viability_pct)   AS viability_pct,
                   avg(avg_diameter_um) AS avg_diameter_um,
                   count(*)             AS n_vicell,
                   string_agg(DISTINCT sample_id, ' ｜ ')    AS vicell_sample_ids,
                   string_agg(DISTINCT parse_status, ',')    AS vicell_status
            FROM mart.fact_vicell
            WHERE batch_key = ANY(:keys) AND culture_day IS NOT NULL
            GROUP BY batch_key, culture_day
        ),
        n AS (
            SELECT batch_key, culture_day,
                   min(measured_at)::date AS sample_date,
                   avg(gluc) AS gluc, avg(lac) AS lac,
                   avg(gln)  AS gln,  avg(glu) AS glu,
                   avg(nh4)  AS nh4,  avg(na)  AS na,
                   avg(k)    AS k,    avg(ca)  AS ca,
                   avg(ph)   AS ph_nova,
                   avg(po2)  AS po2,  avg(pco2) AS pco2,
                   count(*)  AS n_nova,
                   string_agg(DISTINCT sample_id, ' ｜ ')    AS nova_sample_ids,
                   string_agg(DISTINCT parse_status, ',')    AS nova_status
            FROM mart.fact_nova
            WHERE batch_key = ANY(:keys) AND culture_day IS NOT NULL
            GROUP BY batch_key, culture_day
        ),
        b AS (
            SELECT DISTINCT ON (batch_key) batch_key, procid, source_instance
            FROM mart.dim_batch
            WHERE batch_key = ANY(:keys)
            ORDER BY batch_key, (procid IS NULL), starttime DESC NULLS LAST
        ),
        p AS (
            SELECT b.batch_key, d.culture_day,
                   d.ph_mean, d.do_pct_mean, d.do_pct_min, d.temp_c_mean,
                   d.stirrer_rpm_mean, d.air_mlmin_mean, d.o2_mlmin_mean,
                   d.co2_mlmin_mean, d.alkali_cum_ml, d.acid_cum_ml
            FROM b
            JOIN mart.fact_process_daily d
              ON d.source_instance = b.source_instance AND d.procid = b.procid
        ),
        vn AS (
            SELECT
                coalesce(v.batch_key, n.batch_key)     AS batch_key,
                coalesce(v.culture_day, n.culture_day) AS culture_day,
                coalesce(v.sample_date, n.sample_date) AS sample_date,
                v.density_tcd, v.density_vcd, v.viability_pct, v.avg_diameter_um,
                n.gluc, n.lac, n.gln, n.glu, n.nh4, n.na, n.k, n.ca,
                n.ph_nova, n.po2, n.pco2,
                coalesce(v.n_vicell, 0) AS n_vicell,
                coalesce(n.n_nova, 0)   AS n_nova,
                v.vicell_sample_ids, v.vicell_status,
                n.nova_sample_ids, n.nova_status
            FROM v
            FULL OUTER JOIN n
              ON n.batch_key = v.batch_key AND n.culture_day = v.culture_day
        )
        SELECT
            coalesce(vn.batch_key, p.batch_key)     AS batch_key,
            coalesce(vn.culture_day, p.culture_day) AS culture_day,
            vn.sample_date,
            p.ph_mean, p.do_pct_mean, p.do_pct_min, p.temp_c_mean,
            p.stirrer_rpm_mean, p.air_mlmin_mean, p.o2_mlmin_mean,
            p.co2_mlmin_mean, p.alkali_cum_ml, p.acid_cum_ml,
            vn.density_tcd, vn.density_vcd, vn.viability_pct, vn.avg_diameter_um,
            vn.gluc, vn.lac, vn.gln, vn.glu, vn.nh4, vn.na, vn.k, vn.ca,
            vn.ph_nova, vn.po2, vn.pco2,
            coalesce(vn.n_vicell, 0) AS n_vicell,
            coalesce(vn.n_nova, 0)   AS n_nova,
            vn.vicell_sample_ids, vn.vicell_status,
            vn.nova_sample_ids, vn.nova_status,
            (p.batch_key IS NOT NULL) AS has_process
        FROM vn
        FULL OUTER JOIN p
          ON p.batch_key = vn.batch_key AND p.culture_day = vn.culture_day
        ORDER BY 1, 2
    """).bindparams(bindparam("keys", type_=ARRAY(String())))

    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"keys": req.batch_keys})).mappings().all()

    def num(v):
        return float(v) if v is not None else None

    metric_cols = _TABLE_PROC_COLS + _TABLE_CELL_COLS + _TABLE_NOVA_COLS
    out = [
        {
            "batch_key": r["batch_key"],
            "culture_day": int(r["culture_day"]) if r["culture_day"] is not None else None,
            "sample_date": r["sample_date"].isoformat() if r["sample_date"] else None,
            **{c: num(r[c]) for c in metric_cols},
            "n_vicell": int(r["n_vicell"]),
            "n_nova": int(r["n_nova"]),
            # 溯源列：原始样本名（仪器上录入的名字）+ 解析状态 + 是否有工艺关联。
            # 项目/批号/罐号都是从样本名拆出来的——样本名录错 = 原始数据错；
            # 样本名没问题但拆出来的字段不对 = 解析错误（走 ETL 别名修正）。
            "vicell_sample_ids": r["vicell_sample_ids"],
            "vicell_status": r["vicell_status"],
            "nova_sample_ids": r["nova_sample_ids"],
            "nova_status": r["nova_status"],
            "has_process": bool(r["has_process"]),
        }
        for r in rows
    ]
    return {"rows": out, "columns": metric_cols}


@router.get("/process-daily")
async def get_process_daily(
    source_instance: str = Query(..., description="Lucullus 工作站编码，如 rd_ws01_usp_lucullus_01"),
    procid: int = Query(..., description="工艺批次编号（Lucullus procid）"),
):
    """某工艺批次按培养天汇总的核心工艺参数（总览页嵌图用）。

    数据源 mart.fact_process_daily（rd-lucullus-etl 每日从 signal_timeseries 物化）。
    ⚠️ procid 跨工作站撞号，必须带 source_instance 消歧（工艺侧编码，来自
    /api/overview/batches 的 lucullus_source_instance）。
    没数据返回空 points（前端做空态提示），不报错。
    """
    cols = ",\n            ".join(PROCESS_METRICS)
    sql = text(f"""
        SELECT
            culture_day,
            {cols},
            n_samples_max
        FROM mart.fact_process_daily
        WHERE source_instance = :si
          AND procid = :procid
        ORDER BY culture_day
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"si": source_instance, "procid": procid})).mappings().all()

    def num(v):
        return float(v) if v is not None else None

    points = [
        {
            "culture_day": int(r["culture_day"]),
            **{m: num(r[m]) for m in PROCESS_METRICS},
            "n_samples_max": int(r["n_samples_max"]) if r["n_samples_max"] is not None else None,
        }
        for r in rows
    ]
    return {
        "source_instance": source_instance,
        "procid": procid,
        "metrics": PROCESS_METRICS,
        "points": points,
    }
