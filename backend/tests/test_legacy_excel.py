"""Excel 历史适配隔离测试：合成 ORM 对象，不写业务数据库。"""
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from app.repositories.legacy_excel_repository import LegacyExcelRepository, LegacyQualityResult
from app.repositories.quality_repository import QualityFilter, StagingQualityRepository
from app.schemas.release import ReleaseRequest
from app.schemas.stability import StabilityRequest
from app.services.dashboards.release_filters import filter_release_rows, release_options
from app.services.dashboards.release_service import analyze_qc_release
from app.services.dashboards.stability_service import analyze_stability, stability_options


def record(**updates):
    values = dict(id=42, data_source='QC_LIMS', data_type='Stability', project_id='CMAB007',
                  production_line_id='FF1', group_id='IH', sample_type='制剂', batch_number='000123',
                  sub_lot=None, test_type='长期试验', placement_status='正置', timepoint=3., timepoint_unit='月',
                  sample_submission_date=date(2020, 1, 2), attribute_name='purity_pct', value=0.985, source_file='synthetic.xlsx')
    values.update(updates)
    return LegacyQualityResult(**values)


class FakeSession:
    def __init__(self, rows): self.rows, self.statements = rows, []
    def execute(self, statement): self.statements.append(statement); return self
    def scalars(self): return self
    def all(self): return self.rows


def frame(rows):
    session = FakeSession(rows)
    df = StagingQualityRepository(session).fetch_long_table(QualityFilter(project_id='CMAB007', source_systems=['legacy_excel_qc']))
    compiled = session.statements[0].compile(dialect=postgresql.dialect())
    assert 'quality.quality_data' in str(compiled) and 'staging.' not in str(compiled)
    assert 'QC_LIMS' in compiled.params.values() and 'CMAB007' in compiled.params.values()
    return df


def test_excel_preserves_business_dimensions_and_never_invents_unit_or_scales():
    df = frame([record(), record(id=43)])
    assert len(df) == 2  # 同批同时间的复测不去重
    assert df.project_id.tolist() == ['CMAB007'] * 2
    assert df.batch_number.tolist() == ['000123'] * 2
    assert df.value.tolist() == [0.985] * 2
    assert df.production_line_id.tolist() == ['FF1'] * 2
    assert df.group_id.tolist() == ['IH'] * 2
    assert df.unit.isna().all() and not df.is_pct.any()
    assert df.source_result_id.tolist() == ['42', '43']
    assert df.sample_submission_date.iloc[0] == date(2020, 1, 2)


def test_placement_scopes_remain_separate_and_source_filters_match_excel():
    df = frame([record(), record(id=43, placement_status='倒置', value=.5)])
    req = StabilityRequest(project_id='CMAB007', data_source='EXCEL')
    assert set(stability_options(df, req)['placement_statuses']) == {'正置', '倒置'}
    panels = analyze_stability(df, req)
    assert len(panels) == 2
    assert all(not p['statistics_available'] and p['plotted_n'] == 1 for p in panels)
    assert panels[0]['observations'][0]['source_file'] == 'synthetic.xlsx'
    assert len(analyze_stability(df, req.model_copy(update={'placement_statuses': ['正置']}))) == 1
    assert analyze_stability(df, req.model_copy(update={'data_source': 'QC'})) == []
    df['data_type'] = 'Release'
    assert set(release_options(df)['placement_statuses']) == {'正置', '倒置'}
    selected = filter_release_rows(df, ReleaseRequest(project_id='CMAB007', data_source='EXCEL', placement_statuses=['正置']))
    assert selected.value.tolist() == [.985]
    panels = analyze_qc_release(df, project_id='CMAB007', sample_type=None)
    assert len(panels) == 2
    assert all(p['spec'] == {'lsl': None, 'usl': None} and p['groups'] == [] for p in panels)


def test_database_error_is_not_an_empty_success_or_secret_leak():
    class Denied:
        def execute(self, statement):
            raise OperationalError('private query', {}, Exception('secret credential'))
    with pytest.raises(HTTPException) as error:
        LegacyExcelRepository(Denied()).list_projects()
    assert error.value.status_code == 503
    assert 'secret' not in error.value.detail
    assert 'Excel' in error.value.detail


def test_query_filters_are_bound_and_history_classification_is_preserved():
    session = FakeSession([record(data_type='Unknown')])
    request = QualityFilter(project_id="P' OR 1=1 --", source_systems=['legacy_excel_qc'], data_types=['Release'], attribute_names=['a'], production_line_ids=['FF1'])
    result = LegacyExcelRepository(session).fetch_long_table(request)
    compiled = session.statements[0].compile(dialect=postgresql.dialect())
    assert request.project_id not in str(compiled)
    assert request.project_id in compiled.params.values()
    assert ['Release'] in compiled.params.values() and ['FF1'] in compiled.params.values()
    assert result.data_type.tolist() == ['Unknown']  # 不凭“长期试验”重新猜类别
