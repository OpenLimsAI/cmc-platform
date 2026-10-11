#!/usr/bin/env python3
"""Fixed-SHA monitor-only P16 release; no migrations or source executions."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT=Path('/opt/cmc-platform-monitor')


def call(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def output(args):
    return subprocess.check_output(args,text=True).strip()


def main(sha):
    if os.geteuid()!=0:raise RuntimeError('controlled release requires root')
    if output(['git','-C',str(ROOT),'rev-parse','HEAD'])!=sha or output(['git','-C',str(ROOT),'status','--porcelain']):
        raise RuntimeError('fixed SHA/clean checkout required')
    if not Path('/var/lib/cmc-platform-monitor/mdm-verification').is_dir():
        raise RuntimeError('MDM verification export must be installed first')
    env=dict(os.environ);env.pop('VITE_DEMO_MODE',None)
    call(['sudo','-u','prometheus','npm','run','build'],cwd=ROOT/'frontend',env=env)
    call(['systemctl','restart','cmc-platform-monitor-api.service','cmc-platform-monitor-collector.service'])
    call(['systemctl','is-active','cmc-platform-monitor-api.service','cmc-platform-monitor-collector.service'])
    # Both services read code from this checkout; startup collection rereads
    # fixed sources and reports. No task schedule or database schema changes.
    print('Released monitor P16 at '+sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sha',required=True)
    main(parser.parse_args().sha)
