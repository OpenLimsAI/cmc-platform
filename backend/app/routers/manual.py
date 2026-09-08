"""人工录入：渗透压等仪器不联网、只能手填的取样结果。

这是本看板唯一的写入点（负责人 2026-09-09 定），其余一切只读：
- 读「当天取过样的样品」走只读连接（fact_nova / fact_vicell 当天跑过的样品，批次 / 罐 / 培养天自动带出）；
- 写 manual.sample_result 走写账号 usp_writer 的连接，只追加不覆盖：改数 = 再存一行，
  取值时按 (batch_key, metric_code, culture_day) 取最新（视图 mart.fact_manual_latest）。
- 录入人 = 当前登录人（MDM JWT 的工号 + 姓名快照）。
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth import CurrentUser, require_viewer
from ..config import settings
from ..db import analytics_engine, manual_write_engine

router = APIRouter(prefix="/api/manual", tags=["manual"])

# 目前只有渗透压；以后加滴度等在这里登记（并同步放开表上的 CHECK 约束）
METRICS: dict[str, dict] = {
    "osmolality": {"name": "渗透压", "unit": "mOsm/kg", "min": 100, "max": 1000},
}


@router.get("/status")
async def status():
    """录入功能是否可用（后端是否配了写账号）。"""
    return {"enabled": manual_write_engine() is not None, "metrics": METRICS}


@router.get("/daily-sheet")
async def daily_sheet(
    sample_date: date = Query(..., description="取样日期，如 2026-09-09"),
    metric_code: str = Query("osmolality"),
):
    """某天的录入表：当天在 Nova / Vi-CELL 上跑过的全部样品，每个 (批次, 培养天) 一行。

    自动带出项目 / 批号 / 罐 / 培养天 / 仪器上的样本名，以及该指标已录的最新值（有的话）。
    试验员只需要在对应行填数值。
    """
    if metric_code not in METRICS:
        raise HTTPException(status_code=400, detail=f"未知指标：{metric_code}")
    sql = text("""
        WITH s AS (
            SELECT batch_key, culture_day, project_id, batch_number, bioreactor_id,
                   sample_id, 'nova' AS src
            FROM mart.fact_nova
            WHERE measured_at::date = :d AND batch_key IS NOT NULL AND culture_day IS NOT NULL
            UNION ALL
            SELECT batch_key, culture_day, project_id, batch_number, bioreactor_id,
                   sample_id, 'vicell' AS src
            FROM mart.fact_vicell
            WHERE run_date::date = :d AND batch_key IS NOT NULL AND culture_day IS NOT NULL
        ),
        g AS (
            SELECT batch_key, culture_day,
                   min(project_id)    AS project_id,
                   min(batch_number)  AS batch_number,
                   min(bioreactor_id) AS bioreactor_id,
                   string_agg(DISTINCT sample_id, ' ｜ ') AS sample_ids,
                   bool_or(src = 'nova')   AS has_nova,
                   bool_or(src = 'vicell') AS has_vicell
            FROM s
            GROUP BY batch_key, culture_day
        )
        SELECT g.*,
               m.value          AS existing_value,
               m.entered_by     AS existing_by,
               m.entered_by_name AS existing_by_name,
               m.entered_at     AS existing_at,
               m.note           AS existing_note
        FROM g
        LEFT JOIN mart.fact_manual_latest m
          ON m.batch_key = g.batch_key AND m.culture_day = g.culture_day AND m.metric_code = :metric
        ORDER BY g.project_id, g.batch_number, g.bioreactor_id, g.culture_day
    """)
    async with analytics_engine().connect() as conn:
        rows = (await conn.execute(sql, {"d": sample_date, "metric": metric_code})).mappings().all()
    out = []
    for r in rows:
        out.append({
            "batch_key": r["batch_key"],
            "project_id": r["project_id"],
            "batch_number": r["batch_number"],
            "bioreactor_id": r["bioreactor_id"],
            "culture_day": int(r["culture_day"]),
            "sample_ids": r["sample_ids"],
            "has_nova": bool(r["has_nova"]),
            "has_vicell": bool(r["has_vicell"]),
            "existing_value": float(r["existing_value"]) if r["existing_value"] is not None else None,
            "existing_by": r["existing_by"],
            "existing_by_name": r["existing_by_name"],
            "existing_at": r["existing_at"].isoformat() if r["existing_at"] else None,
            "existing_note": r["existing_note"],
        })
    return {"sample_date": sample_date.isoformat(), "metric": {"code": metric_code, **METRICS[metric_code]}, "rows": out}


class ResultRow(BaseModel):
    batch_key: str = Field(..., max_length=64)
    culture_day: int = Field(..., ge=0, le=365)
    value: float
    note: str | None = Field(None, max_length=500)
    source_sample_ids: str | None = Field(None, max_length=1000)


class SaveRequest(BaseModel):
    sample_date: date
    metric_code: str = "osmolality"
    rows: list[ResultRow] = Field(..., min_length=1, max_length=500)


@router.post("/results")
async def save_results(req: SaveRequest, user: CurrentUser = Depends(require_viewer)):
    """保存一批录入值（只追加）。与当前最新值相同的行跳过，不重复存。"""
    eng = manual_write_engine()
    if eng is None:
        raise HTTPException(status_code=503, detail="后端未配置写库账号（MANUAL_WRITE_DATABASE_URL），暂不能录入")
    if user.is_system and settings.app_env != "dev":
        raise HTTPException(status_code=403, detail="未登录不能录入")
    meta = METRICS.get(req.metric_code)
    if not meta:
        raise HTTPException(status_code=400, detail=f"未知指标：{req.metric_code}")
    bad = [r for r in req.rows if not (meta["min"] <= r.value <= meta["max"])]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"{meta['name']}数值超出合理范围 {meta['min']}–{meta['max']} {meta['unit']}：{bad[0].batch_key} 第 {bad[0].culture_day} 天 = {bad[0].value}",
        )

    # 写账号只有本表权限，最新值直接查表（不走 mart 视图）
    latest_sql = text("""
        SELECT value FROM manual.sample_result
        WHERE batch_key = :bk AND culture_day = :cd AND metric_code = :metric
        ORDER BY entered_at DESC, result_id DESC LIMIT 1
    """)
    insert_sql = text("""
        INSERT INTO manual.sample_result
            (batch_key, culture_day, sample_date, metric_code, value, unit, note, source_sample_ids,
             entered_by, entered_by_name)
        VALUES (:bk, :cd, :d, :metric, :v, :unit, :note, :src, :by, :by_name)
    """)
    saved = 0
    skipped = 0
    async with eng.begin() as conn:
        for r in req.rows:
            cur = (await conn.execute(
                latest_sql, {"bk": r.batch_key, "cd": r.culture_day, "metric": req.metric_code}
            )).scalar()
            if cur is not None and abs(float(cur) - r.value) < 1e-9 and not r.note:
                skipped += 1
                continue
            await conn.execute(insert_sql, {
                "bk": r.batch_key, "cd": r.culture_day, "d": req.sample_date,
                "metric": req.metric_code, "v": r.value, "unit": meta["unit"],
                "note": r.note, "src": r.source_sample_ids,
                "by": user.username, "by_name": user.full_name,
            })
            saved += 1
    return {"saved": saved, "skipped": skipped}
