"""Configured, authenticated A/B -> D task bridge for one shared server."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import threading

from .contract import ContractError, ERROR_CODES
from extensions.continuity.fix_gateway import FixTaskGateway, RequestContext
from extensions.continuity.fix_tasks import FixTaskService, STATES, render_fix_task
from extensions.continuity.store import Store
from extensions.handoff.architecture import (ArchitectureError, build_version_handoff,
                                           digest, source_locator)


def guarded(function):
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ArchitectureError as exc:
            code = exc.code if exc.code in ERROR_CODES else (
                'VALIDATION_FAILED' if exc.status == 400 else 'EVIDENCE_MISMATCH')
            raise ContractError(code, str(exc), {'dCode': exc.code}) from exc
        except (TypeError, ValueError):
            raise ContractError('VALIDATION_FAILED', '任务字段类型或规范内容无效') from None
    return call


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) \
            or set(value) - set(required) - set(optional):
        raise ContractError('VALIDATION_FAILED', '任务请求缺少必要字段或包含未支持字段')


class GovernedTasks:
    def __init__(self, workbench, backend_b, data_root, origin):
        from deployment.access import _outside_git
        self.workbench, self.backend_b = workbench, backend_b
        root = _outside_git(Path(data_root) / 'd')
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.stat().st_mode & 0o077:
            raise ContractError('STORAGE_FAILED', '任务数据目录必须为私有目录')
        self.store = Store(_outside_git(root / 'continuity.sqlite3'))
        self.store.path.chmod(0o600)
        self.service = FixTaskService(self.store, architecture_repo=backend_b.architecture_repo,
            code_repositories=list(backend_b.code_repositories.values()), actor_identity='authenticated_account')
        self.gateway = FixTaskGateway(self.service, origin, trusted_https_proxy=True)
        self.auth = {}
        self.lock = threading.RLock()

    def status(self):
        configured = callable(self.service.verification_provider)
        return {'available': True, 'kind': 'd_governed_tasks', 'storage': 'private_server_sqlite',
                'actorIdentity': 'authenticated_account', 'verificationConfigured': configured,
                'verification': 'READY' if configured else 'NOT_RUN_AWAITING_CONFIGURATION'}

    def _context(self, meta):
        if not isinstance(meta, dict):
            raise ContractError('REQUEST_FORBIDDEN', '需要真实登录请求上下文')
        context = RequestContext(meta.get('peer', ''), meta.get('host', ''), meta.get('origin', ''),
                                 actor=meta.get('actor', ''), browser_binding=meta.get('browserSession', ''))
        self.gateway._request(context)
        with self.lock, self.gateway.lock:
            self.gateway._prune()
            self.auth = {key: auth for key, auth in self.auth.items()
                         if auth['sessionId'] in self.gateway.sessions}
            auth = self.auth.get(context.browser_binding)
            if auth is None:
                auth = self.gateway.create_session(context.actor, context)
                self.auth[context.browser_binding] = auth
            return replace(context, session_id=auth['sessionId'], csrf_token=auth['csrfToken'])

    def _packet(self, record):
        draft, published = record.get('draft'), record.get('lastPublish') or {}
        if not draft or not published.get('mapRevision'):
            raise ContractError('HUMAN_REVIEW_REQUIRED', '先复核并发布架构版本，再创建治理任务')
        self.workbench._sample_guard(draft)
        identity = self.workbench._envelope(record)['identity']
        if identity.get('mapRevision') != published['mapRevision']:
            raise ContractError('STALE_CONTEXT', '当前草稿已偏离发布版本；先复核并发布更新')
        binding = record.get('backendB') or {}
        if not binding.get('workspaceId'):
            raise ContractError('BACKEND_UNAVAILABLE', '工作区没有真实版本服务绑定')
        envelope = self.backend_b.export_version(binding['workspaceId'], published['mapRevision'])
        version = envelope['version']
        if version['mapId'] != identity.get('mapId') or version['codeRepoId'] != identity.get('codeRepoId') \
                or version['codeRevision'] != identity.get('codeRevision'):
            raise ContractError('STALE_CONTEXT', '工作区身份与不可变版本不一致')
        repo = self.backend_b.code_repositories.get(version['codeRepoId'])
        sources = {'code': source_locator(repo) if repo else None,
                   'architecture': source_locator(self.backend_b.architecture_repo)}
        return build_version_handoff(envelope, workspace_id=record['workspaceId'], sources=sources)

    @guarded
    def hints(self, record):
        packet = self._packet(record)
        version = packet['versionEnvelope']['version']
        covered = set(version['reviewCoverage']['processes'])
        processes = [deepcopy(p) for p in version['graph']['processes'] if p['id'] in covered]
        return {'workspaceId': record['workspaceId'], 'mapRevision': version['mapRevision'],
                'draftRevision': record['draft']['draftRevision'], 'codeRepoId': version['codeRepoId'],
                'codeRevision': version['codeRevision'], 'canCreate': version['codeRepoId'] is not None and bool(processes),
                'disabledReason': 'CODE_REQUIRED' if version['codeRepoId'] is None else (
                    None if processes else 'EXPECTED_PROCESS_REVIEW_REQUIRED'), 'processes': processes,
                'verification': 'NOT_RUN_AWAITING_CONFIGURATION', 'backend': self.status()}

    @staticmethod
    def public_task(task):
        # Keep server-local source locators and full transport packages private.
        return {key: deepcopy(value) for key, value in task.items() if key != 'versionHandoff'}

    @guarded
    def create(self, record, request, meta):
        fields(request, ('expectedMapRevision', 'expectedDraftRevision', 'deviation',
                         'expectedProcessRef', 'evidence', 'scope', 'acceptance'), ('actor',))
        context = self._context(meta)
        packet = self._packet(record)
        version = packet['versionEnvelope']['version']
        if request['expectedMapRevision'] != version['mapRevision'] \
                or request['expectedDraftRevision'] != record['draft']['draftRevision']:
            raise ContractError('STALE_CONTEXT', '任务所见版本或草稿已变化，请重新读取')
        definition = {key: request[key] for key in ('deviation', 'expectedProcessRef', 'evidence', 'scope', 'acceptance')}
        deviation_id = 'dev-' + digest({'workspaceId': record['workspaceId'], 'mapRevision': version['mapRevision'],
                                      'actor': context.actor, 'definition': definition})[7:39]
        task = self.gateway.call('create_fix_task', {
            'packet': packet, 'deviation_id': deviation_id, 'deviation': request['deviation'],
            'expected_process_ref': request['expectedProcessRef'], 'evidence': request['evidence'],
            'scope': request['scope'], 'acceptance': request['acceptance']}, context)
        return {**self.public_task(task), 'taskId': task['id'], 'markdown': render_fix_task(task),
                'backend': self.status()}

    @guarded
    def tasks(self, workspace_id):
        return {'workspaceId': workspace_id,
                'tasks': [dict(self.public_task(t), taskId=t['id']) for t in self.service.listing()
                          if t['workspaceId'] == workspace_id],
                'statuses': list(STATES), 'backend': self.status(),
                'labeled': '服务器持久化任务；回挂后须真实验证与相同浏览器人工确认才能关闭偏差'}

    def _task(self, workspace_id, task_id):
        task = self.service.get(task_id)
        if task['workspaceId'] != workspace_id:
            raise ContractError('NOT_FOUND', '任务不属于当前工作区')
        return task

    @guarded
    def markdown(self, workspace_id, task_id):
        return {'taskId': task_id, 'markdown': render_fix_task(self._task(workspace_id, task_id)),
                'filename': task_id + '.md'}

    @guarded
    def action(self, record, task_id, request, meta):
        context = self._context(meta)
        task = self._task(record['workspaceId'], task_id)
        packet = self._packet(record)
        if packet['versionEnvelope']['version']['mapRevision'] != task['mapRevision']:
            raise ContractError('STALE_CONTEXT', '当前工作区已发布其他版本；不能沿用旧任务确认')
        action = request.get('action') if isinstance(request, dict) else None
        schema = {
            'transition': ('status', 'description'), 'submit': ('revision', 'evidence'),
            'verification_preview': (), 'confirm_verification': ('confirmationToken', 'reason')}
        if action not in schema:
            raise ContractError('VALIDATION_FAILED', '未知任务治理操作')
        required = ('action',) + schema[action]
        if action != 'verification_preview':
            required += ('expectedRevision', 'expectedMapRevision')
        fields(request, required, ('actor',))
        payload = {'task_id': task_id}
        if action != 'verification_preview':
            payload.update(expected_revision=request['expectedRevision'], expected_map_revision=request['expectedMapRevision'])
        for name in schema[action]:
            payload[{'confirmationToken': 'confirmation_token'}.get(name, name)] = request[name]
        result = self.gateway.call(action, payload, context)
        if action == 'verification_preview':
            return result
        return {**self.public_task(result), 'taskId': result['id'], 'backend': self.status()}

    @guarded
    def handover(self, record):
        packet = self._packet(record)
        if any(isinstance(v, str) and v.startswith('local:') for v in packet['sources'].values()):
            raise ContractError('BACKEND_UNAVAILABLE', '跨副本交接需配置可传递的 Git origin；本机路径不导出')
        return packet
