"""稳定性只读请求；不接受单位换算、零点补齐或批准参数。"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.data_source import DataSource


class StabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=256)
    sample_types: list[str] = Field(default_factory=list)
    test_types: list[str] = Field(default_factory=list)
    production_line_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    batch_numbers: list[str] = Field(default_factory=list)
    attribute_names: list[str] = Field(default_factory=list)
    placement_statuses: list[str] = Field(default_factory=list)
    data_source: DataSource = "RD"

    @field_validator("project_id")
    @classmethod
    def require_project(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project is required")
        return value
