"""
文件: backend/tests/test_severity.py
用途: 严重度纯函数 severity_of 的单元测试(不连库)
"""
from __future__ import annotations

import pytest

from crud import severity_of


@pytest.mark.parametrize(
    "days, threshold, expected",
    [
        (-1,  90, "EXPIRED"),
        (-365, 90, "EXPIRED"),
        (0,   90, "URGENT"),
        (15,  90, "URGENT"),
        (30,  90, "URGENT"),    # 30 天临界 → URGENT(README §5.5)
        (31,  90, "WARNING"),
        (60,  90, "WARNING"),
        (90,  90, "WARNING"),   # 90 天临界 → WARNING
        (91,  90, None),        # 超出阈值,不告警
        (10,  30, "URGENT"),    # threshold=30 时 31 天就脱出
        (31,  30, None),
        (5,   7,  "URGENT"),    # 窗口 < 30 时 URGENT 上限收到窗口
        (7,   7,  "URGENT"),
        (25,  7,  None),        # 窗口外不返回(修复:曾被硬编码 30 误判为 URGENT)
    ],
)
def test_severity_classification(days, threshold, expected):
    assert severity_of(days, warning_threshold=threshold) == expected
