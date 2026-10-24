#!/usr/bin/env python3
"""Authorized fixed-SHA release phases. Never starts source ETL/backup/reset tasks."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys

ROOT=Path('/opt/cmc-platform-monitor')
CONFIG=Path('/etc/cmc-platform-monitor')
BACKUP=Path('/var/backups/cmc-platform-monitor/20261010')
VERSIONS=json.loads((ROOT/'deploy/linux/release-20261010.json').read_text())
REVISION='20261010_ops_monitor_v1'
BEFORE='analytics_water_mart_perf_1009'
PATHS={'rd-vicell-etl':'vicell-etl','rd-nova-etl':'nova-etl'}

def run(args,**kwargs):
    return subprocess.run([str(a) for a in args],check=True,**kwargs)
def output(args,**kwargs):
    return subprocess.check_output([str(a) for a in args],text=True,**kwargs).strip()
def user(args,**kwargs):return run(['sudo','-u','prometheus',*args],**kwargs)
def sql(port,db,query):
    return output(['sudo','-u','postgres','psql','-X','-v','ON_ERROR_STOP=1','-At','-p',port,'-d',db],input=query)
def save(path,content,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content);path.chmod(mode)
def update_repo(name):
    item=VERSIONS[name];repo=Path('/opt')/PATHS.get(name,name)
    dirty=output(['sudo','-u','prometheus','git','-C',repo,'diff','--name-only'])
    staged=output(['sudo','-u','prometheus','git','-C',repo,'diff','--cached','--name-only'])
    if dirty or staged:raise RuntimeError('tracked worktree dirty: '+name)
    user(['git','-C',repo,'fetch','origin',item['branch']])
    if name=='rd-batch-registry-training':
        branch=output(['sudo','-u','prometheus','git','-C',repo,'branch','--show-current'])
        if branch!=item['branch']:user(['git','-C',repo,'switch','-c',item['branch'],item['sha']])
    else:user(['git','-C',repo,'merge','--ff-only',item['sha']])
    if output(['sudo','-u','prometheus','git','-C',repo,'rev-parse','HEAD'])!=item['sha']:raise RuntimeError('SHA mismatch: '+name)
    print('VERSION',name,item['sha'],flush=True)
def prepare():
    for group in ['opsmonitor-api','opsmonitor-events','opsmonitor-evidence']:
        if subprocess.run(['getent','group',group],stdout=subprocess.DEVNULL).returncode:run(['groupadd','--system',group])
    for name,group in [('opsmonitor-api','opsmonitor-api'),('opsmonitor','opsmonitor-events')]:
        if subprocess.run(['id',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
            run(['useradd','--system','--gid',group,'--no-create-home','--shell','/usr/sbin/nologin',name])
    run(['usermod','-aG','opsmonitor-events','prometheus']);run(['usermod','-aG','opsmonitor-events','flex2ingest'])
    run(['install','-d','-m','0750','-o','opsmonitor-api','-g','opsmonitor-api','/var/log/cmc-platform-monitor'])
    run(['install','-d','-m','2770','-o','prometheus','-g','opsmonitor-evidence','/var/lib/cmc-platform-monitor/schedule-source'])
    CONFIG.mkdir(mode=0o700,exist_ok=True);BACKUP.mkdir(mode=0o700,parents=True,exist_ok=True)
    user(['/home/prometheus/.local/bin/uv','sync','--locked','--no-dev','--python','/usr/bin/python3','--no-managed-python'],cwd=ROOT/'backend')
    user(['npm','ci'],cwd=ROOT/'frontend')
    env=dict(os.environ);env.pop('VITE_DEMO_MODE',None)
    user(['npm','run','build'],cwd=ROOT/'frontend',env=env)
    update_repo('rd-batch-registry-training');update_repo('cmc-schema-migrations')
def migrate():
    for db in ['cmc_analytics','cmc_analytics_training']:
        current=sql(5432,db,'SELECT version_num FROM alembic_version;')
        if current not in (BEFORE,REVISION):raise RuntimeError('unexpected migration revision: '+db)
        if current==REVISION:continue
        dump=BACKUP/(db+'.dump')
        if not dump.exists():
            tmp=dump.with_suffix('.partial')
            with tmp.open('wb') as f:run(['sudo','-u','postgres','pg_dump','-p','5432','-Fc',db],stdout=f)
            tmp.chmod(0o600);os.replace(tmp,dump)
        run(['pg_restore','--list',dump],stdout=subprocess.DEVNULL)
        with dump.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        save(dump.with_suffix('.sha256'),digest+'  '+dump.name+'\n')
        print('BACKUP',db,dump.stat().st_size,digest,flush=True)
        user(['./dbmig',db,'upgrade',REVISION],cwd='/opt/cmc-schema-migrations')
        assert sql(5432,db,'SELECT version_num FROM alembic_version;')==REVISION
        print('MIGRATED',db,REVISION,flush=True)
def read_env(path):
    result={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        try:result[key]=shlex.split(value,comments=True)[0]
        except IndexError:result[key]=''
    return result
def configure():
    password_file=CONFIG/'db-passwords.json'
    if password_file.exists():passwords=json.loads(password_file.read_text())
    else:
        passwords={r:secrets.token_hex(32) for r in ['ops_monitor_api','ops_monitor_collector','ops_monitor_reader']}
        save(password_file,json.dumps(passwords))
    for port,roles in [(5432,list(passwords)),(5434,['ops_monitor_reader'])]:
        for role in roles:
            exists=sql(port,'postgres',f"SELECT count(*) FROM pg_roles WHERE rolname='{role}';")=='1'
            if not exists:sql(port,'postgres',f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '{passwords[role]}';")
            if sql(port,'postgres',f"SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit FROM pg_roles WHERE rolname='{role}';")!='f':raise RuntimeError('role broader than expected')
    sql(5432,'cmc_analytics',"""
GRANT CONNECT ON DATABASE cmc_analytics TO ops_monitor_api,ops_monitor_collector;
GRANT USAGE ON SCHEMA ops_monitor TO ops_monitor_api,ops_monitor_collector;
GRANT SELECT ON ops_monitor.collection_batch,ops_monitor.run_reference,ops_monitor.update_event TO ops_monitor_api;
GRANT INSERT ON ops_monitor.access_audit_log,ops_monitor.update_event TO ops_monitor_api;
GRANT SELECT,INSERT,DELETE ON ALL TABLES IN SCHEMA ops_monitor TO ops_monitor_collector;
GRANT UPDATE ON ops_monitor.update_event TO ops_monitor_collector;
""")
    common="""
GRANT USAGE ON SCHEMA meta TO ops_monitor_reader;
GRANT SELECT (run_id,job_name,source_instance,run_started_at,run_finished_at,status,rows_written,rows_errored) ON meta.etl_run TO ops_monitor_reader;
GRANT SELECT (run_id,error_type) ON meta.load_error_log TO ops_monitor_reader;
GRANT SELECT (job_name,source_instance,target_table,last_success_ts,last_run_id,updated_at) ON meta.etl_watermark TO ops_monitor_reader;
ALTER ROLE ops_monitor_reader SET default_transaction_read_only = on;
"""
    for port,db in [(5432,'cmc_rd'),(5434,'cmc_gmp')]:
        sql(port,db,f'GRANT CONNECT ON DATABASE {db} TO ops_monitor_reader;'+common)
    sql(5432,'cmc_rd',"""
GRANT USAGE ON SCHEMA raw_rd_usp_vicell,raw_rd_usp_nova TO ops_monitor_reader;
GRANT SELECT (id,run_started_at,run_finished_at,status,files_loaded,files_errored,watermark_before,watermark_after) ON raw_rd_usp_vicell.etl_log TO ops_monitor_reader;
GRANT SELECT (id,run_started_at,run_finished_at,status,files_loaded,files_errored,watermark_before,watermark_after,rows_conflict,rows_unresolved) ON raw_rd_usp_nova.etl_log TO ops_monitor_reader;
""")
    mdm=read_env(Path('/opt/cmab-mdm-platform/.env'))
    if mdm.get('JWT_ALGORITHM','HS256')!='HS256' or len(mdm.get('SECRET_KEY',''))<32:raise RuntimeError('MDM signing config mismatch')
    def url(role,port,db):return f'postgresql+asyncpg://{role}:{passwords[role]}@127.0.0.1:{port}/{db}'
    def envtext(values):return ''.join(k+'='+shlex.quote(v)+'\n' for k,v in values.items())
    save(CONFIG/'api.env',envtext({'OPS_MODE':'production','OPS_COMPONENT':'api','OPS_JWT_ALGORITHM':'HS256','OPS_JWT_VERIFY_KEY':mdm['SECRET_KEY'],'OPS_DATABASE_URL':url('ops_monitor_api',5432,'cmc_analytics')}))
    save(CONFIG/'collector.env',envtext({'OPS_MODE':'production','OPS_COMPONENT':'collector','OPS_DATABASE_URL':url('ops_monitor_collector',5432,'cmc_analytics'),'OPS_RD_READ_URL':url('ops_monitor_reader',5432,'cmc_rd'),'OPS_GMP_READ_URL':url('ops_monitor_reader',5434,'cmc_gmp'),'OPS_JOURNAL_SOCKET_PATH':'/run/cmc-platform-monitor-evidence/journal.sock'}))
    print('PROVISIONED dedicated roles and root-only environment files (no secrets printed)',flush=True)
def install(src,dst):
    dst=Path(dst)
    if dst.exists():
        backup=BACKUP/(str(dst).strip('/').replace('/','_'))
        if not backup.exists():shutil.copy2(dst,backup)
    shutil.copy2(src,dst);dst.chmod(0o644)
def start():
    for f in (ROOT/'deploy/linux').glob('cmc-platform-monitor-*.service'):install(f,Path('/etc/systemd/system')/f.name)
    f=ROOT/'deploy/linux/cmc-platform-monitor-schedule-export.timer';install(f,Path('/etc/systemd/system')/f.name)
    run(['systemctl','daemon-reload'])
    run(['systemctl','start','cmc-platform-monitor-schedule-export.service'])
    run(['systemctl','enable','--now','cmc-platform-monitor-evidence.service','cmc-platform-monitor-api.service','cmc-platform-monitor-collector.service','cmc-platform-monitor-schedule-export.timer'])
def sources():
    for name in VERSIONS:
        if name not in ['cmab-hub','cmc-schema-migrations','rd-batch-registry-training']:update_repo(name)
    units={
      'qc-lims-etl.service':('/opt/qc-lims-etl','deploy/linux/qc-lims-etl.service'),
      'vicell-etl.service':('/opt/vicell-etl','deploy/vicell-etl.service'),
      'nova-etl.service':('/opt/nova-etl','deploy/nova-etl.service'),
      'instrument-ingest-day.service':('/opt/cmc-instrument-ingest','tools/deploy/instrument-ingest-day.service'),
      'instrument-ingest-night.service':('/opt/cmc-instrument-ingest','tools/deploy/instrument-ingest-night.service'),
      'heartbeat-check.service':('/opt/cmc-instrument-ingest','tools/deploy/heartbeat-check.service'),
      'cmab-mdm-backup.service':('/opt/cmab-mdm-platform','deploy/systemd/cmab-mdm-backup.service')}
    before={u:output(['systemctl','show',u,'--property=User,ExecStart']) for u in units}
    for f in (ROOT/'deploy/linux').glob('ops-notify-*.service'):install(f,Path('/etc/systemd/system')/f.name)
    for unit,(repo,file) in units.items():
        lines=Path(repo,file).read_text().splitlines();values={k:[] for k in ['OnSuccess','OnFailure']}
        for line in lines:
            for k in values:
                if line.startswith(k+'='):values[k].extend(x for x in line.split('=',1)[1].split() if x.startswith('ops-notify-'))
        if not all(values.values()):raise RuntimeError('missing completion integration: '+unit)
        dst=Path('/etc/systemd/system')/(unit+'.d')/'50-platform-monitor.conf';dst.parent.mkdir(exist_ok=True)
        save(dst,'[Unit]\n'+''.join(k+'='+' '.join(v)+'\n' for k,v in values.items()),0o644)
    run(['systemctl','daemon-reload'])
    after={u:output(['systemctl','show',u,'--property=User,ExecStart']) for u in units}
    assert before==after,'source identity/business entry changed'
    print('SOURCE NOTIFICATIONS LOADED; no source task started; original User/ExecStart unchanged',flush=True)
def hub():
    update_repo('cmab-hub')
    old=Path('/opt/cmab-hub/frontend/dist')
    if old.exists() and not (BACKUP/'hub-dist').exists():shutil.copytree(old,BACKUP/'hub-dist')
    user(['npm','run','build'],cwd='/opt/cmab-hub/frontend')
    install(ROOT/'deploy/linux/cmc-platform-monitor-frontend.conf','/etc/nginx/conf.d/cmc-platform-monitor-frontend.conf')
    run(['nginx','-t']);run(['systemctl','reload','nginx'])
    print('HUB /ops production route live',flush=True)

if __name__=='__main__':
    if os.geteuid()!=0:raise SystemExit('run via authorized sudo')
    phase=sys.argv[1];expected=sys.argv[2]
    actual=output(['sudo','-u','prometheus','git','-C',ROOT,'rev-parse','HEAD'])
    if actual!=expected:raise SystemExit('monitor fixed SHA mismatch')
    {'prepare':prepare,'migrate':migrate,'configure':configure,'start':start,'sources':sources,'hub':hub}[phase]()
