#!/usr/bin/env python3
"""Offline companion checks. Every Docker/SQL operation is a stub."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[2]/'cmab-mdm-platform/scripts/mdm_backup_verification.py'
spec=importlib.util.spec_from_file_location('mdm_verify',MODULE)
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


class VerificationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.backups=self.root/'backups';self.state=self.root/'state';self.export=self.root/'export'
        for p in (self.backups,self.state/'reports',self.state/'requests',self.export):p.mkdir(parents=True)
        self.art=self.backups/'cmab_mdm_test_20261010_1801.dump';self.art.write_bytes(b'synthetic dump')
        self.request=v.make_request(self.art,v.now(),v.now(),'test-invocation')
        self.config={'image':'sha256:'+'a'*64,'memory':'512m','cpus':'1','timeout_seconds':600}
        self.calls=[]
        self.patches=[patch.object(v,'BACKUPS',self.backups),patch.object(v,'STATE',self.state),patch.object(v,'EXPORT',self.export)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in self.patches:p.stop()
        self.temp.cleanup()
    def fake(self,args,**kwargs):
        self.calls.append(args)
        if args[0]=='inspect':return json.dumps([{'Config':{'Labels':{v.LABEL:'true',v.LABEL+'.id':self.request['verification_id']}}}]).encode()
        if 'psql' in args:return b'BEGIN\nSET\nSET\n"16.15"\nCOMMIT\n'
        return b''
    def exercise(self,baseline=None,restored=None,fault=None):
        self.request['baseline']=baseline
        self.request['baseline_basis']='same_exported_snapshot' if baseline is not None else None
        def fake(d,args,**kwargs):
            if fault and kwargs.get('step')==fault:raise v.StepFailure(fault,fault=='restore')
            return self.fake(args,**kwargs)
        with patch.object(v.Docker,'run',fake),patch.object(v,'catalog',return_value=restored or {'coverage_gaps':[]}),patch.object(v.shutil,'disk_usage',return_value=type('Disk',(),{'free':5*1024**3})()):
            return v.verify(self.request,self.config)
    def test_restore_target_is_new_container_no_network_mount_or_port(self):
        result=self.exercise()
        args=next(c for c in self.calls if c[0]=='run')
        self.assertIn('--network=none',args);self.assertIn('--memory=512m',args)
        self.assertFalse(any(x in args for x in ['-p','--publish','-v','--volume','--network=host']))
        self.assertIn('--exit-on-error',next(c for c in self.calls if 'pg_restore' in c))
        self.assertEqual(result['restore_status'],'verified')
        self.assertEqual(result['integrity_status'],'not_verified')
        self.assertTrue(any(c[0:2]==['rm','-fv'] for c in self.calls))
    def test_same_snapshot_comparison_passes(self):
        base={k:[] for k in v.QUERIES};base.update(table_counts={'mm.material':5},coverage_gaps=[])
        result=self.exercise(base,base)
        self.assertEqual(result['integrity_status'],'verified')
    def test_count_mismatch_fails(self):
        base={k:[] for k in v.QUERIES};base.update(table_counts={'mm.material':5},coverage_gaps=[])
        target={**base,'table_counts':{'mm.material':4}}
        self.assertEqual(self.exercise(base,target)['status'],'failed')
    def test_checksum_mismatch_never_starts_docker(self):
        self.art.write_bytes(b'wrong')
        self.assertEqual(self.exercise()['failure_step'],'artifact_identity')
        self.assertFalse(any(c[0]=='run' for c in self.calls))
    def test_restore_error_fails_and_cleans_only_own_container(self):
        result=self.exercise(fault='restore')
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['restore_status'],'failed')
        self.assertTrue(any(c[0:2]==['rm','-fv'] and c[-1]=='cmab-mdm-verify-'+self.request['verification_id'] for c in self.calls))
    def test_environment_failure_is_incomplete(self):
        self.assertEqual(self.exercise(fault='image_unavailable')['status'],'incomplete')
    def test_rls_scope_gap_does_not_pass_integrity(self):
        base={k:[] for k in v.QUERIES};base.update(table_counts={},coverage_gaps=['row_level_security'])
        result=self.exercise(base,base)
        self.assertEqual(result['status'],'incomplete');self.assertEqual(result['restore_status'],'verified')
    def test_cleanup_error_preserves_restore_and_is_visible(self):
        self.exercise(fault='cleanup')
        report=v.read_json(self.export/(self.art.name+'.json'))
        self.assertEqual(report['cleanup_status'],'failed')
        self.assertEqual(report['verification']['restore_status'],'verified')
    def test_symlink_artifact_refused(self):
        self.art.unlink();self.art.symlink_to(self.root/'missing')
        self.assertEqual(self.exercise()['status'],'incomplete')
        self.assertFalse(any(c[0]=='run' for c in self.calls))
    def test_unpinned_image_refused(self):
        with self.assertRaises(ValueError):v.check_image('postgres:latest')
    def test_summary_excludes_baseline_and_business_rows(self):
        self.request['baseline']={'PRIVATE':'secret business value'}
        v.publish(self.request,{'status':'pending'},'not_started')
        value=(self.export/(self.art.name+'.json')).read_text()
        self.assertNotIn('PRIVATE',value);self.assertNotIn('secret business value',value)


if __name__=='__main__':unittest.main()
