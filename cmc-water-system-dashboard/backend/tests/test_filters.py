"""Execute cascade SQL on synthetic, in-memory fixtures; no business DB or MDM."""
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from test_rules import signed
from app import db, main
from app.analysis import SOURCE, TZ


@pytest.fixture
def cascade_api(monkeypatch):
    columns=['source_system','sdcid','samplesubtypeid','selection_rule','samplestatus',
             'samplepoint_code','samplepointid','samplepoint_name','workitemid',
             'paramlistid','paramlistversionid','variantid','paramid','unit']
    table=Table('synthetic_choices',MetaData(),*[Column(name,String) for name in columns],Column('trend_dt',DateTime()))
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    table.metadata.create_all(engine)
    base=dict(source_system=SOURCE,sdcid='Sample',samplesubtypeid='注射用水',
              selection_rule='water_system_v1',samplestatus='Reviewed',samplepoint_code='WFI002',
              samplepointid='SP-A',samplepoint_name='测试总送',workitemid='电导率',
              paramlistid='方法甲',paramlistversionid='1',variantid='阶段甲',paramid='结果',unit='µS/cm',
              trend_dt=datetime(2026,10,9,0,0,tzinfo=TZ))
    variants=[{}, {'samplepointid':'SP-B','samplepoint_name':'测试同号独立点位'},
              {'samplepoint_code':'WFI003','samplepointid':'SP-C'},
              {'paramlistversionid':'2','unit':'mS/cm'}, {'variantid':'阶段乙'},
              {'paramid':'结论','unit':None}, {'unit':'mS/cm'},
              {'workitemid':'TOC','paramlistid':'方法乙','unit':'mg/L'},
              {'samplesubtypeid':'纯化水','samplepoint_code':'PW001','samplepointid':'SP-PW'},
              {'samplesubtypeid':'纯蒸汽','samplepoint_code':'PS001','samplepointid':'SP-PS'},
              {'samplepoint_code':'OLD','trend_dt':datetime(2026,10,8,23,59,59,tzinfo=TZ)},
              {'samplepoint_code':'END','trend_dt':datetime(2026,10,10,0,0,tzinfo=TZ)},
              {'samplepoint_code':'COMPLETED','samplestatus':'Completed'},
              {'samplepoint_code':'EXCLUDED','selection_rule':'unapproved_rule'},
              {'samplepoint_code':'OTHER_SOURCE','source_system':'other'},
              {'samplepoint_code':'MISSING_DATE','trend_dt':None}]
    with engine.begin() as conn:
        conn.execute(table.insert(),[{**base,**variant} for variant in variants])
    monkeypatch.setitem(db.models,'wide',type('SyntheticWide',(),{name:table.c[name] for name in table.c.keys()}))

    class Session:
        def __init__(self,conn): self.conn=conn
        async def scalars(self,stmt): return self.conn.execute(stmt).scalars()
        async def execute(self,stmt): return self.conn.execute(stmt)

    @asynccontextmanager
    async def transaction():
        with engine.connect() as conn:
            yield Session(conn)

    async def context(session): return {'environment':'isolated_fixture'}
    monkeypatch.setattr(db,'transaction',transaction)
    monkeypatch.setattr(main,'context',context)
    # Do not run the application's production DB preflight on this synthetic fixture.
    yield TestClient(main.app)
    engine.dispose()


def request(client,**filters):
    query={'date_from':'2026-10-09','date_to':'2026-10-10','sample_status':'Reviewed',**filters}
    return client.get('/api/v1/filters?'+urlencode(query,doseq=True),headers={'Authorization':'Bearer '+signed(['CMC_WATER_VIEWER'])})


def test_water_type_limits_points_without_guessing_prefixes(cascade_api):
    response=request(cascade_api,water_type='注射用水')
    assert response.status_code==200
    data=response.json()
    assert data['options']['samplepoint_code']==['WFI002','WFI003']
    assert data['options']['samplesubtypeid']==['注射用水','纯化水','纯蒸汽']
    assert data['filter']['water_type']=='注射用水'
    assert {point['value'] for point in data['point_options']}=={'SP-A','SP-B','SP-C'}
    # Selecting a point must leave both internal identities of the same code available.
    data=request(cascade_api,water_type='注射用水',samplepoint_code='WFI002',samplepoint_id='SP-A').json()
    assert {point['value'] for point in data['point_options']}=={'SP-A','SP-B'}
    assert all(point['code']=='WFI002' and '测试' in point['label'] for point in data['point_options'])


def test_method_version_phase_parameter_unit_cascade(cascade_api):
    data=request(cascade_api,water_type='注射用水',samplepoint_code='WFI002',samplepoint_id='SP-A',
                 workitem_id='电导率',paramlist_id='方法甲',paramlist_version_id='1',variant_id='阶段甲',param_id='结果',unit='µS/cm').json()
    options=data['options']
    assert options['workitemid']==['TOC','电导率']
    assert options['paramlistid']==['方法甲']
    assert options['paramlistversionid']==['1','2']
    assert options['variantid']==['阶段乙','阶段甲']
    assert options['paramid']==['结果','结论']
    assert options['unit']==['mS/cm','µS/cm']
    # Unit choices change with a different method; lower conditions cannot hide upper choices.
    other=request(cascade_api,water_type='注射用水',workitem_id='TOC',paramlist_id='方法乙').json()['options']
    assert other['paramlistid']==['方法乙'] and other['unit']==['mg/L']
    assert other['workitemid']==['TOC','电导率']


def test_date_status_bounds_and_empty_population(cascade_api):
    assert request(cascade_api,water_type='注射用水',sample_status='Completed').status_code==422
    assert 'COMPLETED' not in request(cascade_api,water_type='注射用水').json()['options']['samplepoint_code']
    # Inclusive UI end date is already represented as exclusive next-day date_to.
    data=request(cascade_api,water_type='注射用水',date_from='2026-10-08',date_to='2026-10-09').json()
    assert data['options']['samplepoint_code']==['OLD']
    empty=request(cascade_api,date_from='2026-11-01',date_to='2026-11-02').json()
    assert all(values==[] for values in empty['options'].values()) and empty['point_options']==[]


def test_filters_keep_validation_and_backend_authorization(cascade_api):
    assert cascade_api.get('/api/v1/filters').status_code==401
    assert cascade_api.get('/api/v1/filters',headers={'Authorization':'Bearer '+signed([])}).status_code==403
    for filters in [{'water_type':'unknown'},{'sample_status':'unknown'},{'date_to':'2026-10-08'},{'unexpected':'x'}]:
        assert request(cascade_api,**filters).status_code==422


def test_filters_query_failure_is_not_empty_options(cascade_api,monkeypatch):
    async def broken(session,f): raise OperationalError('isolated',{},Exception('fixture query failed'))
    monkeypatch.setattr(db,'read_options',broken)
    response=request(cascade_api)
    assert response.status_code==503 and response.json()['code']=='DATA_UNAVAILABLE'
