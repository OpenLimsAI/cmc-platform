"""稳定性独立边界/算例验证；合成观察与身份，不读取业务库。"""
from time import time

import jwt
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import api_router
from app.core.config import Settings, get_auth_settings
from app.core.database import get_session
from app.core.envelope import register_exception_handlers
from app.repositories.quality_repository import StagingQualityRepository
from app.schemas.stability import StabilityRequest
from app.services.dashboards.stability_service import analyze_stability, stability_options


def row(**changes):
    return {"project_id": "SYNTHETIC", "data_type": "Stability", "source_system": "rd_samplemanager", "sample_type": "原液",
            "test_type": "长期试验", "production_line_id": "L1", "group_id": "G1", "batch_number": " 0007-A ",
            "attribute_name": "synthetic", "attribute_raw": "合成检测项", "method_code": "M1", "unit": "%", "timepoint_unit": "月",
            "sample_id": "sample-1", "source_test_id": "test-1", "source_result_id": "result-1", "value": 1., "timepoint": 0., **changes}


def analyze(rows, **filters):
    return analyze_stability(pd.DataFrame(rows), StabilityRequest(project_id="SYNTHETIC", **filters))


@pytest.mark.parametrize("field,new", [("sample_type", "成品"), ("test_type", "加速试验"), ("method_code", "M2"), ("unit", "mg/mL"), ("timepoint_unit", "天"), ("attribute_raw", "另一来源名")])
def test_different_scopes_never_share_statistics(field, new):
    panels = analyze([row(), row(**{field: new})])
    assert len(panels) == 2
    assert sum(panel["n"] for panel in panels) == 2
    assert all(panel["groups"][0]["points"][0]["sd"] is None for panel in panels)


def test_hand_calculated_fit_mean_sd_and_same_time_repeats():
    rows = [row(timepoint=x, value=y, source_result_id=f"result-{i}") for i, (x, y) in enumerate([(0, 1), (1, 3), (2, 5), (1, 3)])]
    panel = analyze(rows)[0]
    series = panel["batches"][0]
    assert panel["n"] == panel["plotted_n"] == 4
    assert panel["timepoint_count"] == 3
    assert series["batch_number"] == " 0007-A "
    assert series["connect_points"] is False
    assert series["fit"]["slope"] == pytest.approx(2)
    assert series["fit"]["intercept"] == pytest.approx(1)
    assert series["fit"]["x"] == [0., 2.]
    assert series["fit"]["y"] == pytest.approx([1., 5.])
    assert series["fit"]["r_squared"] == pytest.approx(1)
    assert [p["n"] for p in panel["groups"][0]["points"]] == [1, 2, 1]
    assert panel["groups"][0]["points"][1]["sd"] == 0
    assert {p["source_result_id"] for p in panel["observations"]} == {f"result-{i}" for i in range(4)}
    assert analyze(rows[::-1])[0]["batches"][0]["fit"] == series["fit"]
    two = analyze([row(value=1), row(value=3)])[0]
    assert two["groups"][0]["points"][0]["mean"] == 2
    assert two["groups"][0]["points"][0]["sd"] == pytest.approx(2 ** 0.5)
    assert two["batches"][0]["fit"]["available"] is False


@pytest.mark.parametrize("field,value", [("unit", ""), ("unit", None), ("timepoint_unit", ""), ("timepoint_unit", "  "), ("timepoint_unit", None)])
def test_unknown_units_show_original_values_without_statistics(field, value):
    panel = analyze([row(**{field: value, "value": .98})])[0]
    assert not panel["statistics_available"]
    assert panel["groups"] == []
    assert not panel["batches"][0]["fit"]["available"]
    assert panel["observations"][0]["value"] == .98
    assert panel[field] == value


def test_invalid_observations_are_not_silently_lost_and_unknown_batch_not_connected():
    cases = [row(timepoint=None), row(timepoint="later"), row(timepoint=float("inf")), row(timepoint=-1), row(value=float("inf")),
             row(batch_number=None, group_id=None), row(batch_number=None, group_id=None, timepoint=1)]
    panel = analyze(cases)[0]
    assert panel["n"] == 7 and panel["plotted_n"] == 2
    assert len(panel["observations"]) == 7
    assert all(p["issues"] for p in panel["observations"][:5])
    assert len(panel["batches"]) == 2
    assert all(not s["connect_points"] and not s["fit"]["available"] for s in panel["batches"])
    assert panel["groups"][0]["group_id"] is None


def test_cascading_options_and_exact_filters_exclude_release_and_other_sources():
    data = pd.DataFrame([row(), row(test_type="加速试验", batch_number="ACCEL"), row(sample_type="成品", batch_number="PRODUCT"),
                         row(data_type="Release", batch_number="RELEASE-ONLY"), row(project_id="OTHER"), row(source_system="gmp_labvantage")])
    req = StabilityRequest(project_id="SYNTHETIC", sample_types=["原液"], test_types=["长期试验"])
    options = stability_options(data, req)
    assert options["sample_types"] == ["原液", "成品"]
    assert set(options["test_types"]) == {"长期试验", "加速试验"}
    assert options["batch_numbers"] == [" 0007-A "]
    assert options["row_count"] == 1 and options["project_row_count"] == 3
    assert len(analyze_stability(data, req)) == 1
    assert analyze_stability(data, req.model_copy(update={"batch_numbers": ["0007-A"]})) == []
    assert analyze_stability(data, req.model_copy(update={"group_ids": ["unmatched"]})) == []
    assert analyze_stability(data, req.model_copy(update={"production_line_ids": ["L2"]})) == []
    assert analyze_stability(data, req.model_copy(update={"attribute_names": ["absent"]})) == []


def test_empty_stability_contract():
    req = StabilityRequest(project_id="SYNTHETIC")
    assert analyze_stability(pd.DataFrame(), req) == []
    options = stability_options(pd.DataFrame(), req)
    assert options["attributes"] == options["batch_numbers"] == []
    assert options["row_count"] == options["project_row_count"] == 0


def test_excel_raw_statistics_keep_scale_and_separate_timepoints():
    rows = [row(source_system="legacy_excel_qc", unit=None, timepoint=x, value=y)
            for x, y in [(0, .98), (0, 1.), (3, .96)]]
    panel = analyze(rows, data_source="EXCEL")[0]
    assert panel["statistics_available"] and panel["unit"] is None
    points = panel["groups"][0]["points"]
    assert [point["n"] for point in points] == [2, 1]
    assert points[0]["mean"] == pytest.approx(.99)
    assert points[0]["sd"] == pytest.approx(.02 / 2**.5)
    assert points[0]["min"] == .98 and points[0]["max"] == 1.
    assert points[1]["sd"] is None
    assert panel["batches"][0]["fit"]["slope"] == pytest.approx(-.01)
    assert not panel["batches"][0]["connect_points"]
    assert any("存储原值" in warning for warning in panel["warnings"])
    unknown = analyze([{**r, "timepoint_unit": None} for r in rows], data_source="EXCEL")[0]
    assert not unknown["statistics_available"] and not unknown["groups"]
    assert not unknown["batches"][0]["fit"]["available"]


def api_client(monkeypatch):
    secret = "synthetic-stability-only-signing-key-with-sufficient-length"
    settings = Settings(_env_file=None, environment="development", auth_required=True, jwt_algorithm="HS256", jwt_secret_key=secret, jwt_public_key_path=None)
    captured = []

    def fetch(_self, flt):
        captured.append(flt)
        return pd.DataFrame([row(), row(timepoint=1, value=3)])

    monkeypatch.setattr(StagingQualityRepository, "fetch_long_table", fetch)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    app.dependency_overrides[get_auth_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: object()

    def auth(roles, temporary=False):
        payload = {"sub": "42", "username": "SYNTHETIC", "type": "access", "exp": int(time()) + 300, "roles": roles, "must_change_password": temporary}
        return {"Authorization": "Bearer " + jwt.encode(payload, secret, algorithm="HS256")}

    return TestClient(app), auth, captured


@pytest.mark.parametrize("roles,expected", [(["QAP_QC_GENERAL"], 200), (["QAP_QA_RELEASE"], 200), (["SYS_ADMIN"], 403), ([], 403)])
def test_real_router_guards_and_read_contract(monkeypatch, roles, expected):
    client, auth, captured = api_client(monkeypatch)
    with client:
        for path in ("/stability/options", "/stability"):
            response = client.post("/api/v1/analysis" + path, json={"project_id": "SYNTHETIC"}, headers=auth(roles))
            assert response.status_code == expected
            if expected == 200 and path == "/stability":
                body = response.json()
                assert body["meta"]["row_count"] == body["meta"]["plotted_row_count"] == 2
                assert body["meta"]["release_day0_included"] is False
                assert body["meta"]["approval_state"] == "not_evaluated"
                assert body["data"][0]["observations"][0]["batch_number"] == " 0007-A "
    if expected == 200:
        assert all(f.project_id == "SYNTHETIC" and f.source_systems == ["rd_samplemanager"] and f.data_types == ["Stability"] for f in captured)
    else:
        assert captured == []


def test_anonymous_temporary_and_invalid_requests_never_fetch(monkeypatch):
    client, auth, captured = api_client(monkeypatch)
    with client:
        for path in ("/stability/options", "/stability"):
            url = "/api/v1/analysis" + path
            assert client.post(url, json={"project_id": "SYNTHETIC"}).status_code == 401
            assert client.post(url, json={"project_id": "SYNTHETIC"}, headers=auth(["QAP_QA_RELEASE"], True)).status_code == 403
            for body in ({"project_id": " "}, {"project_id": "SYNTHETIC", "data_source": "ALL"}, {"project_id": "SYNTHETIC", "include_day0": True}):
                assert client.post(url, json=body, headers=auth(["QAP_QA_RELEASE"])).status_code == 422
    assert captured == []
