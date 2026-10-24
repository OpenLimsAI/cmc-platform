# -*- coding: utf-8 -*-
"""data_type 派生：把杂乱的 test_type(检验类别) 归类为 Release / Stability / Unknown。

数据来源现实：staging 没有 data_type 列；test_type 是 300+ 自由文本（最多"常规检测"，
无一条"放行"）。因此 Release/Stability 必须靠业务归类。

权威来源 = 一份可编辑 CSV：config/test_type_buckets.csv（列：test_type,count,bucket）。
- bucket ∈ {Release, Stability, Exclude}（Exclude/空/未知 → 派生为 Unknown，不进看板）。
- 该 CSV 由用户逐个归类（见 scripts/gen_test_type_worksheet.py 生成草稿）。
- 未出现在 CSV 中的新 test_type → 走 suggest_bucket() 启发式兜底，并计入"未分类"。
"""
import csv
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"  # app/config
BUCKETS_CSV = CONFIG_DIR / "test_type_buckets.csv"

# 启发式关键词（用于生成草稿与兜底未覆盖值）。仅作建议，权威以 CSV 的 bucket 为准。
_STABILITY_KW = ("稳定", "长期", "long-term", "long term", "冻融", "光照",
                 "氧化试验", "ph试验", "pH试验", "pH Stress", "stress", "高温", "孵育稳定")
_RELEASE_KW = ("常规检测", "常规检验", "常规", "全检", "复验", "成品", "原液", "放行", "中间产品")


def suggest_bucket(test_type: str | None) -> str:
    """对单个 test_type 给出建议归类（Release / Stability / Exclude）。"""
    if not test_type or not str(test_type).strip():
        return "Exclude"
    s = str(test_type).strip()
    low = s.lower()
    for kw in _STABILITY_KW:
        if kw.lower() in low:
            return "Stability"
    for kw in _RELEASE_KW:
        if kw.lower() in low:
            return "Release"
    # 其余（方法名/小试/方法开发/工艺研究/测试垃圾等）默认排除，待用户确认
    return "Exclude"


@lru_cache(maxsize=1)
def _load_buckets() -> dict[str, str]:
    """加载权威分类表 test_type -> bucket。CSV 不存在则返回空（全部走兜底）。"""
    mapping: dict[str, str] = {}
    if not BUCKETS_CSV.exists():
        return mapping
    with BUCKETS_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tt = (row.get("test_type") or "").strip()
            bucket = (row.get("bucket") or "").strip()
            if tt:
                mapping[tt] = bucket or "Exclude"
    return mapping


def classify(test_type: str | None) -> str:
    """把 test_type 派生为 data_type：Release / Stability / Unknown。

    Exclude 与未覆盖（兜底也判 Exclude）→ Unknown（不进看板，但会被统计为未分类）。
    """
    buckets = _load_buckets()
    raw = (test_type or "").strip()
    bucket = buckets.get(raw)
    if bucket is None:                 # CSV 未覆盖 → 启发式兜底
        bucket = suggest_bucket(raw)
    return bucket if bucket in ("Release", "Stability") else "Unknown"


def reload_buckets() -> None:
    """清缓存（编辑 CSV 后调用）。"""
    _load_buckets.cache_clear()
