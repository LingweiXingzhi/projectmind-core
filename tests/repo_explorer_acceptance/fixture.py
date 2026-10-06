"""Build independent committed fixtures. Never import or execute their source."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
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
    return {r.split(b'\t', 1)[1].decode(): r.split(b' ', 1)[0].decode() for r in records if r}


def blob(repo, revision, path):
    # Only used with manifest-controlled fixture paths, never an HTTP path.
    return git(repo, 'show', revision + ':' + path)


def changes(repo, base, target):
    parts = git(repo, 'diff', '--name-status', '-z', '--find-renames=50%', base, target, '--').split(b'\0')
    result, i = [], 0
    while i < len(parts) and parts[i]:
        code = parts[i].decode(); i += 1
        if code[0] in ('R', 'C'):
            old, path = parts[i:i + 2]; i += 2
        else:
            old, path = None, parts[i]; i += 1
        result.append({'status': code[0], 'path': path.decode(),
                       'oldPath': old.decode() if old else None})
    return result


def init(repo):
    repo.mkdir(parents=True)
    git(repo, 'init', '-q', '-b', 'fixture')
    git(repo, 'config', 'user.name', 'ProjectMind fixture')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    git(repo, 'config', 'core.autocrlf', 'false')


def write(repo, path, content):
    p = repo / path; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content.encode() if isinstance(content, str) else content)


def commit(repo, title, timestamp):
    git(repo, 'add', '--all')
    tree = git(repo, 'write-tree').decode().strip()
    # commit-tree avoids inherited hooks and signing; dates and identities are fixed.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME='ProjectMind fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='ProjectMind fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
               GIT_AUTHOR_DATE=timestamp, GIT_COMMITTER_DATE=timestamp)
    parent = git(repo, 'rev-parse', '--verify', 'HEAD').decode().strip() if (repo / '.git/refs/heads/fixture').exists() else None
    command = ['git', '--no-replace-objects', '-C', str(repo), 'commit-tree', tree]
    if parent: command += ['-p', parent]
    sha = subprocess.check_output(command, input=(title + '\n').encode(), env=env).decode().strip()
    git(repo, 'update-ref', 'refs/heads/fixture', sha)
    return sha


def generate(parent=None):
    if parent is not None:
        parent = Path(parent).resolve()
        if any((p / '.git').exists() for p in (parent, *parent.parents)):
            raise ValueError('Fixture parent must be outside existing repositories')
    root = Path(tempfile.mkdtemp(prefix='projectmind-d-fixture-', dir=parent)).resolve()
    (root / '.d-fixture-owner').write_text(FORMAT)
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
        tree = git(first, 'write-tree').decode().strip()
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='ProjectMind fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                   GIT_COMMITTER_NAME='ProjectMind fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
                   GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        cmd = ['git', '-C', str(first), 'commit-tree', tree] + (['-p', parent_sha] if parent_sha else [])
        sha = subprocess.check_output(cmd, input=(title + '\n').encode(), env=env).decode().strip()
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
    (root / 'outside-canary.txt').write_text('OUTSIDE_CONTENT_MUST_NOT_BE_READ\n')
    manifest = {'format': FORMAT, 'root': str(root), 'repository': str(first), 'secondRepository': str(second),
                'baseRevision': base, 'targetRevision': target, 'secondRevision': second_sha,
                'basePaths': tracked(first, base), 'targetPaths': tracked(first, target),
                'secondPaths': tracked(second, second_sha), 'expectedChanges': changes(first, base, target),
                'environment': {'git': git(first, '--version').decode().strip()},
                'facts': {'sourceExecuted': (first / 'EXECUTED_MARKER').exists(),
                          'mapJson': any(Path(p).name == 'project-map.json' for p in tracked(first, target))}}
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def _is_reparse_point(info):
    # Reparse state cannot be decided on platforms without st_file_attributes;
    # an undecidable object is never retried.
    attributes = getattr(info, 'st_file_attributes', None)
    if attributes is None:
        return True
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _plain_directory(path):
    info = os.lstat(path)
    return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and not _is_reparse_point(info)


def _owned_plain_entry(root, path):
    # The entry must sit under an owned root whose whole chain of directories is
    # plain (no links, no reparse points), so a redirected parent cannot be used
    # to reach an external object through a path that merely looks internal.
    try:
        if not _plain_directory(root):
            return False
        candidate = Path(os.path.abspath(path))
        if candidate != root and root not in candidate.parents:
            return False
        for ancestor in candidate.parents:
            if ancestor == root:
                return True
            if not _plain_directory(ancestor):
                return False
        return False
    except OSError:
        return False


def _make_cleanup_handler(root):
    # Bound the retry to the owned root. Only a permission failure on a plain,
    # singly-linked object inside the fixture is retried: a link, a reparse
    # point, a shared object (st_nlink > 1), an undecidable entry or any
    # redirected parent is re-raised unchanged so nothing outside the fixture
    # can be touched and the tree stays for manual cleanup.
    def handler(func, path, exc):
        if not isinstance(exc, PermissionError):
            raise exc
        if not _owned_plain_entry(root, path):
            raise exc
        try:
            entry = os.lstat(path)
        except OSError:
            raise exc
        if stat.S_ISLNK(entry.st_mode) or _is_reparse_point(entry) or entry.st_nlink != 1:
            raise exc
        os.chmod(path, stat.S_IWRITE)
        func(path)
    return handler


def cleanup(manifest):
    root = Path(manifest['root']).resolve()
    marker = root / '.d-fixture-owner'
    if root.name.startswith('projectmind-d-fixture-') and marker.is_file() and marker.read_text() == FORMAT:
        # Guard against a changed manifest redirecting deletion into a foreign root.
        saved = json.loads((root / 'manifest.json').read_text())
        if saved != manifest: raise ValueError('Manifest changed; refusing cleanup')
        shutil.rmtree(root, onexc=_make_cleanup_handler(root))
    else: raise ValueError('Not an owned generated fixture; refusing cleanup')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=Path, help='existing temporary parent; never an existing repository')
    p.add_argument('--cleanup', type=Path, help='manifest of exactly one owned generated fixture')
    args = p.parse_args()
    if args.cleanup:
        cleanup(json.loads(args.cleanup.read_text())); return
    data = generate(args.parent)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print('Manifest:', Path(data['root']) / 'manifest.json')


if __name__ == '__main__': main()
