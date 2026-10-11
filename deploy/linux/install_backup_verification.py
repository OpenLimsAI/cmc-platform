#!/usr/bin/env python3
"""Install reviewed MDM verifier units/config. Never starts a source backup."""
import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

ROOT=Path('/opt/cmab-mdm-platform')
STATE=Path('/var/lib/cmab-mdm-backup-verify')
EXPORT=Path('/var/lib/cmc-platform-monitor/mdm-verification')


def run(*args):
    return subprocess.check_output(args,text=True).strip()


def install(image):
    if os.geteuid()!=0:raise RuntimeError('root install required')
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    from mdm_backup_verification import check_image
    check_image(image)
    item=json.loads(run('docker','image','inspect',image))[0]
    if item['Architecture']!='amd64' or item['Os']!='linux':raise RuntimeError('unexpected image platform')
    if shutil.disk_usage('/var/lib').free<2*1024**3:raise RuntimeError('insufficient working space')
    user=pwd.getpwnam('prometheus');group=grp.getgrnam('opsmonitor-evidence')
    for p,owner,gid,mode in [(STATE,0,user.pw_gid,0o750),(STATE/'requests',user.pw_uid,user.pw_gid,0o700),
                            (STATE/'reports',0,0,0o700),(EXPORT,user.pw_uid,group.gr_gid,0o2750)]:
        p.mkdir(parents=True,exist_ok=True);os.chown(p,owner,gid);p.chmod(mode)
    config=Path('/etc/cmab-mdm-backup-verify.json')
    config.write_text(json.dumps({'image':image,'memory':'512m','cpus':'1','timeout_seconds':600})+'\n');config.chmod(0o600)
    for name in ('cmab-mdm-backup-verify.service','cmab-mdm-backup-verify.path'):
        target=Path('/etc/systemd/system')/name
        shutil.copyfile(ROOT/'deploy/systemd'/name,target);target.chmod(0o644)
    drop=Path('/etc/systemd/system/cmab-mdm-backup.service.d/60-backup-verification.conf')
    drop.parent.mkdir(parents=True,exist_ok=True)
    drop.write_text('[Service]\nEnvironment=BACKUP_VERIFY_ENABLED=1\n');drop.chmod(0o644)
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','cmab-mdm-backup-verify.path')
    print('Installed verifier path; daily backup timer unchanged; no backup started.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--image',required=True)
    install(parser.parse_args().image)
