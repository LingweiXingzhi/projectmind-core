"""Private cold backups; no running-service copy, overwrite, or automatic restore."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess

from .access import _outside_git, check
from .lease import ServingLease

SCHEMA = 'projectmind_cold_backup_v1'
MANIFEST = 'manifest.json'


def _plain_tree(root):
    check(root.is_dir() and not root.is_symlink(), 'BACKUP_INVALID', '需要普通目录')
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        check(stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'BACKUP_INVALID', '不自动备份符号链接或特殊文件')


def _git(repo):
    check((repo/'.git').is_dir() and not (repo/'.git').is_symlink(),
          'BACKUP_INVALID', '架构仓库须为独立 Git 副本；工作树引用需要专门备份')
    check(not (repo/'.git/commondir').exists() and not (repo/'.git/objects/info/alternates').exists(),
          'BACKUP_INVALID', '架构 Git 引用外部对象目录，需要先建立独立副本')
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    def command(*args):
        try:
            result = subprocess.run(['git','-C',str(repo),*args], env=env, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            check(False, 'BACKUP_INVALID', '架构 Git 检查超时')
        check(result.returncode == 0, 'BACKUP_INVALID', '架构 Git 完整性检查失败')
        return result.stdout.decode().strip()
    command('fsck','--full')
    return {'head': command('rev-parse','HEAD'), 'branch': command('branch','--show-current')}


def _sqlite(root):
    results = {}
    for path in sorted(root.rglob('*.sqlite3')):
        try:
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as connection:
                check(connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)],
                      'BACKUP_INVALID', 'SQLite 完整性检查失败')
        except sqlite3.Error:
            check(False, 'BACKUP_INVALID', 'SQLite 无法读取或完整性检查失败')
        results[path.relative_to(root).as_posix()] = 'ok'
    return results


def _inventory(root):
    _plain_tree(root)
    check((root/'state').is_dir() and (root/'architecture').is_dir(), 'BACKUP_INVALID', '备份缺少数据或架构目录')
    files = {}
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.name == MANIFEST and path.parent == root:
            continue
        relative = path.relative_to(root).as_posix()
        check(relative.startswith(('state/','architecture/')), 'BACKUP_INVALID', '备份含未登记文件')
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024*1024), b''):
                digest.update(chunk)
        files[relative] = {'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}
        check(len(files) <= 100000, 'BACKUP_INVALID', '备份文件数量超出当前检查上限')
    return files


def inspect_backup(directory):
    root = _outside_git(directory)
    check(root.is_dir() and root.stat().st_mode & 0o077 == 0,
          'BACKUP_INVALID', '备份根目录须为私有目录')
    _plain_tree(root)
    manifest = root/MANIFEST
    check(manifest.is_file() and manifest.stat().st_size <= 16*1024*1024,
          'BACKUP_INVALID', '没有可核验的完整清单')
    data = json.loads(manifest.read_text())
    check(isinstance(data, dict) and data.get('schemaVersion') == SCHEMA and data.get('complete') is True,
          'BACKUP_INVALID', '备份没有完成标记')
    check(_inventory(root) == data.get('files'), 'BACKUP_INVALID', '备份文件哈希或清单不一致')
    check(_git(root/'architecture') == data.get('architecture'), 'BACKUP_INVALID', '架构 Git 版本不一致')
    check(_sqlite(root/'state') == data.get('sqliteIntegrity'), 'BACKUP_INVALID', '数据库完整性或清单不一致')
    return {'schemaVersion': SCHEMA, 'complete': True, 'filesVerified': len(data['files']),
            'architecture': data['architecture'], 'sqliteIntegrity': data['sqliteIntegrity'],
            'scope': 'private cold copy; restore and new-host source binding require separate checks'}


def cold_backup(config_path, output):
    config_path = _outside_git(config_path)
    check(config_path.is_file() and config_path.stat().st_size <= 65536)
    config = json.loads(config_path.read_text())
    check(isinstance(config, dict) and config.get('schemaVersion') == 'projectmind_deploy_v1')
    data = _outside_git(config['dataRoot'])
    check(data.is_dir() and data.stat().st_mode & 0o077 == 0, 'BACKUP_INVALID', '源数据根须为私有目录')
    architecture = Path(config['architectureRepo'])
    check(architecture.is_absolute() and not architecture.is_symlink())
    architecture = architecture.resolve()
    target = _outside_git(output)
    check(not target.exists(), 'BACKUP_EXISTS', '备份目录已存在，请使用新目录')
    check(not target.is_relative_to(data) and not target.is_relative_to(architecture)
          and not data.is_relative_to(architecture) and not architecture.is_relative_to(data),
          'BACKUP_INVALID', '数据、架构和输出目录不能互相包含')
    account = Path(config['accountsFile']).resolve()
    check(not account.is_relative_to(data) and not config_path.is_relative_to(data),
          'BACKUP_INVALID', '账号与部署配置须在数据根外，另作私有备份')
    # Only inspect/copy after holding the same kernel lease as the serving CLI.
    # This command never stops another process or initializes application stores.
    with ServingLease(data):
        _plain_tree(data); _plain_tree(architecture)
        git = _git(architecture); sqlite = _sqlite(data)
        target.mkdir(mode=0o700, parents=True, exist_ok=False)
        shutil.copytree(data, target/'state', ignore=shutil.ignore_patterns('.serving.lock'))
        shutil.copytree(architecture, target/'architecture')
        check(_git(target/'architecture') == git and _sqlite(target/'state') == sqlite,
              'BACKUP_INVALID', '备份后的版本或数据库不一致')
        manifest = {'schemaVersion': SCHEMA, 'complete': True, 'architecture': git,
                    'sqliteIntegrity': sqlite, 'files': _inventory(target),
                    'accountsAndRuntimeConfigIncluded': False, 'authorizationSessionsIncluded': False}
        encoded = (json.dumps(manifest, indent=2)+'\n').encode()
        check(len(encoded) <= 16*1024*1024, 'BACKUP_INVALID', '清单超出当前检查上限')
        descriptor = os.open(target/MANIFEST, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        return inspect_backup(target)
