#!/usr/bin/env python3
"""Release probes: no source tasks; synthetic role tokens are API tests, not MDM login."""
import asyncio
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.error
import jwt
from deploy_linux import read_env

ROOT=Path('/opt/cmc-platform-monitor')

def request(path,claims=None,base='http://127.0.0.1:8025'):
    headers={}
    if claims is not None:
        env=read_env(Path('/etc/cmc-platform-monitor/api.env'))
        body={'sub':'release-verification','exp':datetime.now(timezone.utc)+timedelta(minutes=2),
              'type':'access','roles':['SYS_ADMIN'],'must_change_password':False}|claims
        headers['Authorization']='Bearer '+jwt.encode(body,env['OPS_JWT_VERIFY_KEY'],algorithm='HS256')
    try:
        with urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=10) as r:
            return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,None

def api():
    for claims,expected in [(None,401),({},200),({'roles':['DEPT_ADMIN']},403),
                            ({'must_change_password':True},403),({'type':'refresh'},401),({'exp':1},401)]:
        code,_=request('/api/v1/overview',claims)
        assert code==expected,(claims,code)
    assert request('/api/v1/health')[0]==200
    code,data=request('/api/v1/overview',{})
    assert code==200 and data['mode']=='production'
    primary=[x for x in data['tasks'] if x['task']['enabled'] is True]
    assert len(data['tasks'])==16 and len(primary)==10
    for item in primary:
        assert item['collection_status']=='ok',(item['task']['key'],item['collection_status'],item['reasons'])
        print('TASK',item['task']['key'],item['state'],item['label'],item['reasons'])
        path='/api/v1/tasks/'+item['task']['key']+'/runs?snapshot_id='+data['id']
        code,history=request(path,{})
        assert code==200
        print('HISTORY',item['task']['key'],history['total'])
    print('API guard probes passed; tokens are synthetic, not actual MDM login; cutoff',data['collected_at'])

async def permissions():
    import asyncpg
    env=read_env(Path('/etc/cmc-platform-monitor/collector.env'))
    for key in ['OPS_RD_READ_URL','OPS_GMP_READ_URL']:
        conn=await asyncpg.connect(env[key].replace('postgresql+asyncpg://','postgresql://'),timeout=5)
        try:
            assert await conn.fetchval('SHOW default_transaction_read_only')=='on'
            assert not await conn.fetchval("SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user")
            assert await conn.fetchval('SELECT count(*) FROM meta.etl_run')>=0
            assert not await conn.fetchval("SELECT has_column_privilege(current_user,'meta.etl_run','message','SELECT')")
            raw_tables=await conn.fetch("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname LIKE 'raw%' AND c.relname!='etl_log'")
            for t in raw_tables:
                assert not await conn.fetchval('SELECT has_table_privilege(current_user,$1,\'SELECT\')',f'"{t[0]}"."{t[1]}"')
                assert not await conn.fetchval('SELECT has_any_column_privilege(current_user,$1,\'SELECT\')',f'"{t[0]}"."{t[1]}"')
            assert not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=current_user)")
            print('SOURCE readonly exact columns; no raw business reads or inherited role:',await conn.fetchval('SELECT current_database()'),'raw tables denied',len(raw_tables))
        finally:await conn.close()
    env=read_env(Path('/etc/cmc-platform-monitor/api.env'))
    assert not any(k in env for k in ['OPS_RD_READ_URL','OPS_GMP_READ_URL'])
    conn=await asyncpg.connect(env['OPS_DATABASE_URL'].replace('postgresql+asyncpg://','postgresql://'),timeout=5)
    try:
        assert not await conn.fetchval("SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user")
        assert await conn.fetchval("SELECT has_table_privilege(current_user,'ops_monitor.collection_batch','SELECT')")
        assert not await conn.fetchval("SELECT has_table_privilege(current_user,'ops_monitor.collection_batch','UPDATE')")
        assert not await conn.fetchval("SELECT has_table_privilege(current_user,'ops_monitor.collection_batch','INSERT')")
        print('API isolated monitor read/audit/event role; no source credentials')
    finally:await conn.close()

def notifications():
    tasks=json.loads((ROOT/'config/tasks.json').read_text())
    for t in tasks:
        if t.get('enabled',True) is not True or not t.get('producer_users'):continue
        producer=t['producer_users'][0]
        probe=f"import sys;sys.path.insert(0,'/opt/cmc-platform-monitor/scripts');from notify_completion import notify;assert notify({t['key']!r});print({t['key']!r},'peer ACK accepted')"
        subprocess.run(['sudo','-u',producer,'python3','-c',probe],check=True)
    for producer,task in [('opsmonitor-api','rd-lims'),('flex2ingest','rd-lims')]:
        probe=f"import sys;sys.path.insert(0,'/opt/cmc-platform-monitor/scripts');from notify_completion import notify;assert not notify({task!r});print('unregistered peer/task rejected')"
        subprocess.run(['sudo','-u',producer,'python3','-c',probe],check=True)
    print('Probes requested evidence reread only; no source task started')

if __name__=='__main__':
    if os.geteuid()!=0:raise SystemExit('root-only secret handling; no credentials printed')
    if sys.argv[1]=='api':api()
    elif sys.argv[1]=='permissions':asyncio.run(permissions())
    elif sys.argv[1]=='notifications':notifications()
