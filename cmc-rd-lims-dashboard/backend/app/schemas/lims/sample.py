# 样品相关接口的请求/响应 schema（Pydantic v2）
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SampleOverviewItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sample_id: str
    project_id: str | None = None
    sample_name: str | None = None
    batch_number: str | None = None
    sample_type: str | None = None
    test_type: str | None = None
    request_dt: datetime | None = None
    request_person: str | None = None
    sampled_dt: datetime | None = None
    received_dt: datetime | None = None
    started_dt: datetime | None = None
    completed_dt: datetime | None = None
    authorised_dt: datetime | None = None
    tester: str | None = None
    completer: str | None = None
    authoriser: str | None = None
    group_id: str | None = None
    status: str | None = None


class PaginatedSampleOverview(BaseModel):
    total: int
    page: int
    size: int
    items: list[SampleOverviewItem]
