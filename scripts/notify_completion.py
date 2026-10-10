#!/usr/bin/env python3
"""Best-effort completion hint only. Never execute a task or change its result."""
import argparse
import json
import socket
import sys
import time
from uuid import uuid4

TASKS=('lucullus','rd-lims','qc-lims','vicell','nova','ingest-day','ingest-night','mdm-backup','heartbeat-check','training-sync')

def notify(task, path='/run/cmc-platform-monitor/events.sock'):
    if task not in TASKS:return False
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            deadline=time.monotonic()+2
            def remaining():
                left=deadline-time.monotonic()
                if left<=0:raise TimeoutError('notification deadline exceeded')
                client.settimeout(left)
            remaining()
            client.connect(path)
            remaining()
            client.sendall((json.dumps({'task_key':task,'event_id':str(uuid4())})+'\n').encode())
            response=b''
            # Unix stream may split even a short ACK; keep total time/bytes bounded.
            while not response.endswith(b'\n'):
                if len(response)>=128:return False
                remaining()
                part=client.recv(128-len(response))
                if not part:return False
                response+=part
            return json.loads(response).get('accepted') is True
    except Exception:return False

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',required=True,choices=TASKS)
    args=parser.parse_args()
    if not notify(args.task):print('monitor notification unavailable; original task result unchanged',file=sys.stderr)
    return 0

if __name__=='__main__':sys.exit(main())
