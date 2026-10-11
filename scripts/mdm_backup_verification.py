#!/usr/bin/env python3
"""MDM-only backup snapshot and isolated Docker restore verification.

No restore connection string is accepted. The only restore target is a newly
created labelled container with no network, host mounts or published ports.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKUPS = Path('/home/prometheus/cmc_backups/mdm')
STATE = Path('/var/lib/cmab-mdm-backup-verify')
EXPORT = Path('/var/lib/cmc-platform-monitor/mdm-verification')
CONFIG = Path('/etc/cmab-mdm-backup-verify.json')
LABEL = 'cmab.mdm.restore-verification'
NAME = re.compile(r'cmab_mdm_[A-Za-z0-9_-]+\.dump')
MAX_JSON = 1_000_000
EXCLUSIONS = ['server_roles_passwords', 'object_owners_acl', 'application_end_to_end',
              'external_files', 'concurrent_sequence_value_comparison', 'business_field_semantics']


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, payload, mode=0o600):
    path = Path(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temp.open('x') as handle:
            os.chmod(temp, mode)
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JSON:
            raise ValueError('invalid_report_file')
        return json.load(handle)


def digest(handle):
    handle.seek(0)
    result = hashlib.file_digest(handle, 'sha256').hexdigest()
    handle.seek(0)
    return result


def ident(value):
    return '"' + value.replace('"', '""') + '"'


SCOPE = "n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'"
QUERIES = {
    'database': "SELECT json_build_object('encoding',pg_encoding_to_char(encoding),'collate',datcollate,'ctype',datctype) FROM pg_database WHERE datname=current_database()",
    'tables': f"SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'name',c.relname,'kind',c.relkind,'rls',c.relrowsecurity) ORDER BY n.nspname,c.relname),'[]'::json) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE} AND c.relkind IN ('r','p','m') AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e')",
    'columns': f"SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(ad.adbin,ad.adrelid)) ORDER BY n.nspname,c.relname,a.attnum),'[]'::json) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef ad ON ad.adrelid=c.oid AND ad.adnum=a.attnum WHERE {SCOPE} AND c.relkind IN ('r','p','m') AND a.attnum>0 AND NOT a.attisdropped AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.deptype='e')",
    'constraints': f"SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname,k.conname,k.contype,k.convalidated,pg_get_constraintdef(k.oid)) ORDER BY n.nspname,c.relname,k.conname),'[]'::json) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE}",
    'indexes': f"SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname,x.relname,i.indisvalid,pg_get_indexdef(i.indexrelid)) ORDER BY n.nspname,c.relname,x.relname),'[]'::json) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_class x ON x.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE}",
    'views': f"SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname,pg_get_viewdef(c.oid)) ORDER BY n.nspname,c.relname),'[]'::json) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE} AND c.relkind IN ('v','m')",
    'sequences': f"SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname,s.seqstart,s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle) ORDER BY n.nspname,c.relname),'[]'::json) FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE}",
    'extensions': "SELECT json_agg(json_build_array(extname,extversion) ORDER BY extname) FROM pg_extension",
    'unsupported': f"SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname,c.relkind)),'[]'::json) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE} AND c.relkind='f'",
    'large_objects': "SELECT to_json(count(*)) FROM pg_largeobject_metadata",
    'migration_revision': "SELECT coalesce(json_agg(version_num ORDER BY version_num),'[]'::json) FROM public.alembic_version",
}


def catalog(query):
    result = {key: query(sql) for key, sql in QUERIES.items()}
    # Non-superuser backup roles cannot SELECT pg_largeobject. With no large
    # objects, the public metadata proves the empty scope without extra grants.
    count=result['large_objects']
    result['large_objects']={'objects':count,'chunks':[]}
    if count:
        result['large_objects']['chunks']=query("SELECT coalesce(json_agg(json_build_array(loid,pageno,md5(data)) ORDER BY loid,pageno),'[]'::json) FROM pg_largeobject")
    tables = result['tables']
    if len(tables) > 500:
        raise ValueError('table_scope_overflow')
    counts = {}
    for table in tables:
        key = table['schema'] + '.' + table['name']
        counts[key] = query(f"SELECT to_json(count(*)) FROM {ident(table['schema'])}.{ident(table['name'])}")
    result['table_counts'] = counts
    result['coverage_gaps'] = (['row_level_security'] if any(t['rls'] for t in tables) else [])
    if result['unsupported']:
        result['coverage_gaps'].append('foreign_tables')
    return result


def connection_env(dsn):
    from psycopg2.extensions import parse_dsn
    parsed = parse_dsn(dsn.replace('postgresql+psycopg2://', 'postgresql://'))
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    for key, target in [('host','PGHOST'),('port','PGPORT'),('user','PGUSER'),
                        ('password','PGPASSWORD'),('dbname','PGDATABASE')]:
        if key in parsed:
            env[target] = parsed[key]
    env['PGCONNECT_TIMEOUT'] = '5'
    return env


def snapshot_dump(output, level):
    """Optional same-snapshot baseline; fallback preserves a valid daily dump."""
    import psycopg2
    dsn = os.environ['PG_DSN']
    env = connection_env(dsn)
    started = now()
    baseline = None
    error = None
    with psycopg2.connect(dsn.replace('postgresql+psycopg2://','postgresql://'), connect_timeout=5) as conn:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SET LOCAL search_path=pg_catalog")
            cur.execute('SELECT pg_export_snapshot()')
            snapshot = cur.fetchone()[0]
            try:
                def query(sql):
                    cur.execute(sql)
                    return cur.fetchone()[0]
                baseline = catalog(query)
            except Exception:
                error = 'baseline_unavailable'
            if error:
                # A cancelled query aborts the transaction. Run an ordinary full
                # dump afterwards rather than breaking the existing backup.
                conn.rollback()
                args = ['pg_dump','-Fc','-Z',str(level),'-f',str(output)]
            else:
                args = ['pg_dump','--snapshot='+snapshot,'-Fc','-Z',str(level),'-f',str(output)]
            done = subprocess.run(args, env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE, timeout=300)
            if done.returncode:
                raise RuntimeError('pg_dump_failed')
    request = make_request(output, started, now(), os.environ.get('INVOCATION_ID'), baseline)
    request['baseline_error'] = error
    atomic(str(output)+'.baseline.json', request)
    return request


def make_request(artifact, start, finish, invocation=None, baseline=None):
    artifact = Path(artifact)
    if not NAME.fullmatch(artifact.name) or artifact.is_symlink():
        raise ValueError('invalid_artifact')
    with artifact.open('rb') as handle:
        sha = digest(handle)
    return {'schema_version':1,'task_key':'mdm-backup','host':'172.19.0.105',
            'environment':'production','verification_id':uuid.uuid4().hex,
            'source_invocation_id':invocation,'artifact':{'basename':artifact.name,
            'size_bytes':artifact.stat().st_size,'mtime':artifact.stat().st_mtime,
            'sha256':sha,'backup_started_at':start,'backup_finished_at':finish},
            'baseline':baseline,'baseline_basis':'same_exported_snapshot' if baseline else None}


def enqueue(artifact, start=None, finish=None, invocation=None):
    path = Path(artifact)
    if path.parent.resolve() != BACKUPS or not NAME.fullmatch(path.name):
        raise ValueError('unregistered_artifact_directory')
    baseline_path = Path(str(path)+'.baseline.json')
    request = read_json(baseline_path) if baseline_path.exists() else make_request(path,start,finish,invocation)
    key = request['artifact']['basename'] + '.json'
    # The producer writes only its registered spool and safe summary. Verifier
    # owns full reports; Docker access never goes to the monitor.
    publish(request, {'status':'pending','restore_status':'not_verified',
                     'integrity_status':'not_verified','started_at':None,'finished_at':None}, 'not_started')
    # Publish pending before exposing the request to systemd; otherwise a fast
    # worker could finish and have its terminal report overwritten by pending.
    atomic(STATE/'requests'/key, request)


def publish(request, verification, cleanup):
    summary = {k:request.get(k) for k in ('schema_version','task_key','host','environment',
               'verification_id','source_invocation_id','artifact','baseline_basis')}
    summary['verification'] = verification
    summary['cleanup_status'] = cleanup
    summary['exclusions'] = EXCLUSIONS
    summary['reported_at'] = now()
    atomic(EXPORT/(request['artifact']['basename']+'.json'), summary, 0o640)


class StepFailure(Exception):
    def __init__(self, step, failed=False):
        self.step = step
        self.failed = failed


def interrupted(signum, frame):
    raise StepFailure('deadline')


class Docker:
    def __init__(self, deadline):
        self.deadline = deadline
    def run(self, args, *, input=None, stdin=None, step='environment', failed=False):
        remaining = self.deadline-time.monotonic()
        if remaining <= 0:
            raise StepFailure('deadline')
        try:
            result = subprocess.run(['docker',*args], input=input, stdin=stdin,
                         capture_output=True, timeout=min(remaining, 120))
        except subprocess.TimeoutExpired:
            raise StepFailure('deadline') from None
        if result.returncode or len(result.stdout) > 4_000_000:
            raise StepFailure(step, failed)
        return result.stdout


def check_image(image):
    if not re.fullmatch(r'(?:[a-zA-Z0-9./_-]+@)?sha256:[a-f0-9]{64}',image):
        raise ValueError('image_must_be_pinned_digest')
    return image


def config():
    c = read_json(CONFIG)
    check_image(c['image'])
    if c.get('memory') != '512m' or c.get('cpus') != '1' or c.get('timeout_seconds') != 600:
        raise ValueError('unreviewed_resource_limits')
    return c


def verify(request, c):
    art = request['artifact']
    if request.get('schema_version') != 1 or request.get('task_key') != 'mdm-backup' or request.get('host') != '172.19.0.105' or request.get('environment') != 'production':
        raise ValueError('unregistered_request')
    if not NAME.fullmatch(art['basename']) or not re.fullmatch(r'[a-f0-9]{32}',request['verification_id']):
        raise ValueError('invalid_request_identity')
    if not re.fullmatch(r'[a-f0-9]{64}',art['sha256']):
        raise ValueError('invalid_artifact_digest')
    name = 'cmab-mdm-verify-' + request['verification_id']
    verification = {'status':'running','started_at':now(),'finished_at':None,
                    'restore_status':'not_verified','integrity_status':'not_verified',
                    'failure_step':None,'image_digest':c['image'],'checks':{}}
    began=time.monotonic()
    publish(request, verification, 'not_started')
    d = Docker(time.monotonic()+600)
    created = False
    cleanup = 'not_needed'
    restored = None
    try:
        # Fail before starting if stale project containers remain. Never delete
        # arbitrary Docker resources to manufacture space.
        if d.run(['ps','-aq','--filter','label='+LABEL], step='residual_resources').strip():
            raise StepFailure('residual_resources')
        if shutil.disk_usage(STATE).free < 2*1024**3:
            raise StepFailure('free_disk_space')
        fd = os.open(BACKUPS/art['basename'], os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != art['size_bytes'] or digest(handle) != art['sha256']:
                raise StepFailure('artifact_identity', True)
            d.run(['image','inspect',check_image(c['image'])], step='image_unavailable')
            try:
                d.run(['run','-d','--name',name,'--label',LABEL+'=true',
                       '--label',LABEL+'.id='+request['verification_id'],
                       '--network=none','--cpus=1','--memory=512m','--memory-swap=512m',
                       '--pids-limit=128','--security-opt=no-new-privileges',
                       '--log-driver=none','--tmpfs','/tmp:rw,noexec,nosuid,size=16m',
                       '-e','POSTGRES_HOST_AUTH_METHOD=trust',
                       '-e','POSTGRES_INITDB_ARGS=--encoding=UTF8 --locale=C.UTF-8',
                       '-e','PGDATA=/var/lib/postgresql/verify-data',
                       c['image']], step='container_start')
            finally:
                # Even if docker run timed out after creation, inspect and
                # clean this unique labelled container only.
                created = True
            for _ in range(60):
                try:
                    d.run(['exec',name,'pg_isready','-h','127.0.0.1','-U','postgres'],step='database_start')
                    break
                except StepFailure as exc:
                    if exc.step=='deadline':raise
                    time.sleep(0.5)
            else:
                raise StepFailure('database_start')
            d.run(['exec',name,'createdb','-U','postgres','-T','template0','-E','UTF8',
                   '--locale=C.UTF-8','mdm_verify'],step='database_create')
            d.run(['exec','-i',name,'pg_restore','-U','postgres','-d','mdm_verify',
                   '--no-owner','--no-privileges','--exit-on-error'],stdin=handle,
                   step='restore',failed=True)
            verification['restore_status'] = 'verified'
            def query(sql):
                value=d.run(['exec',name,'psql','-X','-At','-v','ON_ERROR_STOP=1',
                             '-U','postgres','-d','mdm_verify','-c',
                             "BEGIN READ ONLY; SET LOCAL search_path=pg_catalog; SET LOCAL statement_timeout='15s'; "+sql+'; COMMIT;'],
                            step='restored_catalog',failed=True).decode()
                # -At still emits BEGIN/SET/COMMIT. Exactly one JSON result.
                rows=[x for x in value.splitlines() if x not in ('BEGIN','SET','COMMIT')]
                return json.loads('\n'.join(rows))
            restored = catalog(query)
            verification['target_pg_version']=query("SELECT to_json(current_setting('server_version'))")
            verification['restored_database_bytes']=query('SELECT to_json(pg_database_size(current_database()))')
            try:
                verification['resource_sample']=d.run(['stats','--no-stream','--format','{{.MemUsage}} | {{.CPUPerc}}',name],step='resource_sample').decode().strip()
                verification['temporary_data_bytes']=int(d.run(['exec',name,'du','-sb','/var/lib/postgresql/verify-data'],step='resource_sample').decode().split()[0])
            except (StepFailure,ValueError,IndexError):
                verification['resource_sample']=None
            baseline=request.get('baseline')
            verification['checks']['full_restore']='passed'
            if baseline is None:
                verification['status']='passed'
                verification['checks']['baseline']='missing'
            else:
                if request.get('baseline_basis') != 'same_exported_snapshot':
                    raise StepFailure('baseline_identity')
                differences = [key for key in QUERIES if baseline[key]!=restored[key]]
                if baseline['table_counts']!=restored['table_counts']:
                    differences.append('table_counts')
                verification['checks'].update({key:'failed' if key in differences else 'passed' for key in [*QUERIES,'table_counts']})
                if differences:
                    raise StepFailure('baseline_compare', True)
                if baseline['coverage_gaps'] or restored['coverage_gaps']:
                    raise StepFailure('scope_incomplete')
                verification['integrity_status']='verified'
                verification['status']='passed'
    except StepFailure as exc:
        verification['status']='failed' if exc.failed else 'incomplete'
        verification['failure_step']=exc.step
        if exc.step=='restore':verification['restore_status']='failed'
        if exc.failed:verification['integrity_status']='failed'
    except Exception:
        verification['status']='incomplete'
        verification['failure_step']='verification_internal'
    finally:
        if created:
            # Cleanup receives its own small budget even after restore timeout.
            clean = Docker(time.monotonic()+25)
            try:
                raw=clean.run(['inspect',name],step='cleanup')
                item=json.loads(raw)[0]
                labels=item['Config'].get('Labels') or {}
                if labels.get(LABEL)!='true' or labels.get(LABEL+'.id')!=request['verification_id']:
                    raise StepFailure('cleanup_identity')
                clean.run(['rm','-fv',name],step='cleanup')
                cleanup='passed'
            except StepFailure:
                # A failed run may never have created a container.
                try:
                    names=clean.run(['ps','-a','--format','{{.Names}}'],step='cleanup').decode().splitlines()
                    cleanup='not_needed' if name not in names else 'failed'
                except StepFailure:cleanup='failed'
        verification['finished_at']=now()
        verification['duration_seconds']=round(time.monotonic()-began,3)
        full={'request':request,'verification':verification,'cleanup_status':cleanup,
              'restored_catalog':restored,'exclusions':EXCLUSIONS}
        atomic(STATE/'reports'/(request['verification_id']+'.json'),full)
        publish(request,verification,cleanup)
    return verification


def process_queue():
    if os.geteuid()!=0:
        raise RuntimeError('verifier_requires_controlled_service')
    c=config()
    signal.signal(signal.SIGTERM, interrupted)
    with (STATE/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        paths=sorted((STATE/'requests').glob('*.json'))
        if len(paths)>100:
            raise RuntimeError('request_queue_overflow')
        for path in paths:
            try:
                request=read_json(path)
                verify(request,c)
            except Exception:
                # Quarantine malformed requests; never spin a PathExistsGlob
                # service on a permanently invalid producer file.
                path.rename(STATE/'reports'/('rejected-'+uuid.uuid4().hex+'.json'))
                continue
            path.unlink()
            # Only the registered sender identity can notify the monitor.
            subprocess.run(['runuser','-u','prometheus','--','/usr/bin/python3',
                            '/opt/cmc-platform-monitor/scripts/notify_completion.py',
                            '--task','mdm-backup'],stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,timeout=5,check=False)
        # Retention removes only bounded regular project reports/exports.
        cutoff=time.time()-90*86400
        for folder in (STATE/'reports',EXPORT):
            for path in folder.glob('*.json'):
                if not path.is_symlink() and path.is_file() and path.stat().st_mtime<cutoff:
                    path.unlink()


def cleanup_owned():
    """Systemd stop fallback, including containers left after a worker crash."""
    if os.geteuid()!=0:
        raise RuntimeError('controlled_service_required')
    d=Docker(time.monotonic()+30)
    ids=d.run(['ps','-aq','--filter','label='+LABEL],step='cleanup').decode().splitlines()
    if len(ids)>10:
        raise RuntimeError('cleanup_scope_overflow')
    for container in ids:
        item=json.loads(d.run(['inspect',container],step='cleanup'))[0]
        labels=item['Config'].get('Labels') or {}
        vid=labels.get(LABEL+'.id','')
        if labels.get(LABEL)!='true' or not re.fullmatch(r'[a-f0-9]{32}',vid) or item['Name']!='/cmab-mdm-verify-'+vid:
            raise RuntimeError('cleanup_identity')
        d.run(['rm','-fv',container],step='cleanup')
        for path in EXPORT.glob('cmab_mdm_*.dump.json'):
            report=read_json(path)
            if report.get('verification_id')==vid and report.get('verification',{}).get('status')=='running':
                report['verification'].update(status='incomplete',failure_step='worker_interrupted',finished_at=now())
                report['cleanup_status']='passed';report['reported_at']=now()
                atomic(path,report,0o640)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    snap=sub.add_parser('snapshot');snap.add_argument('--output',required=True,type=Path);snap.add_argument('--level',type=int,default=6)
    queue=sub.add_parser('enqueue');queue.add_argument('--artifact',required=True,type=Path);queue.add_argument('--start');queue.add_argument('--finish');queue.add_argument('--invocation')
    sub.add_parser('process')
    sub.add_parser('cleanup')
    args=parser.parse_args()
    try:
        if args.command=='snapshot':snapshot_dump(args.output,args.level)
        elif args.command=='enqueue':enqueue(args.artifact,args.start,args.finish,args.invocation)
        elif args.command=='cleanup':cleanup_owned()
        else:process_queue()
        return 0
    except Exception:
        # Never print exceptions containing source credentials or restored data.
        print('MDM backup verification: '+args.command+' unavailable',file=__import__('sys').stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
