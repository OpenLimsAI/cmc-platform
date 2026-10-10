from datetime import timedelta
from types import SimpleNamespace
import json
import os
import pytest
from app.sources import Reader,checksum_summary,journal_summary,evidence
from app.domain import Run,Snapshot,assess
from app.store import MemoryStore
from test_monitor import NOW,run,task,config,token
from app.api import create_app
from fastapi.testclient import TestClient


def test_checksum_is_scoped_and_empty_is_not_verified():
 assert checksum_summary('match_status\nMatch\nMATCH\nMismatch\n?\n')=={'rows':4,'match':2,'mismatch':1,'unknown':1}
 assert checksum_summary('match_status\n')['rows']==0


def test_journal_export_excludes_business_payload_and_credentials():
 s=journal_summary(['sample_id=secret raw payload','postgresql://private','<<< [night] flex2 完成', 'unit-test.service: Deactivated successfully.'])
 assert 'secret' not in s and 'private' not in s and 'flex2 完成' in s


def test_heartbeat_from_other_shift_cannot_prove_integrity(tmp_path):
 reader=Reader(config());r=run();r.evidence=[evidence('journal','example.service','<<< [night] flex2 完成\n<<< [night] vicell 完成')]
 (tmp_path/'State').mkdir()
 for machine in ('T281240040C_Nova','C4V61257XH_ViCell'):
  (tmp_path/'State'/f'{machine}_heartbeat.json').write_text(json.dumps({'last_run_time':(r.start-timedelta(days=1)).isoformat(),'last_run_finished':(r.finish-timedelta(days=1)).isoformat(),'backup_status':'SUCCESS'}))
 reader.instrument_evidence(r,tmp_path)
 assert r.status=='success' and r.integrity is None and '其他批次' in r.message


def test_matched_checksum_mismatch_overrides_exit_zero(tmp_path):
 reader=Reader(config());r=run();r.evidence=[evidence('journal','example.service','<<< [night] flex2 完成\n<<< [night] vicell 完成')]
 (tmp_path/'State').mkdir()
 for machine in ('T281240040C_Nova','C4V61257XH_ViCell'):
  (tmp_path/'State'/f'{machine}_heartbeat.json').write_text(json.dumps({'last_run_time':r.start.isoformat(),'last_run_finished':r.finish.isoformat(),'backup_status':'SUCCESS','files_failed':0}))
  folder=tmp_path/'Checksums'/machine;folder.mkdir(parents=True)
  report=folder/'test_SHA256_Compare.csv';report.write_text('Relative_Path,match_status\nPRIVATE,Mismatch\n');os.utime(report,(r.finish.timestamp(),r.finish.timestamp()))
 reader.instrument_evidence(r,tmp_path)
 assert r.status=='failed'
 assert 'PRIVATE' not in json.dumps(r.evidence)


async def test_history_does_not_acquire_future_terminal_results():
 store=MemoryStore();unfinished=run('running');s1=Snapshot(id='first',collected_at=NOW,trigger='manual',tasks=[assess(task(),[unfinished],NOW)])
 await store.publish(s1,[unfinished],[])
 finished=unfinished.model_copy(deep=True);finished.finish=NOW+timedelta(minutes=1);finished.status='success';finished.children=[{'name':'future','status':'success'}]
 s2=s1.model_copy(update={'id':'second','collected_at':NOW+timedelta(minutes=2)})
 await store.publish(s2,[finished],[])
 old,_=await store.history('example',NOW-timedelta(days=1),NOW+timedelta(microseconds=1))
 new,_=await store.history('example',NOW-timedelta(days=1),NOW+timedelta(minutes=3))
 assert old[0].status=='running' and old[0].children==[] and new[0].status=='success'


def test_pending_update_masks_current_green_but_not_historical_view():
 store=MemoryStore();s=Snapshot(id='first',collected_at=NOW,trigger='manual',mode='demo',tasks=[assess(task(key='rd-lims'),[run()],NOW)])
 import asyncio
 asyncio.run(store.publish(s,[],[]));asyncio.run(store.enqueue({'trigger':'manual'}))
 with TestClient(create_app(config(),store)) as client:
  headers={'Authorization':'Bearer '+token()}
  assert client.get('/api/v1/overview',headers=headers).json()['tasks'][0]['state']=='unknown'
  assert client.get('/api/v1/overview?snapshot_id=first',headers=headers).json()['tasks'][0]['state']=='success'


async def test_missing_raw_or_stage_cannot_show_success(monkeypatch):
 from app import sources
 async def fake(*args):
  if args[-1]=='--property=ExecStart':return 'ExecStart={ path=/run/raw ; }'
  return 'LoadState=loaded\nActiveState=active\nResult=success\nTimersCalendar={ OnCalendar=*-*-* 04:00:00 ; }'
 monkeypatch.setattr(sources,'command',fake)
 with pytest.raises(ValueError,match='两步骤'):await Reader(config()).systemd(task(unit='test.service',timer='test.timer',ledger='nova'),NOW-timedelta(days=7),NOW)

async def test_missed_windows_remain_in_history_after_later_success():
 from app.engine import Engine
 class Reader:
  async def read(self,t,*args):return [run(start=NOW-timedelta(hours=1))],[]
 store=MemoryStore()
 # Reader is isolated synthetic evidence. A scheduled slot must be preserved as a separate reference.
 t=task(times=['00:00'])
 await Engine(config(),[t],store,Reader()).collect()
 assert any(r.source_kind=='schedule' and r.status=='failed' for r in store.runs.values())

async def test_failed_source_cannot_manufacture_missed_windows():
 from app.engine import Engine
 class Reader:
  async def read(self,*args):raise PermissionError()
 store=MemoryStore();s=await Engine(config(),[task()],store,Reader()).collect()
 assert not store.runs and s.tasks[0].state=='unknown'


def test_notification_failure_never_changes_original_exit(tmp_path):
 import subprocess
 snippet=(__import__('pathlib').Path(__file__).resolve().parents[2]/'integration/notifications/cron-exit-trap.sh.example').read_text()
 # Replace only the notifier with a failing stub. Do not execute any real task.
 trap=next(x for x in snippet.splitlines() if x.startswith('trap ')).replace('/usr/bin/python3 /opt/cmc-platform-monitor/scripts/notify_completion.py --task lucullus','false')
 assert subprocess.run(['bash','-c',trap+'\nexit 7'],capture_output=True).returncode==7

async def test_receiver_rejects_unregistered_uid_and_result_claim(monkeypatch):
 import socket,struct
 from app import receiver
 class Sock:
  def getsockopt(self,*args):return struct.pack('3i',42,501,20)
 class Writer:
  def __init__(self):self.data=b''
  def get_extra_info(self,name):return Sock()
  def write(self,data):self.data+=data
  async def drain(self):pass
  def close(self):pass
  async def wait_closed(self):pass
 class Input:
  async def readline(self):return b'{"event_id":"e1","task_key":"example"}\n'
 monkeypatch.setattr(socket,'SO_PEERCRED',17,raising=False)
 monkeypatch.setattr(receiver.pwd,'getpwuid',lambda uid:SimpleNamespace(pw_name='intruder'))
 store=MemoryStore();w=Writer();await receiver.receive(Input(),w,{'example':task(producer_users=['prometheus'])},store)
 assert b'false' in w.data and not store.updates


def test_cron_export_is_metadata_only_and_detects_duplicate_or_disabled_plan():
 import importlib.util
 from pathlib import Path
 spec=importlib.util.spec_from_file_location('cron_export',Path(__file__).resolve().parents[2]/'scripts/export_cron_schedule.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 result=module.parse('0 1 * * * /opt/rd-lucullus-etl/run_lucullus_pipeline.sh > /secret\n# 0 8 * * * /opt/rd-lims-etl/scripts/run_etl.sh\n0 0 * * * /opt/old/scripts/training_db_reset.sh')
 assert result['lucullus']=={'enabled':True,'times':['01:00']}
 assert result['rd-lims']['enabled'] is False and result['training-sync']['enabled'] is False
 assert 'secret' not in json.dumps(result)
 duplicate='0 1 * * * /opt/rd-lucullus-etl/run_lucullus_pipeline.sh\n'*2
 assert module.parse(duplicate)['lucullus']['times'] is None

async def test_journal_pagination_and_manager_start_are_correlated(monkeypatch):
 from app import sources
 t=task(unit='test.service',timer='test.timer',times=['04:00'])
 entries=[{'_PID':'1','MESSAGE':'Starting test.service','INVOCATION_ID':'source-one','__REALTIME_TIMESTAMP':str(int(run().start.timestamp()*1e6)),'__CURSOR':'first'},
          {'_PID':'1','MESSAGE':'test.service: Deactivated successfully.','INVOCATION_ID':'source-one','__REALTIME_TIMESTAMP':str(int(run().finish.timestamp()*1e6)),'__CURSOR':'last'}]
 async def fake(*args):
  if args[0]=='journalctl':return '\n'.join(json.dumps(e) for e in entries)
  return 'LoadState=loaded\nActiveState=active\nTimersCalendar={ OnCalendar=*-*-* 04:00:00 ; }'
 monkeypatch.setattr(sources,'command',fake)
 rows=await Reader(config()).systemd(t,NOW-timedelta(days=7),NOW)
 assert rows[0].start==run().start and rows[0].status=='success'

async def test_changed_timer_plan_is_unknown_not_old_success(monkeypatch):
 from app import sources
 async def fake(*args):return 'LoadState=loaded\nActiveState=active\nTimersCalendar={ OnCalendar=*-*-* 09:00:00 ; }'
 monkeypatch.setattr(sources,'command',fake)
 with pytest.raises(ValueError,match='计划发生变化'):
  await Reader(config()).systemd(task(unit='test.service',timer='test.timer'),NOW-timedelta(days=7),NOW)

@pytest.mark.parametrize('parent_status,rows,expected',[('failed',[{'id':1,'status':'partial','files_errored':0}],'failed'),('running',[],'running')])
async def test_parent_failure_is_not_downgraded_and_unfinished_is_not_completed(monkeypatch,parent_status,rows,expected):
 from app import sources
 r=run(parent_status)
 async def fake_command(*args):return 'Asia/Shanghai'
 monkeypatch.setattr(sources,'command',fake_command)
 reader=Reader(config())
 async def fake_systemd(*args):return [r]
 async def fake_ledger(*args):return [row|{'start':r.start,'finish':r.finish} for row in rows]
 monkeypatch.setattr(reader,'systemd',fake_systemd);monkeypatch.setattr(reader,'ledger',fake_ledger)
 t=task(adapter='systemd',db_source='rd',ledger='nova')
 result,_=await reader.read(t,NOW-timedelta(days=7),NOW)
 assert result[0].status==expected


def test_every_evidence_history_update_route_requires_backend_role():
 with TestClient(create_app(config(),MemoryStore())) as client:
  for route in ('/api/v1/tasks/rd-lims/runs?snapshot_id=s','/api/v1/tasks/rd-lims/evidence?evidence_id='+'a'*24+'&snapshot_id=s','/api/v1/updates/example'):
   assert client.get(route).status_code==401
   assert client.get(route,headers={'Authorization':'Bearer '+token(roles=['DEPT_ADMIN'])}).status_code==403

async def test_unreadable_log_directory_is_unknown_not_confirmed_missed(tmp_path):
 with pytest.raises(ValueError,match='目录不可读'):
  await Reader(config()).log_runs(task(adapter='training',log_dir=str(tmp_path/'does-not-exist')),NOW-timedelta(days=7),NOW)
