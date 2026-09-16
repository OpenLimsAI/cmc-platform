"""Independent raw comparison examples, explicit roles and no production writes."""
import pandas as pd
import pytest
from pydantic import ValidationError
from app.schemas.similarity import SimilarityRequest
from app.services.dashboards.similarity_service import analyze_similarity
from test_stability import api_client


def request(**updates):
    return SimilarityRequest(project_id="SYNTHETIC", reference_lines=["Z-ref"], comparison_lines=["A-test"], attribute_names=["metric"], **updates)


def rows():
    return pd.DataFrame([dict(project_id="SYNTHETIC", data_type="Release", source_system="rd_samplemanager",
        production_line_id=line, attribute_name="metric", value=value, unit="mg", sample_type="sample", test_type="release", batch_number="repeat")
        for line, values in [("Z-ref",[1,3]),("A-test",[2,4])] for value in values])


def test_hand_computed_direction_scale_and_order_invariance():
    data=rows(); panel=analyze_similarity(data,request())[0]
    assert panel["reference"]["mean"]==2
    assert panel["reference"]["sd"]==pytest.approx(2**.5)
    group=panel["comparisons"][0]
    assert group["mean_difference"]==1 and group["differences"]==[0,2]
    assert group["band_hits"]==2 and group["band_ratio"]==1
    assert panel["judgement"]=="not_evaluated"
    assert len(group["points"])==2  # Same batch is not silently deduplicated.
    reverse=analyze_similarity(data.iloc[::-1],request())[0]
    assert reverse["comparisons"][0]["mean_difference"]==1
    renamed=data.replace({"production_line_id":{"Z-ref":"A-ref","A-test":"Z-test"}})
    renamed_req=request().model_copy(update={"reference_lines":["A-ref"],"comparison_lines":["Z-test"]})
    assert analyze_similarity(renamed,renamed_req)[0]["comparisons"][0]["mean_difference"]==1
    swapped=request().model_copy(update={"reference_lines":["A-test"],"comparison_lines":["Z-ref"]})
    assert analyze_similarity(data,swapped)[0]["comparisons"][0]["mean_difference"]==-1


@pytest.mark.parametrize("field,value",[("unit","%"),("sample_type","other"),("method_code","M2"),("placement_status","other"),("sub_lot","other")])
def test_scope_isolation_keeps_missing_reference_explicit(field,value):
    data=rows();data.loc[data.production_line_id=="A-test",field]=value
    panels=analyze_similarity(data,request())
    assert len(panels)==2
    assert all(panel["comparisons"][0]["mean_difference"] is None for panel in panels)


def test_invalid_constant_and_single_reference_do_not_create_band():
    data=rows();data.loc[data.production_line_id=="Z-ref","value"]=1
    panel=analyze_similarity(data,request())[0]
    assert panel["reference"]["sd"]==0 and panel["band"]["lower"] is None
    assert panel["comparisons"][0]["band_ratio"] is None
    data["value"] = data["value"].astype(float)
    data.loc[0,"value"]=float("inf")
    panel=analyze_similarity(data,request())[0]
    assert panel["reference"]["n"]==1 and panel["reference"]["sd"] is None
    assert panel["reference"]["excluded_n"]==1


def test_exact_source_filters_and_missing_units_preserve_raw_scale():
    data=rows();data["source_system"]="legacy_excel_qc";data["unit"]=None;data["value"]/=100
    assert analyze_similarity(data,request())==[]
    panel=analyze_similarity(data,request(data_source="EXCEL"))[0]
    assert panel["reference"]["mean"]==pytest.approx(.02)
    assert panel["comparisons"][0]["mean_difference"]==pytest.approx(.01)
    data["data_type"]="Stability"
    assert analyze_similarity(data,request(data_source="EXCEL"))==[]


@pytest.mark.parametrize("patch",[{"comparison_lines":["Z-ref"]},{"reference_lines":[]},{"reference_lines":["Z-ref","Z-ref"]},
                                  {"attribute_names":[]},{"reference_sd_multiplier":float("nan")},{"approved":True}])
def test_request_rejects_ambiguous_or_unsupported_inputs(patch):
    with pytest.raises(ValidationError):
        SimilarityRequest.model_validate({**request().model_dump(),**patch})


@pytest.mark.parametrize("roles,status",[(["QAP_QA_RELEASE"],200),(["QAP_QC_GENERAL"],200),([],403),(["SYS_ADMIN"],403)])
def test_read_guard_and_release_repository_scope(monkeypatch,roles,status):
    client,auth,captured=api_client(monkeypatch)
    with client:
        response=client.post('/api/v1/analysis/similarity',json=request().model_dump(),headers=auth(roles))
        assert response.status_code==status
        if status==200:
            assert response.json()["meta"]["judgement"]=="not_evaluated"
            assert captured[0].data_types==["Release"]
        else:
            assert not captured
        assert client.post('/api/v1/analysis/similarity',json=request().model_dump()).status_code==401
        assert client.post('/api/v1/analysis/similarity',json=request().model_dump(),headers=auth(["QAP_QA_RELEASE"],True)).status_code==403
