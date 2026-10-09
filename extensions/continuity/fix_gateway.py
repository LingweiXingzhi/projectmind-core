"""D's protected in-process gateway; A supplies actual HTTP metadata.

Default sessions are local operator declarations. The explicit HTTPS mode
requires the authenticated server's actor and browser binding on every call.
Legacy ExtensionContext is deliberately insufficient to use this write surface.
"""
from dataclasses import dataclass
from functools import wraps
import hmac
import ipaddress
import secrets
import time
import re
import threading
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
    actor: str = ''
    browser_binding: str = ''


def serialized(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        with self.lock:
            return function(self, *args, **kwargs)
    return wrapped


class FixTaskGateway:
    def __init__(self, service, allowed_origin, *, preview_provider=None, trusted_https_proxy=False,
                 max_sessions=128, max_confirmations=256, clock=time.time):
        u = urlsplit(allowed_origin)
        if trusted_https_proxy:
            from extensions.architecture_workspace.deployment_preflight import validate_origin
            u = validate_origin(allowed_origin, public=True)
        else:
            require(u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost', '::1')
                and u.port and not u.path and not u.query and not u.fragment,
                'INVALID_INPUT', '必须配置完整本机同源地址', 400)
        require(type(max_sessions) is int and max_sessions > 0 and type(max_confirmations) is int
                and max_confirmations > 0, 'INVALID_INPUT', '会话和预览需要明确容量', 400)
        self.service, self.origin, self.host = service, allowed_origin, u.netloc
        self.sessions, self.confirmations = {}, {}
        self.preview_provider = preview_provider or service.run_verification
        self.public = trusted_https_proxy
        self.max_sessions, self.max_confirmations, self.clock = max_sessions, max_confirmations, clock
        self.lock = threading.RLock()
        self.discard_provider = getattr(service, 'discard_verification', lambda token: None)

    def _discard(self, key):
        confirmation = self.confirmations.pop(key)
        self.discard_provider(confirmation['token'])

    def _prune(self):
        current = self.clock()
        for sid in [sid for sid, value in self.sessions.items() if value['expires'] <= current]:
            del self.sessions[sid]
        for key in [key for key, value in self.confirmations.items()
                    if value['expires'] <= current or value['session'] not in self.sessions]:
            self._discard(key)

    def _request(self, context):
        require(isinstance(context, RequestContext), 'REQUEST_FORBIDDEN', '请求元数据不能来自 JSON', 403)
        try:
            local = ipaddress.ip_address(context.peer).is_loopback
        except (ValueError, TypeError):
            local = False
        require(local and context.host == self.host and context.origin == self.origin,
                'REQUEST_FORBIDDEN', '只接受已配置入口的同源操作', 403)
        if self.public:
            require(isinstance(context.actor, str) and context.actor.strip()
                    and isinstance(context.browser_binding, str)
                    and re.fullmatch(r'[0-9a-f]{64}', context.browser_binding),
                    'REQUEST_FORBIDDEN', '需要运行入口注入的真实登录与浏览器身份', 403)

    @serialized
    def create_session(self, actor, context):
        self._request(context)
        self._prune()
        require(not self.public or actor == context.actor,
                'REQUEST_FORBIDDEN', '会话操作者必须来自登录身份', 403)
        require(len(self.sessions) < self.max_sessions, 'BACKEND_UNAVAILABLE', '任务会话容量已满', 503)
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        require(sid not in self.sessions, 'BACKEND_UNAVAILABLE', '会话标识碰撞，请重试', 503)
        self.sessions[sid] = {'actor': note(actor, '操作者', 100), 'csrf': csrf,
                             'expires': self.clock()+3600, 'binding': context.browser_binding}
        return {'sessionId': sid, 'csrfToken': csrf,
                'actorIdentity': 'authenticated_account' if self.public else 'local_operator_declaration'}

    def _session(self, context):
        self._request(context)
        self._prune()
        session = self.sessions.get(context.session_id)
        require(session is not None and isinstance(context.csrf_token, str) and context.csrf_token.isascii()
                and hmac.compare_digest(session['csrf'], context.csrf_token)
                and (not self.public or (session['binding'] == context.browser_binding
                                         and session['actor'] == context.actor)),
                'REQUEST_FORBIDDEN', '会话或防伪令牌无效', 403)
        return session

    @serialized
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
            require(len(self.confirmations) < self.max_confirmations,
                    'BACKEND_UNAVAILABLE', '验证预览容量已满；等待过期或完成确认', 503)
            token, result = self.preview_provider(payload['task_id'])
            confirmation = secrets.token_urlsafe(32)
            if confirmation in self.confirmations:
                self.discard_provider(token)
                require(False, 'BACKEND_UNAVAILABLE', '预览标识碰撞，请重试', 503)
            self.confirmations[confirmation] = {'session': context.session_id, 'token': token,
                'task_id': payload['task_id'], 'expires': self.clock()+600}
            return {'confirmationToken': confirmation, 'verification': result}
        if action == 'confirm_verification':
            request = dict(payload); key = request.pop('confirmation_token', None)
            confirmation = self.confirmations.get(key)
            require(confirmation is not None and confirmation['session'] == context.session_id
                    and confirmation['task_id'] == request.get('task_id') and confirmation['expires'] > self.clock(),
                    'REQUEST_FORBIDDEN', '确认令牌过期或属于另一会话/任务', 403)
            result = self.service.confirm_verification(**request, token=confirmation['token'],
                actor=session['actor'], human_confirmed=True)
            self._discard(key)
            return result
        require(False, 'INVALID_INPUT', '未知实施任务操作', 400)
