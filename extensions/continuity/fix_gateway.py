"""D's protected in-process gateway; A supplies actual HTTP metadata.

This is local operator session protection, not cloud authentication.
Legacy ExtensionContext is deliberately insufficient to use this write surface.
"""
from dataclasses import dataclass
import hmac
import ipaddress
import secrets
import time
from urllib.parse import urlsplit

from extensions.handoff.architecture import require
from extensions.continuity.fix_tasks import note


@dataclass(frozen=True)
class RequestContext:
    peer: str
    host: str
    origin: str
    session_id: str = ''
    csrf_token: str = ''


class FixTaskGateway:
    def __init__(self, service, allowed_origin, *, preview_provider=None):
        u = urlsplit(allowed_origin)
        require(u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost', '::1')
                and u.port and not u.path and not u.query and not u.fragment,
                'INVALID_INPUT', '必须配置完整本机同源地址', 400)
        self.service, self.origin, self.host = service, allowed_origin, u.netloc
        self.sessions, self.confirmations = {}, {}
        self.preview_provider = preview_provider or service.run_verification

    def _request(self, context):
        require(isinstance(context, RequestContext), 'REQUEST_FORBIDDEN', '请求元数据不能来自 JSON', 403)
        try:
            local = ipaddress.ip_address(context.peer).is_loopback
        except (ValueError, TypeError):
            local = False
        require(local and context.host == self.host and context.origin == self.origin,
                'REQUEST_FORBIDDEN', '只允许本机同源操作', 403)

    def create_session(self, actor, context):
        self._request(context)
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.sessions[sid] = {'actor': note(actor, '操作者', 100), 'csrf': csrf, 'expires': time.time()+3600}
        return {'sessionId': sid, 'csrfToken': csrf, 'actorIdentity': 'local_operator_declaration'}

    def _session(self, context):
        self._request(context)
        session = self.sessions.get(context.session_id)
        require(session is not None and session['expires'] > time.time()
                and isinstance(context.csrf_token, str) and hmac.compare_digest(session['csrf'], context.csrf_token),
                'REQUEST_FORBIDDEN', '会话或防伪令牌无效', 403)
        return session

    def call(self, action, payload, context):
        session = self._session(context)
        require(isinstance(payload, dict) and not set(payload) & {'actor', 'peer', 'host', 'origin',
                'human_confirmed', 'command', 'fixture_root', 'verification_provider', 'session_id', 'csrf_token'},
                'REQUEST_FORBIDDEN', '身份、命令与授权由服务端提供', 403)
        if action == 'create_fix_task':
            return self.service.create_fix_task(**payload, actor=session['actor'])
        if action == 'receive_task':
            return self.service.receive_task(**payload, actor=session['actor'])
        if action == 'transition':
            return self.service.transition(**payload, actor=session['actor'])
        if action == 'submit':
            return self.service.submit(**payload, actor=session['actor'])
        if action == 'verification_preview':
            require(set(payload) == {'task_id'}, 'INVALID_INPUT', '验证预览只接收任务 ID', 400)
            token, result = self.preview_provider(payload['task_id'])
            confirmation = secrets.token_urlsafe(32)
            self.confirmations[confirmation] = {'session': context.session_id, 'token': token,
                'task_id': payload['task_id'], 'expires': time.time()+600}
            return {'confirmationToken': confirmation, 'verification': result}
        if action == 'confirm_verification':
            request = dict(payload); confirmation = self.confirmations.get(request.pop('confirmation_token', None))
            require(confirmation is not None and confirmation['session'] == context.session_id
                    and confirmation['task_id'] == request.get('task_id') and confirmation['expires'] > time.time(),
                    'REQUEST_FORBIDDEN', '确认令牌过期或属于另一会话/任务', 403)
            result = self.service.confirm_verification(**request, token=confirmation['token'],
                actor=session['actor'], human_confirmed=True)
            return result
        require(False, 'INVALID_INPUT', '未知实施任务操作', 400)
