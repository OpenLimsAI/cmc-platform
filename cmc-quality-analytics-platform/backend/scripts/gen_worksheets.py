# -*- coding: utf-8 -*-
"""生成两份给业务核对的工作表 CSV（只读查询 cmc_analytics）：

1) config/test_type_buckets.csv  —— test_type, count, bucket(建议)
   用户把 bucket 改成 Release / Stability / Exclude 即可。

2) config/attribute_map.csv      —— attribute_raw, count, attribute_name(草稿), is_pct(草稿)
   用户核对/补全 attribute_name(canonical 英文) 与 is_pct(是否百分比)。

用法：  uv run python scripts/gen_worksheets.py
重跑会保留已存在文件中用户已填写的值（按 key 合并），仅追加新出现的取值。
"""
import csv
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.services.mapping.data_type import suggest_bucket

CONFIG_DIR = Path(__file__).resolve().parents[1] / "app" / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# 高频检测项的 canonical 英文草稿（仅供用户核对，可能不准；空字符串=留给用户填）。
DRAFT_CANONICAL: dict[str, tuple[str, bool]] = {
    "聚合体峰面积之和": ("sec_aggregate_pct", True),
    "单体峰面积": ("sec_monomer_pct", True),
    "片段峰面积之和": ("sec_fragment_pct", True),
    "主峰": ("main_peak_pct", True),
    "主峰峰面积": ("main_peak_pct", True),
    "碱性变异体": ("iex_basic_variants_pct", True),
    "酸性变异体": ("iex_acidic_variants_pct", True),
    "R-CE纯度": ("rce_purity_pct", True),
    "NR-CE主峰峰面积": ("nrce_main_peak_pct", True),
    "NR-CE报告片段峰面积之和": ("nrce_fragment_pct", True),
    "NGHC": ("nghc_pct", True),
    "表达量": ("expression_titer", False),
    "蛋白含量均值": ("protein_content", False),
    "蛋白含量测定": ("protein_content", False),
    "蛋白质含量测定": ("protein_content", False),
    "氧化修饰比例": ("oxidation_pct", True),
    "脱氨基修饰比例": ("deamidation_pct", True),
}


def _load_existing(path: Path, key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                k = (row.get(key) or "").strip()
                if k:
                    out[k] = row
    return out


def gen_test_type():
    path = CONFIG_DIR / "test_type_buckets.csv"
    existing = _load_existing(path, "test_type")
    sql = """
        SELECT test_type, count(*) AS n
        FROM staging.stg_sample
        WHERE source_system = ANY(:ss) AND project_id IS NOT NULL
        GROUP BY test_type ORDER BY n DESC
    """
    with engine.connect() as c:
        rows = c.execute(text(sql), {"ss": list(settings.source_systems)}).all()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test_type", "count", "bucket"])
        for tt, n in rows:
            tt = tt or ""
            # 保留用户已填的 bucket；否则用建议
            prev = existing.get(tt.strip())
            bucket = (prev or {}).get("bucket", "").strip() if prev else ""
            if not bucket:
                bucket = suggest_bucket(tt)
            w.writerow([tt, n, bucket])
    print(f"[ok] {path}  ({len(rows)} 行)")


def gen_attribute_map():
    path = CONFIG_DIR / "attribute_map.csv"
    existing = _load_existing(path, "attribute_raw")
    sql = """
        SELECT r.attribute, count(*) AS n
        FROM staging.stg_sample s
        JOIN staging.stg_test t ON t.source_system=s.source_system AND t.source_sample_id=s.source_id
        JOIN staging.stg_result r ON r.source_system=t.source_system AND r.source_test_id=t.source_id
        WHERE s.source_system = ANY(:ss) AND r.value_num IS NOT NULL AND r.attribute IS NOT NULL
        GROUP BY r.attribute ORDER BY n DESC
    """
    with engine.connect() as c:
        rows = c.execute(text(sql), {"ss": list(settings.source_systems)}).all()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["attribute_raw", "count", "attribute_name", "is_pct"])
        for raw, n in rows:
            raw = raw or ""
            prev = existing.get(raw.strip())
            if prev and (prev.get("attribute_name") or "").strip():
                name = prev["attribute_name"].strip()
                is_pct = (prev.get("is_pct") or "").strip()
            else:
                draft = DRAFT_CANONICAL.get(raw.strip())
                name = draft[0] if draft else ""
                is_pct = str(draft[1]).lower() if draft else ""
            w.writerow([raw, n, name, is_pct])
    print(f"[ok] {path}  ({len(rows)} 行)")


if __name__ == "__main__":
    gen_test_type()
    gen_attribute_map()
