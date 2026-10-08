"""Independent raw comparison examples, explicit roles and no production writes."""
import pandas as pd
import pytest
import numpy as np
from scipy import stats
from statsmodels.stats.weightstats import CompareMeans
from io import BytesIO
from openpyxl import load_workbook
from pydantic import ValidationError
from app.api.v1.similarity import OLD_REPORT_COLUMNS
from app.schemas.similarity import SimilarityRequest
from app.services.dashboards.similarity_service import analyze_similarity
from app.repositories.quality_repository import StagingQualityRepository
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
    assert panel["reference"]["mean_ci_lower"]==pytest.approx(-4.31375151467504)
    assert panel["reference"]["mean_ci_upper"]==pytest.approx(8.31375151467504)
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


def test_reference_mean_ci_tracks_selected_confidence():
    data=rows()
    low=analyze_similarity(data,request(confidence_level=0.9))[0]["reference"]
    high=analyze_similarity(data,request(confidence_level=0.95))[0]["reference"]
    assert high["mean_ci_lower"] < low["mean_ci_lower"] < low["mean"]
    assert high["mean_ci_upper"] > low["mean_ci_upper"] > low["mean"]


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


def test_old_report_columns_use_corrected_one_pass_tost_and_explicit_parameters():
    data=rows()
    req=request(tier1_attribute_names=["metric"],delta_mode="manual",manual_delta=4,
                confidence_level=0.9,bf_threshold=0.05)
    panel=analyze_similarity(data,req)[0]
    result=panel["comparisons"][0]["exploratory_statistics"]
    assert all(column in result for column in OLD_REPORT_COLUMNS)
    assert result["Mean_Diff"]==pytest.approx(1)  # comparison minus reference
    assert result["alpha"]==pytest.approx(0.05)
    assert result["Delta"]==4 and result["Tier_Level"]=="Tier1"
    assert result["Tier_Judgement"] == ("Similar" if result["Equivalent"]=="Equivalent" else "Not Similar")
    assert result["Approval_Status"]=="探索性计算，未批准"
    assert result["Unit"]=="mg" and result["N_Ref"]==result["N_Test"]==2
    assert panel["judgement"]=="not_evaluated"
    wider=analyze_similarity(data,req.model_copy(update={"manual_delta":8}))[0]["comparisons"][0]["exploratory_statistics"]
    assert wider["Delta"]==8 and wider["pTOST"] < result["pTOST"]


def test_tier2_plot_band_and_report_use_the_same_manual_delta():
    data=pd.DataFrame([dict(project_id="SYNTHETIC",data_type="Release",source_system="rd_samplemanager",
        production_line_id=line,attribute_name="metric",value=value,unit="mg",sample_type="sample",
        test_type="release",batch_number=f"{line}-{i}")
        for line,values in (("Z-ref",[0,1,2]),("A-test",[4.5,5.5]))
        for i,value in enumerate(values)])
    manual=analyze_similarity(data,request(delta_mode="manual",manual_delta=10))[0]
    row=manual["comparisons"][0]["exploratory_statistics"]
    assert manual["band"]["basis"]=="manual_delta"
    assert (manual["band"]["lower"],manual["band"]["upper"])==(-9,11)
    assert (manual["comparisons"][0]["band_hits"],manual["comparisons"][0]["band_ratio"])==(2,1)
    assert row["Delta"]==10 and row["Tier_Judgement"]=="Similar"

    automatic=analyze_similarity(data,request())[0]
    assert automatic["band"]["basis"]=="reference_sd"
    assert (automatic["band"]["lower"],automatic["band"]["upper"])==(-2,4)
    assert automatic["comparisons"][0]["band_hits"]==0
    assert automatic["comparisons"][0]["exploratory_statistics"]["Tier_Judgement"]=="Not Similar"

    tier1=analyze_similarity(data,request(tier1_attribute_names=["metric"],delta_mode="manual",manual_delta=10))[0]
    assert tier1["band"]["basis"]=="reference_sd"  # Tier1 图5保留描述性 k×SD 带。
    assert tier1["comparisons"][0]["exploratory_statistics"]["Delta"]==10


def test_tier2_calculation_status_tracks_range_method_when_tost_is_undefined():
    data=rows()
    data.loc[data.production_line_id=="Z-ref","value"]=1
    data.loc[data.production_line_id=="A-test","value"]=1
    panel=analyze_similarity(data,request(delta_mode="manual",manual_delta=1))[0]
    row=panel["comparisons"][0]["exploratory_statistics"]
    assert panel["band"]["basis"]=="manual_delta"
    assert (panel["band"]["lower"],panel["band"]["upper"])==(0,2)
    assert panel["comparisons"][0]["band_ratio"]==1
    assert row["Tier_Judgement"]=="Similar" and row["Calculation_Status"]=="ok"
    assert row["Equivalent"]=="Unknown"  # 零标准误使均值差 TOST 无法计算。


def test_tier2_boundary_matches_displayed_band_and_report():
    data=pd.DataFrame([dict(project_id="SYNTHETIC",data_type="Release",source_system="rd_samplemanager",
        production_line_id=line,attribute_name="metric",value=value,unit="mg",sample_type="sample",
        test_type="release",batch_number=f"{line}-{i}")
        for line,values in (("Z-ref",[.1,.2,.3]),("A-test",[.1,.1,1.0]))
        for i,value in enumerate(values)])
    panel=analyze_similarity(data,request(delta_mode="manual",manual_delta=.1,tier2_hit_ratio=.6))[0]
    group=panel["comparisons"][0]
    row=group["exploratory_statistics"]
    assert panel["reference"]["mean"]==.2
    assert panel["band"]["lower"]==.1
    assert group["band_hits"]==2 and group["band_ratio"]==pytest.approx(2/3)
    assert row["Calculation_Status"]=="ok" and row["Tier_Judgement"]=="Similar"
    assert row["Mean_Diff"]==pytest.approx(group["mean_difference"])


@pytest.mark.parametrize("bf_threshold,usevar,method",[(.05,"pooled","TOST2 (pooled)"),(.5,"unequal","TOST1 (Welch)")])
def test_summary_numeric_columns_against_independent_calculation(bf_threshold,usevar,method):
    ref=np.array([1.,2.,4.,7.,9.])
    test=np.array([1.,2.,3.,10.,20.])
    data=pd.DataFrame([dict(project_id="SYNTHETIC",data_type="Release",source_system="rd_samplemanager",
        production_line_id=line,attribute_name="metric",value=value,unit="mg",sample_type="sample",
        test_type="release",batch_number=f"{line}-{i}")
        for line,values in (("Z-ref",ref),("A-test",test)) for i,value in enumerate(values)])
    req=request(delta_mode="manual",manual_delta=15,confidence_level=.9,bf_threshold=bf_threshold)
    panel=analyze_similarity(data,req)[0]
    group=panel["comparisons"][0]
    row=group["exploratory_statistics"]
    cm=CompareMeans.from_data(test,ref)
    difference=float(np.mean(test)-np.mean(ref))
    ci=cm.tconfint_diff(alpha=.1,usevar=usevar)
    p=cm.ttost_ind(-15,15,usevar=usevar)[0]
    vr=float(np.var(ref,ddof=1));vt=float(np.var(test,ddof=1))
    se2=((len(ref)-1)*vr+(len(test)-1)*vt)/(len(ref)+len(test)-2)*(1/len(ref)+1/len(test)) if usevar=="pooled" else vr/len(ref)+vt/len(test)
    df=len(ref)+len(test)-2 if usevar=="pooled" else se2**2/((vr/len(ref))**2/(len(ref)-1)+(vt/len(test))**2/(len(test)-1))
    expected={"Mean_Diff":difference,"Ref_Mean":np.mean(ref),"Test_Mean":np.mean(test),
        "Ref_Var":vr,"Test_Var":vt,"SE":np.sqrt(se2),"DF":df,"ci_lower":ci[0],
        "ci_upper":ci[1],"alpha":.05,"conf_level":.9,"pTOST":p,"Delta":15,
        "Brown-Forsythe p-value":stats.levene(ref,test,center="median").pvalue,
        "Levene p-value":stats.levene(ref,test,center="mean").pvalue}
    for column,value in expected.items():
        assert row[column]==pytest.approx(value),column
    assert row["N_Ref"]==len(ref) and row["N_Test"]==len(test)
    assert row["TOST Method"]==method
    assert row["Equivalent"]==("Equivalent" if p < .05 else "Not Equivalent")
    assert row["Calculation_Status"]=="ok"
    assert panel["reference"]["mean_ci_lower"]==pytest.approx(np.mean(ref)-stats.t.ppf(.95,len(ref)-1)*np.std(ref,ddof=1)/np.sqrt(len(ref)))
    assert panel["reference"]["mean_ci_upper"]==pytest.approx(np.mean(ref)+stats.t.ppf(.95,len(ref)-1)*np.std(ref,ddof=1)/np.sqrt(len(ref)))
    assert group["mean_difference"]==pytest.approx(difference)
    assert group["band_hits"]==sum(abs(test-np.mean(ref))<=15)
    assert group["band_ratio"]==pytest.approx(group["band_hits"]/len(test))


def test_exploratory_report_has_legacy_sheets_and_all_columns_without_approval(monkeypatch):
    client,auth,_=api_client(monkeypatch)
    monkeypatch.setattr(StagingQualityRepository,"fetch_long_table",lambda _self,_filter: rows())
    req=request(delta_mode="manual",manual_delta=4)
    with client:
        url='/api/v1/analysis/similarity/report.xlsx'
        assert client.post(url,json=req.model_dump()).status_code==401
        response=client.post(url,json=req.model_dump(),headers=auth(["QAP_QA_RELEASE"]))
    assert response.status_code==200
    book=load_workbook(BytesIO(response.content),read_only=True,data_only=True)
    assert book.sheetnames==["Equivalence Result","Export Info"]
    sheet=book["Equivalence Result"]
    headers=[cell.value for cell in sheet[1]]
    assert headers[:len(OLD_REPORT_COLUMNS)]==OLD_REPORT_COLUMNS
    assert sheet.max_row==2 and sheet["D2"].value in {"探索：Similar","探索：Not Similar","探索：Unknown"}
    exported=dict(zip(headers,[cell.value for cell in sheet[2]]))
    assert exported["Mean_Diff"]==pytest.approx(1)
    assert exported["Ref_Mean"]==pytest.approx(2)
    assert exported["Test_Mean"]==pytest.approx(3)
    assert exported["Ref_Var"]==pytest.approx(2)
    assert exported["Test_Var"]==pytest.approx(2)
    assert exported["Delta"]==pytest.approx(4)
    assert exported["N_Ref"]==exported["N_Test"]==2
    assert book["Export Info"]["B13"].value=="探索性计算，未经批准，不用于质量放行"
    assert "未证实等效" in book["Export Info"]["B16"].value
    assert "规则未满足" in book["Export Info"]["B17"].value


@pytest.mark.parametrize("patch",[{"comparison_lines":["Z-ref"]},{"reference_lines":[]},{"reference_lines":["Z-ref","Z-ref"]},
                                  {"attribute_names":[]},{"reference_sd_multiplier":float("nan")},{"approved":True},
                                  {"delta_mode":"manual"},{"manual_delta":0},{"confidence_level":0.8}])
def test_request_rejects_ambiguous_or_unsupported_inputs(patch):
    with pytest.raises(ValidationError):
        SimilarityRequest.model_validate({**request().model_dump(),**patch})


@pytest.mark.parametrize("roles,status",[(["QAP_QA_RELEASE"],200),(["QAP_QC_GENERAL"],200),([],403),(["SYS_ADMIN"],200)])
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
