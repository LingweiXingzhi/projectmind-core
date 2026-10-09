"""Build independent committed fixtures. Never import or execute their source."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

FORMAT = 'projectmind-repo-explorer-fixture-v1'
SERVICE = '''import os
import pkg.utils as utilities
from .utils import helper as h
from . import utils
import missing_dependency_xyz
from dual import thing
# import fake_comment_module
FAKE = "def imagined(): pass"

def top():
    """中文顶层函数。"""
    return h(1)

class Service:
    """示例服务。"""
    def run(self):
        def nested():
            return "嵌套"
        return nested()

    async def fetch(self):
        return 2

async def async_top():
    return 3

if False:
    import pkg.utils as conditional

def local():
    from .utils import helper as inside
    return inside(2)
'''
SYMBOLS = [
    ('top', 'top', 'function', 10, 12, '中文顶层函数。'),
    ('Service', 'Service', 'class', 14, 22, '示例服务。'),
    ('run', 'Service.run', 'method', 16, 19, None),
    ('nested', 'Service.run.nested', 'function', 17, 18, None),
    ('fetch', 'Service.fetch', 'async_method', 21, 22, None),
    ('async_top', 'async_top', 'async_function', 24, 25, None),
    ('local', 'local', 'function', 30, 32, None),
]
IMPORTS = [
    ('import', 'os', 0, None, None, 1, 1, 'unresolved', None),
    ('import', 'pkg.utils', 0, None, 'utilities', 2, 2, 'resolved', 'pkg/utils.py'),
    ('from', 'utils', 1, 'helper', 'h', 3, 3, 'resolved', 'pkg/utils.py'),
    ('from', '', 1, 'utils', None, 4, 4, 'resolved', 'pkg/utils.py'),
    ('import', 'missing_dependency_xyz', 0, None, None, 5, 5, 'unresolved', None),
    ('from', 'dual', 0, 'thing', None, 6, 6, 'ambiguous', None),
    ('import', 'pkg.utils', 0, None, 'conditional', 28, 28, 'resolved', 'pkg/utils.py'),
    ('from', 'utils', 1, 'helper', 'inside', 31, 31, 'resolved', 'pkg/utils.py'),
]


def git(repo, *args, raw=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(repo), *args],
                                   input=raw, env=env, stderr=subprocess.PIPE, timeout=30)


def tracked(repo, revision):
    records = git(repo, 'ls-tree', '-r', '-z', revision).split(b'\0')
    return {r.split(b'\t', 1)[1].decode('utf-8'): r.split(b' ', 1)[0].decode('utf-8')
            for r in records if r}


def blob(repo, revision, path):
    # Only used with manifest-controlled fixture paths, never an HTTP path.
    return git(repo, 'show', revision + ':' + path)


def changes(repo, base, target):
    parts = git(repo, 'diff', '--name-status', '-z', '--find-renames=50%', base, target, '--').split(b'\0')
    result, i = [], 0
    while i < len(parts) and parts[i]:
        code = parts[i].decode('utf-8'); i += 1
        if code[0] in ('R', 'C'):
            old, path = parts[i:i + 2]; i += 2
        else:
            old, path = None, parts[i]; i += 1
        result.append({'status': code[0], 'path': path.decode('utf-8'),
                       'oldPath': old.decode('utf-8') if old else None})
    return result


def init(repo):
    repo.mkdir(parents=True)
    git(repo, 'init', '-q', '-b', 'fixture')
    git(repo, 'config', 'user.name', 'ProjectMind fixture')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    git(repo, 'config', 'core.autocrlf', 'false')


def write(repo, path, content):
    # Every text write is UTF-8, never the interpreter's default codec, so the
    # committed bytes do not depend on the locale or on UTF-8 mode.
    p = repo / path; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content.encode('utf-8') if isinstance(content, str) else content)


def commit(repo, title, timestamp):
    git(repo, 'add', '--all')
    tree = git(repo, 'write-tree').decode('utf-8').strip()
    # commit-tree avoids inherited hooks and signing; dates and identities are fixed.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME='ProjectMind fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='ProjectMind fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
               GIT_AUTHOR_DATE=timestamp, GIT_COMMITTER_DATE=timestamp)
    parent = git(repo, 'rev-parse', '--verify', 'HEAD').decode('utf-8').strip() if (repo / '.git/refs/heads/fixture').exists() else None
    command = ['git', '--no-replace-objects', '-C', str(repo), 'commit-tree', tree]
    if parent: command += ['-p', parent]
    sha = subprocess.check_output(command, input=(title + '\n').encode('utf-8'), env=env).decode('utf-8').strip()
    git(repo, 'update-ref', 'refs/heads/fixture', sha)
    return sha


def generate(parent=None):
    if parent is not None:
        parent = Path(parent).resolve()
        if any((p / '.git').exists() for p in (parent, *parent.parents)):
            raise ValueError('Fixture parent must be outside existing repositories')
    root = Path(tempfile.mkdtemp(prefix='projectmind-d-fixture-', dir=parent)).resolve()
    (root / '.d-fixture-owner').write_text(FORMAT, encoding='utf-8')
    first, second = root / 'first' / 'sample', root / 'second' / 'sample'
    init(second)
    write(second, 'pkg/service.py', 'def second_only():\n    """第二仓库独有。"""\n    return 99\n')
    write(second, 'second-only.txt', '第二仓库\n')
    second_sha = commit(second, 'second repository', '2026-10-01T00:00:00+0000')
    init(first)
    base_files = {
        'pkg/__init__.py': '', 'pkg/service.py': SERVICE,
        'pkg/utils.py': 'def helper(value):\n    """加一。"""\n    return value + 1\n',
        'pkg/old.py': 'def removed():\n    return "旧文件"\n',
        'pkg/moved.py': ''.join('# unchanged rename line %02d\n' % i for i in range(30)) + 'def moved():\n    return "移动"\n',
        'dual.py': 'thing = 1\n', 'dual/__init__.py': 'thing = 2\n',
        'src/srcpkg/__init__.py': '', 'src/srcpkg/helper.py': 'def src_helper():\n    return 4\n',
        'src/consumer.py': 'from srcpkg.helper import src_helper\n',
        'broken.py': 'def broken(:\n    pass\n', 'empty.py': '',
        'notes.txt': '中文说明\n第二行\n', 'long.txt': ''.join('line %03d\n' % i for i in range(1, 621)),
        'unsupported.js': 'function browserOnly() { return 1; }\n',
        'binary.bin': b'\x00\xff\x00BINARY', 'invalid-encoding.py': b'\xff\xfe\xfa',
        'oversize.py': '# ' + 'x' * (1024 * 1024 + 1) + '\n',
        'DO_NOT_EXECUTE.py': 'from pathlib import Path\nPath(__file__).with_name("EXECUTED_MARKER").write_text("executed")\nraise RuntimeError("fixture source must never run")\n',
    }
    for path, content in base_files.items(): write(first, path, content)
    # Portable Git symlink blob: does not require Windows symlink privileges.
    # add-all stages normal files; special modes are inserted before commit-tree.
    git(first, 'add', '--all')
    link_sha = git(first, 'hash-object', '-w', '--stdin', raw=b'../../../outside-canary.txt').decode().strip()
    git(first, 'update-index', '--add', '--cacheinfo', '120000,' + link_sha + ',outside-link')
    git(first, 'update-index', '--add', '--cacheinfo', '160000,' + second_sha + ',vendor/submodule')
    # commit() re-adds only working files; Git removes missing special entries with -A,
    # so special tree entries are attached directly to the written tree below.
    def special_commit(title, date, parent_sha=None):
        git(first, 'add', '--all')
        git(first, 'update-index', '--add', '--cacheinfo', '120000,' + link_sha + ',outside-link')
        git(first, 'update-index', '--add', '--cacheinfo', '160000,' + second_sha + ',vendor/submodule')
        tree = git(first, 'write-tree').decode('utf-8').strip()
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='ProjectMind fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                   GIT_COMMITTER_NAME='ProjectMind fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
                   GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        cmd = ['git', '-C', str(first), 'commit-tree', tree] + (['-p', parent_sha] if parent_sha else [])
        sha = subprocess.check_output(cmd, input=(title + '\n').encode('utf-8'), env=env).decode('utf-8').strip()
        git(first, 'update-ref', 'refs/heads/fixture', sha)
        return sha
    base = special_commit('first fixture version', '2026-10-01T00:00:00+0000')
    write(first, 'pkg/service.py', SERVICE.replace('return h(1)', 'return h(2)') + '\ndef added():\n    return "新增"\n')
    write(first, 'pkg/new.py', 'from .utils import helper\n\ndef new_entry():\n    return helper(3)\n')
    (first / 'pkg/old.py').unlink()
    (first / 'pkg/moved.py').rename(first / 'pkg/relocated.py')
    target = special_commit('second fixture version', '2026-10-02T00:00:00+0000', base)
    write(first, 'untracked-only.py', 'def untracked_only():\n    return "不属于提交"\n')
    write(first, 'pkg/service.py', '# DIRTY_WORKTREE_CANARY\n' + SERVICE)
    (root / 'outside-canary.txt').write_text('OUTSIDE_CONTENT_MUST_NOT_BE_READ\n', encoding='utf-8')
    manifest = {'format': FORMAT, 'root': str(root), 'repository': str(first), 'secondRepository': str(second),
                'baseRevision': base, 'targetRevision': target, 'secondRevision': second_sha,
                'basePaths': tracked(first, base), 'targetPaths': tracked(first, target),
                'secondPaths': tracked(second, second_sha), 'expectedChanges': changes(first, base, target),
                'environment': {'git': git(first, '--version').decode('utf-8').strip()},
                'facts': {'sourceExecuted': (first / 'EXECUTED_MARKER').exists(),
                          'mapJson': any(Path(p).name == 'project-map.json' for p in tracked(first, target))}}
    # The manifest is written UTF-8 and read back UTF-8 on every platform; the
    # interpreter's default codec (cp936, utf8_mode) must never decide this.
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                        encoding='utf-8')
    return manifest


def _relative_parts(root, path):
    # Names of path below root, refused unless path sits strictly inside root.
    # Only used to derive names: every object is opened relative to a handle we
    # already hold, so a manipulated name can never reach an object outside root.
    try:
        relative = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    except ValueError:
        raise OSError(f'refusing an unrelatable path: {path}')
    if relative == os.curdir:
        return []
    parts = relative.split(os.sep)
    if any(part in ('', os.curdir, os.pardir) for part in parts):
        raise OSError(f'refusing a path outside the owned root: {path}')
    return parts


if os.name == 'nt':
    _ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    _GENERIC_READ = 0x80000000
    _SYNCHRONIZE = 0x00100000
    _FILE_READ_DATA = 0x00000001          # same value as FILE_LIST_DIRECTORY
    _FILE_READ_ATTRIBUTES = 0x00000080
    _DELETE = 0x00010000
    _FILE_SHARE_ALL = 0x00000001 | 0x00000002 | 0x00000004
    _OPEN_EXISTING = 3
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _OBJ_CASE_INSENSITIVE = 0x00000040
    _OBJ_DONT_REPARSE = 0x00001000
    _FILE_OPEN = 1
    _FILE_DIRECTORY_FILE = 0x00000001
    _FILE_NON_DIRECTORY_FILE = 0x00000040
    _FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FileDispositionInfoEx = 21
    _FILE_DISPOSITION_DELETE = 0x00000001
    _FILE_DISPOSITION_IGNORE_READONLY_ATTRIBUTE = 0x00000010
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [('Length', ctypes.c_ushort), ('MaximumLength', ctypes.c_ushort),
                    ('Buffer', ctypes.c_void_p)]

    class _OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [('Length', ctypes.c_ulong), ('RootDirectory', ctypes.c_void_p),
                    ('ObjectName', ctypes.c_void_p), ('Attributes', ctypes.c_ulong),
                    ('SecurityDescriptor', ctypes.c_void_p),
                    ('SecurityQualityOfService', ctypes.c_void_p)]

    class _IO_STATUS_BLOCK(ctypes.Structure):
        _fields_ = [('Status', ctypes.c_void_p), ('Information', ctypes.c_void_p)]

    class _FILE_DISPOSITION_INFO_EX(ctypes.Structure):
        _fields_ = [('Flags', ctypes.c_ulong)]

    class _FILETIME(ctypes.Structure):
        _fields_ = [('dwLowDateTime', ctypes.c_ulong), ('dwHighDateTime', ctypes.c_ulong)]

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [('dwFileAttributes', ctypes.c_ulong), ('ftCreationTime', _FILETIME),
                    ('ftLastAccessTime', _FILETIME), ('ftLastWriteTime', _FILETIME),
                    ('dwVolumeSerialNumber', ctypes.c_ulong), ('nFileSizeHigh', ctypes.c_ulong),
                    ('nFileSizeLow', ctypes.c_ulong), ('nNumberOfLinks', ctypes.c_ulong),
                    ('nFileIndexHigh', ctypes.c_ulong), ('nFileIndexLow', ctypes.c_ulong)]

    _ntdll.NtCreateFile.restype = ctypes.c_long
    _ntdll.NtCreateFile.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong, ctypes.POINTER(_OBJECT_ATTRIBUTES),
        ctypes.POINTER(_IO_STATUS_BLOCK), ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]


def _handle_snapshot(handle):
    # Read the opened object's own facts, never a path that could be re-resolved.
    info = _BY_HANDLE_FILE_INFORMATION()
    if not _kernel32.GetFileInformationByHandle(ctypes.c_void_p(handle), ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return info


def _assert_plain(info, path, *, directory):
    # A plain, singly-linked object with no reparse state, or nothing is touched.
    if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        raise OSError(f'refusing a reparse point under the owned root: {path}')
    if info.nNumberOfLinks != 1:
        raise OSError(f'refusing an object shared with another name: {path}')
    if directory is not None and bool(info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY) != directory:
        raise OSError(f'refusing an unexpected object type: {path}')


def _open_owned_root(root):
    # Open the owned root directory object itself, never through a link. A root
    # redirected to a reparse point is refused by its own snapshot, and every
    # later object is opened relative to this handle, so a parent replaced after
    # this point cannot reach an object outside the root.
    if os.name != 'nt':
        raise OSError('handle-bound removal is only implemented for Windows')
    handle = _kernel32.CreateFileW(str(root), _GENERIC_READ | _DELETE, _FILE_SHARE_ALL, None,
                                   _OPEN_EXISTING,
                                   _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS, None)
    if handle in (None, _INVALID_HANDLE_VALUE):
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _open_child(parent_handle, name, access, *, directory=None):
    # Open one child relative to a handle already held. OBJ_DONT_REPARSE makes the
    # kernel refuse the open if any component is a reparse point, so string path
    # re-resolution can never redirect the traversal away from the owned root.
    if os.name != 'nt':
        raise OSError('handle-bound removal is only implemented for Windows')
    # UNICODE_STRING.Length is a byte count of the UTF-16LE buffer, not a Python
    # character count: a non-BMP character occupies two UTF-16 code units, so
    # len(name) * 2 would truncate the name the kernel opens.
    encoded = name.encode('utf-16-le')
    buffer = ctypes.create_string_buffer(encoded, len(encoded))
    component = _UNICODE_STRING(Length=len(encoded), MaximumLength=len(encoded),
                                Buffer=ctypes.cast(buffer, ctypes.c_void_p))
    attributes = _OBJECT_ATTRIBUTES(Length=ctypes.sizeof(_OBJECT_ATTRIBUTES),
                                    RootDirectory=parent_handle,
                                    ObjectName=ctypes.cast(ctypes.byref(component), ctypes.c_void_p),
                                    Attributes=_OBJ_CASE_INSENSITIVE | _OBJ_DONT_REPARSE,
                                    SecurityDescriptor=None, SecurityQualityOfService=None)
    status_block = _IO_STATUS_BLOCK()
    handle = ctypes.c_void_p()
    # A synchronous handle so the same object can be read, inspected and deleted
    # through this one handle without re-resolving any path.
    options = _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_SYNCHRONOUS_IO_NONALERT
    if directory is True:
        options |= _FILE_DIRECTORY_FILE
    elif directory is False:
        options |= _FILE_NON_DIRECTORY_FILE
    status = _ntdll.NtCreateFile(ctypes.byref(handle), access, ctypes.byref(attributes),
                                 ctypes.byref(status_block), None, 0, _FILE_SHARE_ALL, _FILE_OPEN,
                                 options, None, 0)
    if status < 0:
        raise OSError(f'refusing {name!r}: NtCreateFile status {ctypes.c_ulong(status).value:#010x}')
    return handle.value


def _dispose_handle(handle, path):
    # Delete through the bound handle and change no attribute at all: the
    # read-only bit, where set, is ignored by the delete instead of cleared, so a
    # name shared with another hard link keeps every attribute it held.
    disposition = _FILE_DISPOSITION_INFO_EX(_FILE_DISPOSITION_DELETE |
                                            _FILE_DISPOSITION_IGNORE_READONLY_ATTRIBUTE)
    if not _kernel32.SetFileInformationByHandle(ctypes.c_void_p(handle), _FileDispositionInfoEx,
                                                ctypes.byref(disposition), ctypes.sizeof(disposition)):
        raise ctypes.WinError(ctypes.get_last_error())


def _close_handle(handle):
    _kernel32.CloseHandle(ctypes.c_void_p(handle))


def _read_under(parent_handle, name, limit):
    # Read an owned metadata file through the same root handle that will be
    # purged, so verification and removal cannot disagree about which root it is.
    handle = _open_child(parent_handle, name, _GENERIC_READ | _SYNCHRONIZE, directory=False)
    try:
        _assert_plain(_handle_snapshot(handle), name, directory=False)
        buffer = ctypes.create_string_buffer(65536)
        read = ctypes.c_ulong()
        chunks, total = [], 0
        while True:
            if not _kernel32.ReadFile(ctypes.c_void_p(handle), buffer, len(buffer),
                                      ctypes.byref(read), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not read.value:
                break
            chunks.append(buffer.raw[:read.value])
            total += read.value
            if total > limit:
                raise OSError(f'refusing an oversized metadata file: {name}')
        return b''.join(chunks)
    finally:
        _close_handle(handle)


def _purge_directory(directory_path, directory_handle):
    # Enumerate names for their spelling only; the object behind every name is
    # opened relative to the directory handle, so a redirected enumeration can
    # only cause a refusal, never a change outside the owned root.
    for name in sorted(os.listdir(directory_path)):
        child_path = os.path.join(directory_path, name)
        child_handle = _open_child(directory_handle, name,
                                   _FILE_READ_ATTRIBUTES | _FILE_READ_DATA | _DELETE | _SYNCHRONIZE)
        try:
            info = _handle_snapshot(child_handle)
            _assert_plain(info, child_path, directory=None)
            if info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY:
                _purge_directory(child_path, child_handle)   # emptied before it goes
            _dispose_handle(child_handle, child_path)
        finally:
            _close_handle(child_handle)


def _remove_owned_tree(root):
    # One pass, no retry: every object is verified and deleted through handles
    # bound to the owned root, so a parent directory redirected at any point still
    # cannot reach an external object. The first refusal propagates.
    root_handle = _open_owned_root(root)
    try:
        _assert_plain(_handle_snapshot(root_handle), root, directory=True)
        _purge_directory(str(root), root_handle)
        _dispose_handle(root_handle, root)
    finally:
        _close_handle(root_handle)


def _remove_plain_object(root, path):
    # Remove exactly one object below root, opening every component relative to a
    # handle already held, so a parent replaced after inspection cannot redirect
    # the deletion to a different object.
    parts = _relative_parts(root, path)
    if not parts:
        raise OSError(f'refusing to remove the owned root itself: {path}')
    handles = [_open_owned_root(root)]
    try:
        _assert_plain(_handle_snapshot(handles[0]), root, directory=True)
        for part in parts:
            handles.append(_open_child(handles[-1], part,
                                       _FILE_READ_ATTRIBUTES | _FILE_READ_DATA | _DELETE | _SYNCHRONIZE))
        _assert_plain(_handle_snapshot(handles[-1]), path, directory=None)
        _dispose_handle(handles[-1], path)
    finally:
        for handle in reversed(handles):
            _close_handle(handle)


def cleanup(manifest):
    root = Path(manifest['root']).resolve()
    if not root.name.startswith('projectmind-d-fixture-'):
        raise ValueError('Not an owned generated fixture; refusing cleanup')
    if os.name == 'nt':
        handle = _open_owned_root(root)
        try:
            _assert_plain(_handle_snapshot(handle), root, directory=True)
            # Owner marker and manifest are read through the same handle that is
            # about to be purged, so a root redirected after the name check cannot
            # pass verification while a different tree is removed.
            if _read_under(handle, '.d-fixture-owner', 4096) != FORMAT.encode('utf-8'):
                raise ValueError('Not an owned generated fixture; refusing cleanup')
            if json.loads(_read_under(handle, 'manifest.json', 1 << 20).decode('utf-8')) != manifest:
                raise ValueError('Manifest changed; refusing cleanup')
            _purge_directory(str(root), handle)
            _dispose_handle(handle, root)
        finally:
            _close_handle(handle)
    else:
        marker = root / '.d-fixture-owner'
        if marker.is_file() and marker.read_text(encoding='utf-8') == FORMAT:
            if json.loads((root / 'manifest.json').read_text(encoding='utf-8')) != manifest:
                raise ValueError('Manifest changed; refusing cleanup')
            shutil.rmtree(root)
        else:
            raise ValueError('Not an owned generated fixture; refusing cleanup')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, help='existing temporary parent; never an existing repository')
    p.add_argument('--cleanup', type=Path, help='manifest of exactly one owned generated fixture')
    args = p.parse_args()
    if args.cleanup:
        cleanup(json.loads(args.cleanup.read_text(encoding='utf-8'))); return
    data = generate(args.parent)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print('Manifest:', Path(data['root']) / 'manifest.json')


if __name__ == '__main__': main()
