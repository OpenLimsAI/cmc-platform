# 统计服务层：健康检查、KPI 等统计查询
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lims.views import TestTaskMonitor


async def get_health_stats(db: AsyncSession) -> dict:
    """检查数据库连通性，并返回 v_test_task_monitor 的行数"""
    try:
        result = await db.execute(
            select(func.count()).select_from(TestTaskMonitor)
        )
        count = result.scalar_one()
        return {"status": "ok", "db": "connected", "sample_count": count}
    except Exception as e:
        return {"status": "error", "db": str(e), "sample_count": 0}


async def get_data_freshness(
    analytics_db: AsyncSession,
    raw_db: AsyncSession | None,
) -> dict:
    """
    返回三段时间：
      - db_name：当前主库名
      - data_max_at：cmc_analytics.staging.stg_result.updated_at 的 MAX —— 业务上最新一条结果的变更时间
      - etl_last_run_at：cmc_rd.meta.etl_run 最近一次 SUCCESS 的 run_finished_at —— ETL 跑完时间
    raw_db 未配置时 etl_last_run_at 返回 None，端点降级仍可用。
    """
    row = (await analytics_db.execute(text(
        "SELECT current_database() AS db_name, "
        "(SELECT MAX(updated_at) FROM staging.stg_result) AS data_max_at"
    ))).mappings().first()
    db_name = row["db_name"]
    data_max_at = row["data_max_at"]

    etl_last_run_at = None
    if raw_db is not None:
        # run_finished_at 列是 naive timestamp，但 PG server 时区是 UTC，写入用 NOW() 故本质是 UTC。
        # 显式 AT TIME ZONE 'UTC' 把 naive 当 UTC 解释 → 输出 timestamptz，Pydantic 序列化带 +00:00。
        # 否则前端 dayjs 按本地时区解析会错算 8 小时。
        etl_row = (await raw_db.execute(text(
            "SELECT MAX(run_finished_at) AT TIME ZONE 'UTC' AS finished_at "
            "FROM meta.etl_run WHERE status = 'SUCCESS'"
        ))).mappings().first()
        etl_last_run_at = etl_row["finished_at"] if etl_row else None

    return {
        "db_name": db_name,
        "data_max_at": data_max_at,
        "etl_last_run_at": etl_last_run_at,
    }


# ---------- KPI ----------

# 状态过滤，与 Streamlit 版保持一致
_STATUS_EXCL_XU = "UPPER(COALESCE(sample_status, '')) NOT IN ('X','U') AND UPPER(COALESCE(test_status, '')) NOT IN ('X','U')"
_STATUS_EXCL_X  = "UPPER(COALESCE(test_status, '')) <> 'X'"

# 时间区间统一左闭右开 [start, end+1day)
_DATE_WINDOW_RECEIVED   = "sample_received_dt >= CAST(:start AS date) AND sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')"
_DATE_WINDOW_AUTHORISED = "test_authorised_dt  >= CAST(:start AS date) AND test_authorised_dt  < (CAST(:end_date AS date) + INTERVAL '1 day')"


def _group_clause(groups: list[str] | None) -> tuple[str, dict]:
    """
    当 groups 为空时不加过滤条件；
    有值时用 ANY(ARRAY[...]) 内联，避免 asyncpg 无法推断 NULL 参数类型的问题。
    """
    if not groups:
        return "TRUE", {}
    # groups 来自 HTTP query 参数（list[str]，无 enum 白名单），必须防注入。
    # asyncpg 无法推断 NULL 参数类型，这里内联成 ARRAY 字面量，但每个值都把单引号
    # 转义成 ''（PG 字符串里的字面单引号），恶意输入只会变成匹配不到任何行的 group_id。
    arr = "ARRAY[" + ",".join("'" + g.replace("'", "''") + "'" for g in groups) + "]"
    return f"group_id = ANY({arr})", {}


async def _scalar(db: AsyncSession, sql: str, params: dict) -> int:
    result = await db.execute(text(sql), params)
    return result.scalar_one() or 0


async def get_kpi(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
) -> dict:
    """
    顺序执行 4 条 COUNT 查询，对应 Streamlit 看板 View 1 的 4 个 KPI 卡片：
    - sample_n:       到样口径样品数
    - test_n:         到样口径检项数
    - done_test_n:    完结口径已完成检项数
    - pending_test_n: 截止 end_date 未完成检项数
    """
    group_sql, _ = _group_clause(groups)
    params = {"start": start, "end_date": end_date}

    sql_samples = f"""
        SELECT COUNT(DISTINCT sample_id) FROM mart.v_test_task_monitor
        WHERE {_DATE_WINDOW_RECEIVED} AND {_STATUS_EXCL_XU} AND {group_sql}
    """
    sql_tests = f"""
        SELECT COUNT(DISTINCT test_id) FROM mart.v_test_task_monitor
        WHERE {_DATE_WINDOW_RECEIVED} AND {_STATUS_EXCL_XU} AND {group_sql}
    """
    sql_done = f"""
        SELECT COUNT(DISTINCT test_id) FROM mart.v_test_task_monitor
        WHERE {_DATE_WINDOW_AUTHORISED} AND {_STATUS_EXCL_X} AND {group_sql}
    """
    sql_pending = f"""
        SELECT COUNT(DISTINCT test_id) FROM mart.v_test_task_monitor
        WHERE sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND test_authorised_dt IS NULL
          AND {_STATUS_EXCL_XU} AND {group_sql}
    """

    sample_n  = await _scalar(db, sql_samples, params)
    test_n    = await _scalar(db, sql_tests, params)
    done_n    = await _scalar(db, sql_done, params)
    pending_n = await _scalar(db, sql_pending, params)

    return {
        "sample_n": sample_n,
        "test_n": test_n,
        "done_test_n": done_n,
        "pending_test_n": pending_n,
        "start_date": start,
        "end_date": end_date,
    }


# ---------- 月度趋势 ----------

async def get_monthly_trend(
    db: AsyncSession,
    months: int = 12,
    groups: list[str] | None = None,
) -> list[dict]:
    """
    近 N 个月的样品数/检项数/未完成检项数趋势，对应 Streamlit 看板 View 1 折线图。
    当前月截止今天，历史月截止月末，与原始 SQL 逻辑完全一致。
    """
    group_sql, _ = _group_clause(groups)

    sql = f"""
        WITH months AS (
          SELECT
            gs::date AS m_start_date,
            CASE
              WHEN gs::date = date_trunc('month', CURRENT_DATE)::date
              THEN CURRENT_DATE
              ELSE (gs + interval '1 month - 1 day')::date
            END AS cutoff_date
          FROM generate_series(
            date_trunc('month', CURRENT_DATE) - ((:months - 1) || ' months')::interval,
            date_trunc('month', CURRENT_DATE),
            interval '1 month'
          ) AS gs
        )
        SELECT
          to_char(m.m_start_date, 'YYYY-MM') AS ym,
          m.cutoff_date AS month_end,

          (SELECT COUNT(DISTINCT v.sample_id)
           FROM mart.v_test_task_monitor v
           WHERE v.sample_received_dt::date >= m.m_start_date
             AND v.sample_received_dt::date < (m.cutoff_date + 1)
             AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
             AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
             AND {group_sql}
          ) AS sample_n,

          (SELECT COUNT(DISTINCT v.test_id)
           FROM mart.v_test_task_monitor v
           WHERE v.sample_received_dt::date >= m.m_start_date
             AND v.sample_received_dt::date < (m.cutoff_date + 1)
             AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
             AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
             AND {group_sql}
          ) AS test_n,

          (SELECT COUNT(DISTINCT v.test_id)
           FROM mart.v_test_task_monitor v
           WHERE v.sample_received_dt::date < (m.cutoff_date + 1)
             AND (v.test_authorised_dt IS NULL
                  OR v.test_authorised_dt::date >= (m.cutoff_date + 1))
             AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
             AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
             AND {group_sql}
          ) AS pending_test_n

        FROM months m
        ORDER BY ym
    """

    result = await db.execute(text(sql), {"months": months})
    rows = result.mappings().all()
    return [dict(r) for r in rows]


# ---------- 检验周期 ----------

# 工作日计算：49元素数组查找法，O(1)，与 Streamlit 版完全一致
def _biz_days_between(start_col: str, end_col: str) -> str:
    """返回 SQL 工作日差表达式（end - start，按 49 元素数组查表）。"""
    return f"""(
    5 * (({end_col}::date - {start_col}::date) / 7)
    + (ARRAY[0,1,2,3,4,5,5, 0,1,2,3,4,4,4, 0,1,2,3,3,3,4,
             0,1,2,2,2,3,4, 0,1,1,1,2,3,4, 0,0,0,1,2,3,4,
             0,0,1,2,3,4,5])[
        EXTRACT(DOW FROM {start_col}::date)::int * 7
        + ({end_col}::date - {start_col}::date) % 7
        + 1
    ]
)::numeric"""


def _stage_biz_days(start_col: str, end_col: str) -> str:
    """单个阶段的工作日；端点缺一或终点早于起点 → NULL（让 AVG/COUNT 自动忽略）。"""
    return f"""CASE
        WHEN {start_col} IS NOT NULL
         AND {end_col} IS NOT NULL
         AND {end_col}::date >= {start_col}::date
        THEN {_biz_days_between(start_col, end_col)}
    END"""


_BIZ_DAYS_EXPR = _biz_days_between("v.sample_received_dt", "v.test_authorised_dt")

# 基础过滤条件（完结口径，排除X/U，要求两个日期均不为空且授权≥收样）
_CYCLE_BASE_FILTER = """
    v.test_authorised_dt IS NOT NULL
    AND v.sample_received_dt IS NOT NULL
    AND v.test_authorised_dt >= v.sample_received_dt
    AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
    AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
"""


async def get_cycle_time_by_method(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
) -> list[dict]:
    """按方法汇总检验周期（avg/median/max），对应 Streamlit View 3 方法明细表。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        WITH raw AS (
            SELECT
                v.method_code,
                v.test_id,
                {_BIZ_DAYS_EXPR} AS biz_days
            FROM mart.v_test_task_monitor v
            WHERE v.test_authorised_dt >= CAST(:start AS date)
              AND v.test_authorised_dt <  (CAST(:end_date AS date) + INTERVAL '1 day')
              AND {_CYCLE_BASE_FILTER}
              AND {group_sql}
        )
        SELECT
            COALESCE(m.method_name, r.method_code, '（未知）') AS method_name,
            r.method_code,
            COUNT(DISTINCT r.test_id)                                                  AS completed_n,
            ROUND(AVG(r.biz_days), 1)                                                  AS avg_cycle_days,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.biz_days)::numeric, 1) AS median_cycle_days,
            MAX(r.biz_days)::int                                                        AS max_cycle_days
        FROM raw r
        LEFT JOIN mart.dim_method m ON r.method_code = m.method_code
        GROUP BY r.method_code, m.method_name
        ORDER BY avg_cycle_days DESC
    """
    result = await db.execute(text(sql), {"start": start, "end_date": end_date})
    return [dict(r) for r in result.mappings().all()]


async def get_cycle_time_monthly_trend(
    db: AsyncSession,
    months: int = 12,
    groups: list[str] | None = None,
) -> list[dict]:
    """月度整体检验周期趋势，对应 Streamlit View 3 主趋势图。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        WITH months AS (
            SELECT
                gs::date                        AS m_start,
                (gs + INTERVAL '1 month')::date AS m_end,
                to_char(gs, 'YYYY-MM')          AS ym
            FROM generate_series(
                date_trunc('month', CURRENT_DATE) - ((:months - 1) || ' months')::interval,
                date_trunc('month', CURRENT_DATE),
                INTERVAL '1 month'
            ) AS gs
        ),
        raw AS (
            SELECT
                m.ym,
                m.m_start,
                v.test_id,
                {_BIZ_DAYS_EXPR} AS biz_days
            FROM months m
            JOIN mart.v_test_task_monitor v
              ON  v.test_authorised_dt::date >= m.m_start
              AND v.test_authorised_dt::date <  m.m_end
            WHERE {_CYCLE_BASE_FILTER}
              AND {group_sql}
        )
        SELECT
            ym,
            COUNT(DISTINCT test_id)                                                  AS completed_n,
            ROUND(AVG(biz_days), 1)                                                  AS avg_cycle_days,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY biz_days)::numeric, 1) AS median_cycle_days
        FROM raw
        GROUP BY ym, m_start
        ORDER BY ym
    """
    result = await db.execute(text(sql), {"months": months})
    return [dict(r) for r in result.mappings().all()]


async def get_cycle_time_trend_by_method(
    db: AsyncSession,
    months: int = 12,
    groups: list[str] | None = None,
) -> list[dict]:
    """月度分方法检验周期趋势，对应 Streamlit View 3 五个重点方法趋势图。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        WITH months AS (
            SELECT
                gs::date                        AS m_start,
                (gs + INTERVAL '1 month')::date AS m_end,
                to_char(gs, 'YYYY-MM')          AS ym
            FROM generate_series(
                date_trunc('month', CURRENT_DATE) - ((:months - 1) || ' months')::interval,
                date_trunc('month', CURRENT_DATE),
                INTERVAL '1 month'
            ) AS gs
        ),
        raw AS (
            SELECT
                m.ym,
                m.m_start,
                v.test_id,
                v.method_code,
                {_BIZ_DAYS_EXPR} AS biz_days
            FROM months m
            JOIN mart.v_test_task_monitor v
              ON  v.test_authorised_dt::date >= m.m_start
              AND v.test_authorised_dt::date <  m.m_end
            WHERE {_CYCLE_BASE_FILTER}
              AND {group_sql}
        )
        SELECT
            r.ym,
            COALESCE(dm.method_name, r.method_code, '（未知）') AS method_name,
            COUNT(DISTINCT r.test_id)                                                  AS completed_n,
            ROUND(AVG(r.biz_days), 1)                                                  AS avg_cycle_days,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.biz_days)::numeric, 1) AS median_cycle_days
        FROM raw r
        LEFT JOIN mart.dim_method dm ON r.method_code = dm.method_code
        GROUP BY r.ym, r.m_start, r.method_code, dm.method_name
        ORDER BY r.ym, dm.method_name
    """
    result = await db.execute(text(sql), {"months": months})
    return [dict(r) for r in result.mappings().all()]


# ---------- 检验周期：4 段细分 ----------
#
# 4 段定义（口径同检验周期：完结 + 排除 X/U）：
#   alloc:  sample_received_dt   → assigned_dt          分配前等待
#   wait:   assigned_dt          → test_started_dt      待检（已分配未开工）
#   test:   test_started_dt      → test_completed_dt    实际检验
#   review: test_completed_dt    → test_authorised_dt   复核授权
# 每段独立平均，缺端点的记录在该段不计入（AVG/COUNT 自动忽略 NULL）。

_STAGE_COLUMNS = [
    ("alloc",  "v.sample_received_dt", "v.assigned_dt"),
    ("wait",   "v.assigned_dt",        "v.test_started_dt"),
    ("test",   "v.test_started_dt",    "v.test_completed_dt"),
    ("review", "v.test_completed_dt",  "v.test_authorised_dt"),
]


def _stage_select_cte() -> str:
    """CTE 内的 4 段工作日列。"""
    return ",\n            ".join(
        f"{_stage_biz_days(s, e)} AS {name}_days"
        for name, s, e in _STAGE_COLUMNS
    )


def _stage_aggregate_cols() -> str:
    """外层 GROUP BY 后的 4 段聚合列（n + avg）。"""
    parts = []
    for name, _, _ in _STAGE_COLUMNS:
        parts.append(f"COUNT({name}_days)::int                       AS {name}_n")
        parts.append(f"ROUND(AVG({name}_days), 1)                    AS {name}_avg_days")
    return ",\n            ".join(parts)


def _attach_bottleneck(item: dict) -> dict:
    """在 Python 端算出 4 段中均值最大的一段（NULL 段跳过）。"""
    stages = {
        name: item.get(f"{name}_avg_days")
        for name, _, _ in _STAGE_COLUMNS
    }
    valid = {k: float(v) for k, v in stages.items() if v is not None}
    item["bottleneck_stage"] = max(valid, key=valid.get) if valid else None
    return item


async def get_cycle_time_stages_by_method(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
) -> list[dict]:
    """各方法 4 段平均工作日（区间汇总）。完结口径与 cycle-time/by-method 一致。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        WITH raw AS (
            SELECT
                v.method_code,
                v.test_id,
                {_stage_select_cte()}
            FROM mart.v_test_task_monitor v
            WHERE v.test_authorised_dt >= CAST(:start AS date)
              AND v.test_authorised_dt <  (CAST(:end_date AS date) + INTERVAL '1 day')
              AND {_CYCLE_BASE_FILTER}
              AND {group_sql}
        )
        SELECT
            COALESCE(m.method_name, r.method_code, '（未知）') AS method_name,
            r.method_code,
            COUNT(DISTINCT r.test_id)::int                    AS completed_n,
            {_stage_aggregate_cols()}
        FROM raw r
        LEFT JOIN mart.dim_method m ON r.method_code = m.method_code
        GROUP BY r.method_code, m.method_name
        ORDER BY (
            COALESCE(AVG(alloc_days),  0)
          + COALESCE(AVG(wait_days),   0)
          + COALESCE(AVG(test_days),   0)
          + COALESCE(AVG(review_days), 0)
        ) DESC
    """
    result = await db.execute(text(sql), {"start": start, "end_date": end_date})
    return [_attach_bottleneck(dict(r)) for r in result.mappings().all()]


async def get_cycle_time_stages_trend_by_method(
    db: AsyncSession,
    months: int = 12,
    groups: list[str] | None = None,
) -> list[dict]:
    """各方法按月份的 4 段平均工作日（重点检项卡片堆叠柱用）。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        WITH months AS (
            SELECT
                gs::date                        AS m_start,
                (gs + INTERVAL '1 month')::date AS m_end,
                to_char(gs, 'YYYY-MM')          AS ym
            FROM generate_series(
                date_trunc('month', CURRENT_DATE) - ((:months - 1) || ' months')::interval,
                date_trunc('month', CURRENT_DATE),
                INTERVAL '1 month'
            ) AS gs
        ),
        raw AS (
            SELECT
                m.ym,
                m.m_start,
                v.test_id,
                v.method_code,
                {_stage_select_cte()}
            FROM months m
            JOIN mart.v_test_task_monitor v
              ON  v.test_authorised_dt::date >= m.m_start
              AND v.test_authorised_dt::date <  m.m_end
            WHERE {_CYCLE_BASE_FILTER}
              AND {group_sql}
        )
        SELECT
            r.ym,
            COALESCE(dm.method_name, r.method_code, '（未知）') AS method_name,
            r.method_code,
            COUNT(DISTINCT r.test_id)::int                      AS completed_n,
            {_stage_aggregate_cols()}
        FROM raw r
        LEFT JOIN mart.dim_method dm ON r.method_code = dm.method_code
        GROUP BY r.ym, r.m_start, r.method_code, dm.method_name
        ORDER BY r.ym, dm.method_name
    """
    result = await db.execute(text(sql), {"months": months})
    return [dict(r) for r in result.mappings().all()]


# ---------- 项目分布 ----------

async def get_project_distribution(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
) -> list[dict]:
    """到样口径各项目样品数和检项数，按样品数降序。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        SELECT
            COALESCE(v.project_id, '（未知）')          AS project_id,
            COUNT(DISTINCT v.sample_id)                  AS sample_n,
            COUNT(DISTINCT v.test_id)                    AS test_n,
            ROUND(COALESCE(SUM(m.std_minutes), 0) / 60.0, 2) AS std_hours
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.sample_received_dt >= CAST(:start AS date)
          AND v.sample_received_dt <  (CAST(:end_date AS date) + INTERVAL '1 day')
          AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
          AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
          AND {group_sql}
        GROUP BY v.project_id
        ORDER BY sample_n DESC
    """
    result = await db.execute(text(sql), {"start": start, "end_date": end_date})
    return [dict(r) for r in result.mappings().all()]


# ---------- 员工工时汇总 ----------

def _workload_where(scope: str, group_sql: str) -> str:
    if scope == "submitted":
        return f"""
            v.sample_received_dt >= CAST(:start AS date)
            AND v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
            AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
            AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
            AND v.tester IS NOT NULL AND TRIM(v.tester) <> ''
            AND {group_sql}
        """
    elif scope == "pending":
        return f"""
            v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
            AND v.test_authorised_dt IS NULL
            AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
            AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
            AND v.tester IS NOT NULL AND TRIM(v.tester) <> ''
            AND {group_sql}
        """
    else:  # completed (default)
        return f"""
            v.test_authorised_dt >= CAST(:start AS date)
            AND v.test_authorised_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
            AND UPPER(COALESCE(v.test_status, '')) <> 'X'
            AND v.tester IS NOT NULL AND TRIM(v.tester) <> ''
            AND {group_sql}
        """


async def get_workload_summary(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
    scope: str = "completed",
) -> list[dict]:
    """
    员工工时汇总，支持三口径：submitted（到样）/ completed（完结）/ pending（待完成）。
    JOIN mart.dim_method 取标准工时，JOIN mart.dim_employee 取姓名和部门。
    """
    group_sql, _ = _group_clause(groups)
    where = _workload_where(scope, group_sql)
    sql = f"""
        SELECT
            v.tester,
            e.employee_name,
            e.department,
            COUNT(DISTINCT v.test_id)                                      AS test_n,
            COALESCE(SUM(m.std_minutes), 0)                                AS total_minutes,
            ROUND(COALESCE(SUM(m.std_minutes), 0) / 60.0, 1)              AS total_hours
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        LEFT JOIN (SELECT employee_id, employee_name, department FROM mart.dim_employee) e
               ON v.tester = e.employee_id
        WHERE {where}
        GROUP BY v.tester, e.employee_name, e.department
        ORDER BY total_hours DESC
    """
    result = await db.execute(text(sql), {"start": start, "end_date": end_date})
    return [dict(r) for r in result.mappings().all()]


async def get_workload_kpi(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
) -> dict:
    """三口径工时汇总 KPI：送检/已完成/未完成工时及检验效率。"""
    group_sql, _ = _group_clause(groups)
    params = {"start": start, "end_date": end_date}

    sql_sub = f"""
        SELECT ROUND(COALESCE(SUM(m.std_minutes),0)/60.0,1)
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.sample_received_dt >= CAST(:start AS date)
          AND v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND UPPER(COALESCE(v.sample_status,'')) NOT IN ('X','U')
          AND UPPER(COALESCE(v.test_status,  '')) NOT IN ('X','U')
          AND {group_sql}
    """
    sql_done = f"""
        SELECT ROUND(COALESCE(SUM(m.std_minutes),0)/60.0,1)
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.test_authorised_dt >= CAST(:start AS date)
          AND v.test_authorised_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND UPPER(COALESCE(v.test_status,'')) <> 'X'
          AND {group_sql}
    """
    sql_pend = f"""
        SELECT ROUND(COALESCE(SUM(m.std_minutes),0)/60.0,1)
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND v.test_authorised_dt IS NULL
          AND UPPER(COALESCE(v.sample_status,'')) NOT IN ('X','U')
          AND UPPER(COALESCE(v.test_status,  '')) NOT IN ('X','U')
          AND {group_sql}
    """

    # method_codes that appear in the window but have no std_minutes defined
    sql_missing = f"""
        SELECT DISTINCT v.method_code
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE m.method_code IS NULL
          AND v.method_code IS NOT NULL
          AND (
              (v.sample_received_dt >= CAST(:start AS date)
               AND v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day'))
           OR (v.test_authorised_dt >= CAST(:start AS date)
               AND v.test_authorised_dt < (CAST(:end_date AS date) + INTERVAL '1 day'))
          )
          AND {group_sql}
        ORDER BY v.method_code
    """

    submitted  = float((await db.execute(text(sql_sub),     params)).scalar_one() or 0)
    completed  = float((await db.execute(text(sql_done),    params)).scalar_one() or 0)
    pending    = float((await db.execute(text(sql_pend),    params)).scalar_one() or 0)
    missing_rows = (await db.execute(text(sql_missing), params)).scalars().all()
    efficiency = round(completed / submitted, 3) if submitted > 0 else None

    return {
        "start_date": start,
        "end_date": end_date,
        "submitted_hours": submitted,
        "completed_hours": completed,
        "pending_hours": pending,
        "efficiency": efficiency,
        "missing_methods": list(missing_rows),
    }


async def get_workload_by_method(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
    scope: str = "completed",
) -> list[dict]:
    """各口径（submitted/completed/pending）方法工时占比，用于饼图。"""
    group_sql, _ = _group_clause(groups)
    where = _workload_where(scope, group_sql)
    sql = f"""
        WITH raw AS (
            SELECT v.method_code,
                   v.test_id,
                   m.std_minutes
            FROM mart.v_test_task_monitor v
            LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
            WHERE {where}
        )
        SELECT
            COALESCE(dm.method_name, r.method_code, '（未知）') AS method_name,
            r.method_code,
            COUNT(DISTINCT r.test_id)                           AS test_n,
            ROUND(COALESCE(SUM(r.std_minutes),0)/60.0,1)       AS total_hours
        FROM raw r
        LEFT JOIN mart.dim_method dm ON r.method_code = dm.method_code
        GROUP BY r.method_code, dm.method_name
        ORDER BY total_hours DESC
    """
    result = await db.execute(text(sql), {"start": start, "end_date": end_date})
    return [dict(r) for r in result.mappings().all()]


# ---------- 方法分布 ----------

async def get_method_distribution(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
) -> list[dict]:
    """到样口径各方法检项数分布，按检项数降序。"""
    group_sql, _ = _group_clause(groups)
    sql = f"""
        SELECT
            COALESCE(m.method_name, v.method_code, '（未知）') AS method_name,
            v.method_code,
            COUNT(DISTINCT v.test_id) AS test_count
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.sample_received_dt >= CAST(:start AS date)
          AND v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
          AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
          AND {group_sql}
        GROUP BY v.method_code, m.method_name
        ORDER BY test_count DESC
    """
    result = await db.execute(text(sql), {"start": start, "end_date": end_date})
    return [dict(r) for r in result.mappings().all()]


# ---------- 超期未检 ----------

async def get_overdue(
    db: AsyncSession,
    as_of: date,
    groups: list[str] | None = None,
) -> dict:
    """
    截止 as_of 日期的超期未检情况，对应 Streamlit 看板 View 4：
    - summary: 4 类未完成检项计数
    - incomplete_distribution: 未完成检项按方法分布（饼图）
    - unsubmitted_distribution: 未送样检项按方法分布（饼图）
    """
    group_sql, _ = _group_clause(groups)
    params = {"end_date": as_of}

    # 四类计数，UNION ALL 一次查完
    sql_summary = f"""
        SELECT 'unsubmitted' AS category, COUNT(DISTINCT test_id) AS n
        FROM mart.v_test_task_monitor
        WHERE test_status = 'U'
          AND request_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND {group_sql}
        UNION ALL
        SELECT 'unassigned', COUNT(DISTINCT test_id)
        FROM mart.v_test_task_monitor
        WHERE test_status = 'V'
          AND (tester IS NULL OR TRIM(tester) = '')
          AND sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND {group_sql}
        UNION ALL
        SELECT 'inprogress', COUNT(DISTINCT test_id)
        FROM mart.v_test_task_monitor
        WHERE test_status = 'V'
          AND (tester IS NOT NULL AND TRIM(tester) <> '')
          AND test_completed_dt IS NULL
          AND sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND {group_sql}
        UNION ALL
        SELECT 'unauthorized', COUNT(DISTINCT test_id)
        FROM mart.v_test_task_monitor
        WHERE test_status = 'C'
          AND sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND {group_sql}
    """

    sql_incomplete = f"""
        SELECT COALESCE(m.method_name, v.method_code, '（未知）') AS method_name,
               COUNT(DISTINCT v.test_id) AS test_count
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.sample_received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND UPPER(COALESCE(v.test_status, '')) NOT IN ('X','U')
          AND v.test_authorised_dt IS NULL
          AND {group_sql}
        GROUP BY v.method_code, m.method_name
        ORDER BY test_count DESC
    """

    sql_unsubmitted = f"""
        SELECT COALESCE(m.method_name, v.method_code, '（未知）') AS method_name,
               COUNT(DISTINCT v.test_id) AS test_count
        FROM mart.v_test_task_monitor v
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE v.request_dt < (CAST(:end_date AS date) + INTERVAL '1 day')
          AND v.test_status = 'U'
          AND {group_sql}
        GROUP BY v.method_code, m.method_name
        ORDER BY test_count DESC
    """

    summary_rows = (await db.execute(text(sql_summary), params)).mappings().all()
    summary = {r["category"]: r["n"] for r in summary_rows}

    incomplete_rows = (await db.execute(text(sql_incomplete), params)).mappings().all()
    unsubmitted_rows = (await db.execute(text(sql_unsubmitted), params)).mappings().all()

    return {
        "as_of": as_of,
        "summary": {
            "unsubmitted":  summary.get("unsubmitted", 0),
            "unassigned":   summary.get("unassigned", 0),
            "inprogress":   summary.get("inprogress", 0),
            "unauthorized": summary.get("unauthorized", 0),
        },
        "incomplete_distribution":  [dict(r) for r in incomplete_rows],
        "unsubmitted_distribution": [dict(r) for r in unsubmitted_rows],
    }


# ---------- 待检测检项导出 ----------

async def get_pending_tests(
    db: AsyncSession,
    groups: list[str] | None = None,
) -> list[dict]:
    """全量未完成检项清单，对应原版 export_pending_tests_to_excel 的口径。"""
    group_sql, _ = _group_clause(groups)

    sql = f"""
        SELECT DISTINCT
            v.test_id           AS "TN",
            v.sample_id         AS "SN",
            v.group_id          AS "样品检验组ID",
            v.project_id        AS "项目编号",
            v.sample_name       AS "样品名称",
            v.batch_number      AS "样品批号",
            v.request_dt::date  AS "请验日期",
            v.sample_received_dt::date    AS "收样日期",
            v.groupleader_received_dt::date AS "组长收样日期",
            v.assigned_dt::date AS "分配日期",
            v.method_code       AS "方法代码",
            v.method_name       AS "检验方法",
            v.test_started_dt::date       AS "开始日期",
            v.sample_status     AS "样品状态",
            v.test_status       AS "检项状态",
            v.tester            AS "检测员",
            v.test_completed_dt::date     AS "完成日期"
        FROM mart.v_test_task_monitor v
        WHERE v.test_authorised_dt IS NULL
          AND UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')
          AND UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')
          AND {group_sql}
        ORDER BY v.sample_id, v.test_id
    """

    rows = (await db.execute(text(sql))).mappings().all()
    return [dict(r) for r in rows]


# ---------- 样本总览 ----------

async def get_sample_list(
    db: AsyncSession,
    start: date,
    end_date: date,
    groups: list[str] | None = None,
    status_filter: str | None = None,
    project_search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    group_sql, _ = _group_clause(groups)
    params: dict = {
        "start": start,
        "end_date": end_date,
        "offset": (page - 1) * page_size,
        "limit": page_size,
    }

    where_parts = [
        "received_dt >= CAST(:start AS date)",
        "received_dt < (CAST(:end_date AS date) + INTERVAL '1 day')",
        group_sql,
    ]

    if status_filter == "completed":
        where_parts.append("authorised_dt IS NOT NULL")
    elif status_filter == "inprogress":
        where_parts.append("authorised_dt IS NULL AND status NOT IN ('X','U')")
    elif status_filter == "unsubmitted":
        where_parts.append("UPPER(COALESCE(status,'')) = 'U'")
    else:
        # 默认排除取消
        where_parts.append("UPPER(COALESCE(status,'')) <> 'X'")

    if project_search:
        where_parts.append("(project_id ILIKE :project_search OR sample_id ILIKE :project_search)")
        params["project_search"] = f"%{project_search}%"

    where_sql = " AND ".join(where_parts)

    sql_count = f"SELECT COUNT(*) FROM mart.v_sample_overview WHERE {where_sql}"
    sql_data = f"""
        SELECT sample_id, project_id, sample_name, batch_number, sample_type,
               received_dt::date AS received_dt,
               completed_dt::date AS completed_dt,
               authorised_dt::date AS authorised_dt,
               tester, group_id, status
        FROM mart.v_sample_overview
        WHERE {where_sql}
        ORDER BY received_dt DESC NULLS LAST, sample_id
        LIMIT :limit OFFSET :offset
    """

    total = (await db.execute(text(sql_count), params)).scalar_one() or 0
    rows = (await db.execute(text(sql_data), params)).mappings().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }


# ---------- 方法月度报表 ----------

async def get_method_monthly(
    db: AsyncSession,
    months: int = 12,
    groups: list[str] | None = None,
) -> list[dict]:
    group_sql, _ = _group_clause(groups)
    params = {"months": months}

    sql = f"""
        WITH month_range AS (
            SELECT TO_CHAR(
                DATE_TRUNC('month', NOW()) - (n || ' months')::interval,
                'YYYY-MM'
            ) AS ym
            FROM generate_series(0, :months - 1) AS n
        )
        SELECT
            mr.ym,
            COALESCE(m.method_name, v.method_code, '（未知）') AS method_name,
            v.method_code,
            COUNT(DISTINCT v.test_id) AS test_n,
            ROUND(
                SUM(COALESCE(m.std_minutes, 0))::numeric / 60.0,
                2
            ) AS std_hours
        FROM month_range mr
        JOIN mart.v_test_task_monitor v
            ON TO_CHAR(v.test_authorised_dt, 'YYYY-MM') = mr.ym
        LEFT JOIN mart.dim_method m ON v.method_code = m.method_code
        WHERE UPPER(COALESCE(v.test_status, '')) NOT IN ('X','U')
          AND {group_sql}
        GROUP BY mr.ym, v.method_code, m.method_name
        ORDER BY mr.ym, test_n DESC
    """

    rows = (await db.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]
