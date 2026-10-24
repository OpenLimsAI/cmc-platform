# -*- coding: utf-8 -*-
"""质量结果数据访问层：只读共享 staging 三表中的 RD / 旧 QC 记录。

设计要点：
- **只读**：所有查询走只读引擎（database.py 强制 read-only）。
- **source_system**：默认 rd_samplemanager；显式 QC 仅取 gmp_labvantage 历史记录，
  不含 stg_lv_*、旧 Excel 或最新 GMP 快照，不把 RD 检测项字典套用到 QC。
- **契约**：输出列 = project_id, production_line_id, group_id, sample_type, batch_number,
  test_type, data_type(派生), timepoint, timepoint_unit, attribute_raw, attribute_name(映射),
  value, value_str, unit, judgement, method_code, source_system, received_dt, sample_id。
- 长期目标态：中台提供 mart.fct_quality_result 后，新增 MartQualityRepository 直读单表即可
  （本类与接口隔离）。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.mapping import attribute_mapping, data_type
from app.services.mapping.batch import extract_batch_order, extract_year_from_batch


@dataclass
class QualityFilter:
    project_id: str | None = None
    production_line_ids: list[str] | None = None
    sample_type: str | None = None
    data_types: list[str] | None = None        # 派生后过滤：["Release"] / ["Release","Stability"]
    attribute_names: list[str] | None = None    # canonical 英文，映射后过滤
    source_systems: list[str] = field(default_factory=lambda: list(settings.source_systems))
    only_mapped: bool = False                    # True=仅已映射 canonical 的检测项；False=未映射用原始名显示


_BASE_SQL = """
SELECT
    s.source_system,
    s.source_id              AS sample_id,
    t.source_id              AS source_test_id,
    r.source_id              AS source_result_id,
    s.project_id,
    s.production_line_id,
    s.group_id,
    s.sample_type,
    s.test_type,
    s.batch_number,
    s.timepoint,
    s.timepoint_unit,
    s.received_dt,
    t.method_code,
    t.method_name,
    r.attribute              AS attribute_raw,
    r.value_num              AS value,
    r.value_str,
    r.unit,
    r.judgement
FROM staging.stg_sample s
JOIN staging.stg_test   t ON t.source_system = s.source_system AND t.source_sample_id = s.source_id
JOIN staging.stg_result r ON r.source_system = t.source_system AND r.source_test_id  = t.source_id
WHERE s.source_system = ANY(:source_systems)
  AND r.value_num IS NOT NULL
  AND s.project_id IS NOT NULL
"""


class QualityRepository(ABC):
    """质量数据访问接口（便于 Phase2/3 切换实现，如改读 mart.fct_quality_result）。"""

    @abstractmethod
    def fetch_long_table(self, flt: QualityFilter) -> pd.DataFrame: ...


class StagingQualityRepository(QualityRepository):
    def __init__(self, session: Session):
        self.session = session

    def fetch_long_table(self, flt: QualityFilter) -> pd.DataFrame:
        if flt.source_systems == ["legacy_excel_qc"]:
            from app.repositories.legacy_excel_repository import LegacyExcelRepository
            return LegacyExcelRepository(self.session).fetch_long_table(flt)
        sql = _BASE_SQL
        params: dict = {"source_systems": flt.source_systems}
        if flt.project_id:
            sql += " AND s.project_id = :project_id"
            params["project_id"] = flt.project_id
        if flt.production_line_ids:
            sql += " AND s.production_line_id = ANY(:lines)"
            params["lines"] = flt.production_line_ids
        if flt.sample_type:
            sql += " AND s.sample_type = :sample_type"
            params["sample_type"] = flt.sample_type

        rows = self.session.execute(text(sql), params).mappings().all()
        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # ---- 派生 data_type、映射 attribute_name、is_pct ----
        df["data_type"] = df["test_type"].map(data_type.classify)
        df["attribute_canonical"] = df["attribute_raw"].map(attribute_mapping.map_name)
        df["is_pct"] = df["attribute_raw"].map(attribute_mapping.is_pct)
        # 展示用名称：已映射用 canonical 英文，未映射回退原始名（保证数据照样能提取/展示）
        df["attribute_name"] = df["attribute_canonical"].fillna(df["attribute_raw"])
        # QC 旧 staging 仅接受来源中这两个明确类别；不套用 RD 关键词推断、
        # 指标映射和百分比口径。其余 QC 类别保留为 Unknown，供覆盖率查看。
        qc = df["source_system"].eq("gmp_labvantage")
        df.loc[qc, "data_type"] = df.loc[qc, "test_type"].map({"常规放行": "Release", "稳定性": "Stability"}).fillna("Unknown")
        df.loc[qc, "attribute_canonical"] = None
        df.loc[qc, "attribute_name"] = df.loc[qc, "attribute_raw"]
        df.loc[qc, "is_pct"] = False

        # ---- 派生过滤 ----
        if flt.only_mapped:
            df = df[df["attribute_canonical"].notna()]
        if flt.data_types:
            df = df[df["data_type"].isin(flt.data_types)]
        if flt.attribute_names:
            df = df[df["attribute_name"].isin(flt.attribute_names)]

        return df.reset_index(drop=True)

    # ---------- 维度枚举（驱动前端筛选器） ----------
    def list_projects(self, source_systems: list[str] | None = None) -> list[dict]:
        if source_systems == ["legacy_excel_qc"]:
            from app.repositories.legacy_excel_repository import LegacyExcelRepository
            return LegacyExcelRepository(self.session).list_projects()
        sql = """
        SELECT s.project_id, count(*) AS n
        FROM staging.stg_sample s
        JOIN staging.stg_test t ON t.source_system=s.source_system AND t.source_sample_id=s.source_id
        JOIN staging.stg_result r ON r.source_system=t.source_system AND r.source_test_id=t.source_id
        WHERE s.source_system = ANY(:ss) AND r.value_num IS NOT NULL AND s.project_id IS NOT NULL
        GROUP BY s.project_id ORDER BY n DESC
        """
        rows = self.session.execute(text(sql), {"ss": list(settings.source_systems) if source_systems is None else source_systems}).mappings().all()
        return [dict(r) for r in rows]

    def list_lines(self, project_id: str | None = None, source_systems: list[str] | None = None) -> list[str]:
        if source_systems == ["legacy_excel_qc"]:
            from app.repositories.legacy_excel_repository import LegacyExcelRepository
            return LegacyExcelRepository(self.session).list_lines(project_id)
        sql = "SELECT DISTINCT production_line_id FROM staging.stg_sample WHERE source_system = ANY(:ss) AND production_line_id IS NOT NULL"
        params = {"ss": list(settings.source_systems) if source_systems is None else source_systems}
        if project_id:
            sql += " AND project_id = :pid"
            params["pid"] = project_id
        sql += " ORDER BY 1"
        return [r[0] for r in self.session.execute(text(sql), params).all()]

    def list_attributes(self, project_id: str | None = None, data_types: list[str] | None = None, source_systems: list[str] | None = None) -> list[dict]:
        """列出可选检测项（原始名 + 映射后 canonical + 行数），驱动前端属性多选。"""
        flt = QualityFilter(project_id=project_id, data_types=data_types, only_mapped=False)
        if source_systems is not None:
            flt.source_systems = source_systems
        df = self.fetch_long_table(flt)
        if df.empty:
            return []
        # 按展示名(attribute_name)去重并合并行数（与看板 groupby 口径一致，避免下拉重复 value）。
        # 多个原始名映射到同一展示名时，raws 收集到一起备查。
        g = (
            df.groupby("attribute_name")
            .agg(n=("value", "count"), raws=("attribute_raw", lambda s: sorted(set(s))))
            .reset_index()
            .sort_values("n", ascending=False)
        )
        return [
            {"attribute_name": r.attribute_name, "attribute_raws": list(r.raws), "n": int(r.n)}
            for r in g.itertuples(index=False)
        ]

    # ---------- 覆盖率报表（透明暴露未分类/未映射） ----------
    def coverage_report(self, project_id: str | None = None, source_systems: list[str] | None = None) -> dict:
        flt = QualityFilter(project_id=project_id, only_mapped=False)
        if source_systems is not None:
            flt.source_systems = source_systems
        df = self.fetch_long_table(flt)
        if df.empty:
            return {"total_rows": 0}
        total = len(df)
        dt = df["data_type"].value_counts(dropna=False).to_dict()
        mapped = int(df["attribute_canonical"].notna().sum())
        return {
            "total_rows": total,
            "data_type_counts": {str(k): int(v) for k, v in dt.items()},
            "attribute_mapped_rows": mapped,
            "attribute_unmapped_rows": total - mapped,
            "attribute_mapped_pct": round(mapped / total * 100, 1) if total else 0,
            "distinct_attribute_raw": int(df["attribute_raw"].nunique()),
            "distinct_attribute_unmapped": int(df.loc[df["attribute_canonical"].isna(), "attribute_raw"].nunique()),
        }


__all__ = ["QualityFilter", "QualityRepository", "StagingQualityRepository",
           "extract_batch_order", "extract_year_from_batch"]
