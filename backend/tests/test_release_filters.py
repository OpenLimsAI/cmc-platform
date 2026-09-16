"""放行筛选契约：合成观察，保留未知年份/缺失组别和重复值，不连接数据库。"""
from collections import Counter

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
import pytest

from app.api.v1 import release
from app.core.database import get_session
from app.repositories.quality_repository import StagingQualityRepository
from app.schemas.release import ReleaseRequest
from app.services.dashboards import release_service
from app.services.dashboards.release_filters import filter_release_rows, release_options


@pytest.fixture
def observations():
    return pd.DataFrame({
        "project_id": ["SYNTHETIC"] * 5,
        "production_line_id": ["L1"] * 5,
        "group_id": ["G1", "G1", "G2", None, "G2"],
        "batch_number": [" 007-202601A ", " 007-202601A ", "007-202501A", "UNKNOWN", None],
        "test_type": ["Release", "Release", "Release", "Release", "Trial"],
        "sample_type": ["原液"] * 5,
        "attribute_name": ["synthetic_value"] * 5,
        "attribute_raw": ["合成观察"] * 5,
        "value": [1., 1., 3., 4., 5.], "is_pct": [False] * 5,
        "unit": ["g/L"] * 5,
    })


@pytest.mark.parametrize("filters,expected", [
    ({}, [1, 1, 3, 4, 5]),
    ({"group_ids": ["G1"]}, [1, 1]),
    ({"batch_numbers": [" 007-202601A "]}, [1, 1]),
    ({"batch_numbers": ["007-202601A"]}, []),
    ({"test_types": ["Trial"]}, [5]),
    ({"batch_years": [2026]}, [1, 1]),
    ({"batch_years": [2025], "include_unknown_batch_year": True}, [3, 4, 5]),
    ({"include_unknown_batch_year": True}, [4, 5]),
    ({"group_ids": ["G2"], "batch_years": [2026]}, []),
])
def test_filters_intersect_without_changing_values_or_unknown_defaults(observations, filters, expected):
    before = observations.copy(deep=True)
    result = filter_release_rows(observations, ReleaseRequest(project_id="SYNTHETIC", **filters))
    assert result["value"].tolist() == expected
    pd.testing.assert_frame_equal(observations, before)


def test_options_preserve_raw_batch_and_explain_inferred_year(observations):
    result = release_options(observations)
    assert result["batch_numbers"] == [" 007-202601A ", "007-202501A", "UNKNOWN"]
    assert result["batch_years"] == [2025, 2026]
    assert result["unknown_batch_year_count"] == 2
    assert result["year_basis"] == "legacy_batch_number_inference"
    assert result["attributes"] == [{"attribute_name": "synthetic_value", "n": 5, "attribute_raws": ["合成观察"]}]


def test_empty_project_options_are_a_complete_empty_contract():
    result = release_options(pd.DataFrame())
    assert result["row_count"] == 0
    assert result["batch_years"] == result["attributes"] == result["group_ids"] == []
    assert filter_release_rows(pd.DataFrame(), ReleaseRequest(project_id="empty", batch_years=[2026])).empty


def test_release_routes_apply_filters_and_keep_ungrouped_observations(observations, monkeypatch):
    captured = []

    def fetch(_self, flt):
        captured.append(flt)
        return observations.copy()

    monkeypatch.setattr(StagingQualityRepository, "fetch_long_table", fetch)
    monkeypatch.setattr(release_service, "get_spec_limit", lambda *args: (None, None))
    app = FastAPI()
    app.include_router(release.router, prefix="/api/v1")
    app.dependency_overrides[get_session] = lambda: object()
    with TestClient(app) as client:
        opts = client.get("/api/v1/analysis/release/options", params={"project_id": "SYNTHETIC"})
        assert opts.json()["data"]["unknown_batch_year_count"] == 2
        assert captured[-1].project_id == "SYNTHETIC"
        assert captured[-1].source_systems == ["rd_samplemanager"]
        assert captured[-1].data_types == ["Release"]
        payload = {"project_id": "SYNTHETIC", "production_line_ids": ["L1"], "sample_type": "原液", "include_unknown_batch_year": True}
        response = client.post("/api/v1/analysis/release", json=payload)
        assert response.status_code == 200
        body = response.json()
        attr = body["data"][0]
        assert captured[-1].production_line_ids == ["L1"]
        assert captured[-1].sample_type == "原液"
        assert body["meta"]["row_count"] == attr["n"] == 2
        assert body["meta"]["applied_filters"]["include_unknown_batch_year"] is True
        assert body["meta"]["reference_scope"] == "current_filtered_rows"
        assert sum(group["n"] for group in attr["groups"]) == 2
        assert Counter((p["batch_number"], p["group_id"]) for p in attr["points"]) == Counter([("UNKNOWN", None), (None, "G2")])
        assert attr["units"] == ["g/L"]
