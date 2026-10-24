# -*- coding: utf-8 -*-
"""业务批号端到端响应契约；使用内存观察，不连接数据库或认定历史规格有效。"""
from collections import Counter

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import release
from app.core.database import get_session
from app.repositories.quality_repository import StagingQualityRepository
from app.services.dashboards import release_service
from app.services.mapping.batch import attach_sort_key, attach_year


def test_derived_batch_fields_preserve_complete_source_value():
    numbers = ["00012-a", " 007-201903f ", "PG1B20201104", "SOURCE-" + "0" * 40]
    original = pd.DataFrame({"batch_number": numbers})
    before = original.copy(deep=True)

    result = attach_year(attach_sort_key(original))

    assert result["batch_number"].tolist() == numbers
    assert "batch_id" not in result.columns
    assert result.loc[1, "lot_sort_key"] == 201903
    assert result.loc[1, "year"] == 2019
    pd.testing.assert_frame_equal(original, before)


def test_release_response_keeps_each_observation_with_standard_batch_number(monkeypatch):
    # 同一批号有三个观察，其中两个数值也相同，仍须保留三条趋势点。
    observations = pd.DataFrame({
        "batch_number": [" 0007-202601a "] * 3 + ["SOURCE-" + "0" * 40],
        "attribute_name": ["contract_test_measurement"] * 4,
        "group_id": ["group_a"] * 4,
        "value": [1.0, 1.0, 2.0, 3.0],
        "is_pct": [False] * 4,
    })
    before = observations.copy(deep=True)

    # 依赖替换切断数据库；保留真实路由、服务、排序和 JSON 序列化。
    monkeypatch.setattr(StagingQualityRepository, "fetch_long_table", lambda self, flt: observations)
    monkeypatch.setattr(release_service, "get_spec_limit", lambda *args: (None, None))
    app = FastAPI()
    app.include_router(release.router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: object()

    with TestClient(app) as client:
        response = client.post("/api/v1/analysis/release", json={"project_id": "contract_test"})

    assert response.status_code == 200
    body = response.json()
    assert body["errors"] == []
    assert body["meta"]["row_count"] == 4
    points = body["data"][0]["points"]
    assert body["data"][0]["n"] == len(points) == 4
    assert Counter((p["batch_number"], p["value"]) for p in points) == Counter(
        zip(observations["batch_number"], observations["value"])
    )
    assert '"batch_id":' not in response.text
    pd.testing.assert_frame_equal(observations, before)
