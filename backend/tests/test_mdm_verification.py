import json
import os
from datetime import timedelta

from app.sources import Reader
from app.domain import assess
from test_monitor import config, run, task, NOW


def fixture(tmp_path, status='passed', baseline=True):
    a=tmp_path/'cmab_mdm_test_20261010_1801.dump';a.write_bytes(b'test')
    r=run();os.utime(a,(r.finish.timestamp(),r.finish.timestamp()))
    root=tmp_path/'reports';root.mkdir()
    report={'schema_version':1,'task_key':'mdm-backup','host':'172.19.0.105','environment':'production',
      'verification_id':'a'*32,'source_invocation_id':None,'baseline_basis':'same_exported_snapshot' if baseline else None,
      'artifact':{'basename':a.name,'size_bytes':4,'sha256':'b'*64,'mtime':a.stat().st_mtime,
                  'backup_started_at':r.start.isoformat(),'backup_finished_at':r.finish.isoformat()},
      'verification':{'status':status,'started_at':r.finish.isoformat(),'finished_at':NOW.isoformat(),
                     'restore_status':'verified' if status=='passed' else 'failed',
                     'integrity_status':'verified' if status=='passed' and baseline else 'not_verified',
                     'checks':{k:'passed' for k in ('full_restore','database','tables','columns','constraints','indexes','views','sequences','extensions','unsupported','large_objects','migration_revision','table_counts')}},'cleanup_status':'passed','exclusions':[]}
    p=root/(a.name+'.json');p.write_text(json.dumps(report))
    s=config();s.mdm_verification_path=root
    r.task_key='mdm-backup'
    return Reader(s),r,a,p,report


def test_exact_artifact_verified_green(tmp_path):
    reader,r,a,p,report=fixture(tmp_path)
    reader.mdm_verification(r,[a],NOW)
    o=assess(task(key='mdm-backup',kind='backup'),[r],NOW)
    assert o.state=='success' and o.label=='备份完成，恢复验证通过'
    assert r.status=='success' and r.restore=='verified'


def test_old_artifact_or_wrong_invocation_not_green(tmp_path):
    reader,r,a,p,report=fixture(tmp_path)
    report['source_invocation_id']='wrong';p.write_text(json.dumps(report))
    reader.mdm_verification(r,[a],NOW)
    assert assess(task(key='mdm-backup',kind='backup'),[r],NOW).state=='unknown'
    assert r.status=='success'


def test_historical_restore_without_baseline_warns(tmp_path):
    reader,r,a,p,report=fixture(tmp_path,baseline=False)
    reader.mdm_verification(r,[a],NOW)
    assert r.restore=='verified' and r.integrity=='not_verified'
    assert assess(task(key='mdm-backup',kind='backup'),[r],NOW).state=='warning'


def test_validation_failed_is_red_but_backup_still_success(tmp_path):
    reader,r,a,p,report=fixture(tmp_path,status='failed')
    reader.mdm_verification(r,[a],NOW)
    o=assess(task(key='mdm-backup',kind='backup'),[r],NOW)
    assert o.state=='failed' and o.label=='备份完成，验证失败'
    assert r.status=='success'


def test_unreadable_report_unknown_not_old_green(tmp_path):
    reader,r,a,p,report=fixture(tmp_path)
    p.write_text('{')
    reader.mdm_verification(r,[a],NOW)
    assert assess(task(key='mdm-backup',kind='backup'),[r],NOW).state=='unknown'


def test_pending_expired_and_cleanup_failure_warn(tmp_path):
    reader,r,a,p,report=fixture(tmp_path,status='pending')
    report['verification'].update(restore_status='not_verified',finished_at=None)
    p.write_text(json.dumps(report));reader.mdm_verification(r,[a],NOW+timedelta(minutes=15))
    assert r.verification['status']=='incomplete'
    assert assess(task(key='mdm-backup',kind='backup'),[r],NOW).state=='warning'
    report['verification'].update(status='passed',restore_status='verified',integrity_status='verified',finished_at=NOW.isoformat())
    report['cleanup_status']='failed';p.write_text(json.dumps(report));reader.mdm_verification(r,[a],NOW)
    assert assess(task(key='mdm-backup',kind='backup'),[r],NOW).state=='warning'


def test_future_or_false_baseline_cannot_pass(tmp_path):
    reader,r,a,p,report=fixture(tmp_path)
    report['verification']['finished_at']=(NOW+timedelta(minutes=1)).isoformat();p.write_text(json.dumps(report))
    reader.mdm_verification(r,[a],NOW);assert r.restore=='unknown'
    report['verification']['finished_at']=NOW.isoformat();report['verification']['checks']={'full_restore':'failed'}
    p.write_text(json.dumps(report));reader.mdm_verification(r,[a],NOW);assert r.integrity=='unknown'


def test_partial_required_check_list_cannot_claim_full_integrity(tmp_path):
    reader,r,a,p,report=fixture(tmp_path)
    report['verification']['checks']={'full_restore':'passed'}
    p.write_text(json.dumps(report));reader.mdm_verification(r,[a],NOW)
    assert assess(task(key='mdm-backup',kind='backup'),[r],NOW).state=='unknown'
