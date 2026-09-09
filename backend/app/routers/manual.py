"""人工录入：渗透压等仪器不联网、只能手填的取样结果。

这是本看板唯一的写入点（负责人 2026-09-09 定），其余一切只读：
- 读「当天取过样的样品」走只读连接（fact_nova / fact_vicell 当天跑过的样品，批次 / 罐 / 培养天自动带出）；
- 写 manual.sample_result 走写账号 usp_writer 的连接，只追加不覆盖：改数 = 再存一行，
  取值时按 (batch_key, metric_code, culture_day) 取最新（视图 mart.fact_manual_latest）。
- 录入人 = 当前登录人（MDM JWT 的工号 + 姓名快照）。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

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


# 仪器时间 → 北京时间钟点。Nova 是真 UTC；Vi-CELL 的 run_date 是把北京时间当 UTC 存的（ETL bug，见 vicell.py 注释）
_NOVA_TIME = "(measured_at AT TIME ZONE 'Asia/Shanghai')::time"
_VICELL_TIME = "(run_date AT TIME ZONE 'UTC')::time"
# 同一样品当天两次仪器记录相隔超过这个小时数，就当作两次取样（分两行，第二次起样品名加 -T1）
_RESAMPLE_GAP_H = 2.0


def _base_sample_name(batch_key: str, day: int) -> str:
    """没有登记系统样品名时，按批次身份拼一个标准样品名：016_R2605_A6 + 第 5 天 → 016-R2605-A6-D05。"""
    return f"{batch_key.replace('_', '-')}-D{day:02d}"


@router.get("/daily-sheet")
async def daily_sheet(
    sample_date: date = Query(..., description="取样日期，如 2026-09-09"),
    metric_code: str = Query("osmolality"),
):
    """某天的录入表：批号登记系统「当天该取样的样品」∪ 仪器（Nova / Vi-CELL）当天实测到的样品。

    一行 = 一次取样。取样时刻自动从仪器记录带出（生化仪 / 细胞计数仪当天最早一次）；同一样品当天
    仪器记录相隔 2 小时以上视为多次取样，分成多行，第二次起样品名加 -T1、-T2。
    已录的最新值按 (批次, 培养天, 样品名) 带出。
    """
    if metric_code not in METRICS:
        raise HTTPException(status_code=400, detail=f"未知指标：{metric_code}")
    planned, registry_error = await _registry_samples(sample_date)

    sql = text(f"""
        SELECT batch_key, culture_day, project_id, batch_number, bioreactor_id, sample_id,
               'nova' AS src, {_NOVA_TIME} AS t
        FROM mart.fact_nova
        WHERE measured_at::date = :d AND batch_key IS NOT NULL AND culture_day IS NOT NULL
        UNION ALL
        SELECT batch_key, culture_day, project_id, batch_number, bioreactor_id, sample_id,
               'vicell' AS src, {_VICELL_TIME} AS t
        FROM mart.fact_vicell
        WHERE (run_date AT TIME ZONE 'UTC')::date = :d AND batch_key IS NOT NULL AND culture_day IS NOT NULL
        ORDER BY 1, 2, 8
    """)
    existing_sql = text("""
        SELECT batch_key, culture_day, sample_name, value, entered_by, entered_by_name, entered_at, note,
               (sampled_at AT TIME ZONE 'Asia/Shanghai')::time AS t
        FROM mart.fact_manual_latest
        WHERE metric_code = :metric AND batch_key = ANY(:keys)
    """).bindparams(bindparam("keys", type_=ARRAY(String())))

    async with analytics_engine().connect() as conn:
        measured = (await conn.execute(sql, {"d": sample_date})).mappings().all()

        # 按 (批次, 培养天) 归拢仪器记录
        groups: dict[tuple[str, int], dict] = {}
        for m in measured:
            k = (m["batch_key"], int(m["culture_day"]))
            g = groups.setdefault(k, {
                "batch_key": m["batch_key"], "project_id": m["project_id"], "batch_number": m["batch_number"],
                "bioreactor_id": m["bioreactor_id"], "culture_day": int(m["culture_day"]),
                "has_nova": False, "has_vicell": False, "sample_ids": set(), "times": [],
            })
            g["has_nova"] |= m["src"] == "nova"
            g["has_vicell"] |= m["src"] == "vicell"
            if m["sample_id"]:
                g["sample_ids"].add(m["sample_id"])
            if m["t"] is not None:
                g["times"].append(m["t"])
        for p in planned:
            k = (p["batch_key"], p["culture_day"])
            g = groups.setdefault(k, {
                "batch_key": p["batch_key"], "project_id": p["project_id"], "batch_number": p["batch_number"],
                "bioreactor_id": p["bioreactor_id"], "culture_day": p["culture_day"],
                "has_nova": False, "has_vicell": False, "sample_ids": set(), "times": [],
            })
            g["planned"] = True
            g["registry_name"] = p["sample_name"]

        keys = sorted({k[0] for k in groups})
        existing = (await conn.execute(existing_sql, {"metric": metric_code, "keys": keys})).mappings().all() if keys else []

    ex_by_name = {(e["batch_key"], int(e["culture_day"]), e["sample_name"] or ""): e for e in existing}

    def fmt_t(t) -> str | None:
        return f"{t.hour:02d}:{t.minute:02d}" if t is not None else None

    out = []
    for k in sorted(groups, key=lambda k: (groups[k]["project_id"] or "", groups[k]["batch_number"] or "", groups[k]["bioreactor_id"] or "", k[1])):
        g = groups[k]
        base = g.get("registry_name") or _base_sample_name(g["batch_key"], g["culture_day"])
        # 仪器时刻聚成"几次取样"：相邻记录相隔 ≥ 2 小时算新一次
        clusters: list[list] = []
        for t in sorted(g["times"]):
            if clusters and (t.hour * 60 + t.minute) - (clusters[-1][-1].hour * 60 + clusters[-1][-1].minute) < _RESAMPLE_GAP_H * 60:
                clusters[-1].append(t)
            else:
                clusters.append([t])
        if not clusters:
            clusters = [[]]
        # 已录但仪器没体现的样品名（如手工加的 -T1）也要列出来
        names = [base if i == 0 else f"{base}-T{i}" for i in range(len(clusters))]
        for (bk, cd, nm), e in ex_by_name.items():
            if (bk, cd) == k and nm and nm not in names:
                names.append(nm)
                clusters.append([e["t"]] if e["t"] is not None else [])
        for i, nm in enumerate(names):
            e = ex_by_name.get((k[0], k[1], nm)) or (ex_by_name.get((k[0], k[1], "")) if i == 0 else None)
            out.append({
                "batch_key": g["batch_key"],
                "project_id": g["project_id"],
                "batch_number": g["batch_number"],
                "bioreactor_id": g["bioreactor_id"],
                "culture_day": g["culture_day"],
                "sample_name": nm,
                "sample_time": fmt_t(clusters[i][0]) if clusters[i] else (fmt_t(e["t"]) if e else None),
                "planned": bool(g.get("planned")),
                "has_nova": g["has_nova"],
                "has_vicell": g["has_vicell"],
                "sample_ids": " ｜ ".join(sorted(g["sample_ids"])) or None,
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
    sample_name: str | None = Field(None, max_length=64)  # 标准样品名（一天多次取样带 -T1 尾缀）
    sample_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")  # 取样时刻 HH:MM（北京时间）
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

    # 写账号只有本表权限，最新值直接查表（不走 mart 视图）；同一样品名的最新一行
    latest_sql = text("""
        SELECT value FROM manual.sample_result
        WHERE batch_key = :bk AND culture_day = :cd AND metric_code = :metric
          AND coalesce(sample_name, '') = :nm
        ORDER BY entered_at DESC, result_id DESC LIMIT 1
    """)
    insert_sql = text("""
        INSERT INTO manual.sample_result
            (batch_key, culture_day, sample_date, sampled_at, sample_name, metric_code, value, unit, note,
             source_sample_ids, entered_by, entered_by_name)
        VALUES (:bk, :cd, :d, :sampled_at, :nm, :metric, :v, :unit, :note, :src, :by, :by_name)
    """)
    saved = 0
    skipped = 0
    async with eng.begin() as conn:
        for r in req.rows:
            nm = (r.sample_name or "").strip() or None
            sampled_at = None
            if r.sample_time:
                hh, mm = r.sample_time.split(":")
                sampled_at = datetime.combine(req.sample_date, time(int(hh), int(mm)), tzinfo=ZoneInfo("Asia/Shanghai"))
            cur = (await conn.execute(
                latest_sql, {"bk": r.batch_key, "cd": r.culture_day, "metric": req.metric_code, "nm": nm or ""}
            )).scalar()
            if cur is not None and abs(float(cur) - r.value) < 1e-9 and not r.note:
                skipped += 1
                continue
            await conn.execute(insert_sql, {
                "bk": r.batch_key, "cd": r.culture_day, "d": req.sample_date, "sampled_at": sampled_at, "nm": nm,
                "metric": req.metric_code, "v": r.value, "unit": meta["unit"],
                "note": r.note, "src": r.source_sample_ids,
                "by": user.username, "by_name": user.full_name,
            })
            saved += 1
    return {"saved": saved, "skipped": skipped}
