# 回归护栏：2026-08 体检修过的坑，用测试钉住不许再犯
import inspect
from decimal import Decimal

from app.schemas.lims.stats import WorkloadItem
from app.services.lims import stats_service


def test_workload_minutes_accepts_decimal_fraction():
    """std_minutes 是 Numeric(6,2)，SUM 出带小数的 Decimal；int 字段曾让工时接口整个 500。"""
    item = WorkloadItem(tester="t", test_n=1, total_minutes=Decimal("37.50"), total_hours=0.6)
    assert item.total_minutes == 37.5


def test_pending_scope_is_as_of_end_date():
    """"未完成"必须是"截至所选日期未完成"：漏掉 OR test_authorised_dt >= end+1day
    会把之后完成的检项从历史结存里错误扣掉（KPI 与月度趋势对不上）。"""
    where = stats_service._workload_where("pending", "TRUE")
    assert "test_authorised_dt IS NULL" in where
    assert "test_authorised_dt >= (CAST(:end_date AS date) + INTERVAL '1 day')" in where

    kpi_src = inspect.getsource(stats_service.get_kpi)
    assert "OR test_authorised_dt >= (CAST(:end_date AS date) + INTERVAL '1 day')" in kpi_src


def test_date_windows_are_half_open():
    """日期窗口统一左闭右开 [start, end+1day)，不许出现 BETWEEN/<= 混用。"""
    assert ">= CAST(:start AS date)" in stats_service._DATE_WINDOW_RECEIVED
    assert "< (CAST(:end_date AS date) + INTERVAL '1 day')" in stats_service._DATE_WINDOW_RECEIVED
    assert "< (CAST(:end_date AS date) + INTERVAL '1 day')" in stats_service._DATE_WINDOW_AUTHORISED


def test_freshness_scoped_to_lims_job():
    """"ETL 更新"必须限定本管道 job_name：meta.etl_run 是多 ETL 共用台账，
    不过滤会被 lucullus 的成功"代刷"，LIMS 断流被掩盖（2026-07 事故根因之一）。"""
    src = inspect.getsource(stats_service.get_data_freshness)
    assert "job_name = 'rd_lims_etl_samplemanager'" in src
    # timestamptz 再套 AT TIME ZONE 'UTC' 会剥时区显示慢 8 小时——SQL 里不许出现
    # （注释里解释性提及不算，所以只检查 SQL 字符串行）
    sql_lines = [l for l in src.splitlines() if l.strip().startswith('"')]
    assert not any("AT TIME ZONE" in l for l in sql_lines)


def test_inprogress_filter_keeps_null_status():
    """样品"检验中"筛选必须 COALESCE 保留状态为空的行，与"全部"分支口径一致。"""
    src = inspect.getsource(stats_service.get_sample_list)
    assert "UPPER(COALESCE(status,'')) NOT IN ('X','U')" in src
