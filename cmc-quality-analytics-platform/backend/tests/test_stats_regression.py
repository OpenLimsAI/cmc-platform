# -*- coding: utf-8 -*-
"""Golden 回归对齐：新移植统计引擎 vs 旧 Streamlit 工具原始实现。

策略：同一 Python 进程、同一库版本，对同一批（含随机种子）输入分别调用
"旧函数"与"新函数"，逐一断言结果完全一致。用于尚未修正的移植函数。TOST/Tier已改为独立验证，见 test_equivalence_corrected.py。

若旧工具不可导入（路径缺失/环境差异），整文件 skip——但 CI/本地有旧工具时必须全绿。
"""
import math

import numpy as np
import pandas as pd
import pytest

# ---- 新移植实现 ----
from app.services.stats import (
    clean_numeric as new_clean_numeric,
    compute_auto_margins as new_compute_auto_margins,
    compute_capability as new_compute_capability,
    compute_rsd as new_compute_rsd,
    compute_stats as new_compute_stats,
    levene_test as new_levene_test,
    linear_regression_summary as new_linear_regression_summary,
    run_lme_for_pair as new_run_lme_for_pair,
    within_group_slope_pool_test as new_within_group_slope_pool_test,
)

# ---- 旧工具原始实现（可选导入）----
try:
    from analytics.stat_core import (
        compute_auto_margins as old_compute_auto_margins,
        compute_rsd as old_compute_rsd,
        linear_regression_summary as old_linear_regression_summary,
        run_lme_for_pair as old_run_lme_for_pair,
        within_group_slope_pool_test as old_within_group_slope_pool_test,
    )
    from analytics.equivalence_test import (
        levene_test as old_levene_test,
    )
    from components.utils import (
        clean_numeric as old_clean_numeric,
        compute_capability as old_compute_capability,
        compute_stats as old_compute_stats,
    )
    _OLD_OK = True
    _OLD_ERR = None
except Exception as exc:  # pragma: no cover
    _OLD_OK = False
    _OLD_ERR = repr(exc)

pytestmark = pytest.mark.skipif(not _OLD_OK, reason=f"旧工具不可导入: {_OLD_ERR}")


# =====================================================================
# 通用比较器
# =====================================================================
def assert_equal(old, new, ctx=""):
    """递归比较：标量(含 NaN)、字符串、dict、tuple/list、Series、DataFrame。"""
    # None
    if old is None or new is None:
        assert old is new or (old is None and new is None), f"{ctx}: None 不一致 old={old} new={new}"
        return
    # 字符串
    if isinstance(old, str) or isinstance(new, str):
        assert old == new, f"{ctx}: 字符串不一致 old={old!r} new={new!r}"
        return
    # bool（注意要在 int 之前）
    if isinstance(old, (bool, np.bool_)) or isinstance(new, (bool, np.bool_)):
        assert bool(old) == bool(new), f"{ctx}: bool 不一致 old={old} new={new}"
        return
    # dict
    if isinstance(old, dict):
        assert isinstance(new, dict), f"{ctx}: 类型不一致"
        assert set(old.keys()) == set(new.keys()), f"{ctx}: dict keys 不一致 old={set(old)} new={set(new)}"
        for k in old:
            assert_equal(old[k], new[k], ctx=f"{ctx}.{k}")
        return
    # DataFrame
    if isinstance(old, pd.DataFrame):
        pd.testing.assert_frame_equal(
            old.reset_index(drop=True), new.reset_index(drop=True),
            check_exact=False, rtol=1e-9, atol=1e-12, check_dtype=False,
        )
        return
    # Series
    if isinstance(old, pd.Series):
        pd.testing.assert_series_equal(
            old.reset_index(drop=True), new.reset_index(drop=True),
            check_exact=False, rtol=1e-9, atol=1e-12, check_dtype=False, check_names=False,
        )
        return
    # tuple/list
    if isinstance(old, (tuple, list)):
        assert len(old) == len(new), f"{ctx}: 长度不一致"
        for i, (a, b) in enumerate(zip(old, new)):
            assert_equal(a, b, ctx=f"{ctx}[{i}]")
        return
    # 数值（含 NaN）
    try:
        a = float(old)
        b = float(new)
        if math.isnan(a) or math.isnan(b):
            assert math.isnan(a) and math.isnan(b), f"{ctx}: NaN 不一致 old={a} new={b}"
        else:
            assert a == pytest.approx(b, rel=1e-9, abs=1e-12), f"{ctx}: 数值不一致 old={a} new={b}"
        return
    except (TypeError, ValueError):
        pass
    assert old == new, f"{ctx}: 不一致 old={old!r} new={new!r}"


# =====================================================================
# levene_test
# =====================================================================
@pytest.mark.parametrize("seed", range(6))
def test_levene_test(seed):
    rng = np.random.default_rng(seed + 100)
    ref = rng.normal(50, rng.uniform(1, 4), size=rng.integers(3, 10)).tolist()
    tst = rng.normal(50, rng.uniform(1, 4), size=rng.integers(3, 10)).tolist()
    assert_equal(old_levene_test(ref, tst), new_levene_test(ref, tst), ctx=f"levene_test(seed={seed})")


def test_levene_test_small():
    assert_equal(old_levene_test([1.0], [2.0, 3.0]),
                 new_levene_test([1.0], [2.0, 3.0]), ctx="levene_small")


# =====================================================================
# compute_capability
# =====================================================================
@pytest.mark.parametrize("lsl,usl", [(None, 5.0), (1.0, None), (1.0, 5.0), (None, None)])
@pytest.mark.parametrize("mode", ["sample", "population"])
def test_compute_capability(lsl, usl, mode):
    old = old_compute_capability(lsl, usl, 3.0, 0.4, 0.35, mode)
    new = new_compute_capability(lsl, usl, 3.0, 0.4, 0.35, mode)
    assert_equal(old, new, ctx=f"capability({lsl},{usl},{mode})")


# =====================================================================
# compute_stats / compute_rsd / clean_numeric
# =====================================================================
@pytest.mark.parametrize("is_pct", [True, False])
def test_compute_stats(is_pct):
    rng = np.random.default_rng(7)
    df = pd.DataFrame({"value": rng.normal(0.95, 0.02, size=20)})
    assert_equal(old_compute_stats(df, is_pct=is_pct),
                 new_compute_stats(df, is_pct=is_pct), ctx=f"compute_stats(is_pct={is_pct})")


def test_compute_rsd():
    s = pd.Series([1.0, 1.1, 0.9, 1.05, 0.98])
    assert_equal(old_compute_rsd(s), new_compute_rsd(s), ctx="compute_rsd")


def test_clean_numeric():
    vals = ["12%", "1.2e-3", "-3E+05", "abc", "", "3.5E-2%", "100"]
    old = old_clean_numeric(vals)
    new = new_clean_numeric(vals)
    assert_equal(pd.Series(old), pd.Series(new), ctx="clean_numeric")


# =====================================================================
# compute_auto_margins
# =====================================================================
def _ts_df(seed):
    rng = np.random.default_rng(seed + 300)
    rows = []
    for batch in ["b1", "b2", "b3"]:
        base = rng.normal(100, 2)
        slope = rng.normal(0, 0.5)
        for t in [0, 1, 3, 6]:
            rows.append({"grp": "ctrl", "t": t, "batch": batch,
                         "val": base + slope * t + rng.normal(0, 0.3)})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("seed", range(4))
def test_compute_auto_margins(seed):
    df = _ts_df(seed)
    assert_equal(old_compute_auto_margins(df, "val", "ctrl", "grp", "t", "batch", k=1.5),
                 new_compute_auto_margins(df, "val", "ctrl", "grp", "t", "batch", k=1.5),
                 ctx=f"auto_margins(seed={seed})")


# =====================================================================
# within_group_slope_pool_test
# =====================================================================
@pytest.mark.parametrize("seed", range(4))
def test_within_group_slope_pool_test(seed):
    df = _ts_df(seed).rename(columns={"val": "y"})
    df["y"] = df["y"]  # noqa
    old = old_within_group_slope_pool_test(df, "ctrl", "t", "grp", "batch")
    new = new_within_group_slope_pool_test(df, "ctrl", "t", "grp", "batch")
    assert_equal(old, new, ctx=f"slope_pool(seed={seed})")


# =====================================================================
# run_lme_for_pair
# =====================================================================
def _pair_df(seed):
    rng = np.random.default_rng(seed + 400)
    rows = []
    for grp, drift in [("ctrl", 0.0), ("cmp", rng.normal(0, 0.4))]:
        for batch in ["b1", "b2"]:
            base = rng.normal(100, 1.5)
            slope = rng.normal(0, 0.3) + drift
            for t in [0, 1, 3, 6, 9]:
                rows.append({"group": grp, "time": t, "batch": f"{grp}_{batch}",
                             "val": base + slope * t + rng.normal(0, 0.25)})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("seed", range(4))
def test_run_lme_for_pair(seed):
    df = _pair_df(seed)
    old = old_run_lme_for_pair(df, "val", "ctrl", "cmp", "time", "group", "batch")
    new = new_run_lme_for_pair(df, "val", "ctrl", "cmp", "time", "group", "batch")
    assert_equal(old, new, ctx=f"lme(seed={seed})")


# =====================================================================
# linear_regression_summary
# =====================================================================
def test_linear_regression_summary():
    rng = np.random.default_rng(9)
    rows = []
    for g in ["A", "B"]:
        for t in [0, 1, 2, 3, 4]:
            rows.append({"group_id": g, "time_numeric": t, "value": 10 + 0.5 * t + rng.normal(0, 0.1)})
    df = pd.DataFrame(rows)
    assert_equal(old_linear_regression_summary(df, "attr"),
                 new_linear_regression_summary(df, "attr"), ctx="linreg")
