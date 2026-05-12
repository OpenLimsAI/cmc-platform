"""
全局搜索 schemas
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict

SearchEntityType = Literal["substance", "project", "asset"]
MatchedField = Literal[
    "code", "name", "name_en", "internal_code", "objective", "xref",
    "trade_name", "inn_name",
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
