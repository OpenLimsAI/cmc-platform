"""单来源读取契约；QC 为共享 staging 历史，EXCEL 为旧 Excel 表，禁止混合。"""
from typing import Literal

DataSource = Literal["RD", "QC", "EXCEL"]
DATA_SOURCE_MAP = {"RD": ["rd_samplemanager"], "QC": ["gmp_labvantage"], "EXCEL": ["legacy_excel_qc"]}


def source_meta(source: DataSource) -> dict:
    return {
        "data_source": source,
        "source_scope": {"RD": "rd_staging", "QC": "qc_legacy_staging", "EXCEL": "legacy_excel_quality"}[source],
        "legacy_excel_included": source == "EXCEL",
        "approval_state": "not_evaluated",
    }
