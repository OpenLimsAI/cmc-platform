"""旧看板筛选体验；批号年份仅为旧规则推算，不是检测日期。"""
import pandas as pd

from app.schemas.release import ReleaseRequest
from app.services.mapping.batch import extract_year_from_batch


def filter_release_rows(df: pd.DataFrame, req: ReleaseRequest) -> pd.DataFrame:
    result = df.copy()
    if result.empty:
        return result
    for field, selected in (
        ("group_id", req.group_ids), ("batch_number", req.batch_numbers),
        ("test_type", req.test_types), ("placement_status", req.placement_statuses),
    ):
        if selected:
            result = result[result.get(field, pd.Series(None, index=result.index, dtype=object)).isin(selected)]
    if req.batch_years or req.include_unknown_batch_year:
        years = result["batch_number"].map(extract_year_from_batch)
        mask = years.isin(req.batch_years or [])
        if req.include_unknown_batch_year:
            mask |= years.isna()
        result = result[mask]
    return result.reset_index(drop=True)


def release_options(df: pd.DataFrame) -> dict:
    """选项仅取当前项目的放行数值记录，不猜测来源缺失字段。"""
    def values(column):
        return sorted(str(value) for value in df[column].dropna().unique()) if column in df else []

    years = df["batch_number"].map(extract_year_from_batch) if "batch_number" in df else pd.Series(dtype=float)
    attributes = []
    if not df.empty:
        for name, group in df.groupby("attribute_name", sort=True):
            attributes.append({
                "attribute_name": name, "n": int(len(group)),
                "attribute_raws": sorted(str(x) for x in group["attribute_raw"].dropna().unique()),
            })
    return {
        "production_line_ids": values("production_line_id"), "group_ids": values("group_id"),
        "batch_numbers": values("batch_number"), "test_types": values("test_type"),
        "placement_statuses": values("placement_status"), "sample_types": values("sample_type"), "attributes": attributes,
        "batch_years": sorted(int(year) for year in years.dropna().unique()),
        "unknown_batch_year_count": int(years.isna().sum()),
        "year_basis": "legacy_batch_number_inference", "row_count": int(len(df)),
    }
