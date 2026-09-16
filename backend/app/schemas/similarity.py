"""Explicit reference selection; descriptive comparisons only."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.data_source import DataSource


class SimilarityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=256)
    data_source: DataSource = "RD"
    sample_type: str | None = None
    test_types: list[str] = Field(default_factory=list)
    placement_statuses: list[str] = Field(default_factory=list)
    batch_numbers: list[str] = Field(default_factory=list)
    attribute_names: list[str] = Field(min_length=1, max_length=100)
    reference_lines: list[str] = Field(min_length=1, max_length=20)
    comparison_lines: list[str] = Field(min_length=1, max_length=20)
    reference_sd_multiplier: float = Field(default=3, ge=0.5, le=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_selection(self):
        if not self.project_id.strip():
            raise ValueError("请选择项目")
        for values in (self.reference_lines, self.comparison_lines, self.attribute_names):
            if any(not value.strip() for value in values) or len(values) != len(set(values)):
                raise ValueError("选择项不得为空或重复")
        if set(self.reference_lines) & set(self.comparison_lines):
            raise ValueError("参比产线和比较产线不能重叠")
        return self
