#!/usr/bin/env python3
"""Read this account's crontab; export only three registered plans, without command/env text."""
import json
import os
import pwd
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

ENTRIES={'lucullus':'/opt/rd-lucullus-etl/run_lucullus_pipeline.sh',
         'rd-lims':'/opt/rd-lims-etl/scripts/run_etl.sh',
         'training-sync':'/opt/rd-batch-registry-training/scripts/training_db_reset.sh'}
OUTPUT=Path('/var/lib/cmc-platform-monitor/schedule-source/crontab.json')

def parse(content):
    tasks={k:{'enabled':False,'times':[]} for k in ENTRIES}
    for line in content.splitlines():
        parts=line.strip().split(None,5)
        if not parts or line.lstrip().startswith('#') or len(parts)!=6:continue
        for key,path in ENTRIES.items():
            # Exact token boundary, not an older project's similarly named entry.
            if not any(token.strip('\"\'')==path for token in parts[5].split()):continue
            entry=tasks[key];entry['enabled']=True
            minute,hour,day,month,weekday=parts[:5]
            if (day,month,weekday)!=('*','*','*') or not minute.isdigit() or not all(h.isdigit() for h in hour.split(',')):
                entry['times']=None;continue
            if not 0<=int(minute)<60 or any(not 0<=int(h)<24 for h in hour.split(',')):
                entry['times']=None;continue
            if entry['times'] is not None:entry['times'].extend(f'{int(h):02d}:{int(minute):02d}' for h in hour.split(','))
    for entry in tasks.values():
        if entry['times'] is not None and len(entry['times'])!=len(set(entry['times'])):entry['times']=None
        elif entry['times'] is not None:entry['times'].sort()
    return tasks

def main():
    # Run as prometheus. No sudo, other users, writes to cron or arbitrary arguments.
    if pwd.getpwuid(os.geteuid()).pw_name!='prometheus':raise RuntimeError('unexpected source identity')
    result=subprocess.run(['/usr/bin/crontab','-l'],capture_output=True,text=True,timeout=3)
    if result.returncode:raise RuntimeError('cannot verify source crontab')
    if len(result.stdout)>65536:raise RuntimeError('source crontab exceeds budget')
    payload={'observed_at':datetime.now(timezone.utc).isoformat(),'source_user':'prometheus','tasks':parse(result.stdout)}
    tmp=OUTPUT.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(payload,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,OUTPUT)
    return 0
if __name__=='__main__':sys.exit(main())
