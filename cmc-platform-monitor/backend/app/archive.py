"""Per-device references derived from fixed parent journals and checksum reports."""
import csv
import io
import re
from datetime import datetime,timedelta
from pathlib import Path
from .domain import Run,SH,UTC

MACHINES={'flex2':'T281240040C_Nova','vicell':'C4V61257XH_ViCell'}
PARENTS={'ingest-day':'day','ingest-night':'night'}
HASH=re.compile(r'[a-fA-F0-9]{64}')


def lifecycle(entries,mode,parent):
    children=[]
    for device in MACHINES:
        begin=[];end=[]
        for e in entries:
            message=str(e.get('MESSAGE',''))
            stamp=datetime.fromtimestamp(int(e['__REALTIME_TIMESTAMP'])/1e6,UTC)
            if message==f'>>> [{mode}] 开始采集 {device}':begin.append(stamp)
            match=re.fullmatch(rf'<<< \[{mode}\] {device} (完成|失败，退出码 [1-9]\d*)',message)
            if match:end.append((stamp,'success' if match[1]=='完成' else 'failed'))
        child={'name':device,'status':'unknown','archive_mode':mode,'evidence':[]}
        if (len(begin)==len(end)==1 and parent.start-timedelta(seconds=2)<=begin[0]<=end[0][0]
                and (parent.finish is None or end[0][0]<=parent.finish+timedelta(seconds=2))):
            child.update(status=end[0][1],start=begin[0].isoformat(),finish=end[0][0].isoformat())
        elif parent.status=='failed':
            child.update(status='failed',message='批次异常结束，本设备未取得完整结束记录')
        else:child['message']='本设备完整开始/结束记录未取得'
        children.append(child)
    return children


def checked_report(content):
    reader=csv.DictReader(io.StringIO(content))
    if not {'match_status','Local_SHA256','NAS_SHA256'}.issubset(reader.fieldnames or []):
        raise ValueError('checksum header missing')
    counts={'rows':0,'match':0,'mismatch':0,'unknown':0}
    for row in reader:
        counts['rows']+=1
        if None in row:raise ValueError('malformed checksum row')
        state=str(row.get('match_status','')).upper()
        a=row.get('Local_SHA256') or '';b=row.get('NAS_SHA256') or ''
        if state=='MISMATCH':counts['mismatch']+=1
        elif state!='MATCH' or not HASH.fullmatch(a) or not HASH.fullmatch(b):counts['unknown']+=1
        elif a.lower()!=b.lower():counts['mismatch']+=1
        else:counts['match']+=1
    return counts


def instrument_evidence(run,make_evidence,root,cache):
    for child in run.children:
        device=child['name'];machine=MACHINES[device]
        child['evidence'].append(make_evidence('journal',run.evidence[0]['ref'],
            f"device={device};parent={run.id};mode={child['archive_mode']};status={child['status']};start={child.get('start')};finish={child.get('finish')}"))
        known_failed=child['status']=='failed'
        if child['status'] not in ('success','failed') or not child.get('start') or not child.get('finish'):continue
        try:
            start=datetime.fromisoformat(child['start']);finish=datetime.fromisoformat(child['finish'])
            folder=root/'Checksums'/machine
            if machine not in cache:
                if not folder.is_dir():raise ValueError('checksum directory missing')
                paths=list(folder.glob(f'{machine}_SHA256_Compare*.csv'))
                if len(paths)>1000:raise ValueError('checksum directory over budget')
                parsed=[]
                pattern=re.compile(rf'{re.escape(machine)}_SHA256_Compare_v\d+(?:_\d+)*_(\d{{8}})_(\d{{6}})\.csv')
                for p in paths:
                    match=pattern.fullmatch(p.name)
                    if match:
                        stamp=datetime.strptime(match[1]+match[2],'%Y%m%d%H%M%S').replace(tzinfo=SH)
                        parsed.append((p,stamp))
                cache[machine]=parsed
            associated=[p for p,stamp in cache[machine] if start-timedelta(seconds=2)<=stamp<=finish+timedelta(seconds=2)]
            if len(associated)!=1:raise ValueError('checksum identity missing or ambiguous')
            p=associated[0]
            if p.is_symlink() or not p.is_file() or p.stat().st_size>2_000_000:raise ValueError('checksum unavailable')
            report=checked_report(p.read_text(encoding='utf-8-sig'))
            child.update(files=report['rows'],integrity='failed' if report['mismatch'] else 'unknown' if report['unknown'] else 'scope_verified' if report['rows'] else 'no_changed_files')
            child['evidence'].append(make_evidence('checksum',p.name,str(report)+';本设备同次文件SHA256'))
            if report['mismatch']:child.update(status='failed',message='本次文件SHA256校验不一致')
            elif report['unknown']:child.update(status='failed' if known_failed else 'unknown',message='本次校验清单含未识别结论或缺有效SHA256')
        except Exception:
            child.update(status='failed' if known_failed else 'unknown',integrity='unknown',message='设备执行失败且校验清单未取得' if known_failed else '本设备同次校验清单缺失、不可读或关联不明确')
        run.evidence.extend(child['evidence'])
    if any(c['status']=='failed' for c in run.children):run.status='failed'


def device_runs(task,parents):
    result=[]
    for parent in parents:
        mode=PARENTS[parent.task_key]
        if parent.source_kind=='schedule':
            result.append(parent.model_copy(update={'id':f'{task.key}:schedule:{parent.start.isoformat()}',
                'task_key':task.key,'archive_mode':mode,'parent_run_id':parent.id}))
            continue
        child=next((c for c in parent.children if c['name']==task.archive_device),None)
        if child is None:continue
        start=datetime.fromisoformat(child['start']) if child.get('start') else parent.start
        finish=datetime.fromisoformat(child['finish']) if child.get('finish') else parent.finish
        # Schedule identity is the parent start; actual device duration is independent.
        run=Run(id=f'{task.key}:parent:{parent.id}',task_key=task.key,start=parent.start,finish=finish,
                duration_seconds=max(0,(finish-start).total_seconds()) if finish else None,
                status=child['status'],message=child.get('message',''),files=child.get('files'),
                integrity=child.get('integrity'),restore='not_applicable',archive_mode=mode,
                parent_run_id=parent.id,source_kind='device_archive',evidence=child.get('evidence',[]))
        if parent.evidence:
            # Keep the parent identity and only this device's lifecycle excerpt.
            markers=[line for line in parent.evidence[0]['excerpt'].splitlines()
                     if f'] {task.archive_device} ' in line or f'开始采集 {task.archive_device}' in line]
            run.children=[{'name':task.archive_device,'status':child['status'],
                           'actual_start':start.isoformat(),'actual_finish':finish.isoformat() if finish else None,
                           'parent_run_id':parent.id,'archive_mode':mode}]
            # Checksum evidence is sufficient; source marker identity remains in the child reference.
            if not markers and run.status=='success':run.status='unknown';run.message='设备结束标记缺失'
        result.append(run)
    return result
