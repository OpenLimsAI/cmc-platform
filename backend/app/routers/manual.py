"""人工录入：渗透压等仪器不联网、只能手填的取样结果。

这是本看板唯一的写入点（负责人 2026-09-09 定），其余一切只读：
- 读「当天取过样的样品」走只读连接（fact_nova / fact_vicell 当天跑过的样品，批次 / 罐 / 培养天自动带出）；
- 写 manual.sample_result 走写账号 usp_writer 的连接，只追加不覆盖：改数 = 再存一行，
  取值时按 (batch_key, metric_code, culture_day) 取最新（视图 mart.fact_manual_latest）。
- 录入人 = 当前登录人（MDM JWT 的工号 + 姓名快照）。
"""
from __future__ import annotations

import logging
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY

from ..auth import CurrentUser, require_viewer
from ..config import settings
from ..db import analytics_engine, manual_write_engine

router = APIRouter(prefix="/api/manual", tags=["manual"])
log = logging.getLogger(__name__)

# 目前只有渗透压；以后加滴度等在这里登记（并同步放开表上的 CHECK 约束）
METRICS: dict[str, dict] = {
    "osmolality": {"name": "渗透压", "unit": "mOsm/kg", "min": 100, "max": 1000},
}


@router.get("/status")
async def status():
    """录入功能是否可用（后端是否配了写账号）。"""
    return {"enabled": manual_write_engine() is not None, "metrics": METRICS}


async def _registry_samples(target: date) -> tuple[list[dict], str | None]:
    """问批号登记系统：这天按计划该取样的全部样品。返回 (样品行, 错误说明)。

    登记系统的样品名 = 批号-阶段码-D天数（如 0092-26001-A1-D05）；批次身份按它的 v_batch_dim 规则拼：
    replace(批号,'-','_') || '_' || 阶段码，与仪器样品名拆出来的 batch_key 一致。
    """
    base = settings.registry_base_url.rstrip("/")
    if not base:
        return [], None
    url = f"{base}/api/v1/batches:samples-by-date"
    try:
        # trust_env=False：内网服务，不走本机代理
        async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
            resp = await client.get(url, params={"date": target.isoformat()})
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body)
    except Exception as e:  # noqa: BLE001 —— 登记系统不可达不能拖垮录入页
        log.warning("批号登记系统取当天样品失败: %s", e)
        return [], f"批号登记系统暂时连不上（{type(e).__name__}），下面只列了仪器实测到的样品"
    out = []
    for b in data.get("batches", []):
        batch_no = b.get("business_batch_no") or ""
        for it in b.get("items", []):
            stage = it.get("stage_code") or ""
            out.append({
                "batch_key": f"{batch_no.replace('-', '_')}_{stage}",
                "project_id": b.get("project_code"),
                "batch_number": batch_no.split("-")[-1] if "-" in batch_no else batch_no,
                "bioreactor_id": stage,
                "culture_day": int(it.get("day", 0)),
                "sample_name": it.get("sample_name"),
                "kind": it.get("kind"),
            })
    return out, None


@router.get("/daily-sheet")
async def daily_sheet(
    sample_date: date = Query(..., description="取样日期，如 2026-09-09"),
    metric_code: str = Query("osmolality"),
):
    """某天的录入表：批号登记系统「当天该取样的样品」∪ 仪器（Nova / Vi-CELL）当天实测到的样品，
    每个 (批次, 培养天) 一行，自动带出项目 / 批号 / 罐 / 培养天 / 样品名，以及该指标已录的最新值。
    试验员只需要在对应行填数值；没取样的行在页面上删掉即可，临时样品可加行。
    """
    if metric_code not in METRICS:
        raise HTTPException(status_code=400, detail=f"未知指标：{metric_code}")
    planned, registry_error = await _registry_samples(sample_date)

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
        )
        SELECT batch_key, culture_day,
               min(project_id)    AS project_id,
               min(batch_number)  AS batch_number,
               min(bioreactor_id) AS bioreactor_id,
               string_agg(DISTINCT sample_id, ' ｜ ') AS sample_ids,
               bool_or(src = 'nova')   AS has_nova,
               bool_or(src = 'vicell') AS has_vicell
        FROM s
        GROUP BY batch_key, culture_day
    """)
    existing_sql = text("""
        SELECT batch_key, culture_day, value, entered_by, entered_by_name, entered_at, note
        FROM mart.fact_manual_latest
        WHERE metric_code = :metric AND batch_key = ANY(:keys)
    """).bindparams(bindparam("keys", type_=ARRAY(String())))

    async with analytics_engine().connect() as conn:
        measured = (await conn.execute(sql, {"d": sample_date})).mappings().all()

        # 合并：计划的 + 实测的，按 (批次, 培养天) 去重
        rows: dict[tuple[str, int], dict] = {}
        for p in planned:
            k = (p["batch_key"], p["culture_day"])
            rows[k] = {**p, "planned": True, "has_nova": False, "has_vicell": False, "sample_ids": None}
        for m in measured:
            k = (m["batch_key"], int(m["culture_day"]))
            r = rows.get(k)
            if r is None:
                r = {
                    "batch_key": m["batch_key"],
                    "project_id": m["project_id"],
                    "batch_number": m["batch_number"],
                    "bioreactor_id": m["bioreactor_id"],
                    "culture_day": int(m["culture_day"]),
                    "sample_name": None,
                    "kind": None,
                    "planned": False,
                }
                rows[k] = r
            r["sample_ids"] = m["sample_ids"]
            r["has_nova"] = bool(m["has_nova"])
            r["has_vicell"] = bool(m["has_vicell"])

        keys = sorted({k[0] for k in rows})
        existing = (await conn.execute(existing_sql, {"metric": metric_code, "keys": keys})).mappings().all() if keys else []

    ex = {(e["batch_key"], int(e["culture_day"])): e for e in existing}
    out = []
    for k in sorted(rows, key=lambda k: (rows[k]["project_id"] or "", rows[k]["batch_number"] or "", rows[k]["bioreactor_id"] or "", k[1])):
        r = rows[k]
        e = ex.get(k)
        out.append({
            **r,
            "existing_value": float(e["value"]) if e else None,
            "existing_by": e["entered_by"] if e else None,
            "existing_by_name": e["entered_by_name"] if e else None,
            "existing_at": e["entered_at"].isoformat() if e else None,
            "existing_note": e["note"] if e else None,
        })
    return {
        "sample_date": sample_date.isoformat(),
        "metric": {"code": metric_code, **METRICS[metric_code]},
        "registry_used": bool(settings.registry_base_url) and registry_error is None,
        "registry_error": registry_error,
        "rows": out,
    }


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
