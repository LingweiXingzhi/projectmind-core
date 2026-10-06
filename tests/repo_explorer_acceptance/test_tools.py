"""D tool self-checks, never product acceptance."""
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock
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
    """R40-C1: verification, attribute change and deletion share one bound handle."""

    def _owned_root(self, folder):
        root = Path(folder).resolve() / 'projectmind-d-fixture-handler'
        root.mkdir()
        return root

    def test_plain_readonly_file_inside_root_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            target = root / 'object.bin'
            target.write_bytes(b'x')
            os.chmod(target, stat.S_IREAD)
            fixture._remove_owned_tree(root)
            self.assertFalse(root.exists())

    def test_shared_object_with_an_outside_name_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            outside = Path(folder).resolve() / 'canary.bin'
            outside.write_bytes(b'canary')
            hard = root / 'hard.bin'
            try:
                os.link(outside, hard)
            except OSError as exc:
                self.skipTest(f'hard links unavailable here: {exc}')
            self.assertEqual(os.lstat(hard).st_nlink, 2)
            os.chmod(hard, stat.S_IREAD)
            before = outside.stat().st_mode
            with self.assertRaises(OSError):
                fixture._remove_plain_object(root, hard)
            self.assertEqual(outside.stat().st_mode, before)
            self.assertTrue(outside.exists())
            self.assertTrue(hard.exists())

    def test_paths_outside_the_owned_root_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            outside = Path(folder).resolve() / 'outside.txt'
            outside.write_text('canary', encoding='utf-8')
            with self.assertRaises(OSError):
                fixture._remove_plain_object(root, outside)
            self.assertTrue(outside.exists())

    def test_redirected_parent_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            nested = root / 'nested'
            nested.mkdir()
            target = nested / 'object.bin'
            target.write_bytes(b'x')
            real_lstat = os.lstat

            def fake_lstat(path, *args, **kwargs):
                if os.path.abspath(path) == os.path.abspath(nested):
                    return SimpleNamespace(st_mode=stat.S_IFLNK, st_nlink=1, st_file_attributes=0)
                return real_lstat(path, *args, **kwargs)

            with mock.patch('os.lstat', side_effect=fake_lstat):
                with self.assertRaises(OSError):
                    fixture._remove_plain_object(root, target)
            self.assertTrue(target.exists())

    def test_object_replaced_after_inspection_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            target = root / 'object.bin'
            target.write_bytes(b'x')
            real_fstat = os.fstat

            def fake_fstat(fd):
                info = real_fstat(fd)
                return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino + 1, st_mode=info.st_mode)

            with mock.patch('os.fstat', side_effect=fake_fstat):
                with self.assertRaises(OSError):
                    fixture._remove_plain_object(root, target)
            self.assertTrue(target.exists())

    def test_undecidable_entry_metadata_is_never_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            target = root / 'object.bin'
            target.write_bytes(b'x')
            real_lstat = os.lstat

            def fake_lstat(path, *args, **kwargs):
                if os.path.abspath(path) == os.path.abspath(target):
                    raise OSError('metadata unavailable')
                return real_lstat(path, *args, **kwargs)

            with mock.patch('os.lstat', side_effect=fake_lstat):
                with self.assertRaises(OSError):
                    fixture._remove_plain_object(root, target)
            self.assertTrue(target.exists())

    def test_a_failing_entry_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            (root / 'a.bin').write_bytes(b'a')
            (root / 'b.bin').write_bytes(b'b')
            calls = []
            real_remove = fixture._remove_plain_object

            def counting_remove(owned_root, path):
                if Path(path).name == 'a.bin':
                    calls.append(path)
                    raise OSError('refused once')
                return real_remove(owned_root, path)

            with mock.patch.object(fixture, '_remove_plain_object', side_effect=counting_remove):
                with self.assertRaises(OSError):
                    fixture._remove_owned_tree(root)
            self.assertEqual(len(calls), 1)


if __name__ == '__main__': unittest.main()
