from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest

from extensions.handoff.architecture import (ArchitectureError, build_version_handoff,
    digest, inspect_version_handoff, render_version_handoff, validate_handoff, source_locator)
from tests.architecture_loop_acceptance.fixture import create


class SameVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = create(Path(self.tmp.name)/'fixture')
        self.packet = build_version_handoff(self.f['versionEnvelope'], workspace_id='workspace-fixture',
            sources={'code': source_locator(self.f['code']), 'architecture': source_locator(self.f['architecture'])})

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, packet=None, **overrides):
        return inspect_version_handoff(packet or self.packet,
            **{'architecture_repo': self.f['secondArchitecture'], 'code_repo': self.f['secondCode'], **overrides})

    def test_two_independent_clones_exact_version_no_formal_write(self):
        before = self.packet.copy()
        result = self.check()
        self.assertEqual(result['status'], 'same_version_git_checked')
        self.assertEqual(result['versionEnvelope'], self.packet['versionEnvelope'])
        self.assertFalse(result['formalMapWritten'])
        self.assertEqual(self.packet, before)
        self.assertNotEqual(result['codeRevision'], result['mapSourceRevision'])
        self.assertIsNone(result['verifiedCodeRevision'])
        self.assertIn('核查范围', render_version_handoff(self.packet))

    def test_tampered_packet_even_rehashed_is_not_git_version(self):
        bad = deepcopy(self.packet); bad['task']['nextAction'] = 'changed'
        with self.assertRaises(ArchitectureError):self.check(bad)
        env = deepcopy(self.f['versionEnvelope']); env['version']['graph']['nodes'][0]['title'] = 'forged'
        with self.assertRaises(ArchitectureError):build_version_handoff(env, workspace_id='workspace-fixture', sources=self.packet['sources'])
        bad = deepcopy(self.packet); bad['versionEnvelope']['provenance']['mapSourceRevision'] = '0'*40
        bad['transportDigest'] = digest({k:v for k,v in bad.items() if k != 'transportDigest'})
        with self.assertRaises(ArchitectureError):self.check(bad)

    def test_wrong_same_name_repo_rejected(self):
        with self.assertRaises(ArchitectureError) as err:self.check(code_repo=self.f['wrongCode'])
        self.assertEqual(err.exception.code, 'STALE_CONTEXT')

    def test_dirty_workspaces_preserved(self):
        for key, option in [('secondCode','code_repo'), ('secondArchitecture','architecture_repo')]:
            path = Path(self.f[key])/'unsaved.txt'; path.write_text('keep me')
            with self.assertRaises(ArchitectureError) as err:self.check(**{option:self.f[key]})
            self.assertEqual(err.exception.code, 'DIRTY_WORKSPACE'); self.assertEqual(path.read_text(),'keep me'); path.unlink()

    def test_planning_null_sha_round_trip(self):
        p = build_version_handoff(self.f['planningEnvelope'], workspace_id='workspace-planning',
            sources={'code':None,'architecture':source_locator(self.f['architecture'])})
        result = self.check(p, code_repo=None)
        self.assertIsNone(result['codeRepoId']); self.assertIsNone(result['codeRevision'])
        self.assertEqual(result['graphStatus'], 'confirmed_design')

    def test_missing_source_is_draft_not_trusted(self):
        e = deepcopy(self.f['versionEnvelope']);e['provenance']['mapSourceRevision']=None
        p = build_version_handoff(e, workspace_id='workspace-fixture', sources=self.packet['sources'])
        with self.assertRaises(ArchitectureError) as err:self.check(p)
        self.assertEqual(err.exception.code,'SOURCE_REQUIRED')

    def test_credentials_and_bad_shapes_rejected(self):
        with self.assertRaises(ArchitectureError):build_version_handoff(self.f['versionEnvelope'], workspace_id='workspace-fixture', sources={'code':'https://user:secret@host/repo','architecture':'x'})
        for value in [None, [], {'schemaVersion':'architecture_handoff_v1'}]:
            with self.assertRaises(ArchitectureError):validate_handoff(value)

    def test_inherited_git_environment_does_not_redirect_checks(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'GIT_DIR':str(Path(self.f['wrongCode'])/'.git')}):
            self.assertEqual(self.check()['codeRevision'], self.f['badRevision'])

    def test_worklog_snapshot_reads_fixed_version_without_writing_original(self):
        from extensions.worklog.store import Store
        from extensions.handoff.architecture import capture_worklog_refs
        store=Store(Path(self.tmp.name)/'worklog'/'records.sqlite3')
        entry=store.save({'title':'actual log','body':'original evidence','author':'TEST_ONLY',
            'category':'daily','date':'2026-10-07'},self.f['badRevision'])
        store.save({**entry,'expectedVersion':1,'body':'later version'},self.f['badRevision'])
        before=store.path.read_bytes()
        refs=capture_worklog_refs(store,[{'id':entry['id'],'version':1}])
        self.assertEqual(refs[0]['body'],'original evidence')
        self.assertEqual(refs[0]['status'],'contributor_record_unverified')
        self.assertEqual(store.path.read_bytes(),before)


if __name__ == '__main__':unittest.main()
