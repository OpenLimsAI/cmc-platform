# -*- coding: utf-8 -*-
"""检测项映射：原始中文 attribute(LIMS result.NAME) → canonical 英文 attribute_name。

权威来源 = 可编辑 CSV：config/attribute_map.csv
列：attribute_raw, count, attribute_name, is_pct
- attribute_name：canonical 英文标准名（如 sec_aggregate_pct）；空 → 视为未映射。
- is_pct：该指标是否以百分比存储（结果为小数、绘图需 ×100），取 true/false。
未映射的原始 attribute → map_name() 返回 None，调用方计入"未映射"并可选择丢弃。
"""
import csv
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"  # app/config
ATTR_CSV = CONFIG_DIR / "attribute_map.csv"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    if not ATTR_CSV.exists():
        return mapping
    with ATTR_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("attribute_raw") or "").strip()
            name = (row.get("attribute_name") or "").strip()
            is_pct = (row.get("is_pct") or "").strip().lower() in ("true", "1", "yes", "y")
            if raw and name:
                mapping[raw] = {"attribute_name": name, "is_pct": is_pct}
    return mapping


def map_name(attribute_raw: str | None) -> str | None:
    """原始中文 → canonical 英文；未映射返回 None。"""
    if not attribute_raw:
        return None
    rec = _load().get(str(attribute_raw).strip())
    return rec["attribute_name"] if rec else None


def is_pct(attribute_raw: str | None) -> bool:
    """该原始指标是否为百分比型（驱动绘图 ×100）。未映射默认 False。"""
    if not attribute_raw:
        return False
    rec = _load().get(str(attribute_raw).strip())
    return bool(rec["is_pct"]) if rec else False


def reload_map() -> None:
    _load.cache_clear()
