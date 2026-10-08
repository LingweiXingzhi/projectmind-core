"""Real Git, private directories and cold recovery; no fake cloud PASS."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from deployment.access import AccessError, create_account_file
from deployment.host import (prepare, render_domain, preflight, backup_bound, restore_bound,
                             stage_release, set_release_permissions, private_json)
from deployment.lease import ServingLease
from test_archloop_a_backend_b import tiny_code_repo, architecture_repo, run_git


class HostPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.code = tiny_code_repo(self.root)
        self.arch = architecture_repo(self.root)
        self.state = self.root/'state'; self.state.mkdir(mode=0o700)
        self.accounts = self.root/'accounts.json'
        create_account_file(self.accounts, 'fixture', 'synthetic-password-long-enough')
        self.config = self.root/'runtime.json'
        private_json(self.config, {'schemaVersion': 'projectmind_deploy_v1', 'publicOrigin': 'https://projectmind.example.invalid',
                     'accountsFile': str(self.accounts), 'dataRoot': str(self.state), 'codeRepositories': [str(self.code)],
                     'architectureRepo': str(self.arch), 'architectureBranch': 'architecture/candidates/archloop-test'})
        with sqlite3.connect(self.state/'fixture.sqlite3') as db:
            db.execute('CREATE TABLE notes(body TEXT)'); db.execute("INSERT INTO notes VALUES('unchanged fixture')")

    def test_domainless_bundle_no_start_no_password_and_shell_syntax(self):
        result = prepare(self.root/'bundle')
        self.assertTrue(result['domainPending']); self.assertFalse(result['servicesStarted'])
        self.assertEqual((self.root/'bundle/runtime.json').stat().st_mode & 0o777, 0o600)
        for script in (self.root/'bundle').glob('*.sh'):
            subprocess.run(['bash', '-n', str(script)], check=True)
        self.assertFalse((self.root/'bundle/accounts.json').exists())
        with self.assertRaises(AccessError): prepare(self.root/'bundle')

    def test_domain_validation_rejects_config_injection_before_output(self):
        for domain in ('a.example.com {\n reverse_proxy evil', 'https://a.example.com', 'a.example.com:8443', 'test.invalid'):
            with self.subTest(domain=domain), self.assertRaises(Exception): prepare(self.root/'bad', domain)
            self.assertFalse((self.root/'bad').exists())
        self.assertFalse(prepare(self.root/'real', 'pm.example.com')['domainPending'])

    def test_final_domain_render_preserves_registered_sources_and_original_config(self):
        before = self.config.read_bytes()
        result = render_domain(self.config, self.root/'final', 'pm.example.com')
        self.assertFalse(result['domainPending'])
        rendered = json.loads((self.root/'final/runtime.json').read_text())
        original = json.loads(before)
        self.assertEqual(rendered, dict(original, publicOrigin='https://pm.example.com'))
        self.assertEqual(self.config.read_bytes(), before)

    def test_read_only_preflight_and_public_placeholder_refusal(self):
        before = (self.state/'fixture.sqlite3').read_bytes()
        result = preflight(self.config)
        self.assertEqual(result['codeRepositoriesChecked'], 1)
        self.assertEqual(before, (self.state/'fixture.sqlite3').read_bytes())
        self.assertFalse(result['publicNetworkVerified'])
        with self.assertRaises(AccessError) as caught: preflight(self.config, public=True)
        self.assertEqual(caught.exception.code, 'DOMAIN_PENDING')

    def test_preflight_rejects_dirty_source_wrong_sha_and_permissions(self):
        head = run_git(self.code, 'rev-parse', 'HEAD')
        preflight(self.config, self.code, head)
        with self.assertRaises(AccessError): preflight(self.config, self.code, '0'*40)
        (self.code/'untracked').write_text('not committed')
        with self.assertRaises(AccessError): preflight(self.config)
        (self.code/'untracked').unlink(); self.config.chmod(0o644)
        with self.assertRaises(AccessError): preflight(self.config)

    def test_preflight_rejects_token_remote(self):
        run_git(self.code, 'remote', 'set-url', 'origin', 'https://token@example.invalid/private.git')
        with self.assertRaises(AccessError): preflight(self.config)

    def test_public_activation_rejects_runtime_port_mismatch(self):
        config = json.loads(self.config.read_text()); config['publicOrigin'] = 'https://pm.example.com:8443'
        self.config.write_text(json.dumps(config))
        with self.assertRaises(AccessError) as caught: preflight(self.config, public=True)
        self.assertEqual(caught.exception.code, 'HOST_DOMAIN_INVALID')

    def test_preflight_rejects_architecture_branch_or_dirty_tree(self):
        run_git(self.arch, 'checkout', '-b', 'wrong')
        with self.assertRaises(AccessError): preflight(self.config)
        run_git(self.arch, 'checkout', 'architecture/candidates/archloop-test')
        (self.arch/'README.md').write_text('unpublished architecture')
        with self.assertRaises(AccessError): preflight(self.config)

    def test_bound_backup_and_restore_preserve_bytes_and_no_sessions(self):
        before = (self.state/'fixture.sqlite3').read_bytes(); head = run_git(self.arch, 'rev-parse', 'HEAD')
        backup = self.root/'backup'; backup_bound(self.config, backup)
        result = restore_bound(backup, self.config, self.root/'restored', self.root/'recovered-runtime.json')
        self.assertTrue(result['restored']); self.assertFalse(result['serviceStarted']); self.assertFalse(result['sessionsRestored'])
        self.assertEqual((self.root/'restored/state/fixture.sqlite3').read_bytes(), before)
        self.assertEqual((self.state/'fixture.sqlite3').read_bytes(), before)
        self.assertEqual(run_git(self.root/'restored/architecture', 'rev-parse', 'HEAD'), head)
        self.assertEqual(preflight(self.root/'recovered-runtime.json')['architecture']['head'], head)

    def test_restore_refuses_active_service_without_creating_output(self):
        backup = self.root/'backup'; backup_bound(self.config, backup)
        with ServingLease(self.state):
            with self.assertRaises(AccessError) as caught:
                restore_bound(backup, self.config, self.root/'restored', self.root/'recovered.json')
            self.assertEqual(caught.exception.code, 'DATA_ROOT_IN_USE')
        self.assertFalse((self.root/'restored').exists())

    def test_restore_refuses_wrong_repository_binding_and_tampered_backup(self):
        backup = self.root/'backup'; backup_bound(self.config, backup)
        run_git(self.code, 'remote', 'set-url', 'origin', 'https://example.invalid/foreign.git')
        with self.assertRaises(AccessError): restore_bound(backup, self.config, self.root/'restored', self.root/'recovered.json')
        self.assertFalse((self.root/'restored').exists())
        run_git(self.code, 'remote', 'set-url', 'origin', 'https://example.invalid/demo-source.git')
        (backup/'state/fixture.sqlite3').write_bytes(b'tampered')
        with self.assertRaises(AccessError): restore_bound(backup, self.config, self.root/'restored', self.root/'recovered.json')
        self.assertFalse((self.root/'restored').exists())

    def test_restore_never_overwrites_config_or_existing_target(self):
        backup = self.root/'backup'; backup_bound(self.config, backup)
        with self.assertRaises(AccessError): restore_bound(backup, self.config, self.root/'restored', self.config)
        (self.root/'restored').mkdir(); (self.root/'restored/keep').write_text('keep')
        with self.assertRaises(AccessError): restore_bound(backup, self.config, self.root/'restored', self.root/'new.json')
        self.assertEqual((self.root/'restored/keep').read_text(), 'keep')

    def test_missing_binding_receipt_refused(self):
        backup = self.root/'backup'; backup_bound(self.config, backup)
        (self.root/'backup.binding.json').unlink()
        with self.assertRaises(AccessError): restore_bound(backup, self.config, self.root/'restored', self.root/'new.json')

    def test_fixed_release_has_history_and_independent_git_objects(self):
        head = run_git(self.code, 'rev-parse', 'HEAD')
        result = stage_release(self.code, head, self.root/'releases')
        self.assertFalse(result['activated'])
        app = self.root/'releases'/head/'app'
        self.assertEqual(run_git(app, 'rev-parse', 'HEAD'), head)
        self.assertFalse((app/'.git/objects/info/alternates').exists())
        with self.assertRaises(AccessError): stage_release(self.code, head, self.root/'releases')
        (self.code/'entry.py').write_text('uncommitted change')
        self.assertEqual((app/'entry.py').read_text(), 'def run():\n    return 1\n')

    def test_release_rejects_dirty_source_before_allocating_target(self):
        head = run_git(self.code, 'rev-parse', 'HEAD'); (self.code/'entry.py').write_text('dirty')
        with self.assertRaises(AccessError): stage_release(self.code, head, self.root/'releases')
        self.assertFalse((self.root/'releases').exists())

    def installed_release(self):
        head = run_git(self.code, 'rev-parse', 'HEAD')
        previous = os.umask(0o077)
        try:
            stage_release(self.code, head, self.root/'releases')
            release = self.root/'releases'/head
            (release/'venv/bin').mkdir(parents=True)
            script = release/'venv/bin/python'
            script.write_text('#!/bin/sh\nexit 0\n'); script.chmod(0o700)
        finally:
            os.umask(previous)
        return release

    def test_install_umask077_service_group_can_read_but_never_write(self):
        release = self.installed_release()
        self.assertEqual(release.stat().st_mode & 0o777, 0o700)
        private_before = self.accounts.stat().st_mode & 0o777
        result = set_release_permissions(release)
        self.assertTrue(result['serviceGroupReadOnly'])
        for path in (release, release/'app', release/'app/.git', release/'venv/bin'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o750)
        for path in (release/'app/entry.py', release/'app/.git/HEAD', release/'release.json'):
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual((release/'venv/bin/python').stat().st_mode & 0o777, 0o750)
        self.assertEqual(self.accounts.stat().st_mode & 0o777, private_before)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)

    def test_release_permissions_do_not_follow_external_symlinks(self):
        release = self.installed_release()
        outside = self.root/'private-outside'; outside.write_text('private'); outside.chmod(0o600)
        (release/'venv/external').symlink_to(outside)
        set_release_permissions(release)
        self.assertEqual(outside.stat().st_mode & 0o777, 0o600)
        self.assertTrue((release/'venv/external').is_symlink())

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX special-file refusal')
    def test_release_permissions_reject_special_files_before_chmod(self):
        release = self.installed_release()
        os.mkfifo(release/'unexpected-pipe')
        with self.assertRaises(AccessError):
            set_release_permissions(release)
        self.assertEqual(release.stat().st_mode & 0o777, 0o700)

    def test_restore_rejects_nested_output(self):
        backup = self.root/'backup'; backup_bound(self.config, backup)
        with self.assertRaises(AccessError): restore_bound(backup, self.config, self.state/'nested', self.root/'new.json')


if __name__ == '__main__': unittest.main()
