# -*- coding: utf-8 -*-
"""Run against Mac analytics using temporary tables/views; always roll back.

Execute with qc-lims-etl/.venv/bin/python (psycopg + dotenv).
No persistent source data or structure is modified.
"""
from pathlib import Path
import importlib.util
import unittest
from decimal import Decimal
from datetime import datetime, timezone
import psycopg
from psycopg import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
# Alembic is needed only when upgrade/downgrade runs, not for the SQL fixtures.
import sys, types
if 'alembic' not in sys.modules:
    try:
        import alembic
    except ImportError:
        stub = types.ModuleType('alembic')
        stub.op = None
        sys.modules['alembic'] = stub
spec = importlib.util.spec_from_file_location('water_mart_revision', ROOT/'alembic/versions/cmc_analytics/20261009_analytics_water_mart.py')
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)
spec_perf = importlib.util.spec_from_file_location('water_mart_performance', ROOT/'alembic/versions/cmc_analytics/20261009_analytics_water_mart_perf.py')
perf_revision = importlib.util.module_from_spec(spec_perf)
spec_perf.loader.exec_module(perf_revision)
VIEW_DEFINITIONS = [(n,perf_revision.SAMPLE_SQL if n == 'v_water_sample' else q) for n,q in revision.VIEW_DEFINITIONS]


def connect():
    v = dotenv_values(ROOT/'.env')
    return psycopg.connect(host=v.get('PG_HOST','127.0.0.1'),port=v.get('PG_PORT_RD','5432'),
                           user=v['PG_USER'],password=v['PG_PASSWORD'],dbname='cmc_analytics')


class WaterMartSQLTests(unittest.TestCase):
    def setUp(self):
        self.c = connect()
        self.c.execute("SET LOCAL statement_timeout='20s'")
        for t in ('stg_lv_test_result_wide','stg_lv_dataset','stg_lv_sample'):
            self.c.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE staging.{} INCLUDING DEFAULTS)').format(sql.Identifier(t),sql.Identifier(t)))
        for name, query in VIEW_DEFINITIONS:
            self.c.execute(sql.SQL('CREATE TEMP VIEW {} AS ').format(sql.Identifier(name)) + sql.SQL(query.replace('staging.','pg_temp.').replace('mart.','pg_temp.')))

    def tearDown(self):
        self.c.rollback()
        self.c.close()

    def row(self, sample='S1', **changes):
        row = dict(source_system='gmp_labvantage', sdcid='Sample',keyid1=sample,keyid2='(null)',keyid3='(null)',
                   paramlistid='电导率',paramlistversionid='1',variantid='最终',dataset=1,paramid='结果',paramtype='Standard',replicateid=1,
                   s_sampleid=sample,samplesubtypeid='注射用水',samplestatus='Reviewed',sample_name='水样',
                   workitemid='电导率任务',samplepointid='SP1',samplepoint_code='WFI001',samplepoint_name='一号水点',
                   samplepoint_mapping_source='S_SAMPLEPOINT',samplepoint_mapping_scope='current_master',
                   trend_dt=datetime(2026,10,9,tzinfo=timezone.utc),trend_dt_source='eventdt',
                   displayvalue='1.2',unit=None,plot_value=Decimal('1.2'),result_kind='exact_numeric',result_operator=None,
                   result_bound=None,plot_value_rule='water_exact_numeric_v1',result_role='reported_result',
                   selection_rule='water_system_v2',selection_reason='approved final fixture')
        row.update(changes)
        names=list(row)
        self.c.execute(sql.SQL('INSERT INTO pg_temp.stg_lv_test_result_wide ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),list(row.values()))

    def rows(self, query):
        return self.c.execute(query).fetchall()

    def test_units_preserve_source_and_number(self):
        for i,u in enumerate((None,' µS/cm ','μS/cm','uS/cm')):
            self.row(sample='S'+str(i),unit=u)
        out=self.rows('select source_unit,analysis_unit,display_unit,plot_value,exact_numeric_value,unit_status from pg_temp.v_water_numeric_trend order by sample_id')
        self.assertEqual(len(out),4)
        self.assertEqual([r[0] for r in out],[None,' µS/cm ','μS/cm','uS/cm'])
        self.assertTrue(all(r[1:5]==('μS/cm','μS/cm',Decimal('1.2'),Decimal('1.2')) for r in out))
        self.assertEqual([r[5] for r in out],['business_confirmed','normalized','normalized','normalized'])
        self.assertEqual(len({str(r[0]) for r in self.rows('select comparison_key from pg_temp.v_water_result')}),1)

    def test_toc_and_dimensionless_ph(self):
        self.row(sample='T1',paramlistid='总有机碳',paramid='TOC报告值')
        self.row(sample='T2',paramlistid='总有机碳',paramlistversionid='2',paramid='结果',unit='PPB')
        self.row(sample='P',paramlistid='pH值',unit=None,displayvalue='7.01',plot_value=Decimal('7.01'))
        self.assertEqual(self.rows("select analysis_unit,display_unit,unit_status from pg_temp.v_water_numeric_trend where sample_id='P'"),[(None,'无量纲','dimensionless')])
        self.assertEqual(self.rows("select count(*) from pg_temp.v_water_numeric_trend where analysis_unit='ppb'"),[(2,)])

    def test_unit_conflicts_stay_out_of_trends(self):
        self.row(sample='C',unit='mS/cm')
        self.row(sample='T',paramlistid='总有机碳',paramid='TOC报告值',unit='ppm')
        self.row(sample='P',paramlistid='pH值',unit='mg/L')
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_numeric_trend'),[(0,)])
        self.assertEqual(self.rows("select count(*) from pg_temp.v_water_review_item where issue_type='unit_conflict'"),[(3,)])
        self.assertTrue(all(r[0] is None for r in self.rows('select analysis_unit from pg_temp.v_water_result')))

    def test_micro_lt1_is_plot_zero_not_exact(self):
        cases=[('<1','<','1','0','water_microbiology_lt1_zero_v1'),('＜ 1.0','<','1','0','water_microbiology_lt1_zero_v1'),
               ('<=1','<=','1','1','water_censored_bound_plot_v1'),('≤1','<=','1','1','water_censored_bound_plot_v1'),
               ('<10','<','10','10','water_censored_bound_plot_v1')]
        for i,(display,op,bound,plot,rule) in enumerate(cases):
            self.row(sample='M'+str(i),paramlistid='微生物限度',paramid='报告值',unit='cfu/ml',displayvalue=display,
                     result_kind='censored',result_operator=op,result_bound=Decimal(bound),plot_value=Decimal(plot),plot_value_rule=rule)
        self.row(sample='M5',paramlistid='微生物限度',paramid='报告值',unit='cfu/ml',displayvalue='1',plot_value=Decimal('1'))
        out=self.rows('select display_value,plot_value,exact_numeric_value from pg_temp.v_water_numeric_trend order by sample_id')
        self.assertEqual(len(out),6)
        self.assertEqual([r[1] for r in out],list(map(Decimal,['0','0','1','1','10','1'])))
        self.assertEqual([r[2] for r in out],[None]*5+[Decimal('1')])
        self.assertEqual([r[0] for r in out],[c[0] for c in cases]+['1'])

    def test_corrupt_plot_metadata_is_diagnosed(self):
        self.row(sample='E',displayvalue='1.2',plot_value=Decimal('99'))
        self.row(sample='M',paramlistid='微生物限度',paramid='报告值',unit='cfu/ml',displayvalue='<1',
                 result_kind='censored',result_operator='<',result_bound=1,plot_value=1,plot_value_rule='water_microbiology_lt1_zero_v1')
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_numeric_trend'),[(0,)])
        self.assertEqual(self.rows("select count(*) from pg_temp.v_water_review_item where issue_type='invalid_plot_metadata'"),[(2,)])

    def test_only_approved_reviewed_water(self):
        self.row()
        self.row(sample='C',samplestatus='Completed')
        self.row(sample='D',samplesubtypeid='原液')
        self.row(sample='O',source_system='rd_labvantage')
        self.row(sample='I',sdcid='Batch')
        self.row(sample='V1',selection_rule='water_system_v1')
        self.row(sample='NEW',selection_rule='water_future_v3')
        self.assertEqual(self.rows('select sample_id from pg_temp.v_water_result'),[('S1',)])
        self.assertEqual(self.rows("select count(*) from pg_temp.v_water_review_item where issue_type='unsupported_selection_rule'"),[(2,)])

    def test_conclusion_not_counted_twice_or_given_numeric_unit(self):
        self.row(paramlistid='电导率-方法1',selection_rule='water_conductivity_method1_numeric_v2')
        self.row(paramlistid='电导率-方法1',paramid='结论',displayvalue='符合规定',plot_value=None,
                 result_kind='qualitative',result_role='conclusion',plot_value_rule=None)
        self.assertEqual(self.rows('select result_count,trend_result_count,conclusion_count,dataset_count from pg_temp.v_water_sample'),[(2,1,1,1)])
        self.assertEqual(self.rows("select analysis_unit from pg_temp.v_water_result where paramid='结论'"),[(None,)])
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_review_item'),[(0,)])

    def test_missing_unknown_unit_never_promoted(self):
        self.row(paramlistid='未确认方法',unit=None)
        self.assertEqual(self.rows('select not_plotted_reason from pg_temp.v_water_result'),[('missing_unit',)])
        self.assertEqual(self.rows('select issue_type from pg_temp.v_water_review_item'),[('missing_unit',)])
        self.assertEqual(len(self.rows('select comparison_key from pg_temp.v_water_result')[0][0]),10)

    def test_unparsed_kept_and_reviewed(self):
        self.row(displayvalue='见记录',plot_value=None,result_kind='unparsed',plot_value_rule=None)
        self.assertEqual(self.rows('select display_value,exact_numeric_value,plot_eligible from pg_temp.v_water_result'),[('见记录',None,False)])
        self.assertEqual(self.rows('select issue_type from pg_temp.v_water_review_item'),[('unparsed_result',)])

    def test_missing_point_and_date_each_get_issue(self):
        self.row(samplepointid=None,samplepoint_code=None,trend_dt=None)
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_numeric_trend'),[(0,)])
        self.assertEqual({r[0] for r in self.rows('select issue_type from pg_temp.v_water_review_item')},{'missing_samplepoint','missing_trend_date'})

    def test_attribute_conflict_cannot_choose_first_or_max(self):
        self.row()
        self.row(paramid='报告值',samplepointid='SP2',samplepoint_code='WFI002')
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_sample'),[(0,)])
        self.assertEqual(self.rows('select issue_type,entity_grain,details from pg_temp.v_water_review_item'),[('sample_attributes_conflict','sample',{'attribute_versions':2})])

    def test_replications_and_method_stages_not_merged(self):
        self.row()
        self.row(replicateid=2)
        self.row(variantid='独立阶段')
        self.row(paramlistversionid='2')
        self.row(unit='cfu/ml',paramlistid='微生物限度',paramid='报告值')
        self.row(unit='cfu/100ml',paramlistid='微生物限度',paramid='报告值',replicateid=2)
        self.assertEqual(self.rows('select count(*),count(distinct source_key),count(distinct comparison_key) from pg_temp.v_water_result'),[(6,6,5)])
        self.assertEqual(self.rows('select result_count from pg_temp.v_water_sample'),[(6,)])

    def test_method_gap_uses_method_grain_not_each_dataset(self):
        self.c.execute("insert into pg_temp.stg_lv_sample (source_system,s_sampleid,samplesubtypeid,samplestatus) values ('gmp_labvantage','GAP','纯化水','Reviewed')")
        for stage,ds in [('过程',1),('最终',1),('最终',2)]:
            self.c.execute("insert into pg_temp.stg_lv_dataset (source_system,sdcid,keyid1,keyid2,keyid3,paramlistid,paramlistversionid,variantid,dataset,workitemid) values ('gmp_labvantage','Sample','GAP','(null)','(null)','待确认方法','1',%s,%s,'方法任务')",(stage,ds))
        self.assertEqual(self.rows('select entity_grain,issue_type,sample_id,source_key from pg_temp.v_water_review_item'),[
            ('sample_method','no_selected_final_result','GAP',dict(source_system='gmp_labvantage',sdcid='Sample',keyid1='GAP',keyid2='(null)',keyid3='(null)',workitemid='方法任务',paramlistid='待确认方法',paramlistversionid='1'))])
        self.row(sample='GAP',samplesubtypeid='纯化水',paramlistid='待确认方法',workitemid='方法任务',unit='mg/L')
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_review_item'),[(0,)])

    def test_invalid_sample_identity_blocks_plot_and_diagnoses(self):
        self.row(s_sampleid='wrong')
        self.assertEqual(self.rows('select count(*) from pg_temp.v_water_numeric_trend'),[(0,)])
        self.assertEqual(self.rows('select issue_type from pg_temp.v_water_review_item'),[('invalid_sample_identity',)])

    def test_ph_unapproved_version_does_not_inherit_dimensionless(self):
        self.row(paramlistid='pH值',paramlistversionid='3')
        self.assertEqual(self.rows('select unit_status,analysis_unit,plot_eligible from pg_temp.v_water_result'),[('missing',None,False)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
