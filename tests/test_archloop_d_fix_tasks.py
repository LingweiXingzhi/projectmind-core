from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

from extensions.continuity.store import Store
from extensions.continuity.fix_tasks import FixTaskService, render_fix_task
from extensions.handoff.architecture import ArchitectureError, build_version_handoff, source_locator
from tests.architecture_loop_acceptance.fixture import create, git, commit, GOOD


class FixTasksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.f=create(Path(self.tmp.name)/'fixture')
        self.store=Store(Path(self.tmp.name)/'continuity'/'records.sqlite3')
        self.service=FixTaskService(self.store, architecture_repo=self.f['architecture'],code_repositories=[self.f['code']])
        self.packet=build_version_handoff(self.f['versionEnvelope'],workspace_id='workspace-fixture',
            sources={'code':source_locator(self.f['code']),'architecture':source_locator(self.f['architecture'])})
        v=self.packet['versionEnvelope']['version']
        self.args=dict(packet=self.packet,deviation_id='deviation-bypass-C',deviation='B bypasses C',
            expected_process_ref={'processId':'process-ABC','stepIds':['step-B','step-C']},
            evidence=[{'kind':'test_observation','codeRevision':v['codeRevision'],'codeRepoId':v['codeRepoId'],
                'detail':'Fixture check_flow.py fails because trace lacks C; observation must be reproduced'}],
            scope=['flow.py'],acceptance='check_flow.py observes A B C',actor='TEST_ONLY')
        self.task=self.service.create_fix_task(**self.args)

    def tearDown(self):self.tmp.cleanup()

    def move(self,status,task=None):
        t=task or self.task
        return self.service.transition(t['id'],expected_revision=t['revision'],expected_map_revision=t['mapRevision'],
            status=status,actor='TEST_ONLY',description='Actual fixture transition')

    def start(self):
        self.task=self.move('received'); self.task=self.move('in_progress')
        git(self.f['code'], 'checkout', '-b', 'fix/fixture-bypass')

    def submit(self,sha):
        return self.service.submit(self.task['id'],expected_revision=self.task['revision'],
            expected_map_revision=self.task['mapRevision'],revision=sha,actor='TEST_ONLY',evidence='actual fixture commit')

    def fix(self):
        (Path(self.f['code'])/'flow.py').write_text(GOOD)
        return commit(self.f['code'],'actual fixture implementation fix')

    def test_idempotent_create_history_reopen_and_markdown(self):
        self.assertEqual(self.service.create_fix_task(**self.args),self.task)
        args={**self.args,'acceptance':'different contract'}
        with self.assertRaises(ArchitectureError) as e:self.service.create_fix_task(**args)
        self.assertEqual(e.exception.code,'REVISION_CONFLICT')
        self.assertIn('允许改动',render_fix_task(self.task))
        self.start();self.assertEqual(len(self.service.history(self.task['id'])),3)
        reopened=FixTaskService(self.store,architecture_repo=self.f['architecture'],code_repositories=[self.f['code']])
        self.assertEqual(reopened.get(self.task['id']),self.task)

    def test_real_fix_submission_then_test_and_confirmation(self):
        self.start();sha=self.fix();self.task=self.submit(sha)
        self.assertEqual(self.task['status'],'verification_pending'); self.assertNotEqual(self.task['deviationStatus'],'closed')
        token,result=self.service.run_fixture_verification(self.task['id'], command=[sys.executable,'-B','check_flow.py'],
            fixture_root=self.f['root'],observation='Actual trace A B C',recheck_ref='C_TEST_DOUBLE: test-only recheck, not real C')
        self.assertEqual(result['exitCode'],0)
        self.task=self.service.confirm_verification(self.task['id'],token=token,expected_revision=self.task['revision'],
            expected_map_revision=self.task['mapRevision'],actor='TEST_ONLY_SIMULATED_HUMAN',reason='fixture test observed required trace',human_confirmed=True)
        self.assertEqual(self.task['status'],'verified');self.assertTrue(self.task['verification']['fixtureOnly'])
        with self.assertRaises(ArchitectureError):self.service.confirm_verification(self.task['id'],token=token,
            expected_revision=self.task['revision'],expected_map_revision=self.task['mapRevision'],actor='T',reason='replay',human_confirmed=True)

    def test_failed_test_does_not_close_deviation(self):
        self.start();(Path(self.f['code'])/'flow.py').write_text("def execute():\n    return ['A']\n")
        self.task=self.submit(commit(self.f['code'],'still broken'))
        token,result=self.service.run_fixture_verification(self.task['id'],command=[sys.executable,'-B','check_flow.py'],
            fixture_root=self.f['root'],observation='Still wrong trace',recheck_ref='C_TEST_DOUBLE')
        self.assertNotEqual(result['exitCode'],0)
        with self.assertRaises(ArchitectureError) as e:self.service.confirm_verification(self.task['id'],token=token,
            expected_revision=self.task['revision'],expected_map_revision=self.task['mapRevision'],actor='T',reason='cannot close',human_confirmed=True)
        self.assertEqual(e.exception.code,'VERIFICATION_FAILED')
        self.assertEqual(self.service.get(self.task['id'])['status'],'verification_pending')

    def test_out_of_scope_intermediate_commit_cannot_be_hidden_by_revert(self):
        self.start()
        forbidden=Path(self.f['code'])/'unapproved.py'
        forbidden.write_text('outside allowed scope\n')
        commit(self.f['code'],'outside permitted task scope')
        forbidden.unlink()
        sha=self.fix()
        with self.assertRaises(ArchitectureError) as err:self.submit(sha)
        self.assertEqual(err.exception.code,'SCOPE_MISMATCH')
        self.assertEqual(self.service.get(self.task['id'])['status'],'in_progress')
        self.assertIsNone(self.service.get(self.task['id'])['submittedRevision'])

    def test_done_json_or_claim_is_not_verification(self):
        for status in ['verified','submitted','verification_pending']:
            with self.assertRaises(ArchitectureError):self.move(status)
        self.start();self.task=self.submit(self.fix())
        with self.assertRaises(ArchitectureError):self.service.confirm_verification(self.task['id'],token='AI says done',
            expected_revision=self.task['revision'],expected_map_revision=self.task['mapRevision'],actor='AI',reason='done',human_confirmed=True)

    def test_concurrent_stale_writers_no_overwrite(self):
        def writer():
            try:return self.move('received')['revision']
            except ArchitectureError as e:return e.code
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:writer(),range(2)))
        self.assertCountEqual(results,[2,'REVISION_CONFLICT'])
        with self.assertRaises(ArchitectureError):self.service.transition(self.task['id'],expected_revision=2,
            expected_map_revision='sha256:'+'0'*64,status='in_progress',actor='T',description='stale map')

    def test_out_of_scope_wrong_repo_missing_or_old_sha_rejected(self):
        self.start()
        for sha in [self.f['badRevision'],git(self.f['wrongCode'],'rev-parse','HEAD'),'0'*40]:
            with self.assertRaises(ArchitectureError):self.submit(sha)
        (Path(self.f['code'])/'outside.py').write_text('x=1\n')
        with self.assertRaises(ArchitectureError) as e:self.submit(commit(self.f['code'],'outside scope'))
        self.assertEqual(e.exception.code,'SCOPE_MISMATCH')

    def test_unrelated_branch_and_dirty_changes_rejected(self):
        self.start();sha=self.fix();p=Path(self.f['code'])/'unsaved';p.write_text('do not overwrite')
        with self.assertRaises(ArchitectureError):self.submit(sha)
        self.assertEqual(p.read_text(),'do not overwrite');p.unlink()
        git(self.f['code'],'checkout','--orphan','unrelated');git(self.f['code'],'rm','-rf','.')
        (Path(self.f['code'])/'flow.py').write_text('unrelated\n');sha=commit(self.f['code'],'unrelated root')
        with self.assertRaises(ArchitectureError) as e:self.submit(sha)
        self.assertEqual(e.exception.code,'STALE_CONTEXT')

    def test_unknown_process_planning_and_wrong_evidence_rejected(self):
        for changed in [dict(expected_process_ref={'processId':'unknown','stepIds':['step-B']}),
                        dict(evidence=[{'kind':'static_import','detail':'guess'}]),
                        dict(scope=['../outside'])]:
            with self.assertRaises(ArchitectureError):self.service.create_fix_task(**{**self.args,**changed})
        planning=build_version_handoff(self.f['planningEnvelope'],workspace_id='workspace-planning',
            sources={'code':None,'architecture':source_locator(self.f['architecture'])})
        with self.assertRaises(ArchitectureError) as e:self.service.create_fix_task(**{**self.args,'packet':planning})
        self.assertEqual(e.exception.code,'CODE_REQUIRED')

    def test_fixture_execution_cannot_target_formal_root(self):
        self.start();self.task=self.submit(self.fix())
        with self.assertRaises(ArchitectureError) as e:self.service.run_fixture_verification(self.task['id'],
            command=[sys.executable,'-B','check_flow.py'],fixture_root=self.f['code'],observation='x',recheck_ref='x')
        self.assertEqual(e.exception.code,'FORBIDDEN')

    def test_reject_then_rework_keeps_history(self):
        self.task=self.move('rejected');self.task=self.move('in_progress')
        self.assertEqual(self.task['status'],'in_progress')
        self.assertEqual([r['status'] for r in self.service.history(self.task['id'])],['queued','rejected','in_progress'])

    def test_second_client_receives_transfer_without_inheriting_verified(self):
        self.start();self.task=self.submit(self.fix())
        packet=self.service.export_task(self.task['id'])
        second=FixTaskService(Store(Path(self.tmp.name)/'second-continuity'/'records.sqlite3'),
            architecture_repo=self.f['secondArchitecture'],code_repositories=[self.f['secondCode']])
        received=second.receive_task(packet,actor='TEST_ONLY_SECOND')
        self.assertEqual(received['id'],self.task['id']);self.assertEqual(received['status'],'received')
        self.assertIsNone(received['submittedRevision']);self.assertIsNone(received['verification'])
        self.assertEqual(received['importedHistory']['status'],'verification_pending')
        self.assertEqual(second.receive_task(packet,actor='TEST_ONLY_SECOND'),received)
        broken=deepcopy(packet);broken['task']['acceptance']='tampered'
        with self.assertRaises(ArchitectureError):second.receive_task(broken,actor='T')

    def test_json_provider_is_not_actual_verification(self):
        self.start();sha=self.fix();self.task=self.submit(sha)
        self.service.verification_provider=lambda task:{'exitCode':0,'AI':'done'}
        with self.assertRaises(ArchitectureError) as e:self.service.run_verification(self.task['id'])
        self.assertEqual(e.exception.code,'EVIDENCE_MISMATCH')


if __name__=='__main__':unittest.main()
