"""Production WSGI transport delegates to the existing application Handler."""
from email.message import Message
from http import HTTPStatus
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from .access import AccessError, check

MAX_BODY = 1_048_576
WEB = Path(__file__).resolve().parent / "web"
SAFE_HEADERS = [("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                ("X-Frame-Options", "SAMEORIGIN"), ("Referrer-Policy", "same-origin")]


class Application:
    def __init__(self, handler, access, repositories):
        self.handler, self.access = handler, access
        from extensions.architecture_workspace.git_publication import code_identity
        self.repositories = {code_identity(path): Path(path).resolve() for path in repositories}
        check(len(self.repositories) == len(repositories), message="同一来源只登记一个代码副本")

    def _response(self, start, status, body, *, content="application/json; charset=utf-8", headers=()):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        start(f"{status} {HTTPStatus(status).phrase}",
              [("Content-Type", content), ("Content-Length", str(len(raw))), *SAFE_HEADERS, *headers])
        return [raw]

    def _body(self, environ):
        try:
            size = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            raise AccessError(400, "INVALID_INPUT", "请求长度无效") from None
        check(0 <= size <= MAX_BODY, "REQUEST_TOO_LARGE", "请求体过大", 413)
        raw = environ["wsgi.input"].read(size)
        check(len(raw) == size, "REQUEST_INCOMPLETE", "请求体不完整", 400)
        return raw

    def _json(self, raw):
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AccessError(400, "INVALID_INPUT", "需要 JSON 对象") from None
        check(isinstance(value, dict))
        return value

    def _input(self, value):
        if isinstance(value, list):
            return [self._input(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key == "repoPath" and item:
                check(isinstance(item, str) and item.startswith("registered:"),
                      "REPOSITORY_NOT_REGISTERED", "请选择服务器登记的仓库", 403)
                repo = self.repositories.get(item.removeprefix("registered:"))
                check(repo is not None, "REPOSITORY_NOT_REGISTERED", "仓库未登记", 403)
                result[key] = str(repo)
            else:
                result[key] = self._input(item)
        return result

    def _output(self, value):
        if isinstance(value, list):
            return [self._output(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in ("dataRoot", "architectureRepo"):
                continue
            if key == "repoPath":
                matched = next((name for name, path in self.repositories.items() if str(path) == item), None)
                result[key] = "registered:" + matched if matched else None
            else:
                result[key] = self._output(item)
        return result

    def __call__(self, environ, start_response):
        try:
            method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/")
            self.access.transport(environ, write=method not in ("GET", "HEAD"))
            if path in ("/login", "/login.js") and method == "GET":
                name = "login.html" if path == "/login" else "login.js"
                content = "text/html; charset=utf-8" if path == "/login" else "text/javascript; charset=utf-8"
                return self._response(start_response, 200, (WEB / name).read_bytes(), content=content)
            if path == "/api/auth/login" and method == "POST":
                check(environ.get("CONTENT_TYPE", "").split(";", 1)[0] == "application/json")
                raw = self._body(environ); check(len(raw) <= 4096, status=413)
                request = self._json(raw)
                check(set(request) == {"username", "password"})
                sid, session = self.access.login(request["username"], request["password"])
                return self._response(start_response, 200, {"actor": session.actor, "csrf": session.csrf},
                                      headers=[("Set-Cookie", self.access.cookie(sid))])
            session = self.access.session(environ, write=method not in ("GET", "HEAD"))
            if path == "/api/auth/session" and method == "GET":
                return self._response(start_response, 200, {"actor": session.actor, "csrf": session.csrf,
                    "scope": "shared_team_workspace", "origin": self.access.origin,
                    "repositories": [{"key": "registered:" + key, "label": path.name + " · " + key[-8:]}
                                     for key, path in self.repositories.items()]})
            if path == "/api/auth/logout" and method == "POST":
                self.access.logout(environ)
                return self._response(start_response, 200, {"loggedOut": True},
                                      headers=[("Set-Cookie", self.access.cookie())])
            if path == "/auth-client.js" and method == "GET":
                return self._response(start_response, 200, (WEB / "auth-client.js").read_bytes(),
                                      content="text/javascript; charset=utf-8")
            check(method in ("GET", "POST"), "METHOD_NOT_ALLOWED", "只支持 GET/POST", 405)
            body = self._body(environ) if method == "POST" else b""
            if body and environ.get("CONTENT_TYPE", "").split(";", 1)[0] == "application/json":
                payload = self._input(self._json(body))
                if path.startswith("/api/archloop/"):
                    payload["actor"] = session.actor
                body = json.dumps(payload, ensure_ascii=False).encode()
            # Identity is a Python object provided by this authenticated boundary,
            # never a header or request JSON field.
            handler = self.handler.__new__(self.handler)
            handler.trusted_operator = {"actor": session.actor, "browserSession": session.binding}
            handler.command = method
            handler.path = quote(path, safe="/%") + (("?" + environ["QUERY_STRING"]) if environ.get("QUERY_STRING") else "")
            handler.request_version = "HTTP/1.1"
            handler.requestline = f"{method} {handler.path} HTTP/1.1"
            handler.client_address = (environ["REMOTE_ADDR"], 0)
            handler.server = SimpleNamespace(server_address=("127.0.0.1", 8765))
            handler.headers = Message()
            for name, value in environ.items():
                if name.startswith("HTTP_"):
                    handler.headers[name[5:].replace("_", "-")] = value
            handler.headers["Content-Type"] = environ.get("CONTENT_TYPE", "")
            handler.headers["Content-Length"] = str(len(body))
            handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
            handler.close_connection = True
            getattr(handler, "do_" + method)()
            raw = handler.wfile.getvalue()
            head, contents = raw.split(b"\r\n\r\n", 1)
            lines = head.decode("iso-8859-1").split("\r\n")
            status = int(lines[0].split()[1])
            headers = [line.split(": ", 1) for line in lines[1:]]
            content = next((v for k, v in headers if k.lower() == "content-type"), "application/octet-stream")
            if content.startswith("application/json"):
                output = self._output(json.loads(contents))
                if status >= 500 and isinstance(output, dict) and "error" in output:
                    from archloop.contract import ERROR_CODES
                    error = output["error"]
                    code = error.get("code") if isinstance(error, dict) else None
                    output["error"] = {"code": code if code in ERROR_CODES else "SERVICE_UNAVAILABLE",
                                       "message": "服务暂不可用，请管理员检查服务器运行状态"}
                contents = json.dumps(output, ensure_ascii=False).encode()
            elif content.startswith("text/html") and path in ("/", "/index.html") and status == 200:
                contents = contents.replace(b"<head>", b'<head><script src="/auth-client.js" defer></script>', 1)
            extra = [(k, v) for k, v in headers if k.lower() not in {
                "content-length", "content-type", "cache-control", "connection", "transfer-encoding",
                "server", "date", "x-content-type-options", "x-frame-options", "referrer-policy"}]
            return self._response(start_response, status, contents, content=content, headers=extra)
        except AccessError as exc:
            if exc.code == "LOGIN_REQUIRED" and environ.get("PATH_INFO") in ("/", "/index.html"):
                return self._response(start_response, 303, b"", content="text/plain; charset=utf-8",
                                      headers=[("Location", "/login")])
            return self._response(start_response, exc.status, {"error": {"code": exc.code, "message": str(exc)}})
        except Exception:
            return self._response(start_response, 500, {"error": {"code": "INTERNAL", "message": "服务未能完成请求"}})
