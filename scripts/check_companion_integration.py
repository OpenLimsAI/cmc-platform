#!/usr/bin/env python3
"""离线配套验证：源入口只在临时副本执行，数据库/服务/ETL/通知全部为桩。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / 'cmc-platform-monitor'
STUB = r'''
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['RECORD'], 'a') as f:
    f.write(json.dumps([name, args]) + '\n')
case = os.environ['CASE']
if name == 'sudo':
    import subprocess
    if args[:2] == ['-u', 'postgres']: args = args[2:]
    sys.exit(subprocess.call(args))
if name == 'pg_dump':
    print('stub data')
    sys.exit(2 if case == 'dump-fail' else 0)
if name == 'psql':
    if '-c' not in args:
        body = sys.stdin.read()
        sys.exit(3 if case == ('isolation-fail' if 'DO $$' in body else 'restore-fail') else 0)
    sql = args[args.index('-c') + 1]
    if 'count(*)' in sql:
        print('bad' if case == 'invalid-count' else '7')
    for key, marker in [('terminate-fail','pg_terminate_backend'),
                        ('old-rename-fail','cmc_analytics_training rename'),
                        ('new-rename-fail','cmc_analytics_training_new rename')]:
        if case == key and marker in sql: sys.exit(4)
if name == 'systemctl':
    if case == args[0] + '-fail': sys.exit(5)
if name == 'uv': sys.exit(7 if case == 'etl-fail' else 0)
if name == 'fake-etl':
    sys.exit(9 if case == 'etl-fail' and 'sync_reference' in args[-1] else 0)
if name == 'notify.py': sys.exit(6 if case == 'notify-fail' else 0)
'''


def run_copy(relative, case='success', notifier=True):
    """No real original entry point, sudo, database or ETL executable is invoked."""
    with tempfile.TemporaryDirectory(prefix='ops-companion-') as temp:
        base = Path(temp)
        record = base / 'calls.jsonl'
        bin_path = base / 'bin'
        bin_path.mkdir()
        for name in ['sudo', 'pg_dump', 'psql', 'dropdb', 'createdb', 'systemctl', 'uv', 'fake-etl', 'notify.py']:
            p = bin_path / name
            p.write_text(f'#!{sys.executable}\n' + STUB)
            p.chmod(0o700)
        if not notifier:
            (bin_path / 'notify.py').unlink()
        repo = base / 'repo'
        (repo / 'scripts').mkdir(parents=True)
        env_dir = base / 'env'
        env_dir.mkdir()
        for station in ['ws01', 'ws02']:
            (env_dir / f'{station}.env').write_text('')
        script = repo / 'scripts/entry.sh'
        text = (ROOT / relative).read_text()
        text = text.replace('/opt/cmc-platform-monitor/scripts/notify_completion.py', str(bin_path / 'notify.py'))
        text = text.replace('/usr/bin/python3', sys.executable)
        text = text.replace('/opt/rd-batch-registry-training/logs/db_reset.log', str(base / 'db_reset.log'))
        script.write_text(text)
        env = {**os.environ, 'PATH': str(bin_path) + ':' + os.environ['PATH'],
               'RECORD': str(record), 'CASE': case, 'REPO': str(repo),
               'PY': str(bin_path / 'fake-etl'), 'ENV_DIR': str(env_dir),
               'LOG_DIR': str(base / 'logs'), 'DRY_RUN': '1' if case == 'dry-run' else '0'}
        result = subprocess.run(['bash', str(script)], env=env, text=True, capture_output=True, timeout=10)
        calls = [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
        if os.environ.get('OPS_TEST_DEBUG') == '1':
            print(result.stderr, result.stdout, (base / 'db_reset.log').read_text(errors='replace') if (base / 'db_reset.log').exists() else '', calls)
        return result.returncode, calls


class CompletionTests(unittest.TestCase):
    def test_lims_success_failure_and_unavailable_notification(self):
        for case, notifier, rc in [('success',True,0),('etl-fail',True,7),('notify-fail',True,0),('etl-fail',False,7)]:
            with self.subTest(case=case, notifier=notifier):
                actual, calls = run_copy('rd-lims-etl/scripts/run_etl.sh',case,notifier)
                self.assertEqual(actual,rc)
                self.assertEqual(sum(name=='notify.py' for name,_ in calls), int(notifier))
                if notifier:self.assertEqual(calls[-1][1],['--task','rd-lims'])

    def test_lucullus_full_pipeline_failure_and_dry_run(self):
        for case, rc, count in [('success',0,1),('etl-fail',2,1),('notify-fail',0,1),('dry-run',0,0)]:
            with self.subTest(case=case):
                actual,calls=run_copy('rd-lucullus-etl/run_lucullus_pipeline.sh',case)
                self.assertEqual(actual,rc)
                self.assertEqual(sum(name=='notify.py' for name,_ in calls),count)
                self.assertEqual(sum(name=='fake-etl' for name,_ in calls),0 if case=='dry-run' else 6)
                if count:self.assertEqual(calls[-1][1],['--task','lucullus'])


class TrainingTests(unittest.TestCase):
    def test_success_exclusion_and_strict_restore(self):
        rc,calls=run_copy('rd-batch-registry/scripts/training_db_reset.sh')
        self.assertEqual(rc,0)
        dump=next(args for name,args in calls if name=='pg_dump')
        self.assertEqual(dump,["--exclude-table-data=ops_monitor.*",'cmc_analytics'])
        restore=next(args for name,args in calls if name=='psql' and '-c' not in args)
        self.assertIn('ON_ERROR_STOP=1',restore)
        self.assertEqual(calls[-1][1],['--task','training-sync'])

    def test_failures_before_swap_do_not_stop_or_rename(self):
        for case in ['dump-fail','restore-fail','isolation-fail','invalid-count']:
            with self.subTest(case=case):
                rc,calls=run_copy('rd-batch-registry/scripts/training_db_reset.sh',case)
                self.assertEqual(rc,1)
                self.assertFalse(any(name=='systemctl' for name,_ in calls))
                self.assertFalse(any('alter database' in ' '.join(args) for _,args in calls))
                self.assertEqual(calls[-1][0],'notify.py')

    def test_stop_and_terminate_failure(self):
        for case in ['stop-fail','terminate-fail']:
            with self.subTest(case=case):
                rc,calls=run_copy('rd-batch-registry/scripts/training_db_reset.sh',case)
                self.assertEqual(rc,1)
                self.assertFalse(any('alter database' in ' '.join(args) for _,args in calls))
                if case=='terminate-fail':self.assertIn(['systemctl',['start','rd-batch-registry-training-backend.service']],calls)

    def test_failed_new_rename_restores_original_name(self):
        rc,calls=run_copy('rd-batch-registry/scripts/training_db_reset.sh','new-rename-fail')
        self.assertEqual(rc,1)
        self.assertTrue(any(name=='psql' and 'alter database cmc_analytics_training_old rename to cmc_analytics_training' in args for name,args in calls))
        self.assertIn(['systemctl',['start','rd-batch-registry-training-backend.service']],calls)

    def test_old_rename_failure_restarts_backend(self):
        rc,calls=run_copy('rd-batch-registry/scripts/training_db_reset.sh','old-rename-fail')
        self.assertEqual(rc,1)
        self.assertFalse(any('cmc_analytics_training_new rename' in ' '.join(args) for _,args in calls))
        self.assertIn(['systemctl',['start','rd-batch-registry-training-backend.service']],calls)

    def test_restart_failure_keeps_old_database(self):
        rc,calls=run_copy('rd-batch-registry/scripts/training_db_reset.sh','start-fail')
        self.assertEqual(rc,1)
        rename=next(i for i,(name,args) in enumerate(calls) if name=='psql' and 'alter database cmc_analytics_training_new rename to cmc_analytics_training' in args)
        self.assertFalse(any(name=='dropdb' and 'cmc_analytics_training_old' in args for name,args in calls[rename+1:]))

    def test_notification_failure_keeps_success_and_missing_notification_keeps_error(self):
        for case,notifier,rc in [('notify-fail',True,0),('dump-fail',False,1)]:
            actual,_=run_copy('rd-batch-registry/scripts/training_db_reset.sh',case,notifier)
            self.assertEqual(actual,rc)


class UnitTests(unittest.TestCase):
    def test_whole_units_and_old_alerts_are_preserved(self):
        paths={
            'qc-lims-etl/deploy/linux/qc-lims-etl.service':'qc-lims',
            'rd-vicell-etl/deploy/vicell-etl.service':'vicell',
            'rd-nova-etl/deploy/nova-etl.service':'nova',
            'cmc-instrument-ingest/tools/deploy/instrument-ingest-day.service':'ingest-day',
            'cmc-instrument-ingest/tools/deploy/instrument-ingest-night.service':'ingest-night',
            'cmc-instrument-ingest/tools/deploy/heartbeat-check.service':'heartbeat-check',
            'cmab-mdm-platform/deploy/systemd/cmab-mdm-backup.service':'mdm-backup'}
        for rel,key in paths.items():
            with self.subTest(task=key):
                text=(ROOT/rel).read_text()
                self.assertIn(f'OnSuccess=ops-notify-{key}.service',text)
                self.assertIn(f'OnFailure=ops-notify-{key}.service',text)
                self.assertNotIn('ExecStopPost=',text)
                self.assertNotIn('RemainAfterExit=yes',text)
                if key in ['vicell','nova','ingest-day','ingest-night']:
                    self.assertIn('OnFailure=instrument-alert@%n.service',text)
                observer=(MONITOR/f'deploy/linux/ops-notify-{key}.service').read_text()
                self.assertIn(f'--task {key}',observer)
                self.assertIn('SupplementaryGroups=opsmonitor-events',observer)
                expected='flex2ingest' if key in ['ingest-day','ingest-night','heartbeat-check'] else 'prometheus'
                self.assertIn(f'User={expected}',observer)


if __name__ == '__main__':
    unittest.main(verbosity=2)
