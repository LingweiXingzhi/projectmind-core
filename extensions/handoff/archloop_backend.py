"""Configured A→D seam. Caller JSON cannot choose stores, roots or approvals."""
from copy import deepcopy

from extensions.handoff.architecture import ArchitectureError, require
from extensions.continuity.fix_tasks import render_fix_task


def create_archloop_backend(service, workspace_provider):
    """Register with A.adapter.register('handoff', ...).

    workspace_provider(workspaceId) is A's trusted in-process binding to B's
    version export and the operator/session. It returns versionHandoff, actor,
    scope, deviationId and optional continuityId/logRefs. No fallback identity.
    """
    def dispatch(action, payload):
        require(action == 'create_fix_task', 'INVALID_INPUT', '此接入仅创建修正任务', 400)
        require(isinstance(payload, dict), 'INVALID_INPUT', '请求须为对象', 400)
        context = workspace_provider(payload.get('workspaceId'))
        require(isinstance(context, dict) and all(k in context for k in
                ('versionHandoff', 'actor', 'scope', 'deviationId')),
                'BACKEND_UNAVAILABLE', 'A 尚未登记 B 版本包、操作者或任务范围', 503)
        require(payload.get('workspaceId') == context['versionHandoff'].get('workspaceId'),
                'STALE_CONTEXT', '请求与服务端登记的工作区不同，不能跨工作区创建任务')
        v = context['versionHandoff']['versionEnvelope']['version']
        require(payload.get('mapRevision') == v['mapRevision'], 'STALE_CONTEXT',
                'A 草稿图摘要与 B 已确认图不同；先对齐并确认版本再创建任务')
        task = service.create_fix_task(packet=context['versionHandoff'],
                deviation_id=context['deviationId'], deviation=payload.get('deviation'),
                expected_process_ref=payload.get('expectedProcessRef'),
                evidence=payload.get('evidence'), scope=context['scope'],
                acceptance=payload.get('acceptance'), actor=context['actor'],
                continuity_id=context.get('continuityId'), log_refs=context.get('logRefs'))
        return {**deepcopy(task), 'markdown': render_fix_task(task)}

    def call(action, payload):
        try:
            return dispatch(action, payload)
        except ArchitectureError as exc:
            # A's existing call_backend only preserves its own ContractError.
            try:
                from archloop.contract import ContractError, ERROR_CODES
            except ImportError:
                raise exc
            code = exc.code if exc.code in ERROR_CODES else (
                'BAD_REQUEST' if exc.status == 400 else 'EVIDENCE_MISMATCH')
            raise ContractError(code, str(exc), {'dCode': exc.code}) from exc
    return {'kind': 'd_architecture_handoff_v1', 'call': call}


def contract_info():
    return {'contractCandidate': 'CONTRACT_V1', 'capability': 'handoff',
            'status': 'CONFIGURED_ADAPTER_REQUIRED',
            'actions': ['create_fix_task'],
            'requiredBindings': ['B versionHandoff', 'actor', 'scope', 'deviationId'],
            'note': '旧 ExtensionContext 没有真实会话与版本绑定；不自动注册为已接通后端。'}
