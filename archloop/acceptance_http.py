"""Session-aware acceptance transport; credentials stay in memory, TLS verified."""
from http.client import HTTPConnection, HTTPSConnection
from http.cookies import SimpleCookie
import ipaddress
import json
import socket
import ssl
from urllib.parse import urlsplit

from deployment.access import COOKIE

MAX_BODY = 4 * 1024 * 1024


class AcceptanceHTTP:
    def __init__(self, origin, *, ca=None, connect_ip=None):
        self.origin = origin.rstrip('/')
        self.public = urlsplit(self.origin)
        p = self.public
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password \
                or p.path not in ('', '/') or p.query or p.fragment:
            raise ValueError('验收地址必须是无凭据的站点 origin')
        p.port  # Refuse malformed ports before a request.
        if p.scheme == 'http':
            try:
                local = p.hostname == 'localhost' or ipaddress.ip_address(p.hostname).is_loopback
            except ValueError:
                local = False
            if not local or connect_ip is not None:
                raise ValueError('HTTP 只用于明确的本地演示')
        self.context = ssl.create_default_context(cafile=str(ca) if ca else None)
        self.connect_ip = connect_ip
        self.auth = {}
        self.repositories = []

    def request(self, method, path, payload=None, *, origin=True, authenticated=True):
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//'):
            raise ValueError('验收请求必须使用本站相对路径')
        if self.public.scheme == 'https':
            connect_ip = self.connect_ip
            class Connection(HTTPSConnection):
                def connect(connection):
                    if connect_ip is None:
                        return super().connect()
                    raw = socket.create_connection((connect_ip, connection.port), timeout=connection.timeout)
                    try:
                        connection.sock = connection._context.wrap_socket(raw, server_hostname=connection.host)
                    except Exception:
                        raw.close()
                        raise
            connection = Connection(self.public.hostname, self.public.port or 443, context=self.context, timeout=60)
        else:
            connection = HTTPConnection(self.public.hostname, self.public.port or 80, timeout=60)
        headers = {'Host': self.public.netloc, **(self.auth if authenticated else {})}
        if origin:
            headers['Origin'] = self.origin
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(body) > MAX_BODY:
                raise ValueError('验收请求超过上限')
            headers['Content-Type'] = 'application/json'
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise ValueError('验收响应超过上限')
            # HTTPConnection never follows redirects, including for login.
            try:
                value = json.loads(raw) if raw else None
            except (ValueError, RecursionError):
                value = {'error': {'code': 'NON_JSON'}}
            return response.status, dict(response.getheaders()), value
        finally:
            connection.close()

    def login(self, username, password):
        if self.public.scheme != 'https':
            raise ValueError('登录密码只能通过校验证书的 HTTPS 发送')
        status, headers, body = self.request('POST', '/api/auth/login',
                                            {'username': username, 'password': password})
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get('csrf'), str):
            raise ValueError('验收登录失败（不记录账号凭据或响应）')
        cookie = SimpleCookie()
        cookie.load(headers.get('Set-Cookie', ''))
        if COOKIE not in cookie or not cookie[COOKIE]['secure'] or not cookie[COOKIE]['httponly'] \
                or cookie[COOKIE]['samesite'].lower() != 'strict' or cookie[COOKIE]['path'] != '/':
            raise ValueError('验收登录未提供安全的浏览器会话')
        self.auth = {'Cookie': COOKIE + '=' + cookie[COOKIE].value, 'X-ProjectMind-CSRF': body['csrf']}
        try:
            status, _, session = self.request('GET', '/api/auth/session')
            if status != 200 or not isinstance(session, dict) or not isinstance(session.get('repositories'), list):
                raise ValueError('验收登录没有有效的服务端仓库清单')
            self.repositories = session['repositories']
        except Exception:
            self.close()
            raise

    def close(self):
        if self.auth and self.public.scheme != 'https':
            self.auth = {}; self.repositories = []
            return
        if self.auth:
            try:
                status, _, _ = self.request('POST', '/api/auth/logout', {})
                if status != 200:
                    raise ValueError('验收会话注销失败')
            finally:
                self.auth = {}
                self.repositories = []
