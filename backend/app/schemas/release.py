# -*- coding: utf-8 -*-
"""放行看板请求 schema。"""
from typing import Literal

from pydantic import BaseModel, Field
from app.schemas.data_source import DATA_SOURCE_MAP, DataSource


class ReleaseRequest(BaseModel):
    project_id: str = Field(..., description="项目编号，如 007_2 / 009 / 015")
    sample_type: str | None = Field(None, description="样品类型（如 原液/成品），用于规格匹配")
    production_line_ids: list[str] | None = Field(None, description="生产线过滤（空=全部）")
    group_ids: list[str] | None = None
    batch_numbers: list[str] | None = None
    test_types: list[str] | None = None
    batch_years: list[int] | None = None
    include_unknown_batch_year: bool = False
    attribute_names: list[str] | None = Field(None, description="canonical 英文属性（空=全部已映射）")
    capability_mode: Literal["population", "sample"] = "population"
    placement_statuses: list[str] = Field(default_factory=list)
    sd_reference_mode: Literal["current", "history"] = "current"
    lookback_years: int = Field(default=3, ge=1, le=10)
    data_source: DataSource = "RD"
