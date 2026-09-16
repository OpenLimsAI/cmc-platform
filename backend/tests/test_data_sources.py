"""来源隔离及 QC 原始口径；合成数据，不连接真实库。"""
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import meta, release, stability
from app.core.database import get_session
from app.repositories.quality_repository import QualityFilter, StagingQualityRepository
from app.schemas.stability import StabilityRequest
from app.services.dashboards import release_service
from app.services.dashboards.stability_service import analyze_stability, stability_options


def observation(**updates):
    return dict(project_id="SAME", source_system="gmp_labvantage", batch_number=" 0001 ",
                production_line_id="L1", group_id="G1", sample_type="成品", test_type="常规放行",
                attribute_raw="原始检测项", attribute_name="原始检测项", value=1., unit="mg/mL",
                method_code="M1", timepoint=1., timepoint_unit="天", data_type="Release", **updates)


@pytest.mark.parametrize("data_source,system", [("RD", "rd_samplemanager"), ("QC", "gmp_labvantage"), ("EXCEL", "legacy_excel_qc")])
def test_source_reaches_every_dimension_and_analysis_query(monkeypatch, data_source, system):
    captured = []

    def fetch(self, flt):
        captured.append(flt.source_systems)
        return pd.DataFrame()

    monkeypatch.setattr(StagingQualityRepository, "fetch_long_table", fetch)
    monkeypatch.setattr(StagingQualityRepository, "list_projects", lambda self, source_systems: captured.append(source_systems) or [])
    monkeypatch.setattr(StagingQualityRepository, "list_lines", lambda self, project_id, source_systems: captured.append(source_systems) or [])
    app = FastAPI()
    for router in (meta.router, release.router, stability.router):
        app.include_router(router)
    app.dependency_overrides[get_session] = lambda: object()
    with TestClient(app) as client:
        params = {"data_source": data_source, "project_id": "SAME"}
        for url in ("/meta/projects", "/meta/lines", "/meta/attributes", "/meta/coverage", "/analysis/release/options"):
            assert client.get(url, params=params).status_code == 200
        for url in ("/analysis/release", "/analysis/stability/options", "/analysis/stability"):
            response = client.post(url, json=params)
            assert response.status_code == 200
            assert response.json()["meta"]["legacy_excel_included"] is (data_source == "EXCEL")
            assert response.json()["meta"]["approval_state"] == "not_evaluated"
        assert client.get("/meta/projects", params={"data_source": "ALL"}).status_code == 422
        assert client.post("/analysis/release", json={**params, "data_source": "ALL"}).status_code == 422
    assert captured == [[system]] * 8


def test_project_and_line_sql_are_scoped_even_for_empty_or_same_project():
    class Session:
        def execute(self, statement, params):
            assert "source_system = ANY(:ss)" in str(statement)
            assert params["ss"] == ["gmp_labvantage"]
            return self

        def mappings(self): return self
        def all(self): return []

    repo = StagingQualityRepository(Session())
    assert repo.list_projects(["gmp_labvantage"]) == []
    assert repo.list_lines("SAME", ["gmp_labvantage"]) == []


def test_qc_uses_exact_source_categories_and_raw_names(monkeypatch):
    class Session:
        def execute(self, statement, params):
            assert params["source_systems"] == ["gmp_labvantage"]
            assert "t.source_system = s.source_system" in str(statement)
            assert "r.source_system = t.source_system" in str(statement)
            return self

        def mappings(self): return self
        def all(self):
            return [{**observation(), "test_type": category} for category in ("常规放行", "稳定性", "长期新试验", None)]

    from app.services.mapping import attribute_mapping
    monkeypatch.setattr(attribute_mapping, "map_name", lambda name: "RD_ALIAS")
    monkeypatch.setattr(attribute_mapping, "is_pct", lambda name: True)
    result = StagingQualityRepository(Session()).fetch_long_table(QualityFilter(source_systems=["gmp_labvantage"]))
    assert result.data_type.tolist() == ["Release", "Stability", "Unknown", "Unknown"]
    assert result.attribute_name.tolist() == ["原始检测项"] * 4
    assert result.attribute_canonical.isna().all()
    assert not result.is_pct.any()
    assert result.value.tolist() == [1.] * 4


def test_same_project_batch_and_attribute_cannot_mix_rd_and_qc_stability():
    frame = pd.DataFrame([
        {**observation(), "data_type": "Stability", "test_type": "稳定性", "value": 2.},
        {**observation(), "data_type": "Stability", "test_type": "稳定性", "source_system": "rd_samplemanager", "value": 99.},
    ])
    for source, expected in (("RD", 99.), ("QC", 2.)):
        req = StabilityRequest(project_id="SAME", data_source=source)
        assert stability_options(frame, req)["row_count"] == 1
        panel = analyze_stability(frame, req)[0]
        assert panel["n"] == 1
        assert panel["observations"][0]["value"] == expected
        assert panel["observations"][0]["batch_number"] == " 0001 "


@pytest.mark.parametrize("dimension,value", [("unit", "%"), ("unit", None), ("method_code", "M2"), ("sample_type", "原液"), ("production_line_id", "L2")])
def test_qc_release_splits_scopes_never_calls_rd_specs(monkeypatch, dimension, value):
    def forbidden(*args):
        pytest.fail("QC must not query legacy RD specs")

    monkeypatch.setattr(release_service, "get_spec_limit", forbidden)
    rows = [observation(), {**observation(), dimension: value, "value": 99.}]
    panels = release_service.analyze_qc_release(pd.DataFrame(rows), project_id="SAME", sample_type=None)
    assert len(panels) == 2
    assert len({panel["panel_id"] for panel in panels}) == 2
    assert sorted(p["points"][0]["value"] for p in panels) == [1., 99.]
    assert all(p["spec"] == {"lsl": None, "usl": None} and p["capability"]["value"] is None for p in panels)
    assert all(p["points"][0]["batch_number"] == " 0001 " for p in panels)
    assert all(p["sd_sample"] is None for p in panels)
    assert all(g["sd"] is None for p in panels for g in p["groups"])
    if value is None:
        missing = next(p for p in panels if not p["statistics_available"])
        assert missing["mean"] is None and missing["groups"] == []
