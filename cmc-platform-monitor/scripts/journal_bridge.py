#!/usr/bin/env python3
"""Fixed lifecycle journal export. No arbitrary unit, command, file or source writes."""
import json
import os
import pwd
import re
import socket
import socketserver
import struct
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

UNITS={'qc-lims-etl.service','vicell-etl.service','nova-etl.service',
       'instrument-ingest-day.service','instrument-ingest-night.service',
       'cmab-mdm-backup.service','heartbeat-check.service'}
SOCKET=Path('/run/cmc-platform-monitor-evidence/journal.sock')
FIELDS={'__CURSOR','__REALTIME_TIMESTAMP','_PID','SYSLOG_IDENTIFIER','_SYSTEMD_INVOCATION_ID','INVOCATION_ID','UNIT'}

def arguments(payload,now=None):
    now=now or datetime.now(timezone.utc)
    unit=payload['unit']
    if unit not in UNITS:raise ValueError('unit not registered')
    since=datetime.fromisoformat(payload['since']);until=datetime.fromisoformat(payload['until'])
    if since.tzinfo is None or until.tzinfo is None or not now-timedelta(days=32)<=since<=until<=now+timedelta(seconds=60):
        raise ValueError('invalid bounded window')
    args=['/usr/bin/journalctl','--unit',unit,'--since',since.isoformat(),'--until',until.isoformat(),
          '--output=json','--output-fields=MESSAGE,_PID,SYSLOG_IDENTIFIER,_SYSTEMD_INVOCATION_ID,INVOCATION_ID,UNIT',
          '--grep=^(Starting |Started |Finished |Failed to start|.*\\.service: (Deactivated successfully|Failed with result|Main process exited)|>>> \\[|<<< \\[)',
          '--no-pager','--lines=+500']
    cursor=payload.get('cursor')
    if cursor:
        if not isinstance(cursor,str) or not re.fullmatch(r'[A-Za-z0-9;=_-]{1,512}',cursor):raise ValueError('invalid cursor')
        args.append('--after-cursor='+cursor)
    return args

def sanitize(content):
    rows=[]
    for line in content.splitlines():
        raw=json.loads(line);message=str(raw.get('MESSAGE',''))
        # Program output is reduced to the exact device lifecycle marker.
        marker=re.search(r'(>>>|<<<) \[(day|night)\] (?:开始采集 )?(flex2|vicell)(?: 完成| 失败，退出码 \d+)?',message)
        manager=(str(raw.get('_PID'))=='1' or raw.get('SYSLOG_IDENTIFIER')=='systemd')
        if manager and (message.startswith(('Starting ','Started ','Finished ','Failed to start')) or re.match(r'^[a-z0-9-]+\.service: (Deactivated successfully|Failed with result|Main process exited)',message)):
            safe=message[:1000]
        else:safe=marker[0] if marker else '[omitted]'
        row={k:v for k,v in raw.items() if k in FIELDS};row['MESSAGE']=safe;rows.append(json.dumps(row))
    if len(rows)>500:raise ValueError('journal page overflow')
    return '\n'.join(rows)

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            _,uid,_=struct.unpack('3i',self.connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if pwd.getpwuid(uid).pw_name!='opsmonitor':raise PermissionError('unregistered reader')
            raw=self.rfile.readline(4097)
            if len(raw)>4096 or not raw.endswith(b'\n'):raise ValueError('request overflow')
            result=subprocess.run(arguments(json.loads(raw)),capture_output=True,text=True,timeout=4,
                                  env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TZ':'Asia/Shanghai'})
            if result.returncode or len(result.stdout)>2_000_000:raise ValueError('journal unavailable')
            payload={'ok':True,'data':sanitize(result.stdout)}
            if len(json.dumps(payload).encode())>2_000_000:raise ValueError('response overflow')
        except Exception:payload={'ok':False}
        self.wfile.write(json.dumps(payload).encode()+b'\n')

class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True

if __name__=='__main__':
    if pwd.getpwuid(os.geteuid()).pw_name!='prometheus':raise RuntimeError('unexpected export identity')
    SOCKET.unlink(missing_ok=True)
    with Server(str(SOCKET),Handler) as server:
        os.chmod(SOCKET,0o660);server.serve_forever()
