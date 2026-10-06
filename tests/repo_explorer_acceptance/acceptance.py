"""Public HTTP acceptance only. Tool READY never means product accepted."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from fixture import FORMAT, SYMBOLS, IMPORTS, blob, tracked, changes, git

SHA = re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')
GROUPS = {
    'D01': '无地图打开独立仓库，固定实测 SHA',
    'D02': '真实目录、提交原文、空文件、行范围、工作区隔离',
    'D03': '函数/方法/嵌套/异步定义、完整范围与 parser',
    'D04': '静态导入字段、明确目标、反向关系、缺失与歧义',
    'D05': '第二版本增改删/rename 与旧版本读取',
    'D06': '同名第二仓库不混用目录、符号、关系及缓存',
    'D07': '路径/行号/版本/身份受控拒绝，旧证据授权不放宽',
    'D08': '二进制/编码/大小/类型/解析错误明确处理',
    'D08-PARSER': '无解析器时明确 unavailable（独立降级实例）',
}
UI_STEPS = ['展开目录', '打开文件', '点击函数看源码', '从静态导入跳转', '比较提交', '切换项目']


class NotRun(Exception): pass


def require(condition, expected, actual=None):
    if not condition:
        raise AssertionError(json.dumps({'expected': expected, 'actual': actual}, ensure_ascii=False, default=str))


class Client:
    def __init__(self, base_url, timeout=8):
        parts = urlsplit(base_url)
        if parts.scheme != 'http' or parts.hostname not in ('127.0.0.1', 'localhost', '::1') or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('', '/'):
            raise ValueError('Use an explicit local HTTP origin, e.g. http://127.0.0.1:8876')
        self.base_url = base_url.rstrip('/'); self.timeout = timeout; self.calls = []

    def request(self, action, params=None, post=None, legacy=False):
        route = '/api/' + action if legacy else '/api/repo-explorer/' + action
        url = self.base_url + route
        if params: url += '?' + urlencode(params)
        raw = None if post is None else json.dumps(post).encode()
        call = {'method': 'GET' if raw is None else 'POST', 'url': url, 'body': post}
        self.calls.append(call)
        try:
            request = Request(url, data=raw, headers={'Content-Type': 'application/json'})
            try:
                response = urlopen(request, timeout=self.timeout)
            except HTTPError as error:
                response = error
            with response:
                status = response.code; content = response.read(8 * 1024 * 1024 + 1)
            require(len(content) <= 8 * 1024 * 1024, 'bounded response <= 8 MiB', len(content))
            try: data = json.loads(content)
            except (ValueError, UnicodeDecodeError) as error:
                raise AssertionError('Response is not UTF-8 JSON: ' + content[:200].decode(errors='replace')) from error
            call.update(httpStatus=status, response=data)
            return status, data
        except (URLError, TimeoutError, ConnectionError) as error:
            call['transportError'] = str(error)
            raise AssertionError('Request failed: ' + str(error)) from error

    def success(self, action, params=None, post=None):
        status, data = self.request(action, params, post)
        require(status == 200 and isinstance(data, dict), 'HTTP 200 object', {'status': status, 'body': data})
        require(type(data.get('schemaVersion')) is int and data['schemaVersion'] == 1, 'schemaVersion integer 1', data)
        return data

    def reject(self, action, params=None, post=None, legacy=False):
        status, data = self.request(action, params, post, legacy)
        require(400 <= status < 500, 'controlled 4xx, never success or 500', {'status': status, 'body': data})
        if not legacy:
            error = data.get('error') if isinstance(data, dict) else None
            require(isinstance(error, dict) and isinstance(error.get('code'), str) and bool(error['code'])
                    and isinstance(error.get('message'), str) and bool(error['message']),
                    'structured error.code and error.message', data)
        return data


def coverage(data, paths):
    cov = data.get('coverage')
    require(isinstance(cov, dict), 'coverage object', cov)
    # Accepted contract (r02-round1-answers Q5, docs/repo-explorer/INTERFACES_V1.md
    # section 1, confirmed by Codex in r08): trackedFileCount counts plain blobs
    # (100644/100755) whose names decode as UTF-8 ONLY. Symlinks and gitlinks stay
    # visible in the tree with a skip reason but are never counted here, so this
    # fixture's 19 plain files plus one symlink and one gitlink must report 19 —
    # accepting 20/21 was R35-T1, a defect in the runner, not in the product.
    counts = {sum(mode in ('100644', '100755') for mode in paths.values())}
    require(type(cov.get('trackedFileCount')) is int and cov['trackedFileCount'] in counts,
            'tracked count matches the plain-blob contract (symlink/gitlink excluded)', cov)
    require(type(cov.get('indexedFileCount')) is int and 0 <= cov['indexedFileCount'] <= cov['trackedFileCount'], 'bounded indexedFileCount', cov)
    require(type(cov.get('partial')) is bool and isinstance(cov.get('skipped'), list), 'partial boolean and skipped list', cov)
    for skip in cov['skipped']:
        require(isinstance(skip, dict) and skip.get('path') in paths and isinstance(skip.get('reason'), str) and bool(skip['reason']), 'known skipped path with explicit reason', skip)
    return cov


def identity(data, project_id, revision, path=None):
    require(data.get('projectId') == project_id and data.get('revision') == revision,
            'same repository context and exact SHA', data)
    if path is not None: require(data.get('path') == path, 'exact requested path', data)


class Runner:
    def __init__(self, manifest, client=None, target=None, degraded=None):
        self.m = manifest; self.client = client; self.target = target or {}; self.degraded = degraded
        self.results = []; self.base = self.latest = self.second = None

    def one(self, key, function):
        before = len(self.client.calls) if self.client else 0
        try:
            if not self.client: raise NotRun('A 集成路径、完整 HEAD 和启动命令尚未交付；未向任何服务发送请求')
            function()
            status, detail = 'PASS', 'All assertions passed against recorded requests'
        except NotRun as error: status, detail = 'NOT_RUN', str(error)
        except Exception as error: status, detail = 'FAIL', str(error)
        calls = self.client.calls[before:] if self.client else []
        self.results.append({'id': key, 'name': GROUPS[key], 'status': status,
                             'severity': ('HIGH' if key in ['D01', 'D02', 'D05', 'D06', 'D07'] else 'MEDIUM') if status == 'FAIL' else None,
                             'detail': detail, 'requests': calls,
                             'reproduce': 'Start the recorded exact A checkout/HEAD and repeat these method/URL/body requests'})
        print(key + ' ' + status + ' ' + GROUPS[key] + (' — ' + detail if status != 'PASS' else ''))

    def need(self, value):
        if value is None: raise NotRun('Prerequisite open failed; no context to check')
        return value

    def open(self, repo, revision, paths):
        d = self.client.success('open', post={'repoPath': repo, 'revision': revision})
        require(isinstance(d.get('projectId'), str) and bool(d['projectId']), 'nonempty projectId', d)
        require(d.get('revision') == (self.m['targetRevision'] if revision == 'HEAD' else revision), 'actual full revision', d)
        require(isinstance(d.get('repositoryName'), str) and bool(d['repositoryName']), 'repositoryName', d)
        caps = d.get('capabilities')
        require(isinstance(caps, dict) and all(type(caps.get(k)) is bool for k in ['files', 'symbols', 'imports', 'changes']), 'four boolean capabilities', caps)
        require(caps['files'] and caps['changes'], 'files and changes installed', caps)
        coverage(d, paths)
        return {'projectId': d['projectId'], 'revision': d['revision']}

    def file(self, ctx, repo, path, start=1, end=200):
        d = self.client.success('file', {**ctx, 'path': path, 'startLine': start, 'endLine': end})
        identity(d, ctx['projectId'], ctx['revision'], path)
        text = blob(repo, ctx['revision'], path).decode('utf-8'); lines = text.splitlines(keepends=True)
        a, b = (start, min(end, len(lines))) if lines else (0, 0)
        expected = ''.join(lines[a - 1:b]) if lines else ''
        require(all(type(d.get(k)) is int for k in ['startLine', 'endLine', 'totalLines']), 'integer line ranges', d)
        require((d['startLine'], d['endLine'], d['totalLines'], d.get('content')) == (a, b, len(lines), expected), 'exact committed text and inclusive range', d)
        require(type(d.get('truncated')) is bool, 'truncated boolean', d)
        if b < len(lines): require(d['truncated'], 'remaining later lines are visible as truncated', d)
        if a in (0, 1) and b == len(lines): require(not d['truncated'], 'full file is not truncated', d)
        # A range omitting only earlier lines has no precise flag semantics in the
        # common plan; preserve the observation rather than inventing a failure.
        return d

    def tree(self, ctx, paths):
        d = self.client.success('tree', ctx); identity(d, ctx['projectId'], ctx['revision'])
        coverage(d, paths); entries = d.get('entries')
        require(isinstance(entries, list), 'entries list', d)
        expected = set(paths)
        for path in paths:
            expected.update('/'.join(path.split('/')[:i]) for i in range(1, len(path.split('/'))))
        actual = [e.get('path') for e in entries if isinstance(e, dict)]
        require(len(actual) == len(entries) == len(set(actual)) and set(actual) == expected, 'exact Git paths and their directories; no root or untracked file', actual)
        for e in entries:
            require('language' in e and e.get('parentPath') == e['path'].rpartition('/')[0] and e.get('kind') in ('file', 'directory'), 'parent, kind and language present', e)
            if e['path'] not in paths:
                require(e['kind'] == 'directory', 'path ancestors are directories', e)
            if e['kind'] == 'directory':
                require(e.get('language') is None, 'directory language null', e)
        again = self.client.success('tree', ctx)
        require(again.get('entries') == entries, 'repeat tree order stable', again)

    def symbols(self, ctx, path, expected):
        d = self.client.success('symbols', {**ctx, 'path': path}); identity(d, ctx['projectId'], ctx['revision'], path)
        require(d.get('status') == 'ok' and d.get('parser') == 'python_ast_v1', 'installed full parser, not legacy or unavailable', d)
        require(isinstance(d.get('warnings'), list) and all(isinstance(w, str) for w in d['warnings']), 'warnings list', d)
        fields = ['name', 'qualified_name', 'kind', 'start_line', 'end_line', 'docstring']
        require(isinstance(d.get('symbols'), list), 'symbols list', d)
        got = [tuple(s.get(k) for k in fields) for s in d['symbols']]
        require(got == expected, 'fixed lexical symbol identities, full lines and docstrings', got)
        for s in d['symbols']:
            require(type(s.get('start_line')) is int and type(s.get('end_line')) is int, 'full integer symbol ranges', s)
        return d

    def relations(self, ctx, path):
        d = self.client.success('relations', {**ctx, 'path': path}); identity(d, ctx['projectId'], ctx['revision'], path)
        require(d.get('status') == 'ok' and isinstance(d.get('imports'), list) and isinstance(d.get('dependents'), list), 'successful static relation lists', d)
        require(isinstance(d.get('warnings'), list) and all(isinstance(w, str) for w in d['warnings']), 'warnings list', d)
        for item in d['imports']:
            r = item.get('resolution')
            require(isinstance(r, dict) and r.get('status') in ['resolved', 'unresolved', 'ambiguous'] and isinstance(r.get('candidates'), list), 'explicit resolution shape', item)
            require((r['status'] == 'resolved' and isinstance(r.get('targetPath'), str) and r['candidates'] == [r['targetPath']]) or (r['status'] != 'resolved' and r.get('targetPath') is None), 'only unique resolved targets', item)
        return d

    def check_open(self):
        self.base = self.open(self.m['repository'], self.m['baseRevision'], self.m['basePaths'])
        require(not any(Path(p).name == 'project-map.json' for p in self.m['basePaths']), 'fixture has no map JSON')
        # r02 Q6 / R49-02: capabilities must express what THIS deployment can
        # do. A complete deployment advertises both parsers, and the endpoints
        # must then really answer with them.
        caps = self.base.get('capabilities')
        require(isinstance(caps, dict) and caps.get('symbols') is True and caps.get('imports') is True,
                'complete deployment advertises both parsers', caps)
        for action in ['symbols', 'relations']:
            result = self.client.success(action, {**self.need(self.base), 'path': 'pkg/service.py'})
            require(result.get('status') != 'unavailable',
                    'advertised capability is actually served', {'action': action, 'result': result})

    def check_files(self):
        ctx = self.need(self.base); self.tree(ctx, self.m['basePaths'])
        for path, mode in self.m['basePaths'].items():
            if mode == '100644' and path not in ['binary.bin', 'invalid-encoding.py', 'oversize.py']:
                self.file(ctx, self.m['repository'], path)
        self.file(ctx, self.m['repository'], 'long.txt', 201, 500)
        self.file(ctx, self.m['repository'], 'long.txt', 600, 800)
        status, d = self.client.request('file', {**ctx, 'path': 'long.txt', 'startLine': 1, 'endLine': 620})
        if status == 200:
            require(d.get('endLine', 621) <= 500 and d.get('truncated') is True, 'at most 500 lines per response', d)
        else:
            require(400 <= status < 500 and isinstance(d.get('error'), dict), 'oversized line window controlled', d)
        self.client.reject('file', {**ctx, 'path': 'untracked-only.py'})

    def check_symbols(self):
        ctx = self.need(self.base)
        self.symbols(ctx, 'pkg/service.py', SYMBOLS)
        self.symbols(ctx, 'empty.py', [])
        for item in SYMBOLS:
            self.file(ctx, self.m['repository'], 'pkg/service.py', item[3], item[4])

    def check_relations(self):
        ctx = self.need(self.base); d = self.relations(ctx, 'pkg/service.py')
        fields = ['kind', 'module', 'level', 'name', 'alias', 'line', 'end_line']
        got = [tuple(i.get(k) for k in fields) + (i['resolution']['status'], i['resolution']['targetPath']) for i in d['imports']]
        require(got == IMPORTS, 'fixed declared imports, order, aliases, relative levels and resolution', got)
        ambiguous = next(i['resolution'] for i in d['imports'] if i['module'] == 'dual')
        require(set(ambiguous['candidates']) == {'dual.py', 'dual/__init__.py'}, 'both ambiguous candidates, no arbitrary winner', ambiguous)
        reverse = self.relations(ctx, 'pkg/utils.py')['dependents']
        require(sorted((i.get('path'), i.get('line'), i.get('end_line')) for i in reverse) ==
                [('pkg/service.py', i, i) for i in [2, 3, 4, 28, 31]], 'resolved-only reverse declarations', reverse)
        src = self.relations(ctx, 'src/consumer.py')
        require(len(src['imports']) == 1 and src['imports'][0]['resolution']['targetPath'] == 'src/srcpkg/helper.py', 'src-layout target', src)
        require(self.relations(ctx, 'empty.py')['imports'] == [], 'valid empty relations')

    def check_changes(self):
        self.latest = self.open(self.m['repository'], 'HEAD', self.m['targetPaths'])
        ctx = self.latest; self.tree(ctx, self.m['targetPaths'])
        self.file(ctx, self.m['repository'], 'pkg/service.py')
        self.symbols(ctx, 'pkg/service.py', SYMBOLS + [('added', 'added', 'function', 34, 35, None)])
        self.file(ctx, self.m['repository'], 'pkg/new.py')
        self.client.reject('file', {**ctx, 'path': 'pkg/old.py'})
        self.client.reject('symbols', {**ctx, 'path': 'pkg/old.py'})
        d = self.client.success('changes', {'projectId': ctx['projectId'], 'base': self.m['baseRevision'], 'target': self.m['targetRevision']})
        require(d.get('projectId') == ctx['projectId'] and d.get('baseRevision') == self.m['baseRevision'] and d.get('targetRevision') == self.m['targetRevision'], 'exact change versions', d)
        got = d.get('changes')
        require(isinstance(got, list), 'change list', got)
        require(sorted((c.get('status'), c.get('path'), c.get('oldPath')) for c in got) == sorted((c['status'], c['path'], c['oldPath']) for c in self.m['expectedChanges']), 'real Git A/M/D/R paths', got)
        base_ctx = self.need(self.base)
        self.file(base_ctx, self.m['repository'], 'pkg/old.py')
        self.file(base_ctx, self.m['repository'], 'pkg/moved.py')
        self.file(ctx, self.m['repository'], 'pkg/relocated.py')
        require(any(i['path'] == 'pkg/new.py' for i in self.relations(ctx, 'pkg/utils.py')['dependents']), 'new reverse relation, no stale target index')

    def check_second(self):
        self.second = self.open(self.m['secondRepository'], self.m['secondRevision'], self.m['secondPaths'])
        require(self.second['projectId'] != self.need(self.base)['projectId'], 'same-name different repos get distinct context IDs', self.second)
        self.tree(self.second, self.m['secondPaths'])
        self.file(self.second, self.m['secondRepository'], 'pkg/service.py')
        self.symbols(self.second, 'pkg/service.py', [('second_only', 'second_only', 'function', 1, 3, '第二仓库独有。')])
        d = self.relations(self.second, 'pkg/service.py')
        require(d['imports'] == [] and d['dependents'] == [], 'second repo relations do not leak first repo', d)
        self.client.reject('file', {**self.second, 'path': 'pkg/utils.py'})
        self.symbols(self.need(self.base), 'pkg/service.py', SYMBOLS)
        self.tree(self.base, self.m['basePaths'])

    def check_errors(self):
        ctx = self.need(self.base)
        for path in ['../outside-canary.txt', '/etc/passwd', '..\\outside-canary.txt', 'C:/outside.txt', 'HEAD:pkg/service.py', ':pkg/service.py', '--help', 'pkg/service.py\x00']:
            self.client.reject('file', {**ctx, 'path': path})
        for start, end in [(0, 1), (-1, 1), ('abc', 2), (1, 0), (10, 2), (900, 901)]:
            self.client.reject('file', {**ctx, 'path': 'pkg/service.py', 'startLine': start, 'endLine': end})
        for revision in ['bad', 'HEAD~1', self.m['secondRevision'], '0' * 40]:
            self.client.reject('tree', {**ctx, 'revision': revision})
        self.client.reject('file', {**ctx, 'projectId': 'unknown-context', 'path': 'pkg/service.py'})
        self.client.reject('open', post={'repoPath': self.m['repository'], 'revision': 'HEAD~1'})
        self.client.reject('changes', {'projectId': ctx['projectId'], 'base': '0' * 40, 'target': self.m['targetRevision']})
        # Legacy error shape is intentionally not redefined by the new contract.
        self.client.reject('evidence', {'path': 'pkg/service.py', 'revision': self.m['baseRevision']}, legacy=True)

    def check_limits(self):
        ctx = self.need(self.base)
        for path in ['binary.bin', 'invalid-encoding.py', 'oversize.py', 'outside-link', 'vendor/submodule']:
            error = self.client.reject('file', {**ctx, 'path': path})
            require('OUTSIDE_CONTENT_MUST_NOT_BE_READ' not in json.dumps(error), 'no symlink outside content', error)
        for action in ['symbols', 'relations']:
            for path, status in [('broken.py', 'parse_error'), ('unsupported.js', 'unsupported')]:
                d = self.client.success(action, {**ctx, 'path': path}); identity(d, ctx['projectId'], ctx['revision'], path)
                field = 'symbols' if action == 'symbols' else 'imports'
                require(d.get('status') == status and d.get(field) == [] and isinstance(d.get('warnings'), list) and bool(d['warnings']), 'explicit failure/unsupported, never ok-empty', d)
                require(all(isinstance(w, str) for w in d['warnings']), 'text warnings', d)
                if action == 'relations': require(d.get('dependents') == [], 'failed or unsupported source does not fabricate dependents', d)
        opened = self.client.success('open', post={'repoPath': self.m['repository'], 'revision': self.m['baseRevision']})
        cov = coverage(opened, self.m['basePaths'])
        require(cov['partial'] and any(i['path'] == 'oversize.py' for i in cov['skipped']), 'size budget visible in partial/skipped', cov)
        require(not (Path(self.m['repository']) / 'EXECUTED_MARKER').exists(), 'fixture source was not executed')
        require(not list((Path(self.m['repository']) / '.git').glob('projectmind-*/records.sqlite3')), 'acceptance did not write Worklog/Continuity database')

    def check_unavailable(self):
        if not self.degraded: raise NotRun('需 A 提供相同目标版本的解析器未接入实例；正常完整实例不能证明缺失分支')
        d = self.degraded.success('open', post={'repoPath': self.m['repository'], 'revision': self.m['baseRevision']})
        ctx = {'projectId': d['projectId'], 'revision': d['revision']}
        require(d['revision'] == self.m['baseRevision'], 'degraded instance exact fixture version', d)
        # R49-02: the degraded instance must not advertise an ability it then
        # refuses — its capabilities have to match the endpoint behaviour.
        caps = d.get('capabilities')
        require(isinstance(caps, dict) and caps.get('symbols') is False and caps.get('imports') is False,
                'degraded deployment advertises no parser capability', caps)
        require(caps.get('files') is True and caps.get('changes') is True,
                'degraded deployment still advertises what it does serve', caps)
        for action in ['symbols', 'relations']:
            result = self.degraded.success(action, {**ctx, 'path': 'pkg/service.py'})
            identity(result, ctx['projectId'], ctx['revision'], 'pkg/service.py')
            require(result.get('status') == 'unavailable' and bool(result.get('warnings')), 'parser absence visible, not success-empty', result)

    def run(self):
        for key, function in zip(GROUPS, [self.check_open, self.check_files, self.check_symbols, self.check_relations,
                                        self.check_changes, self.check_second, self.check_errors, self.check_limits, self.check_unavailable]):
            self.one(key, function)
        return {'schemaVersion': 1, 'role': 'D', 'generatedAt': datetime.now(timezone.utc).isoformat(),
                'target': self.target, 'fixture': self.m,
                'http': self.results, 'degradedRequests': self.degraded.calls if self.degraded else [],
                'ui': [{'step': name, 'status': 'NOT_RUN', 'detail': '未实际操作 A 确切 HEAD 的界面；HTTP 不替代 UI 验收'} for name in UI_STEPS],
                'productAcceptance': 'NOT_PASSED' if any(r['status'] == 'FAIL' for r in self.results) else 'NOT_RUN',
                'toolReadiness': 'READY', 'limits': ['No product implementation modified', 'No fixture source executed', 'No main operation or remote publication']}


def load_fixture(path):
    # R49-05: every text read/write in this runner is explicit UTF-8; the
    # previous locale default (cp936 with UTF-8 mode off) broke the manifest,
    # the UI evidence and the report itself.
    m = json.loads(Path(path).read_text(encoding='utf-8'))
    require(m.get('format') == FORMAT, 'known generated fixture format', m.get('format'))
    for repo_key, sha_key, paths_key in [('repository', 'baseRevision', 'basePaths'), ('repository', 'targetRevision', 'targetPaths'), ('secondRepository', 'secondRevision', 'secondPaths')]:
        repo = Path(m[repo_key]).resolve(); root = Path(m['root']).resolve()
        require(root in repo.parents and (root / '.d-fixture-owner').read_text(encoding='utf-8') == FORMAT, 'owned independent fixture root')
        require(SHA.fullmatch(m[sha_key]) and tracked(repo, m[sha_key]) == m[paths_key], 'manifest versions/paths match actual Git', sha_key)
    require(changes(Path(m['repository']), m['baseRevision'], m['targetRevision']) == m['expectedChanges'], 'actual Git changes match manifest')
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture', required=True, type=Path)
    p.add_argument('--base-url', help='A isolated local origin; omit to record NOT_RUN')
    p.add_argument('--target-checkout', type=Path)
    p.add_argument('--target-head', help='full A commit, never HEAD or branch name')
    p.add_argument('--launch-command', help='actual A startup command; script never executes it')
    p.add_argument('--degraded-base-url', help='optional A parser-absent isolated origin, same target version')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--ui-evidence', type=Path, help='actual six-step UI observation JSON, matching target HEAD/origin')
    args = p.parse_args()
    target = {'checkout': None, 'head': None, 'baseUrl': args.base_url, 'launchCommand': args.launch_command}
    if args.base_url:
        if not args.target_checkout or not args.target_head or not args.launch_command or not SHA.fullmatch(args.target_head):
            p.error('Live acceptance requires target-checkout, full target-head and actual launch-command')
        actual = git(args.target_checkout, 'rev-parse', 'HEAD').decode().strip()
        if actual != args.target_head: p.error('Target checkout HEAD differs from supplied exact HEAD')
        if git(args.target_checkout, 'status', '--porcelain'): p.error('Target checkout is dirty; freeze a clean A commit first')
        target.update(checkout=str(args.target_checkout.resolve()), head=actual)
    manifest = load_fixture(args.fixture)
    runner = Runner(manifest, Client(args.base_url) if args.base_url else None, target,
                    Client(args.degraded_base_url) if args.degraded_base_url else None)
    report = runner.run()
    if args.ui_evidence:
        observed = json.loads(args.ui_evidence.read_text(encoding='utf-8'))
        require(bool(args.base_url) and observed.get('targetHead') == target['head'] and observed.get('baseUrl') == args.base_url, 'UI evidence matches exact live target', observed)
        require(isinstance(observed.get('observer'), str) and bool(observed['observer']) and bool(observed.get('observedAt')), 'named observer and actual timestamp')
        steps = observed.get('steps', [])
        require(len(steps) == len(UI_STEPS) and [step.get('step') for step in steps] == UI_STEPS, 'all six ordered UI steps')
        for step in steps:
            require(step.get('status') in ['PASS', 'FAIL', 'NOT_RUN'] and bool(step.get('detail')) and bool(step.get('evidence')), 'actual UI results and evidence references', step)
        report['ui'] = steps
        report['uiEvidence'] = {'path': str(args.ui_evidence.resolve()), 'observer': observed['observer'], 'observedAt': observed['observedAt'], 'nature': 'participant_observation_not_independently_verified'}
    if args.base_url:
        require(git(args.target_checkout, 'rev-parse', 'HEAD').decode().strip() == target['head'] and not git(args.target_checkout, 'status', '--porcelain'), 'target remained clean at exact HEAD during acceptance')
    statuses = [r['status'] for r in report['http']] + [r['status'] for r in report['ui']]
    report['productAcceptance'] = 'NOT_PASSED' if 'FAIL' in statuses else 'PASS' if all(s == 'PASS' for s in statuses) else 'NOT_RUN'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    print('Report:', args.report.resolve(), '| productAcceptance:', report['productAcceptance'])
    # Incomplete/unexecuted acceptance must not appear green to CI.
    return 0 if report['productAcceptance'] == 'PASS' else 1 if report['productAcceptance'] == 'NOT_PASSED' else 2


if __name__ == '__main__': sys.exit(main())
