"""Overview SQL against isolated fixtures; no business database writes."""
from contextlib import asynccontextmanager
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from app import db, main
from app.analysis import SOURCE, TZ
from test_rules import signed


@pytest.fixture
def overview_api(monkeypatch):
    names=['source_system','sdcid','samplesubtypeid','selection_rule','samplestatus','s_sampleid','samplepointid']
    table=Table('synthetic_results',MetaData(),*[Column(n,String) for n in names],Column('trend_dt',DateTime()))
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    table.metadata.create_all(engine)
    base={'source_system':SOURCE,'sdcid':'Sample','samplesubtypeid':'注射用水',
          'selection_rule':'water_system_v1','samplestatus':'Reviewed','s_sampleid':'S1','samplepointid':'SP-A',
          'trend_dt':datetime(2026,1,1,tzinfo=TZ)}
    variants=[{}, # One sample has multiple parameters, including its numeric companion.
              {'selection_rule':'water_conductivity_method1_numeric_v1'},
              {'s_sampleid':'S2','samplepointid':'SP-B','samplestatus':'Completed','trend_dt':datetime(2026,10,9,23,59,59,tzinfo=TZ)},
              {'s_sampleid':'LAST_YEAR','samplepointid':'SP-OLD','trend_dt':datetime(2025,12,31,23,59,59,tzinfo=TZ)},
              {'s_sampleid':'TOMORROW','trend_dt':datetime(2026,10,10,tzinfo=TZ)},
              {'s_sampleid':'NO_DATE','samplepointid':'SP-NO-DATE','trend_dt':None},
              {'s_sampleid':'NO_POINT','samplepointid':None},
              {'s_sampleid':'EMPTY_POINT','samplepointid':''},
              {'s_sampleid':'EXCLUDED_RULE','samplepointid':'SP-X','selection_rule':'unknown'},
              {'s_sampleid':'EXCLUDED_SOURCE','samplepointid':'SP-X','source_system':'other'},
              {'s_sampleid':'EXCLUDED_STATUS','samplepointid':'SP-X','samplestatus':'Received'},
              {'s_sampleid':'EXCLUDED_DOMAIN','samplepointid':'SP-X','sdcid':'Other'},
              {'s_sampleid':'PW1','samplesubtypeid':'纯化水','samplepointid':'SP-PW'},
              {'s_sampleid':'PRODUCT','samplesubtypeid':'成品','samplepointid':'SP-X'}]
    with engine.begin() as conn:
        conn.execute(table.insert(),[{**base,**v} for v in variants])
    monkeypatch.setitem(db.models,'wide',type('Wide',(),{n:table.c[n] for n in table.c.keys()}))
    reads=[]

    class Session:
        def __init__(self,conn): self.conn=conn
        async def execute(self,stmt):
            reads.append('counts')
            return self.conn.execute(stmt)

    @asynccontextmanager
    async def transaction():
        reads.append('begin')
        with engine.connect() as conn: yield Session(conn)
        reads.append('end')

    async def context(session):
        assert isinstance(session,Session)
        reads.append('context')
        return {'environment':'isolated_fixture'}

    monkeypatch.setattr(db,'transaction',transaction)
    monkeypatch.setattr(main,'context',context)
    monkeypatch.setattr(main,'today',lambda:date(2026,10,9))
    client=TestClient(main.app)
    yield client,engine,table,reads
    engine.dispose()


def headers(roles=None):
    return {'Authorization':'Bearer '+signed(['CMC_WATER_VIEWER'] if roles is None else roles)}


def test_overview_calendar_dedup_scope_and_one_transaction(overview_api):
    client,_,_,reads=overview_api
    response=client.get('/api/v1/overview',headers=headers())
    assert response.status_code==200
    data=response.json()
    assert data['year']==2026 and data['date_from']=='2026-01-01' and data['date_to']=='2026-10-10'
    assert data['sample_status']==['Reviewed','Completed']
    assert data['overview_rule_version']=='water_overview_counts_v1'
    assert data['water_cards']==[
        {'code':'WFI','water_type':'注射用水','point_count':4,'annual_sample_count':4},
        {'code':'PW','water_type':'纯化水','point_count':1,'annual_sample_count':1},
        {'code':'PS','water_type':'纯蒸汽','point_count':0,'annual_sample_count':0}]
    assert data['data_context']['current_date']=='2026-10-09'
    assert reads==['begin','counts','context','end']
    assert 'groups' not in data and 'filter' not in data


def test_current_year_never_moves_to_last_data_year(overview_api,monkeypatch):
    client,_,_,_=overview_api
    monkeypatch.setattr(main,'today',lambda:date(2027,1,1))
    data=client.get('/api/v1/overview',headers=headers()).json()
    assert data['date_from']=='2027-01-01' and data['date_to']=='2027-01-02'
    assert [c['annual_sample_count'] for c in data['water_cards']]==[0,0,0]
    assert [c['point_count'] for c in data['water_cards']]==[4,1,0]


def test_empty_overview_has_three_zero_cards(overview_api):
    client,engine,table,_=overview_api
    with engine.begin() as conn: conn.execute(table.delete()) # Isolated SQLite only.
    data=client.get('/api/v1/overview',headers=headers()).json()
    assert len(data['water_cards'])==3
    assert all(c['point_count']==c['annual_sample_count']==0 for c in data['water_cards'])


def test_overview_requires_view_and_rejects_all_filters(overview_api):
    client,_,_,reads=overview_api
    assert client.get('/api/v1/overview').status_code==401
    assert client.get('/api/v1/overview',headers=headers([])).status_code==403
    for query in ['water_type=纯化水','date_from=2026-01-01','sample_status=Reviewed','year=2025','bad=value']:
        assert client.get('/api/v1/overview?'+query,headers=headers()).status_code==422
    assert reads==[]


def test_overview_failure_is_not_zero(overview_api,monkeypatch):
    client,_,_,_=overview_api
    async def broken(session,current): raise OperationalError('isolated',{},Exception('fixture failure'))
    monkeypatch.setattr(db,'read_overview',broken)
    response=client.get('/api/v1/overview',headers=headers())
    assert response.status_code==503 and response.json()['code']=='DATA_UNAVAILABLE'
    assert 'water_cards' not in response.json()


def test_removed_routes_and_preserved_trace_contract():
    client=TestClient(main.app)
    for path in ['results','summaries','data-quality']:
        assert client.get('/api/v1/'+path,headers=headers()).status_code==404
    assert client.get('/api/v1/results/trace?result_id=bad',headers=headers()).status_code==422
