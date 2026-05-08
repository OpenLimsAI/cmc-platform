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
    ],
)
def test_severity_classification(days, threshold, expected):
    assert severity_of(days, warning_threshold=threshold) == expected
