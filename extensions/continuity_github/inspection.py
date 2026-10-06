"""Read-only checks against the selected repository, never imported paths."""
import hashlib
import re
import subprocess
from urllib.parse import urlsplit
from extensions.handoff.extension import handle as legacy_generate, CORE_SOURCE
from extensions.continuity_github.logs import repository_store as log_store
from extensions.continuity_github.model import path, strings, fail, validate_logs, references


def git(repo, *args):
    try:
        r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        fail('Git 读取失败或超时，请检查本机仓库')
    if r.returncode:
        fail('当前仓库无法读取所需 Git 资料')
    return r.stdout


def canonical_remote(value):
    # Address equality is a clue, not authenticated repository identity.
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    match = re.fullmatch(r'(?:[^/@:]+@)?([^/:]+):([^\s]+)', value)
    if match and '://' not in value and not value.startswith(('/', '.', '~')):
        host, name = match.groups()
    else:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError:
            return None
        if parsed.scheme not in ('http', 'https', 'ssh', 'git') or not parsed.hostname:
            return None
        if parsed.username not in (None, 'git') or parsed.password or parsed.query or parsed.fragment:
            return None
        host, name = parsed.hostname, parsed.path
        if port:
            host += ':' + str(port)
    name = name.strip('/')
    if name.endswith('.git'):
        name = name[:-4]
    if not name or '..' in name.split('/'):
        return None
    return host.lower() + '/' + name


def remotes(repo):
    names = git(repo, 'remote').decode(errors='replace').splitlines()
    result = []
    for name in names:
        for value in git(repo, 'remote', 'get-url', '--all', name).decode(errors='replace').splitlines():
            canonical = canonical_remote(value)
            if canonical:
                result.append({'name': name, 'address': canonical})
    return result


def workspace(repo, include_diff=False):
    parts = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=normal').split(b'\0')
    files = []
    i = 0
    while i < len(parts):
        item = parts[i]
        i += 1
        if not item:
            continue
        status = item[:2].decode(errors='replace')
        filename = item[3:].decode(errors='replace')
        value = {'status': status, 'path': filename}
        if 'R' in status or 'C' in status:
            if i < len(parts):
                value['oldPath'] = parts[i].decode(errors='replace')
                i += 1
        files.append(value)
    if len(files) > 2000:
        fail('工作区变化超过 2000 项，请缩小工作范围后保存')
    diff = ''
    truncated = False
    if include_diff:
        raw = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--binary', 'HEAD', '--').decode(errors='replace')
        truncated = len(raw) > 12000
        diff = raw[:12000]
    return {'files': files, 'diff': diff, 'diffIncluded': bool(include_diff), 'truncated': truncated,
            'note': '文件清单来自保存时工作区。未跟踪文件只列路径，原件不在包内；未提交差异不属于代码提交证据，JSON 不是可直接恢复的补丁。'}


def capture(context, data):
    map_before = context.map_path.read_bytes()
    snap = context.snapshot()
    if data.get('expectedRevision') and data['expectedRevision'] != snap['revision']:
        fail('代码已变化，请刷新版本后再保存', 409)
    if type(data.get('includeWorktreeDiff', False)) is not bool:
        fail('是否携带未提交差异须为布尔值')
    request = {k: data[k] for k in ('sourceLocator', 'comparisonMode', 'baseRevision', 'aiCandidates', 'workNotes') if k in data}
    if 'sourceLocator' not in request:
        remote = remotes(context.repo)
        request['sourceLocator'] = {'kind': 'git_remote', 'value': 'https://' + remote[0]['address']} if remote else {'kind': 'local_path', 'value': str(context.repo)}
    request['expectedRevision'] = snap['revision']
    h = legacy_generate(context, 'POST', request)['handoff']
    logs = []
    selected = data.get('logIds', [])
    strings(selected, 30, '关联日志', 100)
    if len(set(selected)) != len(selected):
        fail('重复选择了同一份日志')
    if type(data.get('includeAttachments', False)) is not bool:
        fail('是否携带日志原件须为布尔值')
    if selected:
        store = log_store(context.repo)
        for log_id in selected:
            entry = store.get(log_id)
            item = dict(entry)
            if entry.get('attachment'):
                f = store.file(entry['attachment']['id'])
                item['attachment'] = {**entry['attachment'], 'preview': f['preview'], 'note': f['note'], 'included': data.get('includeAttachments', False)}
                if item['attachment']['included']:
                    import base64
                    raw = base64.b64decode(f['base64'])
                    if len(raw) > 5 * 1024 * 1024:
                        fail('单个日志原件超过 5 MB，可不携带原件并单独分享')
                    item['attachment'].update(base64=f['base64'], sha256=hashlib.sha256(raw).hexdigest())
            logs.append(item)
        logs = validate_logs(logs)
    w = workspace(context.repo, data.get('includeWorktreeDiff', False))
    if context.snapshot()['revision'] != h['codeRevision'] or map_before != context.map_path.read_bytes():
        fail('读取期间代码或地图发生变化，请重新保存接续点', 409)
    return {'handoff': h, 'workspace': w, 'logs': logs, 'references': references(data.get('references', [])),
            'mapCapture': {'digest': 'sha256:' + hashlib.sha256(map_before).hexdigest(), 'confirmedForRevision': None}}


def inspect(context, record):
    snapshot = context.snapshot()
    h = record['handoff']
    addresses = remotes(context.repo)
    source = h['sourceLocator']
    expected = canonical_remote(source['value']) if source['kind'] == 'git_remote' else None
    if source['kind'] == 'local_path':
        source_state = 'same_local_path' if source['value'] == str(context.repo) else 'unknown'
    elif expected and addresses:
        source_state = 'address_match' if any(e['address'] == expected for e in addresses) else 'address_mismatch'
    else:
        source_state = 'unknown'
    revision = h['codeRevision']
    try:
        exists = git(context.repo, 'rev-parse', '--verify', revision + '^{commit}').decode().strip() == revision
    except Exception as exc:
        from extension_host import ExtensionError
        if not isinstance(exc, ExtensionError):
            raise
        exists = False
    same = exists and snapshot['revision'] == revision
    comparison = None
    if exists and not same and source_state in ('address_match', 'same_local_path'):
        comparison = context.compare(revision, snapshot['revision'])
        # Compare once through the public Git API, match against the saved map.
        declared = {n['id']: set(n['evidencePaths']) for n in h['nodes']}
        changed = {p for c in comparison['changes'] for p in (c['path'], c.get('oldPath')) if p}
        comparison = {**comparison, 'reviewCandidates': [{'nodeId': k, 'changedEvidencePaths': sorted(v & changed)} for k, v in declared.items() if v & changed],
                      'note': '文件变化由 Git 提供，复核项按交接包保存的地图证据匹配；不证明功能影响。'}
    map_state = 'unknown'
    if record.get('mapCapture'):
        digest = 'sha256:' + hashlib.sha256(context.map_path.read_bytes()).hexdigest()
        map_state = 'same_bytes' if digest == record['mapCapture']['digest'] else 'changed'
    log_states = []
    if record['logs']:
        store = log_store(context.repo)
        for log in record['logs']:
            try:
                current = store.get(log['id'])
                state = 'same_version' if current['version'] == log['version'] and current['body'] == log['body'] and current['title'] == log['title'] else 'updated'
            except Exception as exc:
                from extension_host import ExtensionError
                if not isinstance(exc, ExtensionError):
                    raise
                state = 'not_local'
            log_states.append({'id': log['id'], 'title': log['title'], 'state': state, 'savedVersion': log['version']})
    evidence = []
    if exists:
        tracked = set(p.decode(errors='replace') for p in git(context.repo, 'ls-tree', '-r', '--name-only', '-z', revision).split(b'\0') if p)
        evidence = [{'path': p, 'exists': p in tracked} for p in sorted({p for n in h['nodes'] for p in n['evidencePaths']})]
    return {'sourceState': source_state, 'sourceNote': '只比较来源地址；不是已验证的仓库身份。来源未知或不同，不自动比较两个项目。',
            'localAddresses': addresses, 'savedRevision': revision, 'currentRevision': snapshot['revision'],
            'commitAvailable': exists, 'revisionState': 'same' if same else ('different' if exists else 'missing'),
            'comparison': comparison, 'mapState': map_state, 'mapConfirmed': False,
            'workspace': workspace(context.repo), 'logs': log_states, 'evidence': evidence}


def read_evidence(context, record, filename):
    path(filename)
    declared = {p for n in record['handoff']['nodes'] for p in n['evidencePaths']}
    if filename not in declared:
        fail('只能查看交接包声明的证据路径')
    check = inspect(context, record)
    if check['sourceState'] not in ('address_match', 'same_local_path') or not check['commitAvailable']:
        fail('来源或交接提交无法确认，不能把本机文件当作交接证据')
    revision = record['handoff']['codeRevision']
    raw = git(context.repo, 'show', revision + ':' + filename)
    if b'\x00' in raw[:8000]:
        fail('此证据为二进制文件，请使用对应工具查看')
    value = raw.decode(errors='replace')
    return {'path': filename, 'revision': revision, 'content': value[:12000], 'truncated': len(value) > 12000}
