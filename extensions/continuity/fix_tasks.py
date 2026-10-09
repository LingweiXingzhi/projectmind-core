"""Implementation tasks in Continuity's existing store, with CAS and Git checks."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
from datetime import datetime, timezone

from extensions.handoff.architecture import (ArchitectureError, canonical, code_identity,
    commit_exists, digest, evidence_path, full_sha, identity, inspect_version_handoff,
    read_git, require, validate_handoff)

STATES = ('queued', 'received', 'in_progress', 'submitted', 'verification_pending', 'verified', 'rejected')
TRANSITIONS = {'queued': {'received', 'rejected'}, 'received': {'in_progress', 'rejected'},
               'in_progress': {'submitted', 'rejected'}, 'submitted': {'verification_pending'},
               'verification_pending': {'rejected'}, 'rejected': {'in_progress'}, 'verified': set()}
DEFINITION_FIELDS = ('taskType', 'workspaceId', 'mapId', 'mapRevision', 'codeRepoId', 'codeRevision',
    'mapSourceRevision', 'deviationId', 'deviation', 'expectedProcessRef', 'evidence', 'scope',
    'acceptance', 'actor', 'continuityId', 'logRefs', 'versionHandoff')


def now():
    return datetime.now(timezone.utc).isoformat()


def note(value, name, limit=4000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit,
            'INVALID_INPUT', name + '不能为空或超限', 400)
    return value.strip()


@dataclass(frozen=True)
class VerificationReceipt:
    task_id: str
    task_revision: int
    submitted_revision: str
    command: tuple
    exit_code: int
    output_digest: str
    observed_at: str
    observation: str
    recheck_ref: str
    map_revision: str
    fixture_only: bool = False


class FixTaskService:
    """No imported command execution; configured repository paths never come from JSON."""
    def __init__(self, continuity_store, *, architecture_repo, code_repositories, verification_provider=None,
                 actor_identity='local_operator_declaration'):
        require(actor_identity in ('local_operator_declaration', 'authenticated_account'),
                'INVALID_INPUT', '操作者身份来源必须由运行入口配置', 400)
        self.actor_identity = actor_identity
        self.store = continuity_store
        self.architecture_repo = Path(architecture_repo).resolve()
        self.code_repositories = {code_identity(p): Path(p).resolve() for p in code_repositories}
        self._receipts = {}
        self.verification_provider = verification_provider
        with self.store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS architecture_fix_tasks
                (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS architecture_fix_history
                (id TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL,
                 PRIMARY KEY(id,revision));''')

    def discard_verification(self, token):
        """Release an expired/revoked gateway preview without changing a task."""
        self._receipts.pop(token, None)

    def get(self, task_id, db=None):
        identity(task_id)
        if db is None:
            with self.store.connect() as conn:
                return self.get(task_id, conn)
        row = db.execute('SELECT document FROM architecture_fix_tasks WHERE id=?', (task_id,)).fetchone()
        require(row is not None, 'NOT_FOUND', '实施任务不存在', 404)
        return json.loads(row[0])

    def listing(self):
        with self.store.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT document FROM architecture_fix_tasks ORDER BY id')]

    def history(self, task_id):
        identity(task_id)
        with self.store.connect() as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT document FROM architecture_fix_history WHERE id=? ORDER BY revision', (task_id,))]

    def export_task(self, task_id):
        body = {'schemaVersion': 'architecture_fix_task_transfer_v1', 'task': self.get(task_id),
                'trust': 'participant_record_unverified'}
        return {**body, 'transportDigest': digest(body)}

    def receive_task(self, packet, *, actor, local_continuity_id=None):
        """Second client imports into the SAME Continuity store, never closes a deviation."""
        require(isinstance(packet, dict) and set(packet) == {'schemaVersion','task','trust','transportDigest'})
        require(packet['schemaVersion'] == 'architecture_fix_task_transfer_v1'
                and packet['trust'] == 'participant_record_unverified'
                and packet['transportDigest'] == digest({k:v for k,v in packet.items() if k != 'transportDigest'}))
        task = deepcopy(packet['task']); actor = note(actor, '接手者', 100)
        payload = {k:task[k] for k in DEFINITION_FIELDS}
        require(task['definitionDigest'] == digest(payload), 'EVIDENCE_MISMATCH', '任务定义摘要不匹配')
        expected_id = 'fix-' + digest({k:payload[k] for k in ('workspaceId','mapRevision','codeRevision','deviationId')})[7:39]
        require(task['id'] == expected_id and task['status'] in STATES
                and type(task['revision']) is int and task['revision'] > 0)
        v = validate_handoff(task['versionHandoff'])['versionEnvelope']['version']
        require(all(task[k] == v[k] for k in ('mapId','mapRevision','codeRepoId','codeRevision')))
        require(task['mapSourceRevision'] == task['versionHandoff']['versionEnvelope']['provenance'].get('mapSourceRevision'))
        # Validate the original definition using normal creation; transaction and
        # idempotence preserve any local existing task rather than overwrite it.
        existing = None
        with self.store.connect() as db:
            row = db.execute('SELECT document FROM architecture_fix_tasks WHERE id=?',(task['id'],)).fetchone()
            if row:
                existing = json.loads(row[0])
        if existing:
            require(existing['definitionDigest'] == task['definitionDigest'], 'REVISION_CONFLICT', '本机同任务定义不同')
            return existing
        base = self.create_fix_task(packet=task['versionHandoff'],deviation_id=task['deviationId'],
            deviation=task['deviation'],expected_process_ref=task['expectedProcessRef'],evidence=task['evidence'],
            scope=task['scope'],acceptance=task['acceptance'],actor=task['actor'],
            # Imported local IDs are references, not permission to access another client DB.
            continuity_id=task['continuityId'],local_continuity_id=local_continuity_id,log_refs=task['logRefs'])
        if base['revision'] != 1 or base['status'] != 'queued':
            return base
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            local = self._match(db,base['id'],base['revision'],base['mapRevision'])
            local.update(status='received',deviationStatus='open',revision=local['revision']+1,
                actorIdentity='imported_participant_claim', receivedBy=actor,
                receivedByIdentity=self.actor_identity,
                importedHistory={'status':task['status'],'submittedRevision':task.get('submittedRevision'),
                    'events':task.get('events',[]),'verification':task.get('verification'),
                    'trust':'imported_participant_record_unverified'},
                submittedRevision=None,verification=None)
            local['events'].append({'kind':'received','actor':actor,'note':'第二客户端接手；原完成记录未独立核实','at':now()})
            return self._write(db,local)

    def _write(self, db, task):
        raw = canonical(task).decode()
        db.execute('INSERT OR REPLACE INTO architecture_fix_tasks VALUES(?,?,?)',
                   (task['id'], task['revision'], raw))
        db.execute('INSERT INTO architecture_fix_history VALUES(?,?,?)',
                   (task['id'], task['revision'], raw))
        return deepcopy(task)

    def _match(self, db, task_id, expected_revision, expected_map_revision):
        task = self.get(task_id, db)
        require(type(expected_revision) is int and task['revision'] == expected_revision,
                'REVISION_CONFLICT', '任务已更新，请保留输入并重读')
        require(expected_map_revision == task['mapRevision'], 'STALE_CONTEXT', '不能跨图版本继承旧任务/审阅')
        return task

    def _check(self, task):
        repo = self.code_repositories.get(task['codeRepoId'])
        require(repo is not None, 'STALE_CONTEXT', '代码仓库未登记')
        return inspect_version_handoff(task['versionHandoff'], architecture_repo=self.architecture_repo,
                                       code_repo=repo)

    def create_fix_task(self, *, packet, deviation_id, deviation, expected_process_ref,
                        evidence, scope, acceptance, actor, continuity_id=None, log_refs=None,
                        local_continuity_id=None):
        packet = validate_handoff(packet)
        v = packet['versionEnvelope']['version']
        require(v['codeRepoId'] is not None, 'CODE_REQUIRED', '规划图没有代码；先显式关联代码再创建实施修正任务')
        identity(deviation_id); actor = note(actor, '操作者', 100)
        deviation = note(deviation, '偏差描述'); acceptance = note(acceptance, '验收要求')
        require(isinstance(scope, list) and 0 < len(scope) <= 100, 'INVALID_INPUT', '需要明确允许改动路径', 400)
        scope = sorted(set(evidence_path(p) for p in scope))
        require(isinstance(evidence, list) and 0 < len(evidence) <= 100,
                'INVALID_INPUT', '修正实现需要观察证据', 400)
        require(isinstance(expected_process_ref, dict)
                and set(expected_process_ref) == {'processId', 'stepIds'},
                'INVALID_INPUT', '需要固定期望过程与步骤', 400)
        process_id = identity(expected_process_ref['processId'])
        processes = {p['id']: p for p in v['graph']['processes']}
        require(process_id in processes and process_id in v['reviewCoverage']['processes'],
                'EVIDENCE_MISMATCH', '期望过程尚未纳入确认范围')
        ids = expected_process_ref['stepIds']
        require(isinstance(ids, list) and ids and len(set(ids)) == len(ids)
                and set(ids) <= {s['id'] for s in processes[process_id]['steps']})
        for e in evidence:
            require(isinstance(e, dict) and e.get('kind') in ('test_observation', 'trace_observation', 'code'),
                    'EVIDENCE_MISMATCH', '静态缺失或 AI 声明不能替代观察证据')
            require(e.get('codeRevision') == v['codeRevision'] and e.get('codeRepoId') == v['codeRepoId'])
            note(e.get('detail'), '证据说明')
            if e.get('kind') == 'code':
                evidence_path(e.get('path'))
        if continuity_id is not None:
            try:
                record = self.store.get(local_continuity_id or continuity_id)
            except Exception as exc:
                raise ArchitectureError('LOCAL_REFERENCE_REQUIRED', '先导入原接续记录并登记本机记录 ID') from exc
            require(local_continuity_id in (None, continuity_id) or record.get('importedFrom') == continuity_id,
                    'EVIDENCE_MISMATCH', '本机接续记录不是此原记录的导入副本')
        else:
            require(local_continuity_id is None, 'EVIDENCE_MISMATCH', '没有原接续 ID 时不能凭空绑定本机记录')
        log_refs = log_refs or []
        require(isinstance(log_refs, list) and len(log_refs) <= 100)
        for ref in log_refs:
            require(isinstance(ref, dict) and isinstance(ref.get('id'), str)
                    and type(ref.get('version')) is int and ref['version'] > 0
                    and ref.get('status') == 'contributor_record_unverified')
        payload = {'taskType': 'implementation_fix', 'workspaceId': packet['workspaceId'],
                   **{k: v[k] for k in ('mapId', 'mapRevision', 'codeRepoId', 'codeRevision')},
                   'mapSourceRevision': packet['versionEnvelope']['provenance'].get('mapSourceRevision'),
                   'deviationId': deviation_id, 'deviation': deviation,
                   'expectedProcessRef': deepcopy(expected_process_ref), 'evidence': deepcopy(evidence),
                   'scope': scope, 'acceptance': acceptance, 'actor': actor,
                   'continuityId': continuity_id, 'logRefs': deepcopy(log_refs), 'versionHandoff': packet}
        task_id = 'fix-' + digest({k: payload[k] for k in ('workspaceId', 'mapRevision', 'codeRevision', 'deviationId')})[7:39]
        repo = self.code_repositories.get(v['codeRepoId'])
        require(repo is not None, 'STALE_CONTEXT', '代码仓库未登记')
        inspect_version_handoff(packet, architecture_repo=self.architecture_repo, code_repo=repo)
        for e in evidence:
            if e['kind'] == 'code':
                listing = read_git(repo, 'ls-tree', '-z', v['codeRevision'], '--', e['path'])
                require(listing.startswith(b'100644 blob ') or listing.startswith(b'100755 blob '),
                        'EVIDENCE_MISMATCH', '观察引用的代码文件不存在或不是普通 blob')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT document FROM architecture_fix_tasks WHERE id=?', (task_id,)).fetchone()
            if existing:
                task = json.loads(existing[0])
                require(task['definitionDigest'] == digest(payload), 'REVISION_CONFLICT', '同一偏差任务定义不同')
                return task
            task = {**payload, 'id': task_id, 'revision': 1, 'status': 'queued',
                    'actorIdentity': self.actor_identity,
                    'deviationStatus': 'open', 'definitionDigest': digest(payload), 'submittedRevision': None,
                    'localContinuityId': local_continuity_id or continuity_id,
                    'events': [{'kind': 'queued', 'actor': actor, 'note': deviation, 'at': now()}],
                    'verification': None, 'limits': [
                        '操作者由当前服务器登录会话登记；导入包仍是未经认证的参与者记录。'
                        if self.actor_identity == 'authenticated_account'
                        else '任务与反馈为本机参与者记录，不是身份认证。',
                        '提交存在不证明偏差消失；C 复核、真实验证及人确认后才关闭。']}
            return self._write(db, task)

    def transition(self, task_id, *, expected_revision, expected_map_revision, status, actor, description):
        require(status in ('received', 'in_progress', 'rejected'), 'INVALID_INPUT', '回挂/核验有独立操作', 400)
        actor = note(actor, '操作者', 100); description = note(description, '实际反馈')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task = self._match(db, task_id, expected_revision, expected_map_revision)
            require(status in TRANSITIONS[task['status']], 'INVALID_TRANSITION', '当前状态不允许此操作')
            task.update(status=status, revision=task['revision'] + 1)
            task['events'].append({'kind': status, 'actor': actor, 'note': description, 'at': now()})
            return self._write(db, task)

    def submit(self, task_id, *, expected_revision, expected_map_revision, revision, actor, evidence):
        full_sha(revision); actor = note(actor, '操作者', 100); evidence = note(evidence, '提交验证依据')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task = self._match(db, task_id, expected_revision, expected_map_revision)
            require(task['status'] == 'in_progress', 'INVALID_TRANSITION', '先接手并开始工作再回挂')
            self._check(task)
            repo = self.code_repositories[task['codeRepoId']]
            require(code_identity(repo) == task['codeRepoId'], 'STALE_CONTEXT', '代码身份变化')
            commit_exists(repo, revision)
            require(revision != task['codeRevision'], 'STALE_CONTEXT', '旧基线不是修正提交')
            # rev-list returns full parent graph; an ancestor must be present.
            ancestors = read_git(repo, 'rev-list', revision).decode().splitlines()
            require(task['codeRevision'] in ancestors, 'STALE_CONTEXT', '修正提交不继承约定基线')
            branches = read_git(repo, 'for-each-ref', '--format=%(refname:short)', '--contains=' + revision,
                                'refs/heads', 'refs/remotes').decode().splitlines()
            branch = next((b for b in branches if b.split('/')[-1] not in ('main', 'master', 'HEAD')), None)
            require(branch is not None, 'BRANCH_REQUIRED', '修正提交须来自独立开发分支')
            raw = read_git(repo, 'diff', '--name-status', '--no-renames', '-z',
                           task['codeRevision'], revision, '--').split(b'\0')
            paths = [raw[i+1].decode('utf-8') for i in range(0, len(raw)-1, 2)]
            require(paths and set(paths) <= set(task['scope']), 'SCOPE_MISMATCH', '提交无变化或超出约定改动范围')
            # The delivered branch contains its whole history. A later revert
            # must not conceal an out-of-scope file in an intermediate commit.
            commits = read_git(repo, 'rev-list', task['codeRevision'] + '..' + revision).decode().splitlines()
            for commit in commits:
                touched = read_git(repo, 'diff-tree', '--no-commit-id', '--name-only',
                    '--no-renames', '--root', '-r', '-m', '-z', commit, '--').split(b'\0')
                require({p.decode('utf-8') for p in touched if p} <= set(task['scope']),
                        'SCOPE_MISMATCH', '交付历史包含范围外文件，后续撤销不能绕过任务范围')
            task.update(status='verification_pending', deviationStatus='verification_pending',
                        submittedRevision=revision, implementationBranch=branch,
                        revision=task['revision'] + 1, verification=None)
            for kind in ('submitted', 'verification_pending'):
                task['events'].append({'kind': kind, 'actor': actor, 'note': evidence,
                                       'codeRevision': revision, 'at': now()})
            return self._write(db, task)

    def run_fixture_verification(self, task_id, *, command, fixture_root, observation, recheck_ref):
        """Explicit fixture-only verifier. Never execute commands from imported tasks.

        A production verifier must issue its own trusted in-process receipt after
        observing the submitted version and C recheck. JSON receipts are rejected.
        """
        task = self.get(task_id)
        require(task['status'] == 'verification_pending', 'INVALID_TRANSITION', '尚未回挂提交')
        self._check(task)
        repo = self.code_repositories[task['codeRepoId']]
        root = Path(fixture_root).resolve()
        require(root != repo and root in repo.parents and (root / '.projectmind-test-fixture').is_file(),
                'FORBIDDEN', '只允许显式临时测试夹具执行实现验证', 403)
        require(isinstance(command, (tuple, list)) and command and all(isinstance(x, str) for x in command),
                'INVALID_INPUT', '验证命令须由调用者配置', 400)
        require(read_git(repo, 'rev-parse', 'HEAD').decode().strip() == task['submittedRevision'],
                'STALE_CONTEXT', '验证工作区必须是回挂版本')
        result = subprocess.run(list(command), cwd=repo, capture_output=True, timeout=30,
                                stdin=subprocess.DEVNULL, env={
                                    'PATH': __import__('os').environ.get('PATH', ''),
                                    'PYTHONIOENCODING': 'utf-8'})
        self._check(task)
        require(read_git(repo, 'rev-parse', 'HEAD').decode().strip() == task['submittedRevision'],
                'STALE_CONTEXT', '验证期间代码版本变化')
        receipt = VerificationReceipt(task_id, task['revision'], task['submittedRevision'], tuple(command),
            result.returncode, 'sha256:' + __import__('hashlib').sha256(result.stdout + b'\0' + result.stderr).hexdigest(),
            now(), note(observation, '观察结论'), note(recheck_ref, 'C 复核引用'), task['mapRevision'], True)
        token = secrets.token_urlsafe(32); self._receipts[token] = receipt
        return token, {'exitCode': result.returncode, 'stdout': result.stdout.decode('utf-8', errors='replace')[:12000],
                       'stderr': result.stderr.decode('utf-8', errors='replace')[:12000],
                       'outputDigest': receipt.output_digest, 'command': list(command),
                       'submittedRevision': receipt.submitted_revision, 'fixtureOnly': True}

    def run_verification(self, task_id):
        """Call a registered trusted D/C observation provider, never a JSON command."""
        task = self.get(task_id)
        require(task['status'] == 'verification_pending', 'INVALID_TRANSITION', '尚未回挂提交')
        self._check(task)
        require(callable(self.verification_provider), 'BACKEND_UNAVAILABLE',
                '尚未接入真实验证与 C 复核提供者', 503)
        repo = self.code_repositories[task['codeRepoId']]
        require(read_git(repo, 'rev-parse', 'HEAD').decode().strip() == task['submittedRevision'],
                'STALE_CONTEXT', '验证工作区不是回挂代码版本')
        receipt = self.verification_provider(deepcopy(task))
        require(isinstance(receipt, VerificationReceipt) and receipt.task_id == task_id
                and receipt.task_revision == task['revision']
                and receipt.submitted_revision == task['submittedRevision']
                and receipt.map_revision == task['mapRevision'] and receipt.fixture_only is False,
                'EVIDENCE_MISMATCH', '验证提供者返回过期、样例或错误任务的结果')
        note(receipt.recheck_ref, 'C 复核引用'); note(receipt.observation, '实际观察')
        require(type(receipt.exit_code) is int and isinstance(receipt.output_digest, str)
                and __import__('re').fullmatch(r'sha256:[0-9a-f]{64}', receipt.output_digest),
                'EVIDENCE_MISMATCH', '验证结果需要退出码与原始证据摘要')
        self._check(task)
        require(read_git(repo, 'rev-parse', 'HEAD').decode().strip() == task['submittedRevision'],
                'STALE_CONTEXT', '验证期间回挂版本已变化')
        token = secrets.token_urlsafe(32); self._receipts[token] = receipt
        return token, {'exitCode': receipt.exit_code, 'outputDigest': receipt.output_digest,
                       'submittedRevision': receipt.submitted_revision, 'recheckRef': receipt.recheck_ref,
                       'observedAt': receipt.observed_at, 'observation': receipt.observation, 'fixtureOnly': False}

    def confirm_verification(self, task_id, *, token, expected_revision, expected_map_revision,
                             actor, reason, human_confirmed):
        require(human_confirmed is True, 'HUMAN_REVIEW_REQUIRED', '需要人明确确认', 403)
        actor = note(actor, '确认人', 100); reason = note(reason, '确认理由')
        receipt = self._receipts.get(token)
        require(isinstance(receipt, VerificationReceipt), 'VERIFICATION_REQUIRED', '需要本次真实验证凭据', 403)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task = self._match(db, task_id, expected_revision, expected_map_revision)
            require(task['status'] == 'verification_pending' and receipt.task_id == task_id
                    and receipt.task_revision == task['revision']
                    and receipt.submitted_revision == task['submittedRevision']
                    and receipt.map_revision == task['mapRevision'],
                    'STALE_CONTEXT', '验证已过期或属于另一个任务')
            self._check(task)
            require(read_git(self.code_repositories[task['codeRepoId']], 'rev-parse', 'HEAD').decode().strip()
                    == receipt.submitted_revision, 'STALE_CONTEXT', '确认前代码版本已变化，重新核验')
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(receipt.observed_at)).total_seconds()
            require(0 <= age <= 600, 'STALE_CONTEXT', '验证凭据已过期，重新预览')
            require(receipt.exit_code == 0, 'VERIFICATION_FAILED', '验证失败，偏差保持未关闭')
            task.update(status='verified', deviationStatus='closed', revision=task['revision'] + 1,
                        verification={'submittedRevision': receipt.submitted_revision, 'command': list(receipt.command),
                            'exitCode': receipt.exit_code, 'outputDigest': receipt.output_digest,
                            'observedAt': receipt.observed_at, 'observation': receipt.observation,
                            'recheckRef': receipt.recheck_ref, 'actor': actor, 'reason': reason,
                            'actorIdentity': self.actor_identity, 'fixtureOnly': receipt.fixture_only})
            task['events'].append({'kind': 'verified', 'actor': actor, 'note': reason, 'at': now()})
            answer = self._write(db, task)
        self._receipts.pop(token, None)
        return answer


def render_fix_task(task):
    lines = ['# 修正实现任务', '', '任务：' + task['id'], '状态：' + task['status'],
             '偏差：' + task['deviation'], '', '代码基线：' + task['codeRevision'],
             '架构版本：' + task['mapRevision'], '架构来源：' + str(task['mapSourceRevision']),
             '', '允许改动：'] + ['- ' + p for p in task['scope']]
    lines += ['', '验收要求：' + task['acceptance'], '', '观察证据：',
              json.dumps(task['evidence'], ensure_ascii=False), '',
              '期望过程：' + json.dumps(task['expectedProcessRef'], ensure_ascii=False), '',
              '未知与限制：'] + ['- ' + x for x in task['limits']]
    return '\n'.join(lines) + '\n'


from extensions.handoff.architecture import input_guard
for _method in ('create_fix_task', 'transition', 'submit', 'confirm_verification', 'run_verification','receive_task'):
    setattr(FixTaskService, _method, input_guard(getattr(FixTaskService, _method)))
