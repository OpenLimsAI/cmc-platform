from datetime import datetime,timedelta
import json
import pytest
from app.archive import lifecycle,device_runs,checked_report
from app.domain import Task,Run,Snapshot,SH,assess,current_view
from app.sources import Reader,evidence
from app.api import public_snapshot
from app.engine import Engine
from app.store import MemoryStore
from app.inventory import load_tasks
from app.api import create_app
from fastapi.testclient import TestClient
from test_monitor import config,token

AT=datetime(2026,10,12,16,tzinfo=SH)
HEADER='Relative_Path,Local_SHA256,NAS_SHA256,match_status\n'

def device(name):
 return Task(key='ingest-'+('nova' if name=='flex2' else 'vicell'),name=name,kind='backup',project='test',
             adapter='archive_device',archive_device=name,times=['02:00','11:45','16:00'],
             timeout_minutes=240,slot_timeouts={'02:00':240,'11:45':15,'16:00':15})

def parent(vicell='success',mode='day',at=AT):
 r=Run(id='ingest-'+mode+':unit:one',task_key='ingest-'+mode,start=at,finish=at+timedelta(seconds=12),
       status='failed' if vicell=='failed' else 'success',source_kind='systemd',archive_mode=mode)
 entries=[]
 for name,begin,end,state in [('flex2',1,3,'success'),('vicell',4,10,vicell)]:
  for when,message in [(begin,f'>>> [{mode}] 开始采集 {name}'),(end,f'<<< [{mode}] {name} '+('完成' if state=='success' else '失败，退出码 1'))]:
   entries.append({'MESSAGE':message,'__REALTIME_TIMESTAMP':str(int((at+timedelta(seconds=when)).timestamp()*1e6))})
 r.evidence=[evidence('journal','instrument-ingest-'+mode+'.service','\n'.join(e['MESSAGE'] for e in entries))]
 r.children=lifecycle(entries,mode,r)
 return r

def report(root,r,name,content=None,version='1'):
 machine={'flex2':'T281240040C_Nova','vicell':'C4V61257XH_ViCell'}[name]
 c=next(c for c in r.children if c['name']==name)
 stamp=datetime.fromisoformat(c['start']).astimezone(SH).strftime('%Y%m%d_%H%M%S')
 folder=root/'Checksums'/machine;folder.mkdir(parents=True,exist_ok=True)
 p=folder/f'{machine}_SHA256_Compare_v{version}_{stamp}.csv'
 p.write_text(HEADER+(content if content is not None else 'PRIVATE,'+'a'*64+','+'a'*64+',MATCH\n'))
 return p

def read(root,r):
 Reader(config()).instrument_evidence(r,root)
 return {d:device_runs(device(d),[r])[0] for d in ('flex2','vicell')}

def test_each_device_passes_without_recovery_and_other_shift_heartbeat(tmp_path):
 r=parent()
 for d in ('flex2','vicell'):report(tmp_path,r,d)
 (tmp_path/'State').mkdir();(tmp_path/'State'/'bad_heartbeat.json').write_text('{bad')
 rows=read(tmp_path,r)
 for d,row in rows.items():
  o=assess(device(d),[row],AT+timedelta(minutes=2))
  assert o.state=='success' and row.restore=='not_applicable' and row.integrity=='scope_verified'
  assert row.parent_run_id==r.id and row.archive_mode=='day'
  assert 'PRIVATE' not in json.dumps(row.model_dump(mode='json'))

def test_no_new_files_is_success(tmp_path):
 r=parent();report(tmp_path,r,'flex2',content='');report(tmp_path,r,'vicell')
 row=read(tmp_path,r)['flex2']
 o=assess(device('flex2'),[row],AT+timedelta(minutes=1))
 assert o.state=='success' and o.label=='检查完成，无需新增归档' and row.files==0

def test_other_device_failure_does_not_mask_success(tmp_path):
 r=parent(vicell='failed');report(tmp_path,r,'flex2')
 rows=read(tmp_path,r)
 assert assess(device('flex2'),[rows['flex2']],AT+timedelta(minutes=1)).state=='success'
 assert assess(device('vicell'),[rows['vicell']],AT+timedelta(minutes=1)).state=='failed'

@pytest.mark.parametrize('state,hash_b,expected',[('MATCH','b'*64,'failed'),('MISMATCH','a'*64,'failed'),('MATCH','','unknown'),('DRY_RUN','a'*64,'unknown')])
def test_mismatch_unknown_and_dry_run_never_green(tmp_path,state,hash_b,expected):
 r=parent();report(tmp_path,r,'flex2');report(tmp_path,r,'vicell',content=f'PRIVATE,{"a"*64},{hash_b},{state}\n')
 row=read(tmp_path,r)['vicell']
 assert assess(device('vicell'),[row],AT+timedelta(minutes=1)).state==expected

@pytest.mark.parametrize('case',['missing','ambiguous','symlink','bad_header'])
def test_report_identity_is_required(tmp_path,case):
 r=parent();report(tmp_path,r,'flex2')
 if case!='missing':
  p=report(tmp_path,r,'vicell')
  if case=='ambiguous':report(tmp_path,r,'vicell',version='2')
  if case=='symlink':p.unlink();p.symlink_to(tmp_path/'outside')
  if case=='bad_header':p.write_text('match_status\nMATCH\n')
 row=read(tmp_path,r)['vicell']
 assert assess(device('vicell'),[row],AT+timedelta(minutes=1)).state=='unknown'

def test_report_from_another_run_does_not_cover_missing_one(tmp_path):
 r=parent();old=parent(at=AT-timedelta(days=1));report(tmp_path,old,'vicell');report(tmp_path,r,'flex2')
 assert read(tmp_path,r)['vicell'].status=='unknown'

def test_valid_night_report_survives_newer_day_record(tmp_path):
 night=parent(mode='night',at=AT.replace(hour=2));day=parent()
 for r in (night,day):
  for d in ('flex2','vicell'):report(tmp_path,r,d)
 rows=read(tmp_path,night)
 assert all(r.integrity=='scope_verified' for r in rows.values())

def test_day_success_does_not_cover_latest_failed_image_run(tmp_path):
 night=parent(vicell='failed',mode='night',at=AT.replace(hour=2));day=parent()
 for r in (night,day):
  for d in ('flex2','vicell'):report(tmp_path,r,d)
 a=read(tmp_path,night)['vicell'];b=read(tmp_path,day)['vicell']
 assert assess(device('vicell'),[a,b],AT+timedelta(minutes=1)).state=='warning'
 # The next complete night repairs the current scope, preserving failure history.
 later=parent(mode='night',at=AT.replace(hour=2)+timedelta(days=1))
 for d in ('flex2','vicell'):report(tmp_path,later,d)
 c=read(tmp_path,later)['vicell']
 assert assess(device('vicell'),[a,b,c],c.finish+timedelta(minutes=1)).state=='success'

def test_missing_device_terminal_cannot_borrow_other_success():
 r=parent();r.children=lifecycle([],r.archive_mode,r)
 assert all(c['status']=='unknown' for c in r.children)

def test_public_inventory_hides_sources_but_retains_producer_registration():
 tasks=load_tasks(config().inventory_path)
 visible=[t for t in tasks if t.visible]
 assert len(visible)==16 and len([t for t in visible if t.enabled is True])==10
 assert {t.key for t in tasks if not t.visible}=={'ingest-day','ingest-night'}
 assert all(t.producer_users==['flex2ingest'] for t in tasks if not t.visible)
 s=Snapshot(id='test',collected_at=AT,trigger='test',tasks=[assess(t,[],AT) for t in tasks])
 assert len(public_snapshot(s)['tasks'])==16
 assert len(public_snapshot(s,include_hidden=True)['tasks'])==18

async def test_engine_derives_devices_without_extra_workers_or_mixed_upstream(tmp_path):
 r=parent(vicell='failed')
 report(tmp_path,r,'flex2');Reader(config()).instrument_evidence(r,tmp_path)
 called=[]
 class Source:
  async def read(self,t,*args):called.append(t.key);return [r],[]
 t=Task(key='ingest-day',name='parent',kind='backup',project='test',adapter='systemd',visible=False)
 s=await Engine(config(),[t,device('flex2'),device('vicell')],MemoryStore(),Source()).collect()
 assert called==['ingest-day']
 results={o.task.key:o for o in s.tasks}
 assert results['ingest-nova'].last_run.status=='success' and results['ingest-vicell'].last_run.status=='failed'

async def test_etl_upstream_risk_belongs_to_its_own_device(tmp_path):
 r=parent(vicell='failed');report(tmp_path,r,'flex2');Reader(config()).instrument_evidence(r,tmp_path)
 etls=[Task(key=k,name=k,kind='etl',project='test',adapter='rd_lims',times=[]) for k in ('vicell','nova')]
 class Source:
  async def read(self,t,*args):
   if t.key=='ingest-day':return [r],[]
   return [Run(id=t.key,task_key=t.key,start=AT+timedelta(seconds=30),finish=AT+timedelta(seconds=40),status='success')],[]
 t=Task(key='ingest-day',name='parent',kind='backup',project='test',adapter='systemd',visible=False)
 s=await Engine(config(),[t,device('flex2'),device('vicell'),*etls],MemoryStore(),Source()).collect()
 results={o.task.key:o for o in s.tasks}
 assert results['nova'].state=='success' and results['vicell'].state=='warning'

def test_nova_complete_day_can_recover_same_scope_night_failure(tmp_path):
 night=parent(mode='night',at=AT.replace(hour=2));day=parent()
 for r in (night,day):
  for d in ('flex2','vicell'):report(tmp_path,r,d)
 a=read(tmp_path,night)['flex2'].model_copy(update={'status':'failed'})
 b=read(tmp_path,day)['flex2']
 assert assess(device('flex2'),[a,b],AT+timedelta(minutes=1)).state=='success'

def test_old_snapshot_has_legacy_history_but_no_invented_device_result():
 tasks=load_tasks(config().inventory_path)
 old=[t for t in tasks if not t.archive_device]
 store=MemoryStore();store.snapshots['old']=Snapshot(id='old',collected_at=AT,trigger='test',tasks=[assess(t,[],AT) for t in old])
 with TestClient(create_app(config(),store)) as c:
  headers={'Authorization':'Bearer '+token()}
  assert c.get('/api/v1/tasks/ingest-day?snapshot_id=old',headers=headers).status_code==200
  assert c.get('/api/v1/tasks/ingest-vicell?snapshot_id=old',headers=headers).status_code==410

def test_malformed_checksum_header_is_not_no_changes():
 with pytest.raises(ValueError):checked_report('')


async def upstream_snapshot(tmp_path,monkeypatch,latest='recovered',etl_status='success'):
 """Reproduce the Nov 3 ETL followed by the Nov 4 archive in isolated storage."""
 now=datetime(2026,11,4,8,1,tzinfo=SH)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return now.astimezone(tz)
 monkeypatch.setattr('app.engine.datetime',Clock)
 failed=parent(vicell='failed',at=datetime(2026,11,3,16,tzinfo=SH))
 failed.id='ingest-day:unit:previous'
 later=parent(vicell='failed' if latest=='failed' else 'success',mode='night',at=now.replace(hour=2,minute=0))
 later.id='ingest-night:unit:latest'
 for r in (failed,later):
  report(tmp_path,r,'flex2')
  if r is later and latest not in ('missing','failed'):
   report(tmp_path,r,'vicell',content='' if latest=='empty' else None)
  Reader(config()).instrument_evidence(r,tmp_path)
 etl_start=datetime(2026,11,3,16,20,tzinfo=SH)
 etls=[Task(key=k,name=k,kind='etl',project='test',adapter='systemd',times=['12:05','16:20'],timeout_minutes=15) for k in ('vicell','nova')]
 class Source:
  async def read(self,t,*args):
   if t.key=='ingest-day':return [failed],[]
   if t.key=='ingest-night':return [later],['读取失败'] if latest=='unavailable' else []
   return [Run(id=t.key,task_key=t.key,start=etl_start,finish=etl_start+timedelta(seconds=15),
               status=etl_status if t.key=='vicell' else 'success')],[]
 parents=[Task(key='ingest-'+m,name=m,kind='backup',project='test',adapter='systemd',visible=False) for m in ('day','night')]
 s=await Engine(config(),[*parents,device('flex2'),device('vicell'),*etls],MemoryStore(),Source()).collect()
 s.mode='production'
 return s,{o.task.key:o for o in s.tasks}


@pytest.mark.parametrize('latest',['recovered','empty'])
async def test_upstream_recovery_keeps_etl_risk_and_identifies_both_batches(tmp_path,monkeypatch,latest):
 s,items=await upstream_snapshot(tmp_path,monkeypatch,latest)
 o=items['vicell']
 assert o.state=='warning' and o.last_run.status=='success'
 assert o.label=='上次 ETL 有风险，上游已恢复'
 assert '2026-11-03 16:20 ETL' in o.upstream_risk.past
 assert '2026-11-03 16:00 归档批次执行失败' in o.upstream_risk.past
 assert '2026-11-04 02:00 归档批次' in o.upstream_risk.current
 assert '待下一次完整 ETL 确认' in o.upstream_risk.current
 assert items['nova'].state=='success' and items['nova'].upstream_risk is None
 assert current_view(s,s.collected_at).tasks==s.tasks


@pytest.mark.parametrize('latest,label',[('failed','上游风险仍在'),('missing','上游待核实'),('unavailable','上游待核实')])
async def test_latest_failure_or_missing_evidence_cannot_claim_recovery(tmp_path,monkeypatch,latest,label):
 _,items=await upstream_snapshot(tmp_path,monkeypatch,latest)
 o=items['vicell']
 assert label in o.label and '已恢复' not in o.upstream_risk.current
 assert '2026-11-04 02:00' in o.upstream_risk.current
 assert o.state=='warning'


async def test_recovery_is_withdrawn_when_archive_view_expires(tmp_path,monkeypatch):
 s,items=await upstream_snapshot(tmp_path,monkeypatch)
 # Archive 11:45 has no new evidence after its 12:05 deadline; ETL is still within its window.
 now=datetime(2026,11,4,12,6,tzinfo=SH)
 view=current_view(s,now)
 o=next(o for o in view.tasks if o.task.key=='vicell')
 assert o.state=='warning' and o.label=='上次 ETL 有风险，上游待核实'
 assert '已恢复' not in o.upstream_risk.current
 assert o.upstream_risk.past==items['vicell'].upstream_risk.past
 assert '已恢复' in items['vicell'].upstream_risk.current  # historical snapshot unchanged
 assert current_view(view,now)==view
 expired=current_view(s,datetime(2026,11,4,12,26,tzinfo=SH))
 o=next(o for o in expired.tasks if o.task.key=='vicell')
 assert o.state=='unknown' and o.label=='更新逾期，当前未核实'


@pytest.mark.parametrize('case',['running','future_finish','old_batch','scope_warning'])
async def test_current_upstream_recovery_requires_complete_fresh_same_device(tmp_path,monkeypatch,case):
 s,items=await upstream_snapshot(tmp_path,monkeypatch)
 archive=items['ingest-vicell']
 if case=='running':archive.state='unknown';archive.last_run.status='running';archive.last_run.finish=None
 if case=='future_finish':archive.last_run.finish=s.collected_at+timedelta(minutes=1)
 if case=='old_batch':archive.last_run.start=datetime(2026,11,2,16,tzinfo=SH)
 if case=='scope_warning':archive.state='warning';archive.label='归档完成，有提醒'
 o=next(o for o in current_view(s,s.collected_at).tasks if o.task.key=='vicell')
 assert '已恢复' not in o.upstream_risk.current and o.state=='warning'


async def test_etl_own_warnings_and_legacy_snapshots_are_preserved(tmp_path,monkeypatch):
 s,items=await upstream_snapshot(tmp_path,monkeypatch,etl_status='partial_failed')
 assert '部分步骤或记录失败' in items['vicell'].reasons
 old=s.model_dump(mode='json')
 for o in old['tasks']:o.pop('upstream_risk',None)
 parsed=Snapshot.model_validate(old)
 assert all(o.upstream_risk is None for o in current_view(parsed,s.collected_at).tasks)


async def test_pending_api_update_withdraws_recovery_but_preserves_historical_view(tmp_path,monkeypatch):
 s,_=await upstream_snapshot(tmp_path,monkeypatch)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return s.collected_at.astimezone(tz)
 monkeypatch.setattr('app.api.datetime',Clock)
 store=MemoryStore();store.snapshots[s.id]=s
 await store.enqueue({'trigger':'manual'})
 with TestClient(create_app(config(),store)) as c:
  headers={'Authorization':'Bearer '+token()}
  current=c.get('/api/v1/overview',headers=headers).json()
  o=next(o for o in current['tasks'] if o['task']['key']=='vicell')
  assert o['label']=='更新待完成，当前未核实' and '已恢复' not in o['upstream_risk']['current']
  historical=c.get('/api/v1/overview',params={'snapshot_id':s.id},headers=headers).json()
  o=next(o for o in historical['tasks'] if o['task']['key']=='vicell')
  assert '已恢复' in o['upstream_risk']['current']


@pytest.mark.parametrize('status,finish,integrity,expected',[
 ('failed',10,None,'执行失败'),('partial_failed',10,None,'部分执行失败'),
 ('running',None,None,'尚未完成'),('success',40,'scope_verified','晚于ETL开始'),
 ('success',10,'failed','校验未通过'),('success',10,None,'校验证据不足'),
 ('unknown',10,None,'结束或校验证据不足'),
])
def test_historical_upstream_message_names_actual_risk(status,finish,integrity,expected):
 from app.domain import archive_issue
 r=Run(id='archive',task_key='ingest-vicell',start=AT,status=status,
       finish=AT+timedelta(seconds=finish) if finish else None,integrity=integrity)
 assert expected in archive_issue(r,AT+timedelta(seconds=30))
