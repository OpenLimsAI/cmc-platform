import asyncio
import json
from datetime import datetime,timedelta
from pathlib import Path
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.config import Settings
from app.domain import Task,Run,Snapshot,UTC,SH,assess,current_view
from app.api import create_app
from app.store import MemoryStore
from app.engine import Engine,Coordinator
from app.security import redact

KEY='isolated-monitor-test-signing-key-32-bytes'
NOW=datetime(2026,10,10,7,tzinfo=SH).astimezone(UTC)
def config(**kw):return Settings(mode='demo',jwt_verify_key=KEY,source_timeout=1,coalesce_seconds=0,**kw)
def task(**kw):
 data=dict(key='example',name='任务',kind='etl',project='test',times=['04:00'],adapter='rd_lims',timeout_minutes=15)
 return Task(**(data|kw))
def run(status='success',minutes=1,start=None,ident='test-run'):
 a=start or datetime(2026,10,10,4,tzinfo=SH).astimezone(UTC)
 return Run(id=ident,task_key='example',start=a,finish=None if status=='running' else a+timedelta(minutes=minutes),status=status)
def token(**kw):return jwt.encode(dict(sub='1',exp=datetime.now(UTC)+timedelta(hours=1),type='access',roles=['SYS_ADMIN'],must_change_password=False)|kw,KEY,algorithm='HS256')

@pytest.mark.parametrize('state,label', [('success','执行成功'),('failed','执行失败'),('partial_failed','执行完成，有提醒')])
def test_run_meaning(state,label):assert assess(task(),[run(state)],NOW).label==label

def test_completion_not_progress_or_excess_duration():
 o=assess(task(),[run('running')],datetime(2026,10,10,4,5,tzinfo=SH))
 assert o.state=='unknown' and o.label=='本次尚未完成'
 assert assess(task(),[run('running')],NOW).state=='failed'
 finished=assess(task(),[run(minutes=25)],NOW)
 assert finished.state=='warning' and finished.last_run.status=='success'

def test_manual_success_does_not_replace_missed_or_failed_slot():
 manual=run(start=datetime(2026,10,10,6,tzinfo=SH),ident='manual')
 assert assess(task(),[manual],NOW).label=='未按计划启动'
 failed=run('failed')
 assert assess(task(),[failed,manual],NOW).state=='failed'

def test_future_schedule_and_disabled():
 yesterday=run(start=datetime(2026,10,9,8,tzinfo=SH))
 assert assess(task(times=['08:00']),[yesterday],NOW).state=='success'
 assert assess(task(enabled=False),[],NOW).state=='disabled'

def test_source_failure_unknown_keeps_last_known():
 o=assess(task(),[run()],NOW,['权限不足'])
 assert o.state=='unknown' and o.last_run.status=='success'

def test_backup_artifact_is_not_restore():
 o=assess(task(kind='backup'),[run()],NOW)
 assert o.state=='warning' and '恢复未验证' in o.reasons

def test_stale_collectors_never_keep_green():
 old=assess(task(),[run()],NOW)
 s=Snapshot(id='old',collected_at=NOW,trigger='event',tasks=[old])
 updated=current_view(s,NOW+timedelta(days=1))
 assert updated.tasks[0].state=='unknown' and s.tasks[0].state=='success'

@pytest.mark.parametrize('timeout', [15,30])
@pytest.mark.parametrize('status,state', [('success','success'),('failed','failed'),('partial_failed','warning')])
def test_completed_scheduled_run_does_not_expire_at_its_deadline(timeout,status,state):
 t=task(times=['12:05','16:20'],timeout_minutes=timeout)
 start=datetime(2026,10,11,16,20,3,tzinfo=SH)
 observed=start+timedelta(seconds=32)
 o=assess(t,[run(status,start=start,minutes=0.2)],observed)
 s=Snapshot(id='completed',collected_at=observed,trigger='event',tasks=[o])
 result=current_view(s,datetime(2026,10,11,18,tzinfo=SH)).tasks[0]
 assert result.state==state and result.collection_status=='ok'
 assert result.last_run.status==status and s.tasks[0].state==state
 # A successful daily check does not cover tomorrow's missing scheduled run.
 checked=datetime(2026,10,12,7,1,tzinfo=SH)
 s.tasks[0].observed_at=checked
 result=current_view(s,datetime(2026,10,12,12,41,tzinfo=SH)).tasks[0]
 assert result.state=='unknown' and result.collection_status=='stale'

@pytest.mark.parametrize('case', ['wrong_window','missing_finish','future_finish','source_unavailable','running'])
def test_deadline_requires_same_window_observed_terminal_evidence(case):
 t=task(times=['16:20'])
 observed=datetime(2026,10,11,16,20,35,tzinfo=SH)
 r=run(start=datetime(2026,10,11,16,20,3,tzinfo=SH),minutes=0.2)
 if case=='wrong_window':r.start-=timedelta(hours=1);r.finish-=timedelta(hours=1)
 if case=='missing_finish':r.finish=None
 if case=='future_finish':r.finish=observed+timedelta(seconds=1)
 if case=='running':r.status='running';r.finish=None
 o=assess(t,[r],observed,['采集失败'] if case=='source_unavailable' else [])
 s=Snapshot(id='insufficient',collected_at=observed,trigger='event',tasks=[o])
 assert current_view(s,datetime(2026,10,11,18,tzinfo=SH)).tasks[0].state=='unknown'

@pytest.mark.parametrize('minute,state', [(1,'success'),(-1,'unknown')])
def test_daily_safety_grace_is_deadline_not_required_second_observation(minute,state):
 observed=datetime(2026,10,11,7,tzinfo=SH)+timedelta(minutes=minute)
 o=assess(task(times=[]),[run()],observed)
 s=Snapshot(id='safety',collected_at=observed,trigger='daily_safety',tasks=[o])
 result=current_view(s,datetime(2026,10,11,7,6,tzinfo=SH)).tasks[0]
 assert result.state==state

def test_startup_refuses_missing_verification_and_storage():
 with pytest.raises(ValidationError):Settings(mode='demo',jwt_verify_key='short')
 with pytest.raises(ValidationError):Settings(jwt_verify_key=KEY)

@pytest.mark.parametrize('claims,expected', [({},200),({'roles':['DEPT_ADMIN']},403),({'roles':['CMC_USP_MANAGER'],'username':'admin'},403),({'must_change_password':True},403),({'type':'refresh'},401),({'exp':1},401),({'roles':'SYS_ADMIN'},401)])
def test_all_business_routes_guarded(claims,expected):
 with TestClient(create_app(config(),MemoryStore())) as c:
  for url in ['/api/v1/overview','/api/v1/tasks','/api/v1/tasks/rd-lims']:
   res=c.get(url,headers={'Authorization':'Bearer '+token(**claims)})
   assert res.status_code==expected
  if expected!=200:
   res=c.post('/api/v1/refresh',headers={'Authorization':'Bearer '+token(**claims)})
   assert res.status_code==expected

def test_no_token_forged_key_and_unknown_task():
 store=MemoryStore()
 with TestClient(create_app(config(),store)) as c:
  assert c.get('/api/v1/health').json()=={'alive':True}
  assert c.get('/api/v1/overview').status_code==401
  forged=jwt.encode(dict(sub='1',exp=2000000000,type='access',roles=['SYS_ADMIN'],must_change_password=False),'other-isolated-fake-signing-key-32bytes',algorithm='HS256')
  assert c.get('/api/v1/overview',headers={'Authorization':'Bearer '+forged}).status_code==401
  assert c.get('/api/v1/tasks/nonexistent',headers={'Authorization':'Bearer '+token()}).status_code==404
  assert c.get('/api/v1/overview?snapshot_id=missing',headers={'Authorization':'Bearer '+token()}).status_code==410
 assert any(x['result']==401 for x in store.audits)

def test_uncollected_is_unknown_and_audit_failure_closed(tmp_path):
 class BrokenAudit(MemoryStore):
  async def audit(self,entry):raise RuntimeError('store failed')
 with TestClient(create_app(config(),MemoryStore())) as c:
  d=c.get('/api/v1/overview',headers={'Authorization':'Bearer '+token()}).json()
  assert all(x['state']=='unknown' for x in d['tasks'])
 with TestClient(create_app(config(audit_fallback_path=tmp_path/'audit.jsonl'),BrokenAudit())) as c:
  assert c.get('/api/v1/overview',headers={'Authorization':'Bearer '+token()}).status_code==503
 assert 'Bearer' not in (tmp_path/'audit.jsonl').read_text()

def test_redaction():
 output=redact('postgresql://user:private@host/db password=private Bearer private')
 assert 'private' not in output

async def test_event_duplicates_late_events_and_recovery():
 store=MemoryStore();arrived=asyncio.Event();resume=asyncio.Event()
 class Reader:
  async def read(self,*args):arrived.set();await resume.wait();return [run()],[]
 engine=Engine(config(),[task(times=[])],store,Reader());coordinator=Coordinator(engine)
 first=await store.enqueue({'trigger':'event','task_key':'example'},'first')
 assert await store.enqueue({'trigger':'event','task_key':'example'},'first')==first
 running=asyncio.create_task(coordinator.run_once());await arrived.wait()
 late=await store.enqueue({'trigger':'event','task_key':'example'},'late')
 resume.set();await running
 assert (await store.get_update(first))['status']=='done'
 assert (await store.get_update(late))['status']=='pending'
 await coordinator.run_once()
 assert len(store.runs)==1 and len(store.snapshots)==2
 interrupted=await store.enqueue({'trigger':'event'},'interrupted');await store.claim();await store.recover()
 assert (await store.get_update(interrupted))['status']=='pending'

async def test_daily_0700_boundary_and_restart_deduplication():
 store=MemoryStore();engine=Engine(config(),[],store,None);coordinator=Coordinator(engine)
 await coordinator.safety_tick(datetime(2026,10,10,6,59,tzinfo=SH))
 assert not store.updates
 await coordinator.safety_tick(datetime(2026,10,10,7,tzinfo=SH))
 await coordinator.safety_tick(datetime(2026,10,10,8,tzinfo=SH))
 assert len(store.updates)==1

async def test_source_timeout_isolated():
 class Reader:
  async def read(self,t,*args):
   if t.key=='stuck':await asyncio.sleep(3)
   return [run()],[]
 store=MemoryStore();engine=Engine(config(),[task(times=[]),task(key='stuck',times=[])],store,Reader())
 s=await engine.collect()
 assert s.tasks[0].state=='success' and s.tasks[1].state=='unknown'


def test_reader_requires_no_api_or_writer_secret_but_cannot_be_an_api():
 settings=Settings(_env_file=None,component='reader')
 assert settings.jwt_verify_key is None and settings.database_url is None
 with pytest.raises(RuntimeError,match='独立鉴权'):create_app(settings,MemoryStore())

async def test_source_subprocess_does_not_receive_api_or_writer_credentials(monkeypatch):
 from app.engine import WorkerReader
 captured={}
 class Process:
  returncode=0
  async def communicate(self):return b'{"runs":[],"gaps":[]}',b''
 async def spawn(*args,**kwargs):captured.update(kwargs['env']);return Process()
 monkeypatch.setenv('OPS_JWT_VERIFY_KEY',KEY)
 monkeypatch.setenv('OPS_DATABASE_URL','private-writer-url')
 monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
 await WorkerReader(config()).read(task(),NOW-timedelta(days=1),NOW)
 assert 'OPS_JWT_VERIFY_KEY' not in captured and 'OPS_DATABASE_URL' not in captured and captured['OPS_COMPONENT']=='reader'

async def test_worker_concurrency_is_bounded_without_queue_timeout():
 active=0;peak=0
 class Reader:
  async def read(self,t,*args):
   nonlocal active,peak
   active+=1;peak=max(peak,active)
   await asyncio.sleep(.02)
   active-=1
   return [],[]
 store=MemoryStore()
 await Engine(config(),[task(key=str(i),times=[]) for i in range(6)],store,Reader()).collect()
 assert peak==2

async def test_no_inferred_missed_history_before_monitor_start():
 class Reader:
  async def read(self,*args):return [],[]
 store=MemoryStore()
 await Engine(config(),[task()],store,Reader()).collect()
 assert not store.runs
 first=await store.monitoring_started_at()
 old=Run(id='legacy-inference',task_key='example',start=first-timedelta(days=1),status='failed',source_kind='schedule')
 actual=old.model_copy(update={'id':'actual-source','source_kind':'etl_run'})
 store.versions.extend([(first,old),(first,actual)])
 rows,total=await store.history('example',first-timedelta(days=2),first+timedelta(seconds=1))
 assert total==1 and rows[0].id=='actual-source'
