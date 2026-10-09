"""D tool self-checks, never product acceptance."""
import ctypes
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
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
        self.assertIn('DIRTY_WORKTREE_CANARY', (self.repo / 'pkg/service.py').read_text(encoding='utf-8'))
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

    def _child_interpreter(self, extra_args, script, *args):
        result = subprocess.run([sys.executable, '-B', *extra_args, '-c', script,
                                 str(Path(__file__).resolve().parent), *args],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_manifest_round_trips_when_the_default_encoding_is_not_utf8(self):
        # R47-N1: with UTF-8 mode off the default codec is the locale codec. The
        # manifest holds non-ASCII text (the temp root name), so generate() and
        # cleanup() must agree on an explicit encoding, not on the default one.
        script = (
            'import sys;'
            'sys.path.insert(0, sys.argv[1]);'
            'import fixture;'
            'm = fixture.generate();'
            'raw = open(m["root"] + "/manifest.json", "rb").read();'
            'raw.decode("utf-8");'
            'fixture.cleanup(m);'
            'print("ROUNDTRIP_OK")'
        )
        stdout = self._child_interpreter(['-X', 'utf8=0'], script)
        self.assertIn('ROUNDTRIP_OK', stdout)

    def test_generated_revisions_do_not_depend_on_the_default_encoding(self):
        # The committed bytes, and therefore every revision, must be identical
        # whether or not UTF-8 mode is on.
        script = (
            'import json, sys;'
            'sys.path.insert(0, sys.argv[1]);'
            'import fixture;'
            'm = fixture.generate();'
            'print(json.dumps({k: m[k] for k in '
            '("baseRevision", "targetRevision", "secondRevision")}));'
            'fixture.cleanup(m)'
        )
        default = json.loads(self._child_interpreter([], script).strip().splitlines()[-1])
        locale_mode = json.loads(self._child_interpreter(['-X', 'utf8=0'], script).strip().splitlines()[-1])
        self.assertEqual(default, locale_mode)


class CleanupBoundaryTests(unittest.TestCase):
    """R40-C1: verification, traversal and deletion share handles bound under the owned root."""

    def setUp(self):
        if os.name != 'nt':
            self.skipTest('handle-bound cleanup is implemented for Windows only')

    def _owned_root(self, folder):
        root = Path(folder).resolve() / 'projectmind-d-fixture-handler'
        root.mkdir()
        return root

    def _make_junction(self, link, target):
        # A directory junction is a real reparse point and needs no privilege.
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.DeviceIoControl.restype = ctypes.c_int
        kernel32.DeviceIoControl.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
        handle = kernel32.CreateFileW(str(link), 0x40000000, 0, None, 3,
                                      0x00200000 | 0x02000000, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            return False
        try:
            substitute = ('\\??\\' + str(target)).encode('utf-16-le')
            payload = substitute + b'\x00\x00' + b'\x00\x00'
            raw = (struct.pack('<IHH', 0xA0000003, 8 + len(payload), 0) +
                   struct.pack('<HHHH', 0, len(substitute), len(substitute) + 2, 0) + payload)
            buffer = (ctypes.c_char * len(raw)).from_buffer_copy(raw)
            returned = ctypes.c_ulong()
            return bool(kernel32.DeviceIoControl(ctypes.c_void_p(handle), 0x000900A4, buffer,
                                                 len(raw), None, 0, ctypes.byref(returned), None))
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))

    def _redirected_root(self, folder):
        root = self._owned_root(folder)
        nested = root / 'nested'
        nested.mkdir()
        external = Path(folder).resolve() / 'external'
        external.mkdir()
        canary = external / 'object.bin'
        canary.write_bytes(b'canary')
        if not self._make_junction(nested, external):
            self.skipTest('directory junctions are unavailable here')
        return root, nested, canary

    def test_plain_readonly_file_inside_root_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            target = root / 'object.bin'
            target.write_bytes(b'x')
            os.chmod(target, stat.S_IREAD)
            fixture._remove_owned_tree(root)
            self.assertFalse(root.exists())

    def test_a_name_added_after_the_share_check_keeps_every_attribute(self):
        # A shared name can appear after the opened object was checked, so the
        # delete must not touch any attribute of the object: the read-only bit is
        # ignored, never cleared, and the surviving name keeps it.
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            inside = root / 'inside.bin'
            inside.write_bytes(b'shared')
            os.chmod(inside, stat.S_IREAD)
            outside = Path(folder).resolve() / 'canary.bin'
            real_dispose = fixture._dispose_handle

            def adding_alias(handle, path):
                if not outside.exists():
                    os.link(path, outside)
                return real_dispose(handle, path)

            with mock.patch.object(fixture, '_dispose_handle', side_effect=adding_alias):
                fixture._remove_owned_tree(root)
            self.assertFalse(inside.exists())
            self.assertTrue(outside.exists())
            self.assertTrue(outside.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)

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

    def test_a_non_bmp_name_never_deletes_its_sibling(self):
        # R47-N2: a non-BMP character is two UTF-16 code units, so a name whose
        # length was computed from Python characters used to be truncated and the
        # neighbouring name was deleted instead.
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            target = root / '\U0001F600a.bin'
            neighbour = root / '\U0001F600a.bi'
            target.write_bytes(b'target')
            neighbour.write_bytes(b'neighbour')
            fixture._remove_plain_object(root, target)
            self.assertFalse(target.exists())
            self.assertEqual(neighbour.read_bytes(), b'neighbour')

    def test_every_owned_name_is_removed_without_touching_its_siblings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            names = ['plain.txt', '\u4e2d\u6587.txt', '\U0001F600non-bmp.bin']
            for name in names:
                (root / name).write_bytes(name.encode('utf-8'))
            removed = set()
            for name in names:
                fixture._remove_plain_object(root, root / name)
                removed.add(name)
                for other in names:
                    self.assertEqual((root / other).exists(), other not in removed,
                                     f'{other!r} after removing {name!r}')

    def test_a_tree_holding_non_bmp_names_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            nested = root / '\U0001F4C1dir'
            nested.mkdir()
            payload = nested / '\U0001F600deep.bin'
            payload.write_bytes(b'deep')
            os.chmod(payload, stat.S_IREAD)
            fixture._remove_owned_tree(root)
            self.assertFalse(root.exists())

    def test_a_redirected_parent_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root, nested, canary = self._redirected_root(folder)
            try:
                with self.assertRaises(OSError):
                    fixture._remove_plain_object(root, nested / 'object.bin')
                with self.assertRaises(OSError):
                    fixture._remove_owned_tree(root)
                self.assertEqual(canary.read_bytes(), b'canary')
                self.assertTrue(canary.exists())
            finally:
                os.rmdir(nested)

    def test_a_parent_swapped_after_the_names_are_computed_cannot_redirect(self):
        # Emulates the reported race: the parent directory is redirected to an
        # external directory after the names were computed and before any object is
        # opened. Every open is relative to a handle already held, so the redirect
        # is refused and the external object is untouched.
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            nested = root / 'nested'
            nested.mkdir()
            (nested / 'object.bin').write_bytes(b'inside')
            external = Path(folder).resolve() / 'external'
            external.mkdir()
            canary = external / 'object.bin'
            canary.write_bytes(b'canary')
            real_parts = fixture._relative_parts
            state = {'swapped': False}

            def swapping_parts(owner, path):
                parts = real_parts(owner, path)
                if not state['swapped']:
                    os.rename(nested, root / 'nested-moved')
                    nested.mkdir()
                    if not self._make_junction(nested, external):
                        self.skipTest('directory junctions are unavailable here')
                    state['swapped'] = True
                return parts

            with mock.patch.object(fixture, '_relative_parts', side_effect=swapping_parts):
                with self.assertRaises(OSError):
                    fixture._remove_plain_object(root, nested / 'object.bin')
            self.assertEqual(canary.read_bytes(), b'canary')
            self.assertTrue(canary.exists())
            os.rmdir(nested)

    def test_a_failing_entry_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self._owned_root(folder)
            (root / 'a.bin').write_bytes(b'a')
            (root / 'b.bin').write_bytes(b'b')
            calls = []
            real_dispose = fixture._dispose_handle

            def refusing_once(handle, path):
                if Path(path).name == 'a.bin':
                    calls.append(path)
                    raise OSError('refused once')
                return real_dispose(handle, path)

            with mock.patch.object(fixture, '_dispose_handle', side_effect=refusing_once):
                with self.assertRaises(OSError):
                    fixture._remove_owned_tree(root)
            self.assertEqual(len(calls), 1)
            self.assertTrue((root / 'b.bin').exists())


if __name__ == '__main__': unittest.main()
