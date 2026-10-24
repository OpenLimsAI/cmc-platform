import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from uuid import uuid4
from .domain import UTC, SH, Snapshot, Run, assess
from .archive import device_runs,PARENTS

class WorkerReader:
    def __init__(self,settings):self.settings=settings
    async def read(self,task,since,now):
        if task.enabled is False:return [],[]
        if task.adapter=='unconnected':return [],['来源未接入，实际计划/开关未核实']
        # Set inherited validated config without exposing it in argv or logs.
        env=dict(os.environ)
        env.pop('OPS_JWT_VERIFY_KEY',None);env.pop('OPS_DATABASE_URL',None)
        for key,value in self.settings.model_dump().items():
            if key in ('jwt_verify_key','database_url','component'):continue
            if value is None:continue
            env['OPS_'+key.upper()]=value.get_secret_value() if hasattr(value,'get_secret_value') else str(value)
        env['OPS_COMPONENT']='reader'
        p=await asyncio.create_subprocess_exec(sys.executable,'-m','app.source_worker',task.key,since.isoformat(),now.isoformat(),
                                               env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:
            out,_=await p.communicate()
            if p.returncode or len(out)>4_000_000:raise ValueError('source output unavailable/truncated')
            payload=json.loads(out)
            return [Run.model_validate(x) for x in payload['runs']],payload['gaps']
        except BaseException:
            if p.returncode is None:
                p.kill()
                try:await asyncio.wait_for(p.wait(),1)
                except TimeoutError:pass
            raise

class Engine:
    def __init__(self,settings,tasks,store,reader):
        self.settings=settings;self.tasks=tasks;self.store=store;self.reader=reader;self.lock=asyncio.Lock()
    async def collect(self,trigger='manual',ids=None):
        async with self.lock:
            now=datetime.now(UTC)
            prev=await self.store.latest()
            since=now-timedelta(days=self.settings.history_days)
            backfill_gap=False
            if prev and prev.collected_at<since:
                since=max(prev.collected_at-timedelta(minutes=5),now-timedelta(days=31))
                backfill_gap=prev.collected_at<since
            observations=[];all_runs=[]
            # Bound worker startup CPU; queueing does not consume a source's deadline.
            readers=asyncio.Semaphore(2)
            schedule_floor=max(since,await self.store.monitoring_started_at() or now)
            async def read(task):
                try:
                    async with readers:
                        runs,gaps=await asyncio.wait_for(self.reader.read(task,since,now),self.settings.source_timeout)
                except Exception:
                    runs=[];gaps=['采集失败、超时或证据不足；当前未核实']
                await self.store.audit({'action':'source_read','task_key':task.key,'from':since.isoformat(),'until':now.isoformat(),
                                        'returned_rows':len(runs),'result':'unknown' if gaps else 'ok'})
                if not gaps and task.enabled is True:
                    for planned in task.occurrences(now,(now-since).days):
                        grace=timedelta(minutes=task.grace_minutes)
                        if schedule_floor<=planned and planned+grace<now and not any(planned<=r.start<=planned+grace for r in runs):
                            runs.append(Run(id=f'{task.key}:schedule:{planned.isoformat()}',task_key=task.key,start=planned,
                                            status='failed',message='该计划窗口无启动证据（来源有界读取完成）；不是实际启动时间',source_kind='schedule'))
                # Retain last known result, explicitly unknown, after any source failure.
                if gaps and not runs and prev:
                    old=next((x for x in prev.tasks if x.task.key==task.key),None)
                    if old and old.last_run:runs=[old.last_run]
                if backfill_gap:gaps.append('监控中断超31天，较早执行未覆盖')
                return assess(task,runs,datetime.now(UTC),gaps), runs
            results=await asyncio.wait_for(asyncio.gather(*(read(t) for t in self.tasks if not t.archive_device)),self.settings.batch_timeout)
            for obs,runs in results:observations.append(obs);all_runs.extend(runs)
            for task in self.tasks:
                if not task.archive_device:continue
                parents=[r for r in all_runs if r.task_key in PARENTS]
                runs=device_runs(task,parents)
                gaps=[f'{o.task.name}: {g}' for o in observations if o.task.key in PARENTS for g in o.gaps]
                if gaps and not runs and prev:
                    old=next((o for o in prev.tasks if o.task.key==task.key),None)
                    if old and old.last_run:runs=[old.last_run]
                observations.append(assess(task,runs,datetime.now(UTC),gaps));all_runs.extend(runs)
            for obs in observations:
                if obs.task.key not in ('vicell','nova') or not obs.last_run or obs.state not in ('success','warning'):continue
                archive_key={'vicell':'ingest-vicell','nova':'ingest-nova'}[obs.task.key]
                upstream=[r for r in all_runs if r.task_key==archive_key and r.start<=obs.last_run.start]
                parent=max(upstream,key=lambda r:r.start,default=None)
                if parent and (parent.status!='success' or parent.integrity not in ('scope_verified','no_changed_files') or not parent.finish or parent.finish>obs.last_run.start):
                    obs.state='warning';obs.label='执行完成，上游归档有风险';obs.reasons.append('本次ETL之前最近归档失败、未结束或证据不足；ETL成功不证明已取得新文件')
            snap=Snapshot(id=str(uuid4()),collected_at=datetime.now(UTC),trigger=trigger,tasks=observations,mode=self.settings.mode,
                          gaps=['外部来源未全部接入；覆盖以登记清单及各源截至时间为准'])
            await self.store.publish(snap,all_runs,ids or [])
            if 'daily_safety' in trigger:await self.store.prune()
            return snap

class Coordinator:
    """One collector process; event IDs received during collection remain pending."""
    def __init__(self,engine):self.engine=engine;self.stopping=asyncio.Event();self.last_safety_day=None
    async def run_once(self):
        rows=await self.engine.store.claim()
        if not rows:return False
        ids=[x['id'] for x in rows]
        trigger=','.join(sorted({x['payload'].get('trigger','event') for x in rows}))
        try:
            if 'event' in trigger:await asyncio.sleep(self.engine.settings.coalesce_seconds)
            await self.engine.collect(trigger,ids)
        except Exception:
            await self.engine.store.requeue(ids)
            return False
        return True
    async def safety_tick(self,now):
        local=now.astimezone(SH)
        if local.hour>=7 and self.last_safety_day!=local.date():
            await self.engine.store.enqueue({'trigger':'daily_safety'},'daily:'+local.date().isoformat())
            self.last_safety_day=local.date()

    async def run(self):
        store=self.engine.store
        await store.recover()
        await store.enqueue({'trigger':'startup'})
        while not self.stopping.is_set():
            await self.safety_tick(datetime.now(UTC))
            if await self.run_once():continue
            try:await asyncio.wait_for(self.stopping.wait(),max(1,self.engine.settings.coalesce_seconds))
            except TimeoutError:pass
