"""Domain-independent Linux preparation and conservative cold recovery.

No cloud accounts, package installs, DNS changes or service activation are implicit.
Generated files contain no passwords. Restore requires the same code sources and
fixed commits; it never rewrites historical workspace identities.
"""
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

from .access import AccessError, _outside_git, check, load_accounts
from .backup import cold_backup, inspect_backup, _git, _plain_tree
from .lease import ServingLease
from extensions.architecture_workspace.deployment_preflight import validate_origin

TEMPLATES = Path(__file__).with_name('host_templates')
PLACEHOLDER = 'projectmind.example.invalid'
SHA = re.compile(r'[0-9a-f]{40}')


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1')
    result = subprocess.run(['git', '--no-replace-objects', '-c', f'safe.directory={repo}', '-C', str(repo), *args],
                            env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    check(result.returncode == 0, 'HOST_GIT_INVALID', 'Git 来源、提交或对象检查失败')
    return result.stdout.decode().strip()


def private_json(path, value):
    path = _outside_git(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write('\n'); file.flush(); os.fsync(file.fileno())


def read_config(path):
    path = _outside_git(path)
    check(path.is_file() and path.stat().st_size <= 65536 and path.stat().st_mode & 0o077 == 0,
          'HOST_CONFIG_INVALID', 'runtime.json 须在源码外且权限为0600')
    config = json.loads(path.read_text())
    check(isinstance(config, dict) and set(config) == {'schemaVersion', 'publicOrigin', 'accountsFile', 'dataRoot',
          'codeRepositories', 'architectureRepo', 'architectureBranch'} and config['schemaVersion'] == 'projectmind_deploy_v1')
    validate_origin(config['publicOrigin'], public=True)
    load_accounts(config['accountsFile'])
    check(isinstance(config['codeRepositories'], list) and len(config['codeRepositories']) <= 16)
    check(isinstance(config['architectureBranch'], str) and config['architectureBranch'].startswith('architecture/candidates/'))
    data = _outside_git(config['dataRoot'])
    arch = Path(config['architectureRepo'])
    check(arch.is_absolute() and not arch.is_symlink())
    arch = arch.resolve()
    check(data != arch and not data.is_relative_to(arch) and not arch.is_relative_to(data))
    for p in (path, Path(config['accountsFile']).resolve()):
        check(not p.is_relative_to(data) and not p.is_relative_to(arch), 'HOST_CONFIG_INVALID', '配置和账号须与业务数据分离')
    return config


def code_bindings(config):
    result = []
    for value in config['codeRepositories']:
        path = Path(value)
        check(path.is_absolute() and not path.is_symlink() and (path/'.git').is_dir(), 'HOST_GIT_INVALID')
        check(Path(git(path, 'rev-parse', '--show-toplevel')).resolve() == path.resolve(), 'HOST_GIT_INVALID')
        check(git(path, 'rev-parse', '--is-shallow-repository') == 'false', 'HOST_GIT_INVALID', '登记代码仓库须保留完整历史')
        check(not (path/'.git/objects/info/alternates').exists() and not (path/'.git/commondir').exists(), 'HOST_GIT_INVALID')
        check(not git(path, 'status', '--porcelain'), 'HOST_GIT_INVALID', '登记的代码副本须干净')
        origin = git(path, 'remote', 'get-url', 'origin')
        check(origin and not ('://' in origin and urlsplit(origin).password), 'HOST_GIT_INVALID', 'remote 不得含凭据')
        if origin.startswith(('http://', 'https://')):
            check(urlsplit(origin).username is None and not urlsplit(origin).query and not urlsplit(origin).fragment,
                  'HOST_GIT_INVALID', 'HTTP remote 不得含凭据或查询参数')
        git(path, 'fsck', '--full')
        result.append({'path': str(path.resolve()), 'originSHA256': hashlib.sha256(origin.encode()).hexdigest(),
                       'head': git(path, 'rev-parse', 'HEAD')})
    check(len({v['path'] for v in result}) == len(result), 'HOST_CONFIG_INVALID')
    return result


def prepare(output, domain=None):
    domain = domain or PLACEHOLDER
    parsed = validate_origin('https://' + domain, public=True)
    check(parsed.port is None, 'HOST_DOMAIN_INVALID', '生产入口使用443，不接受自定义端口')
    check(domain == PLACEHOLDER or not domain.endswith(('.invalid', '.test', '.example', '.internal', '.home.arpa')),
          'HOST_DOMAIN_INVALID', '请填写真实公网域名，或省略域名生成离线准备包')
    root = _outside_git(output)
    check(not root.exists(), 'HOST_OUTPUT_EXISTS', '准备包不覆盖旧目录')
    root.mkdir(mode=0o700, parents=True)
    config = {'schemaVersion': 'projectmind_deploy_v1', 'publicOrigin': 'https://' + domain,
              'accountsFile': '/etc/projectmind/accounts.json', 'dataRoot': '/var/lib/projectmind/state',
              'codeRepositories': [], 'architectureRepo': '/var/lib/projectmind/architecture',
              'architectureBranch': 'architecture/candidates/team'}
    private_json(root/'runtime.json', config)
    files = {}
    for source in sorted(TEMPLATES.iterdir()):
        text = source.read_text().replace('@DOMAIN@', domain)
        target = root/source.name
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700 if target.suffix == '.sh' else 0o600)
        with os.fdopen(fd, 'w') as file: file.write(text)
        files[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    files['runtime.json'] = hashlib.sha256((root/'runtime.json').read_bytes()).hexdigest()
    receipt = {'schemaVersion': 'projectmind_host_preparation_v1', 'publicOrigin': config['publicOrigin'],
               'domainPending': domain == PLACEHOLDER, 'servicesStarted': False,
               'filesSHA256': files, 'next': ['configure code/architecture sources', 'create private accounts',
               'install fixed release', 'host preflight', 'real DNS/TLS/device acceptance']}
    private_json(root/'PREPARATION.json', receipt)
    return receipt


def render_domain(config_path, output, domain):
    """Render final-domain files without discarding repositories or private state."""
    config = read_config(config_path)
    receipt = prepare(output, domain)
    check(not receipt['domainPending'], 'DOMAIN_PENDING')
    root = _outside_git(output)
    config['publicOrigin'] = receipt['publicOrigin']
    (root/'runtime.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    receipt['filesSHA256']['runtime.json'] = hashlib.sha256((root/'runtime.json').read_bytes()).hexdigest()
    (root/'PREPARATION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    return receipt


def preflight(config_path, source=None, expected_sha=None, public=False):
    config = read_config(config_path)
    domain = urlsplit(config['publicOrigin']).hostname
    if public:
        check(not domain.endswith(('.invalid', '.test', '.example', '.internal', '.home.arpa')),
              'DOMAIN_PENDING', '准备阶段域名不能用于公网激活')
    bindings = code_bindings(config)
    data = _outside_git(config['dataRoot'])
    check(data.is_dir() and data.stat().st_mode & 0o077 == 0, 'HOST_DATA_INVALID')
    _plain_tree(data)
    arch = Path(config['architectureRepo'])
    _plain_tree(arch)
    identity = _git(arch)
    check(Path(git(arch, 'rev-parse', '--show-toplevel')).resolve() == arch.resolve(), 'HOST_GIT_INVALID')
    check(identity['branch'] == config['architectureBranch'] and not git(arch, 'status', '--porcelain'), 'HOST_GIT_INVALID')
    check(all(not Path(v['path']).is_relative_to(data) and not Path(v['path']).is_relative_to(arch)
              and not data.is_relative_to(Path(v['path'])) and not arch.is_relative_to(Path(v['path'])) for v in bindings),
          'HOST_CONFIG_INVALID')
    source_identity = None
    if source is not None:
        source = Path(source).resolve()
        check(expected_sha and SHA.fullmatch(expected_sha), 'HOST_SHA_REQUIRED')
        check(git(source, 'rev-parse', 'HEAD') == expected_sha and not git(source, 'status', '--porcelain'), 'HOST_VERSION_MISMATCH')
        check(git(source, 'rev-parse', '--is-shallow-repository') == 'false', 'HOST_GIT_INVALID')
        git(source, 'fsck', '--full')
        source_identity = {'head': expected_sha, 'tree': git(source, 'rev-parse', 'HEAD^{tree}')}
    return {'schemaVersion': 'projectmind_host_preflight_v1', 'status': 'HOST_FILES_CHECKED',
            'codeRepositoriesChecked': len(bindings), 'architecture': identity, 'source': source_identity,
            'serviceStarted': False, 'publicNetworkVerified': False,
            'remaining': ['service-user runtime permissions', 'systemd service start', 'DNS and public TLS',
                          'second device', 'real model and task verifier']}


def backup_bound(config_path, output):
    config = read_config(config_path)
    target = _outside_git(output)
    receipt = target.with_name(target.name + '.binding.json')
    check(not receipt.exists() and not receipt.is_symlink(), 'HOST_OUTPUT_EXISTS')
    bindings = code_bindings(config)
    result = cold_backup(config_path, target)
    private_json(receipt, {'schemaVersion': 'projectmind_restore_binding_v1',
                           'manifestSHA256': hashlib.sha256((target/'manifest.json').read_bytes()).hexdigest(),
                           'codeRepositories': bindings, 'architectureBranch': config['architectureBranch']})
    return {'backup': result, 'bindingRecorded': True, 'accountsIncluded': False, 'sessionsIncluded': False}


def restore_bound(backup, config_path, output, runtime_output):
    backup = _outside_git(backup); target = _outside_git(output); runtime = _outside_git(runtime_output)
    check(not target.exists() and not runtime.exists() and not runtime.is_relative_to(target), 'HOST_OUTPUT_EXISTS')
    config = read_config(config_path)
    receipt = backup.with_name(backup.name + '.binding.json')
    check(receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_size <= 65536
          and receipt.stat().st_mode & 0o077 == 0, 'RESTORE_BINDING_REQUIRED')
    binding = json.loads(receipt.read_text())
    check(binding.get('schemaVersion') == 'projectmind_restore_binding_v1'
          and binding.get('manifestSHA256') == hashlib.sha256((backup/'manifest.json').read_bytes()).hexdigest()
          and binding.get('codeRepositories') == code_bindings(config)
          and binding.get('architectureBranch') == config['architectureBranch'], 'RESTORE_BINDING_MISMATCH',
          '请保留原登记路径、来源和完整代码版本；本工具不自动迁移工作区身份')
    check(not target.is_relative_to(backup) and not backup.is_relative_to(target), 'HOST_CONFIG_INVALID')
    for value in [config['dataRoot'], config['architectureRepo'], *config['codeRepositories']]:
        path = Path(value).resolve()
        check(not target.is_relative_to(path) and not path.is_relative_to(target), 'HOST_CONFIG_INVALID')
    old_data = _outside_git(config['dataRoot'])
    # Refuse recovery while the configured source service is running. A fresh
    # host may have no old data; activation still requires a separate preflight.
    with ServingLease(old_data) if old_data.is_dir() else nullcontext():
        result = inspect_backup(backup)
        shutil.copytree(backup, target)
        target.chmod(0o700)
        check(inspect_backup(target) == result, 'RESTORE_INVALID')
        recovered = dict(config, dataRoot=str(target/'state'), architectureRepo=str(target/'architecture'))
        private_json(runtime, recovered)
    return {'schemaVersion': 'projectmind_restore_v1', 'restored': True,
            'architecture': result['architecture'], 'sqliteIntegrity': result['sqliteIntegrity'],
            'sourcePreserved': True, 'serviceStarted': False, 'sessionsRestored': False,
            'next': 'preflight restored runtime, then activate explicitly'}


def stage_release(source, sha, releases):
    source = Path(source).resolve(); root = Path(releases).resolve()
    check(SHA.fullmatch(sha) and source.is_dir(), 'HOST_SHA_REQUIRED')
    check(git(source, 'rev-parse', '--is-shallow-repository') == 'false', 'HOST_GIT_INVALID')
    check(not git(source, 'status', '--porcelain'), 'HOST_GIT_INVALID', '发布来源工作区须干净')
    check(git(source, 'rev-parse', sha + '^{commit}') == sha, 'HOST_VERSION_MISMATCH')
    git(source, 'fsck', '--full')
    check(not root.is_relative_to(source) and not source.is_relative_to(root), 'HOST_CONFIG_INVALID')
    root.mkdir(mode=0o755, parents=True, exist_ok=True)
    check(not (root/sha).exists(), 'HOST_OUTPUT_EXISTS', '保留已有发布目录，不覆盖')
    release = root/sha; release.mkdir(mode=0o755)
    app = release/'app'
    result = subprocess.run(['git', 'clone', '--no-local', '--no-checkout', '--', str(source), str(app)],
                            capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    check(result.returncode == 0, 'HOST_GIT_INVALID')
    git(app, 'checkout', '--detach', sha)
    check(git(app, 'rev-parse', 'HEAD') == sha and not git(app, 'status', '--porcelain'), 'HOST_VERSION_MISMATCH')
    git(app, 'fsck', '--full')
    private_json(release/'release.json', {'schemaVersion': 'projectmind_release_v1', 'head': sha,
                 'tree': git(app, 'rev-parse', 'HEAD^{tree}'), 'completeHistory': True})
    return {'head': sha, 'tree': git(app, 'rev-parse', 'HEAD^{tree}'), 'activated': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--output', required=True, type=Path); p.add_argument('--domain')
    p = sub.add_parser('render-domain'); p.add_argument('--config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path); p.add_argument('--domain', required=True)
    p = sub.add_parser('preflight'); p.add_argument('--config', required=True, type=Path)
    p.add_argument('--source', type=Path); p.add_argument('--expected-sha'); p.add_argument('--public', action='store_true')
    p = sub.add_parser('backup'); p.add_argument('--config', required=True, type=Path); p.add_argument('--output', required=True, type=Path)
    p = sub.add_parser('restore'); p.add_argument('--backup', required=True, type=Path); p.add_argument('--config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path); p.add_argument('--runtime-output', required=True, type=Path)
    p = sub.add_parser('stage-release'); p.add_argument('--source', required=True, type=Path)
    p.add_argument('--sha', required=True); p.add_argument('--releases', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare': result = prepare(args.output, args.domain)
        elif args.command == 'render-domain': result = render_domain(args.config, args.output, args.domain)
        elif args.command == 'preflight': result = preflight(args.config, args.source, args.expected_sha, args.public)
        elif args.command == 'backup': result = backup_bound(args.config, args.output)
        elif args.command == 'restore': result = restore_bound(args.backup, args.config, args.output, args.runtime_output)
        else: result = stage_release(args.source, args.sha, args.releases)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        # Configuration and command stderr can contain private paths/remotes.
        code = exc.code if isinstance(exc, AccessError) else type(exc).__name__
        parser.exit(1, f'部署准备未通过：{code}。原数据不自动覆盖，请检查私有配置。\n')


if __name__ == '__main__': main()
