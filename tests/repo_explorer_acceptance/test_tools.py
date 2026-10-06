"""D tool self-checks, never product acceptance."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import fixture
from fixture import generate, cleanup, git, tracked, blob, SYMBOLS, IMPORTS


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.m = generate()
        self.repo = Path(self.m['repository'])

    def tearDown(self):
        cleanup(self.m)

    def test_two_actual_commits_and_fixed_changes(self):
        self.assertEqual(git(self.repo, 'rev-list', '--count', 'HEAD').strip(), b'2')
        self.assertEqual(self.m['expectedChanges'], [
            {'status': 'A', 'path': 'pkg/new.py', 'oldPath': None},
            {'status': 'D', 'path': 'pkg/old.py', 'oldPath': None},
            {'status': 'R', 'path': 'pkg/relocated.py', 'oldPath': 'pkg/moved.py'},
            {'status': 'M', 'path': 'pkg/service.py', 'oldPath': None}])
        self.assertRegex(self.m['baseRevision'], r'^[a-f0-9]{40}$')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD').decode().strip(), self.m['targetRevision'])

    def test_isolated_same_name_repositories_no_map_no_execution(self):
        self.assertEqual(self.repo.name, Path(self.m['secondRepository']).name)
        self.assertNotEqual(git(self.repo, 'rev-parse', '--git-common-dir'), b'../other\n')
        self.assertNotEqual(self.m['targetRevision'], self.m['secondRevision'])
        self.assertFalse(self.m['facts']['mapJson'])
        self.assertFalse(self.m['facts']['sourceExecuted'])
        self.assertFalse((self.repo / 'EXECUTED_MARKER').exists())
        self.assertNotIn('untracked-only.py', self.m['targetPaths'])
        self.assertNotIn('DIRTY_WORKTREE_CANARY', blob(self.repo, self.m['targetRevision'], 'pkg/service.py').decode())
        self.assertIn('DIRTY_WORKTREE_CANARY', (self.repo / 'pkg/service.py').read_text())
        self.assertEqual(self.m['targetPaths']['outside-link'], '120000')
        self.assertEqual(self.m['targetPaths']['vendor/submodule'], '160000')

    def test_fixed_line_oracles_can_be_checked_without_product_parser(self):
        lines = blob(self.repo, self.m['baseRevision'], 'pkg/service.py').decode().splitlines()
        for name, qualified, kind, start, end, doc in SYMBOLS:
            self.assertIn(('class ' if kind == 'class' else 'def ') + name, lines[start - 1])
            self.assertTrue(lines[end - 1].strip())
        for kind, module, level, name, alias, start, end, status, target in IMPORTS:
            self.assertIn('import', lines[start - 1])
            self.assertEqual(start, end)
        self.assertEqual(len(lines), 32)

    def test_rebuild_same_git_shas(self):
        other = generate()
        try:
            for field in ['baseRevision', 'targetRevision', 'secondRevision', 'expectedChanges']:
                self.assertEqual(self.m[field], other[field])
        finally: cleanup(other)

    def test_cleanup_refuses_redirected_root_and_fixture_parent_repo(self):
        forged = dict(self.m, root=str(self.repo))
        with self.assertRaises(ValueError): cleanup(forged)
        with self.assertRaises(ValueError): generate(self.repo)
        with tempfile.TemporaryDirectory() as folder:
            changed = dict(self.m, repository=folder)
            with self.assertRaises(ValueError): cleanup(changed)
        self.assertTrue(self.repo.exists())


class CleanupRetryBoundaryTests(unittest.TestCase):
    """R40-C1: the read-only retry stays inside the owned root and only for permission errors."""

    def _owned_root(self, folder):
        root = Path(folder).resolve() / 'projectmind-d-fixture-handler'
        root.mkdir()
        return root

    def test_non_permission_errors_are_never_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            handler = fixture._make_cleanup_handler(root)
            calls = []
            with self.assertRaises(OSError):
                handler(lambda path: calls.append(path), str(root / 'object.bin'), OSError('boom'))
            self.assertEqual(calls, [])

    def test_paths_outside_the_owned_root_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            outside = Path(folder).resolve() / 'outside.txt'
            outside.write_text('canary', encoding='utf-8')
            handler = fixture._make_cleanup_handler(root)
            calls = []
            with self.assertRaises(PermissionError):
                handler(lambda path: calls.append(path), str(outside), PermissionError('denied'))
            self.assertEqual(calls, [])
            self.assertTrue(outside.exists())

    def test_readonly_file_inside_root_is_cleared_and_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            target = root / 'object.bin'
            target.write_bytes(b'x')
            os.chmod(target, stat.S_IREAD)
            handler = fixture._make_cleanup_handler(root)
            removed = []
            handler(lambda path: (os.unlink(path), removed.append(path)), str(target), PermissionError('denied'))
            self.assertEqual(removed, [str(target)])
            self.assertFalse(target.exists())


if __name__ == '__main__': unittest.main()
