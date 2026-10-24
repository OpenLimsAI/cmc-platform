# 检验员工作台口径护栏（docs/tester_workbench.md）
import inspect

from app.services.lims import tester_service


def test_pending_filter_is_backlog_scope():
    """在手 = 本人 + 未授权 + 已收样 + 样品/检项均排除 X/U（结存口径，与检验周期页"当前超时限"一致）。"""
    f = tester_service._PENDING_FILTER
    assert "v.tester = :tester" in f
    assert "v.test_authorised_dt IS NULL" in f
    assert "v.sample_received_dt < (CAST(:as_of AS date) + INTERVAL '1 day')" in f
    assert "UPPER(COALESCE(v.sample_status, '')) NOT IN ('X','U')" in f
    assert "UPPER(COALESCE(v.test_status,   '')) NOT IN ('X','U')" in f


def test_over_target_uses_biz_days_from_received():
    """超时限 = 收样起算的工作日 > COALESCE(target_days, 默认)，不许用自然日或分配日。"""
    cte = tester_service._PENDING_CTE
    assert "COALESCE(m.target_days, :deft)" in cte
    assert "EXTRACT(DOW FROM v.sample_received_dt::date)" in cte  # 49 元素工作日查表法
    assert "assigned_dt::date" not in cte.split("elapsed_biz_days")[0]


def test_month_windows_half_open():
    """本月 = [月初, as_of+1)；上月 = [上月初, 本月初)，左闭右开不重叠。"""
    src = inspect.getsource(tester_service.get_tester_summary)
    assert "v.test_authorised_dt >= w.prev_start" in src
    assert "v.test_authorised_dt <  w.cur_end" in src
    assert "(CAST(:as_of AS date) + INTERVAL '1 day')::date" in src


def test_tester_list_excludes_blank_tester():
    src = inspect.getsource(tester_service.list_testers)
    assert "v.tester IS NOT NULL AND TRIM(v.tester) <> ''" in src
