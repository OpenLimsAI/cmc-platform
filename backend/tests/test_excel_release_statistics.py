import pandas as pd
import pytest
from app.schemas.release import ReleaseRequest
from app.services.dashboards.excel_release_service import analyze_excel_release


def frame():
    base = dict(project_id='CMAB007',attribute_name='sec_monomer_pct',attribute_raw='sec_monomer_pct',
        method_code=None,unit=None,sample_type='制剂',test_type='放行',production_line_id='FF1',group_id='IH',
        placement_status='正置',sub_lot=None,timepoint=0.,timepoint_unit='月',is_pct=False,source_system='legacy_excel_qc')
    return pd.DataFrame([{**base,'batch_number':f'B{year}0101','value':value} for year,value in
                         [(2020,.90),(2021,.95),(2022,1.00),(2023,.98),(2023,1.00)]])


def test_raw_current_statistics_sd_and_spec_are_separate():
    panels,n=analyze_excel_release(frame(),ReleaseRequest(project_id='CMAB007',data_source='EXCEL'))
    p=panels[0]
    assert n==5 and p['statistics_available']
    assert p['mean']==pytest.approx(.966)
    assert p['sd_sample']==pytest.approx(frame().value.std(ddof=1))
    assert p['sd_lines']['plus_3sd']==pytest.approx(.966+3*frame().value.std(ddof=1))
    assert max(x['value'] for x in p['points'])==1.0  # never multiplied by 100
    assert p['spec']=={'lsl':None,'usl':None} and p['capability']['value'] is None
    assert p['legacy_spec_candidate']['status']=='unverified_legacy_reference'


def test_history_reference_excludes_current_and_future_and_does_not_change_trend_stats():
    req=ReleaseRequest(project_id='CMAB007',data_source='EXCEL',batch_years=[2023],sd_reference_mode='history',lookback_years=3)
    p=analyze_excel_release(frame(),req)[0][0]
    assert p['n']==2 and p['mean']==pytest.approx(.99)
    assert p['reference_summary']['years']==[2020,2021,2022]
    assert p['reference_summary']['n']==3
    assert p['sd_lines']['mean']==pytest.approx(.95)
    assert p['sd_lines']['plus_3sd']==pytest.approx(1.10)


def test_no_history_never_falls_back_and_singleton_sd_is_not_zero():
    req=ReleaseRequest(project_id='CMAB007',data_source='EXCEL',batch_years=[2020],sd_reference_mode='history')
    p=analyze_excel_release(frame(),req)[0][0]
    assert p['n']==1 and p['sd_sample'] is None
    assert p['reference_summary']['n']==0
    assert all(x is None for x in p['sd_lines'].values())


def test_reference_respects_placement_filter_and_unrecognized_years():
    df=frame();other=df.copy();other['placement_status']='倒置';other['value']=100
    df=pd.concat([df,other],ignore_index=True)
    req=ReleaseRequest(project_id='CMAB007',data_source='EXCEL',placement_statuses=['正置'])
    p=analyze_excel_release(df,req)[0][0]
    assert p['n']==5 and p['reference_summary']['n']==5
    df['batch_number']='unknown'
    panels,n=analyze_excel_release(df,req.model_copy(update={'sd_reference_mode':'history'}))
    assert n==5 and panels[0]['reference_summary']['n']==0
