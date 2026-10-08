"""Bounded, read-only handoff of B's immutable architecture version.

No approval, repository checkout, network fetch or formal-map write occurs here.
Transport digests prove byte consistency, never operator authority.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

from extensions.continuity.inspection import git

SHA = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
REV = re.compile(r'sha256:[0-9a-f]{64}\Z')
ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,119}\Z')
MAX_BYTES = 2_000_000
SEMANTIC = ('schemaVersion', 'mapId', 'codeRepoId', 'codeRevision',
            'verifiedCodeRevision', 'status', 'graph', 'reviewCoverage', 'limits')


class ArchitectureError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status

    def as_dict(self):
        return {'code': self.code, 'message': str(self)}


def require(condition, code='EVIDENCE_MISMATCH', message='版本或证据不符合约定', status=409):
    if not condition:
        raise ArchitectureError(code, message, status)


def canonical(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ArchitectureError('INVALID_INPUT', '只接受有限 JSON 值', 400) from exc
    require(len(raw) <= MAX_BYTES, 'INVALID_INPUT', '交换包超过 2 MB', 400)
    return raw


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def identity(value):
    require(isinstance(value, str) and ID.fullmatch(value), 'INVALID_INPUT', '需要稳定 ID', 400)
    return value


def full_sha(value):
    require(isinstance(value, str) and SHA.fullmatch(value), 'INVALID_INPUT', '需要完整 Git SHA', 400)
    return value


def evidence_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 20000 and '\\' not in value
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and ':' not in value and not value.startswith('/')
            and all(p not in ('', '.', '..', '.git') for p in value.split('/')),
            'EVIDENCE_MISMATCH', '证据路径必须是安全仓库相对路径')
    return str(PurePosixPath(value))


def read_git(repo, *args):
    try:
        return git(Path(repo), *args)
    except Exception as exc:
        raise ArchitectureError('STALE_CONTEXT', '当前登记仓库无法读取固定 Git 对象') from exc


def clean(repo):
    require(not read_git(repo, 'status', '--porcelain=v1', '-z'),
            'DIRTY_WORKSPACE', '工作区有未提交改动；保留改动后再核对，不自动清理')


def commit_exists(repo, revision):
    full_sha(revision)
    require(read_git(repo, 'rev-parse', '--verify', revision + '^{commit}').decode().strip() == revision,
            'STALE_CONTEXT', '提交不存在或不是完整提交对象')


def source_locator(repo):
    names = read_git(repo, 'remote').decode().splitlines()
    value = (read_git(repo, 'remote', 'get-url', 'origin').decode().strip()
             if 'origin' in names else 'local:' + str(Path(repo).resolve()))
    require(value and '\n' not in value and '\x00' not in value,
            'INVALID_INPUT', '来源地址无效', 400)
    if '://' in value:
        parsed = urlsplit(value)
        require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
                'INVALID_INPUT', '来源地址不能含凭据、查询或片段', 400)
    return value.rstrip('/')


def code_identity(repo):
    """Exact B origin identity policy; no directory-name matching or URL alias merge."""
    root = Path(read_git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    return 'repo-' + hashlib.sha256(source_locator(root).encode()).hexdigest()


def validate_envelope(envelope):
    canonical(envelope)
    require(isinstance(envelope, dict) and set(envelope) == {'version', 'provenance'},
            'INVALID_INPUT', '需要 B 的 version/provenance 交换包', 400)
    version, provenance = envelope['version'], envelope['provenance']
    require(isinstance(version, dict) and isinstance(provenance, dict), 'INVALID_INPUT', '版本包类型错误', 400)
    require(all(k in version for k in (*SEMANTIC, 'mapRevision', 'review', 'origin', 'confirmation')))
    identity(version['mapId'])
    require(version['schemaVersion'] == 'architecture_version_v1')
    require(version['mapRevision'] == digest({k: version[k] for k in SEMANTIC}),
            'EVIDENCE_MISMATCH', '图版本摘要不匹配')
    planning = version['codeRepoId'] is None
    require(planning == (version['codeRevision'] is None))
    if not planning:
        identity(version['codeRepoId']); full_sha(version['codeRevision'])
    require(version['verifiedCodeRevision'] in (None, version['codeRevision']))
    require(version['status'] == ('confirmed_design' if planning else 'confirmed_cognition'))
    graph, coverage = version['graph'], version['reviewCoverage']
    require(isinstance(graph, dict) and isinstance(coverage, dict))
    for group in ('nodes', 'edges', 'processes', 'evidence'):
        require(isinstance(graph.get(group), list) and len(graph[group]) <= 2000)
        ids = [identity(item.get('id')) for item in graph[group] if isinstance(item, dict)]
        require(len(ids) == len(graph[group]) == len(set(ids)))
        require(isinstance(coverage.get(group), list) and set(coverage[group]) <= set(ids))
        if coverage.get('scope') == 'all':
            require(set(coverage[group]) == set(ids))
    require(coverage.get('scope') in ('all', 'partial'))
    for item in graph['evidence']:
        if item.get('kind') == 'code':
            require(not planning and item.get('codeRepoId') == version['codeRepoId'])
            full_sha(item.get('codeRevision'))
            if item['codeRevision'] != version['codeRevision']:
                require(isinstance(item.get('unknownReason'), str) and item['unknownReason'].strip(),
                        'EVIDENCE_MISMATCH', '旧代码证据必须保留未知/过时原因')
            evidence_path(item.get('path'))
    nodes = {o['id'] for o in graph['nodes']}
    for edge in graph['edges']:
        require(edge.get('from') in nodes and edge.get('to') in nodes)
    step_ids = set()
    for process in graph['processes']:
        steps = process.get('steps')
        require(isinstance(steps, list) and len(steps) <= 2000)
        local_ids = [identity(s.get('id')) for s in steps if isinstance(s, dict)]
        require(len(local_ids) == len(steps) == len(set(local_ids)) and not set(local_ids) & step_ids)
        step_ids.update(local_ids)
        for step in steps:
            require(step.get('nodeId') in nodes and isinstance(step.get('nextStepIds'), list)
                    and set(step['nextStepIds']) <= set(local_ids))
    require(isinstance(version['limits'], list))
    require(isinstance(version['review'], dict) and version['review'].get('decision') == 'accept'
            and version['review'].get('afterGraph') == graph)
    source = provenance.get('mapSourceRevision')
    if source is not None:
        full_sha(source)
        require(provenance.get('sourceKind') == 'git_commit')
    # When B is installed use its canonical validator too; D never publishes.
    try:
        from extensions.architecture_workspace.schema import validate_packet
    except ImportError:
        pass
    else:
        try:
            validate_packet(version)
        except Exception as exc:
            raise ArchitectureError('EVIDENCE_MISMATCH', 'B 版本包校验未通过') from exc
    return deepcopy(envelope)


def build_version_handoff(envelope, *, workspace_id, sources, task=None, references=None):
    envelope = validate_envelope(envelope)
    identity(workspace_id)
    require(isinstance(sources, dict) and set(sources) == {'code', 'architecture'},
            'INVALID_INPUT', '必须明确代码和架构来源', 400)
    version = envelope['version']
    for name, value in sources.items():
        require(value is None or isinstance(value, str) and 0 < len(value) <= 1000,
                'INVALID_INPUT', '来源地址类型错误', 400)
        if isinstance(value, str) and '://' in value:
            u = urlsplit(value)
            require(not u.username and not u.password and not u.query and not u.fragment,
                    'INVALID_INPUT', '来源地址不能包含凭据', 400)
    require((sources['code'] is None) == (version['codeRepoId'] is None))
    if version['codeRepoId']:
        require('repo-' + hashlib.sha256(sources['code'].rstrip('/').encode()).hexdigest()
                == version['codeRepoId'], 'STALE_CONTEXT', '代码来源与 B 仓库身份不匹配')
    task = task or {'state': 'pending', 'nextAction': '核查来源与固定版本'}
    references = references or {'candidates': [], 'reviews': [], 'deviations': [], 'logs': []}
    require(isinstance(task, dict) and isinstance(task.get('nextAction'), str)
            and isinstance(task.get('state'), str), 'INVALID_INPUT', '任务需要状态和下一步', 400)
    require(isinstance(references, dict) and set(references) == {'candidates', 'reviews', 'deviations', 'logs'})
    for items in references.values():
        require(isinstance(items, list) and len(items) <= 100)
        for ref in items:
            require(isinstance(ref, dict) and isinstance(ref.get('id'), str)
                    and isinstance(ref.get('status'), str))
    body = {'schemaVersion': 'architecture_handoff_v1', 'workspaceId': workspace_id,
            'versionEnvelope': envelope, 'sources': deepcopy(sources), 'task': deepcopy(task),
            'references': deepcopy(references), 'trust': 'untrusted_until_local_git_check',
            'limits': ['传输摘要仅检查内容一致，不认证来源或操作者。',
                       '日志/候选/反馈保留参与者记录状态；未核查运行行为为 UNKNOWN。']}
    return {**body, 'transportDigest': digest(body)}


def validate_handoff(packet):
    require(isinstance(packet, dict), 'INVALID_INPUT', '交接包须为对象', 400)
    canonical(packet)
    body = {k: v for k, v in packet.items() if k != 'transportDigest'}
    require(packet.get('transportDigest') == digest(body), 'EVIDENCE_MISMATCH', '交接包被修改或摘要不匹配')
    require(packet.get('schemaVersion') == 'architecture_handoff_v1')
    expected = build_version_handoff(packet.get('versionEnvelope'), workspace_id=packet.get('workspaceId'),
                                    sources=packet.get('sources'), task=packet.get('task'),
                                    references=packet.get('references'))
    require(packet == expected, 'EVIDENCE_MISMATCH', '交接包存在未知或替换字段')
    return deepcopy(packet)


def inspect_version_handoff(packet, *, architecture_repo, code_repo=None, require_clean=True):
    """Read fixed Git bytes in configured clones; no imported path is executed."""
    packet = validate_handoff(packet)
    envelope = packet['versionEnvelope']; version = envelope['version']
    source = envelope['provenance'].get('mapSourceRevision')
    require(source is not None and packet['sources']['architecture'],
            'SOURCE_REQUIRED', '架构尚未保存到 Git 或未提供来源，保持未信任草稿')
    require(source_locator(architecture_repo) == packet['sources']['architecture'].rstrip('/'),
            'STALE_CONTEXT', '架构仓库来源不同，不能只按目录同名接手')
    if require_clean:
        clean(architecture_repo)
    commit_exists(architecture_repo, source)
    path = 'versions/' + identity(version['mapId']) + '/' + version['mapRevision'][7:] + '.json'
    listing = read_git(architecture_repo, 'ls-tree', '-z', source, '--', path)
    require(listing.startswith(b'100644 blob ') or listing.startswith(b'100755 blob '),
            'EVIDENCE_MISMATCH', '固定版本文件不是普通 Git blob')
    size = int(read_git(architecture_repo, 'cat-file', '-s', source + ':' + path))
    require(size <= MAX_BYTES, 'EVIDENCE_MISMATCH', '固定架构文件超限')
    try:
        actual = json.loads(read_git(architecture_repo, 'show', source + ':' + path))
    except (ValueError, UnicodeError) as exc:
        raise ArchitectureError('EVIDENCE_MISMATCH', '固定架构文件不是有效 JSON') from exc
    require(actual == version, 'EVIDENCE_MISMATCH', '传入版本与固定 Git 内容不同')
    if version['codeRepoId'] is not None:
        require(code_repo is not None, 'SOURCE_REQUIRED', '需要登记代码 clone')
        require(source_locator(code_repo) == packet['sources']['code'].rstrip('/')
                and code_identity(code_repo) == version['codeRepoId'], 'STALE_CONTEXT', '代码仓库身份不匹配')
        if require_clean:
            clean(code_repo)
        commit_exists(code_repo, version['codeRevision'])
    return {'status': 'same_version_git_checked', 'codeRepoId': version['codeRepoId'],
            'mapId': version['mapId'], 'codeRevision': version['codeRevision'],
            'mapRevision': version['mapRevision'], 'mapSourceRevision': source,
            'verifiedCodeRevision': version['verifiedCodeRevision'],
            'reviewCoverage': deepcopy(version['reviewCoverage']), 'graphStatus': version['status'],
            'versionEnvelope': envelope, 'formalMapWritten': False,
            'limits': packet['limits'] + ['只证明指定 Git 内容一致，未认证人审身份，也不证明新代码符合期望。']}


def render_version_handoff(packet):
    packet = validate_handoff(packet); version = packet['versionEnvelope']['version']
    lines = ['# 同版架构交接', '', '状态：待本机 Git 核对；参与者记录不等于独立验收。', '']
    for k in ('codeRepoId', 'mapId', 'codeRevision', 'mapRevision', 'verifiedCodeRevision', 'status'):
        lines.append(f'- {k}: {version[k]}')
    lines += ['- mapSourceRevision: ' + str(packet['versionEnvelope']['provenance'].get('mapSourceRevision')),
              '', '下一步：' + packet['task']['nextAction'], '',
              '核查范围：' + json.dumps(version['reviewCoverage'], ensure_ascii=False), '',
              '未知与限制：'] + ['- ' + str(x) for x in version['limits'] + packet['limits']]
    return '\n'.join(lines) + '\n'


def capture_worklog_refs(log_store, selected):
    """Read exact existing Worklog history versions; never edit or certify logs."""
    require(isinstance(selected, list) and len(selected) <= 100, 'INVALID_INPUT', '日志选择超限', 400)
    result = []
    seen = set()
    for ref in selected:
        require(isinstance(ref, dict) and set(ref) == {'id','version'}
                and isinstance(ref['id'], str) and type(ref['version']) is int and ref['version'] > 0,
                'INVALID_INPUT', '每份日志需要 ID 和固定版本', 400)
        key = (ref['id'],ref['version'])
        require(key not in seen, 'INVALID_INPUT', '重复日志版本', 400); seen.add(key)
        try:
            entry = next(e for e in log_store.history(ref['id']) if e['version'] == ref['version'])
        except Exception as exc:
            raise ArchitectureError('EVIDENCE_MISMATCH', '找不到选取的固定日志版本') from exc
        snapshot = {k:deepcopy(entry[k]) for k in ('id','version','title','body','author','category','date','codeRevision')}
        snapshot.update(status='contributor_record_unverified',attachmentIncluded=False)
        result.append({**snapshot,'snapshotDigest':digest(snapshot)})
    canonical(result)
    return result


def input_guard(function):
    """Convert malformed external shapes to a stable machine error."""
    from functools import wraps
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ArchitectureError:
            raise
        except (TypeError, KeyError, AttributeError, IndexError, ValueError, UnicodeError) as exc:
            raise ArchitectureError('INVALID_INPUT', '输入类型或必需字段不符合约定', 400) from exc
    return guarded


validate_envelope = input_guard(validate_envelope)
build_version_handoff = input_guard(build_version_handoff)
validate_handoff = input_guard(validate_handoff)
inspect_version_handoff = input_guard(inspect_version_handoff)
