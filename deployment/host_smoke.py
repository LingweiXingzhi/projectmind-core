"""HTTPS ingress check: verify CA/hostname, login and logout, never approve a graph."""
import argparse
import getpass
from http.client import HTTPSConnection
from http.cookies import SimpleCookie
import json
from pathlib import Path
import socket
import ssl

from .access import COOKIE, AccessError, check
from .host import private_json
from extensions.architecture_workspace.deployment_preflight import validate_origin


def collect(origin, *, ca=None, connect_ip=None, username=None, password=None):
    public = validate_origin(origin, public=True)
    context = ssl.create_default_context(cafile=str(ca) if ca else None)
    observations = []

    class Connection(HTTPSConnection):
        def connect(self):
            if connect_ip is None:
                return super().connect()
            raw = socket.create_connection((connect_ip, self.port), timeout=self.timeout)
            try: self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
            except Exception:
                raw.close(); raise

    def request(name, method, route, expected, body=None, auth=None, browser_origin=origin):
        connection = Connection(public.hostname, public.port or 443, context=context, timeout=10)
        headers = {'Host': public.netloc, 'Content-Type': 'application/json'}
        if browser_origin is not None: headers['Origin'] = browser_origin
        headers.update(auth or {})
        try:
            connection.request(method, route, body=json.dumps(body).encode() if body is not None else None, headers=headers)
            response = connection.getresponse(); raw = response.read(262145)
            check(len(raw) <= 262144, 'SMOKE_RESPONSE_TOO_LARGE')
            observations.append({'check': name, 'status': response.status, 'expected': expected,
                                 'passed': response.status == expected})
            check(response.status == expected, 'SMOKE_FAILED', 'HTTPS 入口未满足预期')
            return dict(response.getheaders()), raw
        finally: connection.close()

    headers, _ = request('login_page', 'GET', '/login', 200, browser_origin=None)
    check('max-age=' in headers.get('Strict-Transport-Security', ''), 'SMOKE_HSTS_MISSING')
    request('anonymous_api_rejected', 'GET', '/api/archloop', 401, browser_origin=None)
    request('forged_identity_rejected', 'GET', '/api/archloop', 401,
            auth={'X-Forwarded-User': 'admin', 'X-ProjectMind-Actor': 'admin'})
    request('foreign_origin_rejected', 'GET', '/api/archloop', 403,
            browser_origin='https://foreign.example.invalid')
    if username is not None:
        sessions = []
        try:
            for i in range(2):
                headers, raw = request(f'login_{i+1}', 'POST', '/api/auth/login', 200,
                                       body={'username': username, 'password': password})
                cookie = SimpleCookie(); cookie.load(headers.get('Set-Cookie', ''))
                check(COOKIE in cookie and cookie[COOKIE]['secure'] and cookie[COOKIE]['httponly']
                      and cookie[COOKIE]['samesite'].lower() == 'strict', 'SMOKE_COOKIE_INVALID')
                body = json.loads(raw)
                sessions.append({'Cookie': COOKIE+'='+cookie[COOKIE].value, 'X-ProjectMind-CSRF': body['csrf']})
                request(f'authenticated_api_{i+1}', 'GET', '/api/archloop', 200, auth=sessions[-1])
            request('missing_csrf_rejected', 'POST', '/api/auth/logout', 403, body={},
                    auth={'Cookie': sessions[0]['Cookie']})
            request('cross_session_csrf_rejected', 'POST', '/api/auth/logout', 403, body={},
                    auth={'Cookie': sessions[0]['Cookie'], 'X-ProjectMind-CSRF': sessions[1]['X-ProjectMind-CSRF']})
        finally:
            # Best effort invalidation even if a later check failed. Never store
            # cookies, passwords, CSRF or response bodies in the report.
            for i, session in enumerate(sessions):
                request(f'logout_{i+1}', 'POST', '/api/auth/logout', 200, body={}, auth=session)
                request(f'logged_out_rejected_{i+1}', 'GET', '/api/archloop', 401, auth=session)
    return {'schemaVersion': 'projectmind_https_ingress_v1', 'status': 'PASS',
            'certificateAndHostnameVerified': True, 'customCA': ca is not None,
            'networkScope': 'explicit_ip_tls' if connect_ip else 'dns_tls',
            'authenticatedChecksRun': username is not None, 'observations': observations,
            'productDataWritten': False, 'scope': 'ingress/session checks only; no browser, model, graph approval or task verification'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True); parser.add_argument('--ca', type=Path)
    parser.add_argument('--connect-ip'); parser.add_argument('--username'); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        password = getpass.getpass('输入测试账号密码（不会写入报告）: ') if args.username else None
        result = collect(args.origin, ca=args.ca, connect_ip=args.connect_ip, username=args.username, password=password)
        private_json(args.output, result)
        print(json.dumps({'status': result['status'], 'checks': len(result['observations']),
                          'authenticatedChecksRun': result['authenticatedChecksRun']}))
    except Exception as exc:
        code = exc.code if isinstance(exc, AccessError) else type(exc).__name__
        parser.exit(1, f'HTTPS 检查未通过：{code}；未保存 PASS 报告。\n')


if __name__ == '__main__': main()
