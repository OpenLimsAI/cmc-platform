import os
os.environ.update(JWT_VERIFY_KEY='isolated-water-test-key-not-mdm-secret-000001',DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/isolated',WATER_VIEW_ROLES='CMC_WATER_VIEWER,CMC_WATER_EXPORTER,SYS_ADMIN',WATER_EXPORT_ROLES='CMC_WATER_EXPORTER,SYS_ADMIN')
from datetime import date,datetime
from decimal import Decimal
import io,json,hashlib,zipfile,time
import jwt,pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from app.analysis import *
from app.core import settings,Settings
from app import main
from app.export import generate
@pytest.mark.parametrize('day,months,expected',[(date(2026,10,2),3,date(2026,7,2)),(date(2026,10,2),6,date(2026,4,2)),(date(2026,10,2),12,date(2025,10,2)),(date(2024,2,29),12,date(2023,2,28)),(date(2026,5,31),3,date(2026,2,28))])
def test_calendar(day,months,expected):assert months_before(day,months)==expected
@pytest.mark.parametrize('raw,kind',[('001.2300','exact_numeric'),('-1e-3','exact_numeric'),('<1','censored'),('≤ 0.5','censored'),('符合规定','qualitative'),('未检出','qualitative'),('', 'missing'),(None,'missing'),('1ppm','unparsed'),('NaN','unparsed')])
def test_parse(raw,kind):assert parse(raw)['result_kind']==kind

def row(value='001.2300',unit='µS/cm',param='结果',rep='1'):
 r={k:'' for k in KEY};r.update(source_system=SOURCE,sdcid='Sample',keyid1='sample',s_sampleid='sample',paramlistid='电导率',paramlistversionid='1',variantid='【纯化水】',dataset=Decimal('1'),paramid=param,paramtype='Standard',replicateid=Decimal(rep),samplesubtypeid='纯化水',samplepointid='001',workitemid='电导率',displayvalue=value,unit=unit,trend_dt=datetime(2026,10,2,23,59,59,tzinfo=TZ),trend_dt_source='eventdt',samplestatus='Reviewed',selection_rule='water_system_v1')
 return normalize(r)
def test_counts_groups():
 rows=[row('1.20'),row('<1',rep='2'),row('符合规定',param='结论')]
 assert metrics(rows)['dataset_count']==1 and metrics(rows)['result_count']==3 and metrics(rows)['sample_count']==1
 assert len({r['comparison_group'] for r in rows})==2
 assert row(unit=None)['plot_status']=='not_plotted'
 assert row(unit='mS/cm')['comparison_group']!=rows[0]['comparison_group']
 assert decode(rows[0]['result_id'])==rows[0]['source_key']
def test_closed_config():
 for changes in [{'water_view_roles':''},{'water_export_roles':'UNKNOWN'},{'jwt_verify_key':'CHANGE_ME'},{'jwt_algorithm':'none'}]:
  with pytest.raises(ValueError):Settings(**changes)
def signed(roles,**claims):return jwt.encode({'sub':'123','type':'access','exp':int(time.time())+300,'roles':roles,**claims},settings.jwt_verify_key,algorithm='HS256')
@pytest.mark.parametrize('token,expected',[(None,401),('broken',401),(signed([]),403),(signed(['SYS_ADMIN'],exp=1),401),(signed(['SYS_ADMIN'],type='refresh'),401),(signed(['SYS_ADMIN'],must_change_password=True),403),(signed(['CMC_WATER_VIEWER']),200),(signed(['CMC_WATER_EXPORTER']),200)])
def test_identity_matrix(monkeypatch,token,expected):
 async def fake(f):return [row()],{'context_id':None}
 monkeypatch.setattr(main,'collection',fake)
 r=TestClient(main.app).get('/api/v1/comparison-groups',headers={'Authorization':'Bearer '+token} if token else {})
 assert r.status_code==expected
@pytest.mark.parametrize('kind',['chart','table','bundle'])
def test_export_roles(monkeypatch,kind):
 async def fake(f):return [row()],{'context_id':None}
 monkeypatch.setattr(main,'collection',fake)
 c=TestClient(main.app);payload={'filter':FilterSpec().model_dump(mode='json'),'comparison_group':row()['comparison_group'],'export_kind':kind,'dataset_digest':main.digest([row()])}
 for roles,status in [(['CMC_WATER_VIEWER'],403),(['CMC_WATER_EXPORTER'],200)]:
  assert c.post('/api/v1/exports',headers={'Authorization':'Bearer '+signed(roles)},json=payload).status_code==status
 payload['dataset_digest']='0'*64
 assert c.post('/api/v1/exports',headers={'Authorization':'Bearer '+signed(['CMC_WATER_EXPORTER'])},json=payload).status_code==409

def test_export_preserves_strings(tmp_path):
 rows=[row('001.2300'),row('=1+1',rep='2'),row('<1',rep='3'),row('中文未知',rep='4')]
 payload=main.ExportRequest(filter=FilterSpec(),comparison_group=rows[0]['comparison_group'],export_kind='bundle',dataset_digest=main.digest(rows))
 content,_,_=generate(rows,{},payload,{'sub':'isolated-test'})
 with zipfile.ZipFile(io.BytesIO(content)) as z:
  assert set(z.namelist())=={'trend.png','results.xlsx','results.csv','results.jsonl','manifest.json'}
  m=json.loads(z.read('manifest.json'))
  for k,h in m['sha256'].items():assert hashlib.sha256(z.read(k)).hexdigest()==h
  assert [json.loads(line) for line in z.read('results.jsonl').decode().splitlines()]==rows
  ws=load_workbook(io.BytesIO(z.read('results.xlsx')))['原始结果'];idx=[c.value for c in ws[1]].index('display_value')+1
  assert [ws.cell(i,idx).value for i in range(2,6)]==['001.2300','=1+1','<1','中文未知']
  assert all(ws.cell(i,idx).data_type=='s' for i in range(2,6))
  assert "'=1+1" in z.read('results.csv').decode('utf-8-sig')
  (tmp_path/'test-trend.png').write_bytes(z.read('trend.png'))

def test_query_contract(monkeypatch):
 async def fake(f):return [row()],{'context_id':None}
 monkeypatch.setattr(main,'collection',fake)
 c=TestClient(main.app);h={'Authorization':'Bearer '+signed(['CMC_WATER_VIEWER'])}
 for path in ['comparison-groups','trends?comparison_group='+__import__('urllib.parse',fromlist=['quote']).quote(row()['comparison_group'])]:
  assert c.get('/api/v1/'+path,headers=h).status_code==200


def test_failures_and_empty(monkeypatch):
 from sqlalchemy.exc import OperationalError
 c=TestClient(main.app);h={'Authorization':'Bearer '+signed(['CMC_WATER_EXPORTER'])}
 async def broken(f):raise OperationalError('isolated',{},Exception('no credentials'))
 monkeypatch.setattr(main,'collection',broken)
 r=c.get('/api/v1/comparison-groups',headers=h);assert r.status_code==503 and r.json()['code']=='DATA_UNAVAILABLE'
 async def large(f):raise __import__('fastapi').HTTPException(413,'范围超过允许行数，请缩小筛选')
 monkeypatch.setattr(main,'collection',large)
 assert c.get('/api/v1/comparison-groups',headers=h).status_code==413
 async def empty(f):return [],{}
 monkeypatch.setattr(main,'collection',empty)
 assert c.get('/api/v1/comparison-groups',headers=h).json()['metrics']['result_count']==0
 payload={'filter':FilterSpec().model_dump(mode='json'),'comparison_group':row()['comparison_group'],'export_kind':'bundle','dataset_digest':main.digest([])}
 r=c.post('/api/v1/exports',headers=h,json=payload);assert r.status_code==422 and r.json()['code']=='EXPORT_NO_RESULTS'
 for suffix in ['?date_from=2026-10-03&date_to=2026-10-02','?date_from=1900-01-01&date_to=2026-10-03','?sample_status=INVALID','?bad=value']:
  assert c.get('/api/v1/comparison-groups'+suffix,headers=h).status_code==422

def test_shanghai_and_date_boundary(monkeypatch):
 import app.analysis as a
 monkeypatch.setattr(a,'today',lambda:date(2026,10,2))
 f=FilterSpec();assert f.date_from==date(2025,10,2) and f.date_to==date(2026,10,3)
 r=row();assert r['trend_at']=='2026-10-02T23:59:59+08:00'
 assert datetime(2026,10,1,16,0,tzinfo=__import__('datetime').timezone.utc).astimezone(TZ).date()==date(2026,10,2)


def test_default_date_frozen_once(monkeypatch):
 import app.analysis as a
 calls=[]
 def crossing():
  calls.append(1)
  return date(2026,10,2) if len(calls)==1 else date(2026,10,3)
 monkeypatch.setattr(a,'today',crossing)
 f=FilterSpec();assert f.date_from==date(2025,10,2) and f.date_to==date(2026,10,3) and len(calls)==1


def test_missing_points_cannot_form_a_trend_group():
 a=row();b=row(rep='2')
 for r in [a,b]:r['samplepointid']=None
 a=normalize(a);b=normalize(b)
 assert a['comparison_group']!=b['comparison_group']
 assert a['plot_status']=='not_plotted' and '内部 ID 缺失' in a['not_plotted_reason']


def test_current_point_codes_do_not_merge_internal_identities():
 a=row(); b=row()
 for r,point in [(a,'SP-A'),(b,'SP-B')]:
  r.update(samplepointid=point,samplepoint_code='WFI002',samplepoint_name='总送水口',samplepoint_mapping_source='MBTK.S_SAMPLEPOINT',samplepoint_mapping_scope='current_master')
 a=normalize(a);b=normalize(b)
 assert a['comparison_group']!=b['comparison_group']
 assert a['samplepoint_code']=='WFI002' and a['samplepoint_name']=='总送水口'
 assert '历史有效期' in a['mapping_status']
 assert a['display_value']=='001.2300'

def test_point_mapping_export_is_preserved_with_source_values():
 from app.export import xlsx,COLUMNS
 r=row();r.update(samplepoint_code='WFI002',samplepoint_name='总送水口',samplepoint_mapping_source='MBTK.S_SAMPLEPOINT',samplepoint_mapping_scope='current_master',samplepoint_source_moddt='2025-12-19T10:51:42+08:00',samplepoint_extracted_at='2026-10-08T12:00:00+08:00')
 r=normalize(r)
 ws=load_workbook(io.BytesIO(xlsx([r],{})))['原始结果']
 values=dict(zip([c.value for c in ws[1]],[c.value for c in ws[2]]))
 for field in ['samplepoint_code','samplepoint_name','samplepoint_mapping_source','samplepoint_mapping_scope','samplepoint_source_moddt','samplepoint_extracted_at','samplepoint_id','display_value']:
  assert values[field]==r[field] and field in COLUMNS


def test_point_code_filter_uses_exact_code_without_merging_ids(monkeypatch):
 from sqlalchemy import Table,Column,MetaData,String,DateTime
 from app import db
 fields=['source_system','sdcid','samplesubtypeid','selection_rule','samplestatus','samplepointid','samplepoint_code','workitemid','paramlistid','paramlistversionid','variantid','paramid','unit']
 t=Table('points',MetaData(),*[Column(n,String) for n in fields],Column('trend_dt',DateTime(timezone=True)))
 monkeypatch.setitem(db.models,'wide',type('Wide',(),{n:t.c[n] for n in t.c.keys()}))
 f=FilterSpec(samplepoint_code='WFI002',samplepoint_id='SP-A')
 from sqlalchemy import and_
 compiled=and_(*db.conditions(f)).compile(compile_kwargs={'literal_binds':True})
 assert "samplepoint_code = 'WFI002'" in str(compiled) and "samplepointid = 'SP-A'" in str(compiled)
 with pytest.raises(ValueError):FilterSpec(samplepoint_code='')


def test_date_warning_follows_verified_staging_origin():
 from app.main import source_notes
 assert '分钟不准确' in source_notes('legacy_xlsx')[1]
 assert '分钟不准确' not in source_notes('oracle_etl')[1]
 assert '最新 raw' in source_notes('unverified')[1]
