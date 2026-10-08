"""Independent Git evidence and safe runner failure reporting."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from archloop.acceptance import (Acceptance, independent_self_coverage_verdict,
                                native_handover_tamper_verdict)
from archloop.acceptance_http import AcceptanceHTTP


class AcceptanceRepairTests(unittest.TestCase):
    def repo(self, root, name):
        repo = root / name; repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                stderr=subprocess.DEVNULL, env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')}).strip()
        git('init'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'fixture')
        for index in range(60):
            (repo / f'file{index}.py').write_text('def fixture(): return 1\n')
        git('add', '.'); git('commit', '-m', 'first')
        return repo, git

    def body(self, head):
        return {'graph': {'nodes': [{'id': 'fixture'}]}, 'contextCoverage': {
            'codeRevision': head, 'trackedFiles': 60, 'pythonFiles': 60}}

    def test_current_head_passes_and_stale_response_fails_at_same_tree_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, git = self.repo(Path(directory), 'repo')
            old = git('rev-parse', 'HEAD')
            status, _ = independent_self_coverage_verdict(200, self.body(old), str(repo), {'codeRevision': old})
            self.assertEqual(status, 'PASS')
            (repo / 'file0.py').write_text('def fixture(): return 2\n')
            git('add', '.'); git('commit', '-m', 'second')
            head = git('rev-parse', 'HEAD')
            status, evidence = independent_self_coverage_verdict(200, self.body(old), str(repo), {'codeRevision': old})
            self.assertEqual(status, 'FAIL')
            self.assertEqual(evidence['localHead'], head)
            self.assertFalse(evidence['revisionMatchesCoverage'])
            self.assertTrue(evidence['treeMatchesRepository'])

    def test_inherited_git_environment_cannot_choose_another_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, git = self.repo(root, 'repo'); other, _ = self.repo(root, 'hostile')
            head = git('rev-parse', 'HEAD')
            with patch.dict(os.environ, {'GIT_DIR': str(other / '.git'), 'GIT_WORK_TREE': str(other)}):
                status, evidence = independent_self_coverage_verdict(200, self.body(head), str(repo), {'codeRevision': head})
            self.assertEqual(status, 'PASS'); self.assertEqual(evidence['localHead'], head)

    def test_invalid_original_packet_is_not_tamper_detection(self):
        status, evidence = native_handover_tamper_verdict({'schemaVersion': 'architecture_handoff_v1'})
        self.assertEqual(status, 'FAIL'); self.assertFalse(evidence['originalValid'])

    def test_cleartext_credentials_and_arbitrary_request_target_refused(self):
        client = AcceptanceHTTP('http://127.0.0.1:1')
        with self.assertRaises(ValueError): client.login('fixture', 'synthetic')
        for origin in ('http://remote.example.invalid', 'https://u:p@example.invalid', 'https://example.invalid/api'):
            with self.assertRaises(ValueError): AcceptanceHTTP(origin)
        with self.assertRaises(ValueError): client.request('POST', '//elsewhere.invalid/api', {})

    def test_runner_refuses_default_fixture_mutations_before_http(self):
        runner = Acceptance('http://127.0.0.1:1', '/does-not-exist')
        with patch.object(runner.client, 'request') as request:
            with self.assertRaises(ValueError): runner.run()
            request.assert_not_called()

    def test_https_repository_input_requires_explicit_registered_alias(self):
        client = AcceptanceHTTP('https://example.invalid')
        client.auth = {'Cookie': 'SYNTHETIC', 'X-ProjectMind-CSRF': 'SYNTHETIC'}
        client.repositories = [{'key': 'registered:fixture'}]
        runner = Acceptance(client.origin, '/tmp/fixture', client=client, repo_key='registered:fixture')
        with patch.object(client, 'request', return_value=(200, {}, {})) as request:
            runner.call('POST', '/api/archloop/workspaces', {'repoPath': '/tmp/fixture'})
            self.assertEqual(request.call_args.args[2]['repoPath'], 'registered:fixture')
        runner.repo_key = 'registered:unlisted'
        with patch.object(client, 'request') as request:
            with self.assertRaises(ValueError): runner.call('POST', '/api/archloop/workspaces', {'repoPath': '/tmp/fixture'})
            request.assert_not_called()
