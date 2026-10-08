"""Cold backup integrity, lease refusal and preservation of existing directories."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from deployment.access import AccessError
from deployment.backup import cold_backup, inspect_backup
from deployment.lease import ServingLease
from test_archloop_a_backend_b import architecture_repo, run_git


@unittest.skipUnless(os.name=='posix', 'Cold backup uses POSIX service lease')
class ColdBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.state=self.root/'state';self.state.mkdir(mode=0o700)
        self.arch=architecture_repo(self.root);self.output=self.root/'cold-backup'
        self.config=self.root/'runtime.json'
        self.config.write_text(json.dumps({'schemaVersion':'projectmind_deploy_v1','dataRoot':str(self.state),
            'architectureRepo':str(self.arch),'accountsFile':str(self.root/'accounts.json')}))
        (self.root/'accounts.json').write_text('synthetic private account fixture; not real credentials')
        with sqlite3.connect(self.state/'fixture.sqlite3') as db:
            db.execute('CREATE TABLE notes(id INTEGER PRIMARY KEY,body TEXT)')
            db.execute('INSERT INTO notes VALUES(1,?)', ('Synthetic work record',))

    def test_round_trip_independent_files_and_read_only_inspection(self):
        head=run_git(self.arch,'rev-parse','HEAD');before=(self.state/'fixture.sqlite3').read_bytes()
        result=cold_backup(self.config,self.output);self.assertTrue(result['complete'])
        self.assertEqual(result['architecture']['head'],head);self.assertEqual(result['sqliteIntegrity'],{'fixture.sqlite3':'ok'})
        self.assertEqual(self.output.stat().st_mode & 0o777,0o700)
        self.assertEqual((self.output/'manifest.json').stat().st_mode & 0o777,0o600)
        self.assertFalse((self.output/'accounts.json').exists());self.assertFalse((self.output/'runtime.json').exists())
        self.assertFalse((self.output/'state/.serving.lock').exists())
        copied=(self.output/'state/fixture.sqlite3').read_bytes();self.assertEqual(copied,before)
        self.assertEqual(inspect_backup(self.output),result)
        self.assertEqual((self.state/'fixture.sqlite3').read_bytes(),before);self.assertEqual(run_git(self.arch,'rev-parse','HEAD'),head)
        (self.state/'fixture.sqlite3').write_bytes(b'changed original after completed copy')
        self.assertEqual((self.output/'state/fixture.sqlite3').read_bytes(),copied)
        self.assertTrue(inspect_backup(self.output)['complete'])

    def test_running_lease_rejected_without_output(self):
        with ServingLease(self.state):
            with self.assertRaises(AccessError) as raised:cold_backup(self.config,self.output)
            self.assertEqual(raised.exception.code,'DATA_ROOT_IN_USE')
        self.assertFalse(self.output.exists())

    def test_existing_output_preserved_and_nested_output_rejected(self):
        self.output.mkdir();marker=self.output/'keep.txt';marker.write_text('preserve')
        with self.assertRaises(AccessError):cold_backup(self.config,self.output)
        self.assertEqual(marker.read_text(),'preserve')
        with self.assertRaises(AccessError):cold_backup(self.config,self.state/'nested')
        self.assertFalse((self.state/'nested').exists())

    def test_tampered_added_or_incomplete_backup_rejected(self):
        cold_backup(self.config,self.output)
        file=self.output/'state/extra.txt';file.write_text('unlisted')
        with self.assertRaises(AccessError):inspect_backup(self.output)
        file.unlink();manifest=self.output/'manifest.json';doc=json.loads(manifest.read_text());doc['complete']=False
        manifest.write_text(json.dumps(doc))
        with self.assertRaises(AccessError):inspect_backup(self.output)

    def test_symlink_corrupt_sqlite_or_external_git_objects_rejected(self):
        link=self.state/'linked';link.symlink_to(self.root/'accounts.json')
        with self.assertRaises(AccessError):cold_backup(self.config,self.output)
        self.assertFalse(self.output.exists());link.unlink()
        alternates=self.arch/'.git/objects/info/alternates';alternates.write_text(str(self.root/'external-objects'))
        with self.assertRaises(AccessError):cold_backup(self.config,self.output)
        self.assertFalse(self.output.exists());alternates.unlink()
        (self.state/'fixture.sqlite3').write_bytes(b'not a database')
        with self.assertRaises(AccessError):cold_backup(self.config,self.output)
        self.assertFalse(self.output.exists())

    def test_credentials_in_data_root_rejected(self):
        config=json.loads(self.config.read_text());config['accountsFile']=str(self.state/'accounts.json')
        self.config.write_text(json.dumps(config))
        with self.assertRaises(AccessError):cold_backup(self.config,self.output)
        self.assertFalse(self.output.exists())
