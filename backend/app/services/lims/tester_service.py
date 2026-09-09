# 检验员工作台：按单个 tester 的在手检项 / 本月产出 / 月度趋势
# 口径见 docs/tester_workbench.md；工作日与状态过滤复用 stats_service，保证与检验周期页一致。
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lims.stats_service import (
    _CYCLE_BASE_FILTER,
    _biz_days_between,
    _group_clause,
)

# 在手（结存）口径：本人、未授权、已收样、样品/检项均排除 X/U
_PENDING_FILTER = """
    v.tester = :tester
    AND v.test_authorised_dt IS NULL
    AND v.sample_received_dt IS NOT NULL
    AND v.sample_received_dt < (CAST(:as_of AS date) + INTERVAL '1 day')
    AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
    AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
"""

# 在手检项逐条派生列：已耗时（工作日）、时限、剩余
_PENDING_CTE = f"""
    SELECT
        v.test_id, v.sample_id, v.project_id, v.sample_name, v.batch_number, v.group_id,
        v.method_code,
        COALESCE(m.method_name, v.method_name, v.method_code, '（未知）') AS method_name,
        v.sample_received_dt, v.assigned_dt, v.test_completed_dt, v.test_status,
        CASE WHEN v.test_completed_dt IS NOT NULL THEN 'unauthorized' ELSE 'inprogress' END AS bucket,
        {_biz_days_between("v.sample_received_dt", "CAST(:as_of AS date)")}::int AS elapsed_biz_days,
        COALESCE(m.target_days, :deft)::int AS target_days,
        (m.target_days IS NULL) AS target_is_default
    FROM mart.v_test_task_monitor v
    LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
    WHERE {_PENDING_FILTER}
"""


async def list_testers(db: AsyncSession, groups: list[str] | None = None) -> list[dict]:
    """
    下拉框名单：有在手检项、或近 12 个月有完成记录的 tester。
    groups 过滤按检项自身的 group_id（dim_employee.group_id 基本为空，不可用）。
    """
    group_sql, _ = _group_clause(groups)
    sql = f"""
        WITH act AS (
            SELECT v.tester, v.group_id,
                   (v.test_authorised_dt IS NULL)::int AS is_pending
            FROM mart.v_test_task_monitor v
            WHERE v.tester IS NOT NULL AND TRIM(v.tester) <> ''
              AND v.sample_received_dt IS NOT NULL
              AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
              AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
              AND (v.test_authorised_dt IS NULL
                   OR v.test_authorised_dt >= date_trunc('month', CURRENT_DATE) - INTERVAL '12 months')
              AND {group_sql}
        )
        SELECT a.tester AS employee_id,
               e.employee_name,
               ARRAY_REMOVE(ARRAY_AGG(DISTINCT a.group_id), NULL) AS group_ids,
               SUM(a.is_pending)::int AS pending_n
        FROM act a
        LEFT JOIN (SELECT employee_id, employee_name FROM mart.dim_employee) e
               ON e.employee_id = a.tester
        GROUP BY a.tester, e.employee_name
        ORDER BY pending_n DESC, e.employee_name NULLS LAST, a.tester
    """
    rows = (await db.execute(text(sql))).mappings().all()
    return [dict(r) for r in rows]


async def get_tester_tasks(
    db: AsyncSession,
    tester: str,
    as_of: date,
    default_target: int = 14,
    soon_days: int = 2,
) -> list[dict]:
    """在手检项明细，最老收样的在前。"""
    sql = f"""
        WITH p AS ({_PENDING_CTE})
        SELECT p.*,
               (p.target_days - p.elapsed_biz_days) AS remaining_biz_days,
               (p.elapsed_biz_days > p.target_days) AS is_over_target,
               (p.elapsed_biz_days <= p.target_days
                AND p.target_days - p.elapsed_biz_days <= :soon) AS is_due_soon
        FROM p
        ORDER BY p.sample_received_dt, p.sample_id, p.method_code
    """
    params = {"tester": tester, "as_of": as_of, "deft": default_target, "soon": soon_days}
    rows = (await db.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


async def get_tester_summary(
    db: AsyncSession,
    tester: str,
    as_of: date,
    default_target: int = 14,
    soon_days: int = 2,
) -> dict:
    """6 张汇总卡 + 辅助小字。"""
    params = {"tester": tester, "as_of": as_of, "deft": default_target, "soon": soon_days}

    sql_pending = f"""
        WITH p AS ({_PENDING_CTE})
        SELECT
            COUNT(*)::int                                                                 AS pending_n,
            COUNT(*) FILTER (WHERE elapsed_biz_days > target_days)::int                   AS over_target_n,
            COUNT(*) FILTER (WHERE elapsed_biz_days <= target_days
                               AND target_days - elapsed_biz_days <= :soon)::int          AS due_soon_n,
            COUNT(*) FILTER (WHERE bucket = 'unauthorized')::int                          AS unauthorized_n,
            MIN(sample_received_dt)::date                                                 AS oldest_received_dt
        FROM p
    """
    pend = (await db.execute(text(sql_pending), params)).mappings().one()

    # 本月（1 日 ~ as_of）与上月整月的完成情况；周期口径与检验周期页一致（_CYCLE_BASE_FILTER）
    cycle_expr = _biz_days_between("v.sample_received_dt", "v.test_authorised_dt")
    sql_month = f"""
        WITH win AS (
            SELECT date_trunc('month', CAST(:as_of AS date))::date                        AS cur_start,
                   (CAST(:as_of AS date) + INTERVAL '1 day')::date                        AS cur_end,
                   (date_trunc('month', CAST(:as_of AS date)) - INTERVAL '1 month')::date AS prev_start,
                   date_trunc('month', CAST(:as_of AS date))::date                        AS prev_end
        ),
        done AS (
            SELECT v.test_id, v.test_authorised_dt, m.std_minutes,
                   CASE WHEN v.sample_received_dt IS NOT NULL
                         AND v.test_authorised_dt >= v.sample_received_dt
                         AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
                        THEN {cycle_expr} END AS biz_days
            FROM mart.v_test_task_monitor v
            LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
            CROSS JOIN win w
            WHERE v.tester = :tester
              AND v.test_authorised_dt >= w.prev_start
              AND v.test_authorised_dt <  w.cur_end
              AND UPPER(COALESCE(v.test_status, '')) <> 'X'
        )
        SELECT
            COUNT(*) FILTER (WHERE d.test_authorised_dt >= w.cur_start)::int                     AS month_completed_n,
            ROUND(COALESCE(SUM(d.std_minutes) FILTER (WHERE d.test_authorised_dt >= w.cur_start), 0) / 60.0, 1)
                                                                                                 AS month_std_hours,
            ROUND(AVG(d.biz_days) FILTER (WHERE d.test_authorised_dt >= w.cur_start), 1)          AS month_avg_cycle_days,
            COUNT(*) FILTER (WHERE d.test_authorised_dt <  w.prev_end)::int                      AS prev_month_completed_n,
            ROUND(AVG(d.biz_days) FILTER (WHERE d.test_authorised_dt <  w.prev_end), 1)           AS prev_month_avg_cycle_days
        FROM win w LEFT JOIN done d ON TRUE
        GROUP BY w.cur_start, w.prev_end
    """
    month = (await db.execute(text(sql_month), params)).mappings().one()

    name_row = (await db.execute(
        text("SELECT employee_name FROM mart.dim_employee WHERE employee_id = :tester"),
        {"tester": tester},
    )).first()

    return {
        "tester": tester,
        "employee_name": name_row[0] if name_row else None,
        "as_of": as_of,
        "default_target": default_target,
        "soon_days": soon_days,
        **dict(pend),
        "month_completed_n": month["month_completed_n"],
        "month_std_hours": float(month["month_std_hours"] or 0),
        "month_avg_cycle_days": month["month_avg_cycle_days"],
        "prev_month_completed_n": month["prev_month_completed_n"],
        "prev_month_avg_cycle_days": month["prev_month_avg_cycle_days"],
    }


async def get_tester_monthly(db: AsyncSession, tester: str, months: int = 6) -> list[dict]:
    """近 N 个月：每月完成检项数、标准工时、平均周期（完结口径，按授权月归属）。"""
    cycle_expr = _biz_days_between("v.sample_received_dt", "v.test_authorised_dt")
    sql = f"""
        WITH months AS (
            SELECT gs::date AS m_start, (gs + INTERVAL '1 month')::date AS m_end, to_char(gs, 'YYYY-MM') AS ym
            FROM generate_series(
                date_trunc('month', CURRENT_DATE) - ((:months - 1) || ' months')::interval,
                date_trunc('month', CURRENT_DATE),
                INTERVAL '1 month'
            ) AS gs
        ),
        done AS (
            SELECT mo.ym, v.test_id, m.std_minutes,
                   CASE WHEN v.sample_received_dt IS NOT NULL
                         AND v.test_authorised_dt >= v.sample_received_dt
                         AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
                        THEN {cycle_expr} END AS biz_days
            FROM months mo
            JOIN mart.v_test_task_monitor v
              ON v.test_authorised_dt >= mo.m_start AND v.test_authorised_dt < mo.m_end
            LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
            WHERE v.tester = :tester
              AND UPPER(COALESCE(v.test_status, '')) <> 'X'
        )
        SELECT mo.ym,
               COUNT(d.test_id)::int                                  AS completed_n,
               ROUND(COALESCE(SUM(d.std_minutes), 0) / 60.0, 1)       AS std_hours,
               ROUND(AVG(d.biz_days), 1)                              AS avg_cycle_days
        FROM months mo LEFT JOIN done d ON d.ym = mo.ym
        GROUP BY mo.ym
        ORDER BY mo.ym
    """
    rows = (await db.execute(text(sql), {"tester": tester, "months": months})).mappings().all()
    return [dict(r) for r in rows]
