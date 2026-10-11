"""Bounded, fixed-source readers. No shell, ETL import, source writes or backup execution."""
import asyncio
import hashlib
import csv
import io
import math
import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from .domain import Task, Run, UTC, SH
from .security import redact

PAGE=500
MAX_LOG_BYTES=65536
MAX_PIPELINE_BYTES=2_000_000
LUC_STEPS={'[ws01] 参考表全量同步','[ws01] 每日曲线增量同步','[ws02] 参考表全量同步','[ws02] 每日曲线增量同步','批次维度构建 (stg_batch)','工艺按天聚合 (stg_process_daily)'}
LUC_PAIRS={(j,i) for j in ('lucullus_sync_reference','lucullus_daily_sync') for i in ('rd_ws01_usp_lucullus_01','rd_ws02_usp_lucullus_01')} | {('lucullus_build_batch_dim',None)}

def journal_summary(messages):
    # Raw program output may contain sample identities/SQL. Export fixed lifecycle markers only.
    safe=[]
    for message in messages:
        if re.match(r'^[a-z0-9-]+\.service: (Deactivated successfully|Failed with result|Main process exited)',message) or message.startswith(('Finished ','Failed to start ','Starting ')):
            safe.append(message)
        marker=re.search(r'(>>>|<<<) \[(day|night)\] (?:开始采集 )?(flex2|vicell)(?: 完成| 失败，退出码 \d+)?',message)
        if marker:safe.append(marker[0])
    return '\n'.join(safe[-100:])

def checksum_summary(content):
    rows=list(csv.DictReader(io.StringIO(content)))
    counts={}
    for row in rows:
        value=str(row.get('match_status','')).upper()
        counts[value]=counts.get(value,0)+1
    return {'rows':len(rows),'match':counts.get('MATCH',0),'mismatch':counts.get('MISMATCH',0),'unknown':sum(n for k,n in counts.items() if k not in ('MATCH','MISMATCH'))}

def dt(value, naive_zone=SH):
    if value is None: return None
    if isinstance(value, datetime): return value.replace(tzinfo=naive_zone) if value.tzinfo is None else value
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return parsed.replace(tzinfo=naive_zone) if parsed.tzinfo is None else parsed
    except ValueError: return None

def status(value):
    return {'success':'success','completed':'success','partial':'partial_failed','partial_failed':'partial_failed',
            'failed':'failed','failure':'failed','error':'failed','running':'running','started':'running'}.get(str(value).lower(),'unknown')

def evidence(kind, locator, excerpt):
    safe=redact(excerpt)
    eid=hashlib.sha256((kind+locator+safe).encode()).hexdigest()[:24]
    return {'id':eid,'kind':kind,'ref':Path(locator).name if kind=='log' else locator,'excerpt':safe}

async def command(*args):
    process=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
                                               env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TZ':'Asia/Shanghai'})
    try:
        out,err=await process.communicate()
        if len(out)>2_000_000: raise ValueError('source output truncated')
        if process.returncode: raise ValueError('source unavailable')
        return out.decode('utf-8',errors='replace')
    except BaseException:
        if process.returncode is None:
            process.kill(); await process.wait()
        raise

class Reader:
    def __init__(self, settings):
        self.settings=settings; self.engines={}
        for key,secret in [('rd',settings.rd_read_url),('gmp',settings.gmp_read_url)]:
            if secret:
                self.engines[key]=create_async_engine(secret.get_secret_value(),pool_pre_ping=True,
                    connect_args={'timeout':settings.source_timeout,'command_timeout':settings.source_timeout})
    async def close(self):
        for engine in self.engines.values(): await engine.dispose()
    async def journal(self,unit,since,now,cursor=None):
        if self.settings.journal_socket_path:
            reader,writer=await asyncio.open_unix_connection(str(self.settings.journal_socket_path),limit=2_000_001)
            try:
                writer.write(json.dumps({'unit':unit,'since':since.isoformat(),'until':now.isoformat(),'cursor':cursor}).encode()+b'\n')
                await writer.drain()
                payload=json.loads(await asyncio.wait_for(reader.readline(),self.settings.source_timeout))
                if not payload.get('ok'):raise ValueError('restricted journal unavailable')
                return payload['data']
            finally:
                writer.close();await writer.wait_closed()
        args=['journalctl','--unit',unit,'--since',since.isoformat(),'--until',now.isoformat(),
              '--output=json','--output-fields=MESSAGE,_PID,SYSLOG_IDENTIFIER,_SYSTEMD_INVOCATION_ID,INVOCATION_ID,UNIT',
              '--grep=^(Starting |Started |Finished |Failed to start|.*\\.service: (Deactivated successfully|Failed with result|Main process exited)|>>> \\[|<<< \\[)',
              '--no-pager','--lines=+500']
        if cursor:args.append('--after-cursor='+cursor)
        return await command(*args)
    async def ledger(self,task,since,now):
        if task.db_source not in self.engines: raise ValueError('运维台账只读连接尚未配置')
        records=[]; cursor=0
        if task.ledger=='meta':
            sql="""SELECT run_id AS id,job_name,source_instance,run_started_at AS start,run_finished_at AS finish,status,
            rows_written AS rows,rows_errored FROM meta.etl_run
            WHERE job_name=ANY(CAST(:jobs AS text[])) AND run_id>:cursor
            AND (run_started_at>=:since OR (run_finished_at IS NULL AND lower(status)='running'))
            ORDER BY run_id LIMIT 500"""
        else:
            table={'vicell':'raw_rd_usp_vicell.etl_log','nova':'raw_rd_usp_nova.etl_log'}[task.ledger]
            extra=',rows_conflict,rows_unresolved' if task.ledger=='nova' else ''
            sql=f"""SELECT id,run_started_at AS start,run_finished_at AS finish,status,files_loaded AS files,files_errored,watermark_before,watermark_after{extra}
            FROM {table} WHERE id>:cursor AND (run_started_at>=:since OR (run_finished_at IS NULL AND lower(status)='running'))
            ORDER BY id LIMIT 500"""
        params={'jobs':task.jobs,'since':since.astimezone(SH).replace(tzinfo=None) if task.db_source=='gmp' else since,'cursor':cursor}
        async with self.engines[task.db_source].connect() as conn:
            async with conn.begin():
                await conn.execute(text('SET TRANSACTION READ ONLY'))
                await conn.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                for page in range(self.settings.max_pages):
                    params['cursor']=cursor
                    rows=(await conn.execute(text(sql),params)).mappings().all()
                    records.extend(dict(r) for r in rows)
                    if len(rows)<PAGE: break
                    cursor=rows[-1]['id']
                else: raise ValueError('运行台账超出有界分页范围，历史覆盖不全')
                if task.ledger=='meta' and records:
                    ids=[r['id'] for r in records]
                    counts=(await conn.execute(text("""SELECT run_id,error_type,count(*) AS count FROM meta.load_error_log
                    WHERE run_id=ANY(CAST(:ids AS bigint[])) GROUP BY run_id,error_type LIMIT 500"""),{'ids':ids})).mappings().all()
                    if len(counts)>=500: raise ValueError('错误摘要读取截断')
                    for r in records:
                        r['validation_count']=sum(x['count'] for x in counts if x['run_id']==r['id'] and str(x['error_type']).upper()=='VALIDATION')
                    watermarks=(await conn.execute(text("""SELECT job_name,source_instance,target_table,last_success_ts,last_run_id,updated_at
                    FROM meta.etl_watermark WHERE job_name=ANY(CAST(:jobs AS text[])) LIMIT 501"""),{'jobs':task.jobs})).mappings().all()
                    if len(watermarks)>500:raise ValueError('水位摘要读取截断')
                    for r in records:
                        r['watermarks']=[{'target_table':w['target_table'],'last_success_ts':str(w['last_success_ts']),'updated_at':str(w['updated_at'])}
                                         for w in watermarks if w['last_run_id']==r['id'] and w['job_name']==r['job_name'] and w['source_instance']==r['source_instance']]
        return records
    async def systemd(self,task,since,now):
        unit=task.unit
        # All units originate in the versioned manifest, never request parameters.
        if not unit or not re.fullmatch(r'[a-z0-9-]+\.service',unit): raise ValueError('任务单元未登记')
        props=await command('systemctl','show',unit,'--property=LoadState,ActiveState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp,InvocationID')
        data=dict(line.split('=',1) for line in props.splitlines() if '=' in line)
        if data.get('LoadState')!='loaded': raise ValueError('任务单元未加载或读取不到')
        if task.ledger in ('vicell','nova'):
            starts=await command('systemctl','show',unit,'--property=ExecStart')
            if starts.count('path=')!=2:raise ValueError('raw与stage两步骤入口发生变化，需重新核实')
        timer=await command('systemctl','show',task.timer,'--property=LoadState,ActiveState,UnitFileState,TimersCalendar') if task.timer else ''
        timer_data=dict(line.split('=',1) for line in timer.splitlines() if '=' in line)
        if task.timer and (timer_data.get('LoadState')!='loaded' or timer_data.get('ActiveState')!='active'):
            raise ValueError('登记的timer未启用或状态未核实')
        calendars=re.findall(r'OnCalendar=([^;]+)',timer)
        actual={m[1] for c in calendars if (m:=re.search(r'\*-\*-\* (\d\d:\d\d):00(?: Asia/Shanghai)?\s*$',c))}
        if not calendars or len(actual)!=len(calendars) or actual!=set(task.times):raise ValueError('timer计划发生变化或未取得完整日历，需核实')
        entries=[];cursor=None
        for page in range(self.settings.max_pages):
            raw=await self.journal(unit,since,now,cursor)
            rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
            entries.extend(rows)
            if len(rows)<500:break
            next_cursor=rows[-1].get('__CURSOR')
            if not next_cursor or next_cursor==cursor:raise ValueError('journal游标无法推进')
            cursor=next_cursor
        else:raise ValueError('journal读取超出有界分页范围')
        groups={};pending_start=None
        # Manager messages carry UNIT/INVOCATION_ID; process output uses _SYSTEMD_INVOCATION_ID.
        for e in entries:
            i=e.get('_SYSTEMD_INVOCATION_ID') or e.get('INVOCATION_ID')
            if str(e.get('MESSAGE','')).startswith('Starting '):pending_start=e
            if i:
                if i not in groups:
                    groups[i]=[pending_start] if pending_start else []
                    pending_start=None
                if e not in groups[i]:groups[i].append(e)
        runs=[]
        for i,items in groups.items():
            items.sort(key=lambda e:int(e['__REALTIME_TIMESTAMP']))
            start=datetime.fromtimestamp(int(items[0]['__REALTIME_TIMESTAMP'])/1e6,UTC)
            if data.get('InvocationID')==i:
                stamp=re.search(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d',data.get('ExecMainStartTimestamp',''))
                if stamp:start=min(start,dt(stamp[0]).astimezone(UTC))
            finish=None; result='running'
            messages=[str(e.get('MESSAGE','')) for e in items]
            has_start=any(m.startswith(('Starting ','Started ')) for m in messages) or bool(data.get('InvocationID')==i and stamp)
            # Only systemd manager terminal evidence decides whole service completion.
            for e in items:
                msg=str(e.get('MESSAGE',''))
                if e.get('_PID')=='1' or e.get('SYSLOG_IDENTIFIER')=='systemd':
                    if re.search(r'(Failed with result|Failed to start|Main process exited)',msg):
                        result='failed'; finish=datetime.fromtimestamp(int(e['__REALTIME_TIMESTAMP'])/1e6,UTC)
                    elif re.search(r'(Finished |Deactivated successfully)',msg):
                        if result!='failed': result='success'
                        finish=datetime.fromtimestamp(int(e['__REALTIME_TIMESTAMP'])/1e6,UTC)
            if start < since: continue
            if not has_start:result='unknown'
            excerpt=journal_summary(messages)
            runs.append(Run(id=f'{task.key}:unit:{i}',task_key=task.key,start=start,finish=finish,status=result,
                            source_kind='systemd',evidence=[evidence('journal',unit,excerpt)]))
        if not runs:
            # Without invocation history do not use "inactive"/Result=success as a success record.
            raise ValueError('缺少可关联的完整systemd执行记录（可能权限不足）')
        return runs
    async def log_runs(self,task,since,now):
        path=Path(task.log_dir)
        if not path.is_dir() or not os.access(path,os.R_OK|os.X_OK):raise ValueError('父日志目录不可读或未配置')
        if task.adapter=='lucullus' and since<now-timedelta(days=30):raise ValueError('回溯窗口超出已知父日志保留范围')
        paths=sorted(path.glob(task.log_pattern),key=lambda p:p.stat().st_mtime)
        if len(paths)>100: raise ValueError('日志文件数量超出读取上限')
        runs=[]
        for p in paths:
            if p.is_symlink() or not p.is_file(): continue
            if p.stat().st_mtime < since.timestamp(): continue
            with p.open('rb') as f:
                size=p.stat().st_size
                # Lucullus needs the opening and all six terminal markers; truncation is unknown.
                budget=MAX_PIPELINE_BYTES if task.adapter=='lucullus' else MAX_LOG_BYTES
                if size>budget and task.adapter=='lucullus': raise ValueError('父日志超出读取预算，步骤覆盖不全')
                f.seek(max(0,size-budget)); content=f.read(budget).decode('utf-8',errors='replace')
            if task.adapter=='training' and size>budget:
                first=re.search(r'== (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) 开始重置',content)
                if not first or dt(first[1])>since:raise ValueError('训练日志截断，所需历史窗口覆盖不全')
            if task.adapter=='lucullus':
                a=re.search(r'\[(.*?)\] === Lucullus 管道开始.*dry_run=0',content)
                b=re.search(r'\[(.*?)\] === 管道结束 \| 失败步骤数=(\d+)',content)
                if not a: continue
                result='failed' if b and int(b[2]) else 'success' if b else 'running'
                children=[{'name':x,'status':'success'} for x in re.findall(r'✓ 完成: (.+)',content)]
                if result=='success' and (len(children)!=6 or {x['name'] for x in children}!=LUC_STEPS): result='unknown'
                start=dt(a[1]); finish=dt(b[1]) if b else None
                ident=f'{task.key}:log:{p.name}'
                runs.append(Run(id=ident,task_key=task.key,start=start,finish=finish,status=result,children=children,
                                source_kind='log',evidence=[evidence('log',str(p),'\n'.join(x for x in content.splitlines() if re.match(r'^\[.*?\] (===|✓ 完成:|✗ 失败\(rc=)',x)))]))
            else:
                # Reset log contains many days. Pair every start with its own next terminal result.
                lines=content.splitlines(); active=None
                for line in lines:
                    a=re.search(r'== (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) 开始重置',line)
                    if a:
                        if active: runs.append(active)
                        start=dt(a[1]); active=Run(id=f'{task.key}:log:{start.isoformat()}',task_key=task.key,start=start,status='running',source_kind='log')
                    elif active and (('完成：' in line) or ('失败：' in line) or ('放弃本次重置' in line)):
                        timestamp=re.search(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d',line)
                        if not timestamp:
                            active.status='unknown'
                        else:
                            active.finish=dt(timestamp[0]);active.status='success' if '完成：' in line else 'failed'
                        active.evidence=[evidence('log',str(p),line)];runs.append(active);active=None
                if active: runs.append(active)
        return [r for r in runs if r.start>=since]
    async def read(self, task, since, now):
        if task.enabled is False: return [],[]
        if task.adapter=='unconnected': return [],['尚未接入，源计划/开关待核实']
        zone=(await command('timedatectl','show','--property=Timezone','--value')).strip()
        if zone!='Asia/Shanghai':raise ValueError('主机时区与源时间解释基线不一致')
        if task.adapter in ('lucullus','rd_lims','training'):
            p=self.settings.cron_schedule_path
            if not p.is_file() or p.is_symlink() or p.stat().st_size>65536:raise ValueError('受限cron调度摘要尚未配置')
            schedule=json.loads(p.read_text())
            observed=dt(schedule.get('observed_at'))
            if not observed or not 0<=(now-observed).total_seconds()<=25*3600:raise ValueError('cron调度摘要过期或时钟异常')
            entry=schedule.get('tasks',{}).get(task.key,{})
            if entry.get('enabled') is not True or set(entry.get('times') or [])!=set(task.times):raise ValueError('实际cron开关/时刻与登记不一致')
        if task.adapter=='systemd': runs=await self.systemd(task,since,now)
        elif task.adapter in ('lucullus','training'): runs=await self.log_runs(task,since,now)
        else: runs=[]
        gaps=[]
        if task.db_source:
            try:records=await self.ledger(task,since,now)
            except Exception:
                for r in runs:
                    if r.status=='success':r.status='unknown';r.message='父退出证据已取得，必要台账不可读'
                return runs,['必要运维台账读取失败或覆盖不全']
            if task.adapter=='rd_lims':
                for row in records:
                    if row.get('source_instance') is not None:continue
                    runs.append(Run(id=f'{task.key}:ledger:{row["id"]}',task_key=task.key,start=dt(row['start']),finish=dt(row['finish']),
                                    status='partial_failed' if status(row['status'])=='success' and row.get('rows_errored',0) else status(row['status']),rows=row.get('rows'),source_kind='ledger',
                                    evidence=[evidence('ledger','meta.etl_run',f'run_id={row["id"]};status={row["status"]};rows_errored={row.get("rows_errored")}')]))
                    if row.get('validation_count'):runs[-1].message='存在数据校验提醒（不替代执行结果）'
                    runs[-1].evidence.extend(evidence('watermark','meta.etl_watermark',json.dumps(w,ensure_ascii=False)+';源业务水位，不是本次执行时间') for w in row.get('watermarks',[]))
            else:
                for run in runs:
                    matched=[r for r in records if dt(r['start'])>=run.start-timedelta(seconds=2) and dt(r['start'])<=(run.finish or now)]
                    if not matched:
                        if run.status=='success':run.status='unknown'
                        run.message='同次运维台账缺失';continue
                    states=[status(r['status']) for r in matched]
                    if run.status=='failed' or 'failed' in states: run.status='failed'
                    elif 'partial_failed' in states and run.finish: run.status='partial_failed'
                    elif any(s!='success' for s in states) and run.status=='success': run.status='unknown'
                    if task.ledger=='meta':
                        complete=(len(matched)==len(task.jobs) and {r['job_name'] for r in matched}==set(task.jobs)) if task.key=='qc-lims' else (len(matched)==5 and {(r['job_name'],r['source_instance']) for r in matched}==LUC_PAIRS)
                        if run.status=='success' and not complete: run.status='unknown';run.message='同次必要子任务身份不匹配'
                        if task.instance and any(r.get('source_instance')!=task.instance for r in matched): run.status='unknown'
                    run.children.extend({'name':r.get('job_name',task.ledger),'status':status(r['status']),'source_run_id':r['id']} for r in matched)
                    run.rows=sum(r.get('rows') or 0 for r in matched) if task.ledger=='meta' else None
                    if sum(r.get('validation_count',0) for r in matched): run.message='存在数据校验提醒（不替代执行结果）'
                    if any((r.get('files_errored') or 0)+(r.get('rows_conflict') or 0)+(r.get('rows_unresolved') or 0)+(r.get('rows_errored') or 0)>0 for r in matched):
                        if run.status=='success':run.status='partial_failed'
                    run.evidence.extend(evidence('ledger',task.ledger,f'run_id={r["id"]};status={r["status"]}') for r in matched)
                    for r in matched:
                        if 'watermark_after' in r:
                            run.evidence.append(evidence('watermark',task.ledger,f'run_id={r["id"]};before={r.get("watermark_before")};after={r.get("watermark_after")};语义=文件mtime，不是业务数据截止时间'))
                        for w in r.get('watermarks',[]):run.evidence.append(evidence('watermark','meta.etl_watermark',json.dumps(w,ensure_ascii=False)+';各任务水位语义不同，不按时间停滞自动判失败'))
        if task.kind=='backup':
            for run in runs:
                run.integrity='not_verified';run.restore='not_verified'
                if task.backup_dir and run.finish:
                    candidates=list(Path(task.backup_dir).glob(task.backup_pattern))
                    if len(candidates)>100: raise ValueError('产物清单超出读取上限')
                    artifacts=[p for p in candidates if not p.is_symlink() and p.is_file() and run.start.timestamp()-2<=p.stat().st_mtime<=run.finish.timestamp()+2]
                    if run.status=='success' and not artifacts:run.status='unknown';run.message='同次备份产物元信息缺失'
                    if artifacts:
                        sizes=[p.stat().st_size for p in artifacts]
                        run.files=len(artifacts);run.size_bytes=sum(sizes)
                        if 0 in sizes:run.status='failed';run.message='备份产物为空'
                        run.evidence.extend(evidence('artifact',p.name,f'产物={p.name};size={p.stat().st_size};mtime={p.stat().st_mtime}') for p in artifacts)
                        if task.key=='mdm-backup':
                            self.mdm_verification(run,artifacts,now)
                elif task.key.startswith('ingest-'):
                    try:self.instrument_evidence(run)
                    except Exception:
                        run.integrity='unknown';run.message='已有执行证据，设备心跳/校验摘要读取失败'
                        gaps.append('设备心跳或文件校验来源不可读/超出范围')
        if task.watermark_path:
            try:
                p=Path(task.watermark_path)
                if not p.is_file() or p.is_symlink() or p.stat().st_size>128:raise ValueError('watermark unavailable')
                value=float(p.read_text().strip())
                if not math.isfinite(value) or value<0:raise ValueError('invalid watermark')
                last=max(runs,key=lambda r:r.start,default=None)
                if last:last.evidence.append(evidence('watermark',task.key+'文件水位',f'current_epoch_seconds={value};observed_at={now.isoformat()};语义=采集时文件mtime水位，不是业务数据截止时间；与失败批次台账候选after可能不同'))
            except Exception:gaps.append('采集时文件水位不可读或格式异常')
        for run in runs:
            if run.finish: run.duration_seconds=max(0,(run.finish-run.start).total_seconds())
            run.message=redact(run.message)
        return runs,list(dict.fromkeys(gaps))

    def mdm_verification(self,run,artifacts,now):
        """Read one bounded, trusted export; never open dump contents or Docker."""
        root=self.settings.mdm_verification_path
        try:
            if len(artifacts)!=1:raise ValueError('ambiguous artifact')
            artifact=artifacts[0];path=root/(artifact.name+'.json')
            if not root.is_dir():raise ValueError('verification export unavailable')
            if not path.exists():
                run.verification={'status':'not_verified','reason':'本次备份没有验证记录'};return
            if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
                raise ValueError('invalid verification export')
            report=json.loads(path.read_text());a=report['artifact'];v=report['verification']
            if report.get('schema_version')!=1 or report.get('task_key')!='mdm-backup' or report.get('host')!='172.19.0.105' or report.get('environment')!='production':raise ValueError('report identity')
            if not re.fullmatch(r'[a-f0-9]{32}',report.get('verification_id','')) or not re.fullmatch(r'[a-f0-9]{64}',a.get('sha256','')):raise ValueError('digest identity')
            stat=artifact.stat()
            if a['basename']!=artifact.name or a['size_bytes']!=stat.st_size or abs(a['mtime']-stat.st_mtime)>0.001:raise ValueError('artifact identity')
            invocation=report.get('source_invocation_id')
            if invocation and run.id!=f'mdm-backup:unit:{invocation}':raise ValueError('invocation identity')
            start=dt(a['backup_started_at']);finish=dt(a['backup_finished_at'])
            if not start or not finish or not run.finish or not run.start-timedelta(seconds=2)<=start<=finish<=run.finish+timedelta(seconds=2):raise ValueError('backup window identity')
            allowed={'pending','running','passed','failed','incomplete'}
            if v.get('status') not in allowed or v.get('restore_status') not in ('not_verified','verified','failed') or v.get('integrity_status') not in ('not_verified','verified','failed'):raise ValueError('verification state')
            end=dt(v.get('finished_at'))
            if end and end>now:raise ValueError('future verification')
            if v['status'] in ('passed','failed','incomplete') and (not end or end<finish):raise ValueError('terminal verification time')
            if v['status']=='passed' and v['restore_status']!='verified':raise ValueError('passed without restore')
            if v['integrity_status']=='verified' and (v['status']!='passed' or report.get('baseline_basis')!='same_exported_snapshot' or v['restore_status']!='verified' or not v.get('checks') or any(x!='passed' for x in v['checks'].values())):raise ValueError('missing baseline checks')
            stage=v['status'];reason={'pending':'验证尚未开始','running':'验证尚未完成','passed':'恢复验证通过','failed':'恢复或完整性检查失败','incomplete':'验证未完成'}.get(stage)
            if stage in ('pending','running'):
                begin=dt(v.get('started_at')) or finish
                if now>begin+timedelta(minutes=12):stage='incomplete';reason='验证更新逾期，未完成'
            run.integrity=v['integrity_status'];run.restore=v['restore_status']
            safe={k:v.get(k) for k in ('status','started_at','finished_at','target_pg_version','image_digest','failure_step','checks')}
            safe.update({'status':stage,'reason':reason,'cleanup_status':report.get('cleanup_status'),
                         'verification_id':report['verification_id'],'artifact':a['basename'],'sha256':a['sha256'],
                         'exclusions':report.get('exclusions',[])})
            run.verification=safe
            run.evidence.append(evidence('verification',a['basename']+'验证摘要',json.dumps(safe,ensure_ascii=False)))
        except Exception:
            run.integrity='unknown';run.restore='unknown';run.verification={'status':'unknown'}

    def instrument_evidence(self,run,root=Path('/mnt/ttlab-backups')):
        # Device heartbeat is overwritten across shifts. Never assign a different shift's success.
        summary='\n'.join(e['excerpt'] for e in run.evidence if e['kind']=='journal')
        found=set()
        for device,machine in [('flex2','T281240040C_Nova'),('vicell','C4V61257XH_ViCell')]:
            ending=re.findall(rf'<<< \[(?:day|night)\] {device} (完成|失败，退出码 \d+)',summary)
            child={'name':device,'status':'unknown'}
            if len(ending)==1:child['status']='success' if ending[0]=='完成' else 'failed';found.add(device)
            if child['status']=='failed':run.status='failed'
            run.children.append(child)
            hb=root/'State'/f'{machine}_heartbeat.json'
            if not hb.exists():run.message='部分设备心跳或校验摘要缺失';continue
            if hb.is_symlink() or hb.stat().st_size>MAX_LOG_BYTES:raise ValueError('心跳不在有界读取范围')
            h=json.loads(hb.read_text())
            start,finish=dt(h.get('last_run_time')),dt(h.get('last_run_finished'))
            if not start or not finish or not run.finish or not (run.start-timedelta(seconds=2)<=start<=finish<=run.finish+timedelta(seconds=2)):
                run.message='部分最新心跳属于其他批次，本次校验范围未齐';continue
            child['files_processed']=h.get('files_processed');child['files_failed']=h.get('files_failed')
            if h.get('backup_status')!='SUCCESS' or h.get('files_failed',0):child['status']='failed';run.status='failed'
            run.evidence.append(evidence('heartbeat',f'{machine}_heartbeat.json',json.dumps({k:h.get(k) for k in ('machine_name','run_tag','last_run_time','last_run_finished','backup_status','files_processed','files_failed','alerts')},ensure_ascii=False)))
            folder=root/'Checksums'/machine
            if not folder.is_dir():run.message='同次校验摘要缺失';continue
            paths=list(folder.glob('*SHA256_Compare*.csv'))
            if len(paths)>1000:raise ValueError('校验清单目录超出范围')
            associated=[p for p in paths if not p.is_symlink() and p.is_file() and start.timestamp()-2<=p.stat().st_mtime<=finish.timestamp()+2]
            if len(associated)!=1:run.message='同次校验清单缺失或关联有歧义';continue
            p=associated[0]
            if p.stat().st_size>2_000_000:raise ValueError('校验清单超出范围')
            report=checksum_summary(p.read_text(encoding='utf-8-sig'))
            child['integrity']='failed' if report['mismatch'] else 'unknown' if report['unknown'] else 'scope_verified' if report['rows'] else 'no_changed_files'
            if report['mismatch']:run.status='failed';run.message='已有文件校验发现不一致'
            if report['unknown']:run.message='已有文件校验存在无法识别的结论'
            run.evidence.append(evidence('checksum',p.name,json.dumps(report,ensure_ascii=False)+';SHA256，仅已列文件范围，不证明整个备份可恢复'))
        if run.status=='success' and found!={'flex2','vicell'}:run.status='unknown';run.message='父执行完成，但两设备结束证据不齐或重复'
        if len(run.children)==2 and all(c.get('integrity')=='scope_verified' for c in run.children):run.integrity='scope_verified'
