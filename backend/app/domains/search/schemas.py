"""
全局搜索 schemas
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict

SearchEntityType = Literal["substance", "project", "asset", "material", "equipment"]
MatchedField = Literal[
    "code", "name", "name_en", "internal_code", "objective", "xref",
    "trade_name", "inn_name", "source_name", "model", "manufacturer", "serial_no",
    "equipment_no", "fixed_asset_no",
]


class SearchHit(BaseModel):
    """搜索单条命中"""

    model_config = ConfigDict(from_attributes=True)

    entity_type: SearchEntityType
    code: str
    name: str
    status: str | None = None
    matched_field: MatchedField
    sub_type: str | None = None  # substance_type / project_type / asset_type
    snippet: str | None = None  # 命中字段的局部值（xref 命中时显示 xref_value）


class SearchGroup(BaseModel):
    """单个 entity_type 分组"""

    total: int
    items: list[SearchHit]


class GlobalSearchResponse(BaseModel):
    """全局搜索响应（API-MDM-001 V1.1 §8.3 行 1688-1721）"""

    query: str
    total: int
    results: dict[SearchEntityType, SearchGroup]
