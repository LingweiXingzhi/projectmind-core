"""Real production HTTP + B publication + private D task storage; fixture approvals only."""
import json
from pathlib import Path
import secrets
import sys
import unittest

import test_public_deployment as fixtures
from deployment.server import build_application


@unittest.skipUnless(__import__('os').name == 'posix', 'Public mode requires POSIX permissions')
class PublicGovernedTaskTests(fixtures.PublicHTTPTests):
    def published(self, auth, planning=False, verify_code=False):
        path, envelope = self.workspace(auth, planning=planning)
        self.assertEqual(self.request('GET', path+'/fix-task-hints', auth=auth)[0], 403)
        node = envelope['draft']['graph']['nodes'][0]['id']
        status, _, envelope = self.request('POST', path+'/apply-ops', {
            'expectedDraftRevision': envelope['draft']['draftRevision'],
            'operations': [{'type': 'update_process', 'nodeId': node, 'process': [
                {'stepId': 'fixture-return', 'title': '返回预期值', 'detail': 'TEST ONLY expected behavior',
                 'inputs': [], 'outputs': [], 'branches': [], 'next': []}]}]}, auth=auth)
        self.assertEqual(status, 200, envelope)
        status, _, preview = self.request('POST', path+'/review-preview', {
            'verifyCode': verify_code, 'reason': 'FIXTURE ONLY simulated explicitly scoped review'}, auth=auth)
        self.assertEqual(status, 200, preview)
        self.assertEqual(self.request('POST', path+'/review-confirm', {
            'previewDigest': preview['previewDigest'], 'decision': 'accept'}, auth=auth)[0], 200)
        status, _, publication = self.request('POST', path+'/publish', {}, auth=auth)
        self.assertEqual(status, 200, publication)
        status, _, hints = self.request('GET', path+'/fix-task-hints', auth=auth)
        self.assertEqual(status, 200, hints)
        if verify_code:
            return path, None, publication
        self.assertTrue(hints['processes'])
        process = hints['processes'][0]
        body = {'expectedMapRevision': hints['mapRevision'], 'expectedDraftRevision': hints['draftRevision'],
            'expectedProcessRef': {'processId': process['id'], 'stepIds': [process['steps'][0]['id']]},
            'deviation': 'TEST ONLY participant observation of unexpected return', 'scope': ['service.py'],
            'evidence': [{'kind': 'test_observation', 'detail': 'Synthetic observation, not real team verification',
                          'codeRepoId': hints['codeRepoId'], 'codeRevision': hints['codeRevision']}],
            'acceptance': 'FIXTURE ONLY: serve returns 3', 'actor': 'FORGED_JSON_ACTOR'}
        return path, body, publication

    def create_task(self, auth):
        path, body, publication = self.published(auth)
        status, _, task = self.request('POST', path+'/fix-tasks', body, auth=auth)
        self.assertEqual(status, 200, task)
        self.assertEqual(task['actor'], 'fixture')
        self.assertEqual(task['actorIdentity'], 'authenticated_account')
        self.assertEqual(task['mapRevision'], publication['version']['mapRevision'])
        return path, body, task

    def action(self, path, task, action, auth, **values):
        body = {'action': action, **values}
        if action != 'verification_preview':
            body.update(expectedRevision=task['revision'], expectedMapRevision=task['mapRevision'])
        return self.request('POST', path+'/fix-tasks/'+task['id']+'/governance', body, auth=auth)

    def submitted(self, auth):
        path, _, task = self.create_task(auth)
        for state in ('received', 'in_progress'):
            status, _, task = self.action(path, task, 'transition', auth, status=state, description='FIXTURE feedback')
            self.assertEqual(status, 200, task)
        old_branch = fixtures.run_git(self.code, 'branch', '--show-current')
        fixtures.run_git(self.code, 'checkout', '-b', 'feat/fixture-'+secrets.token_hex(6))
        self.addCleanup(lambda: fixtures.run_git(self.code, 'checkout', old_branch))
        (self.code/'service.py').write_text('def serve():\n    return 3\n')
        fixtures.run_git(self.code, 'add', 'service.py')
        fixtures.run_git(self.code, 'commit', '-m', 'synthetic scoped implementation')
        revision = fixtures.run_git(self.code, 'rev-parse', 'HEAD')
        status, _, task = self.action(path, task, 'submit', auth, revision=revision,
                                    evidence='TEST ONLY committed fixture change, not proof of correctness')
        self.assertEqual(status, 200, task)
        self.assertEqual(task['status'], 'verification_pending')
        return path, task

    def test_formal_version_task_retry_rebuild_and_private_storage(self):
        auth = self.login()
        before = (fixtures.run_git(self.code, 'rev-parse', 'HEAD'), fixtures.run_git(self.code, 'status', '--porcelain'))
        path, body, task = self.create_task(auth)
        self.assertTrue(task['mapRevision'].startswith('sha256:'))
        self.assertNotIn('versionHandoff', task)
        self.assertNotIn(str(self.root), json.dumps(task))
        status, _, repeated = self.request('POST', path+'/fix-task', body, auth=auth)
        self.assertEqual(status, 200, repeated); self.assertEqual(repeated['id'], task['id'])
        other = self.login()
        status, _, listed = self.request('GET', path+'/fix-tasks', auth=other)
        self.assertEqual(status, 200); self.assertIn(task['id'], [t['id'] for t in listed['tasks']])
        self.assertEqual(self.request('GET', path+'/fix-tasks/'+task['id']+'/markdown', auth=other)[0], 200)
        rebuilt = build_application(self.config)
        self.assertEqual(rebuilt.service.backend_d.service.get(task['id'])['mapRevision'], task['mapRevision'])
        self.assertEqual(rebuilt.service.backend_d.store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(rebuilt.service.backend_d.store.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(before, (fixtures.run_git(self.code, 'rev-parse', 'HEAD'), fixtures.run_git(self.code, 'status', '--porcelain')))

    def test_static_code_review_does_not_expand_into_expected_process_confirmation(self):
        auth = self.login(); path, _, publication = self.published(auth, verify_code=True)
        hints = self.request('GET', path+'/fix-task-hints', auth=auth)[2]
        self.assertFalse(hints['canCreate'])
        self.assertEqual(hints['disabledReason'], 'EXPECTED_PROCESS_REVIEW_REQUIRED')
        self.assertEqual(hints['processes'], [])
        self.assertTrue(any(n['process'] for n in publication['envelope']['draft']['graph']['nodes']))
        self.assertEqual(publication['reviewCoverage']['processes'], [])

    def test_stale_scope_planning_wrong_workspace_and_edited_draft_rejected(self):
        auth = self.login(); path, body, task = self.create_task(auth)
        for change, expected in (({'expectedMapRevision': 'sha256:'+'f'*64}, 409),
                                 ({'scope': ['../outside.py']}, 409), ({'command': ['arbitrary']}, 400)):
            self.assertEqual(self.request('POST', path+'/fix-tasks', dict(body, **change), auth=auth)[0], expected)
        other_path, _, _ = self.published(auth)
        self.assertEqual(self.action(other_path, task, 'transition', auth, status='received', description='wrong workspace')[0], 404)
        planning_path, planning_body, _ = self.published(auth, planning=True)
        status, _, error = self.request('POST', planning_path+'/fix-tasks', planning_body, auth=auth)
        self.assertEqual(status, 409, error); self.assertEqual(error['error']['code'], 'CODE_REQUIRED')
        opened = self.request('GET', path, auth=auth)[2]
        node = opened['draft']['graph']['nodes'][0]['id']
        self.assertEqual(self.request('POST', path+'/apply-ops', {'expectedDraftRevision': opened['draft']['draftRevision'],
            'operations': [{'type': 'update_node', 'nodeId': node, 'fields': {'summary': 'new unreviewed fixture draft'}}]}, auth=auth)[0], 200)
        self.assertEqual(self.request('GET', path+'/fix-task-hints', auth=auth)[0], 409)

    def test_submit_requires_real_branch_and_no_configured_verifier_cannot_close(self):
        auth = self.login(); path, task = self.submitted(auth)
        status, _, error = self.action(path, task, 'verification_preview', auth)
        self.assertEqual(status, 503, error); self.assertEqual(error['error']['code'], 'BACKEND_UNAVAILABLE')
        self.assertEqual(self.action(path, task, 'confirm_verification', auth,
                                    confirmationToken='forged', reason='TEST ONLY')[0], 403)
        self.assertEqual(self.request('POST', path+'/fix-tasks/'+task['id'], {'status': 'verified'}, auth=auth)[0], 400)
        self.assertEqual(self.application.service.backend_d.service.get(task['id'])['status'], 'verification_pending')

    def test_actual_fixture_verification_confirmation_is_bound_to_browser_and_consumed(self):
        auth = self.login(); path, task = self.submitted(auth)
        (self.root/'.projectmind-test-fixture').write_text('explicit synthetic test fixture only\n')
        gateway = self.application.service.backend_d.gateway
        original_provider = gateway.preview_provider
        self.addCleanup(lambda: setattr(gateway, 'preview_provider', original_provider))
        gateway.preview_provider = lambda task_id: gateway.service.run_fixture_verification(task_id,
            command=[sys.executable, '-B', '-c', 'import runpy,sys; assert runpy.run_path(sys.argv[1])["serve"]()==3',
                     'service.py'], fixture_root=self.root,
            observation='Actual synthetic fixture check; real team behavior NOT_RUN',
            recheck_ref='C_TEST_DOUBLE; real C NOT_RUN')
        status, _, preview = self.action(path, task, 'verification_preview', auth)
        self.assertEqual(status, 200, preview); self.assertTrue(preview['verification']['fixtureOnly'])
        values = {'confirmationToken': preview['confirmationToken'], 'reason': 'FIXTURE ONLY simulated human decision'}
        other = self.login()
        self.assertEqual(self.action(path, task, 'confirm_verification', other, **values)[0], 403)
        status, _, verified = self.action(path, task, 'confirm_verification', auth, **values)
        self.assertEqual(status, 200, verified); self.assertEqual(verified['status'], 'verified')
        self.assertEqual(verified['verification']['actorIdentity'], 'authenticated_account')
        self.assertTrue(verified['verification']['fixtureOnly'])
        self.assertEqual(self.action(path, task, 'confirm_verification', auth, **values)[0], 403)


# Reuse the server/fixture helpers, without rerunning the parent suite.
for _name in fixtures.PublicHTTPTests.__dict__:
    if _name.startswith('test_'):
        setattr(PublicGovernedTaskTests, _name, None)
