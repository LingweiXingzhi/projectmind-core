"""Opt-in real-socket transport example, restricted to synthetic Git fixtures.

This does not register routes in Core, provide a UI, or implement A's production
transport. The simulated operator is never a real project owner approval.
Session/reference tables are RAM-only and this transport creates no token log
or store. The existing V1 service retains private intent replay responses in
owner-only SQLite; those records do not restore transport/session authority.
"""
from __future__ import annotations

from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading

from .errors import WorkspaceError, require
from .git_publication import code_identity, read_git
from .proposals import API_VERSION
from .review import HumanReviewGateway
from .schema import canonical, fields, identifier, ID
from .service import WorkspaceService
from .surfaces import UserWorkspaceAPI, workspace_context

FIXTURE_ORIGIN = "https://example.invalid/projectmind-b-fixture.git"
FIXTURE_BRANCH = "architecture/candidates/test-fixture"
COOKIE = "projectmind_b_fixture_session"
MAX_BODY = 2 * 1024 * 1024
SOCKET_TIMEOUT = 3


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-finite JSON value")


def _error(exc, request=None):
    request_id = request.get("requestId") if isinstance(request, dict) else None
    return {"apiVersion": API_VERSION, "requestId": request_id
            if isinstance(request_id, str) and ID.fullmatch(request_id) else None,
            **exc.as_dict()}


def _status(result):
    if "error" not in result:
        return 200
    code = result["error"]["code"]
    return {"INVALID_INPUT": 400, "NOT_FOUND": 404,
            "REQUEST_FORBIDDEN": 403, "PUBLIC_ADAPTER_REQUIRED": 403,
            "REVIEW_EXPIRED": 410, "EVIDENCE_MISMATCH": 422,
            "PUBLICATION_FAILED": 503, "STORAGE_FAILED": 503}.get(code, 409)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT)

    def log_message(self, format, *args):
        # No URL, body, cookie, token or exception logging.
        pass

    def _reply(self, status, result, cookie=None):
        self.close_connection = True
        body = canonical(result).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler parser/unknown-method failures also use JSON.
        status = 405 if code == 501 else code
        error = "REQUEST_FORBIDDEN" if status == 405 else "INVALID_INPUT"
        self._reply(status, _error(WorkspaceError(error)))

    def _one_header(self, name, *, code="INVALID_INPUT"):
        values = self.headers.get_all(name, [])
        require(len(values) == 1, code)
        return values[0]

    def _boundary(self):
        boundary = {"peer": self.client_address[0],
                    "host": self._one_header("Host", code="REQUEST_FORBIDDEN"),
                    "origin": self._one_header("Origin", code="REQUEST_FORBIDDEN")}
        self.server.fixture.gateway._request(**boundary)
        return boundary

    def _json(self):
        require(not self.headers.get_all("Transfer-Encoding"),
                detail="测试传输不接受分块或歧义请求长度")
        length = self._one_header("Content-Length")
        require(re.fullmatch(r"0|[1-9][0-9]{0,9}", length) is not None)
        length = int(length)
        require(0 < length <= MAX_BODY, detail="JSON 请求超过测试传输大小限制")
        content_type = self._one_header("Content-Type").lower()
        require(content_type in ("application/json", "application/json; charset=utf-8"))
        body = self.rfile.read(length)
        require(len(body) == length, detail="JSON 请求长度不完整")
        return json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_constant)

    def _auth(self, boundary):
        raw = self._one_header("Cookie", code="REQUEST_FORBIDDEN")
        require(len(raw) <= 4096 and sum(part.split("=", 1)[0].strip() == COOKIE
                for part in raw.split(";")) == 1, "REQUEST_FORBIDDEN")
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except CookieError as exc:
            raise WorkspaceError("REQUEST_FORBIDDEN") from exc
        require(COOKIE in jar, "REQUEST_FORBIDDEN")
        csrf = self._one_header("X-CSRF-Token", code="REQUEST_FORBIDDEN")
        require(len(csrf) <= 128, "REQUEST_FORBIDDEN")
        return {**boundary, "session_id": jar[COOKIE].value, "csrf_token": csrf}

    def do_POST(self):
        request = None
        try:
            boundary = self._boundary()
            if self.path != "/session" and not self.path.startswith("/user/"):
                self._reply(404, _error(WorkspaceError("NOT_FOUND")))
                return
            request = self._json()
            fixture = self.server.fixture
            if self.path == "/session":
                fields(request, ("apiVersion", "requestId"))
                require(request["apiVersion"] == API_VERSION)
                identifier(request["requestId"])
                session = fixture.gateway.create_session("TEST_ONLY_SIMULATED_HUMAN", **boundary)
                result = {"apiVersion": API_VERSION, "requestId": request["requestId"],
                          "status": "fixture_session", "context": fixture.context,
                          "data": {"csrfToken": session["csrfToken"], "fixtureOnly": True,
                                   "operator": "TEST_ONLY_SIMULATED_HUMAN"}}
                cookie = f"{COOKIE}={session['sessionId']}; Path=/; HttpOnly; SameSite=Strict"
                self._reply(200, result, cookie)
                return
            action = self.path.removeprefix("/user/")
            require(action in UserWorkspaceAPI.ACTIONS, "NOT_FOUND")
            auth = self._auth(boundary)
            result = fixture.api.call(action, request, auth=auth)
            self._reply(_status(result), result)
        except WorkspaceError as exc:
            self._reply(_status(_error(exc)), _error(exc, request))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError,
                OverflowError, UnicodeError, TimeoutError, OSError):
            self._reply(400, _error(WorkspaceError("INVALID_INPUT"), request))

    def _unsupported(self):
        self._reply(405, _error(WorkspaceError("REQUEST_FORBIDDEN")))

    do_GET = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _unsupported


class FixtureHTTPServer:
    """Context-managed loopback server with a deliberately simulated operator.

    Both Git fixture identities are checked before binding or creating state.
    A fresh state path is required; no existing local work is overwritten.
    """
    def __init__(self, state_root, code_repo, architecture_repo, *, test_fixture_only=False):
        require(test_fixture_only is True, detail="必须明确启用纯测试夹具传输")
        self.code = Path(code_repo).resolve()
        self.architecture = Path(architecture_repo).resolve()
        self.state_root = Path(state_root).resolve()
        origin = read_git(self.code, "config", "--get", "remote.origin.url").decode().strip()
        branch = read_git(self.architecture, "symbolic-ref", "--short", "HEAD").decode().strip()
        require(origin == FIXTURE_ORIGIN and branch == FIXTURE_BRANCH,
                "REQUEST_FORBIDDEN", "仅接受专用 example.invalid 代码仓库与测试架构分支")
        require(self.code != self.architecture
                and not self.state_root.exists()
                and not any(self.state_root == repo or repo in self.state_root.parents
                            for repo in (self.code, self.architecture)),
                detail="测试状态必须放入新建的仓库外目录")
        self._thread = None
        self._closed = False
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.daemon_threads = True
        self.httpd.fixture = self
        host, port = self.httpd.server_address
        self.host, self.port = f"{host}:{port}", port
        self.origin = f"http://{self.host}"
        try:
            self.service = WorkspaceService(self.state_root, code_repositories=[self.code],
                architecture_repo=self.architecture, architecture_branch=FIXTURE_BRANCH)
            self.workspace = self.service.open_workspace(mode="existing_project",
                code_repo_id=code_identity(self.code),
                code_revision=read_git(self.code, "rev-parse", "HEAD").decode().strip())
            self.gateway = HumanReviewGateway(self.service, self.origin)
            self.api = UserWorkspaceAPI(self.service, self.gateway, self.workspace["workspaceId"])
        except BaseException:
            self.httpd.server_close()
            raise

    @property
    def context(self):
        return workspace_context(self.api._workspace())

    def start(self):
        require(not self._closed and self._thread is None)
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        kwargs={"poll_interval": 0.02}, daemon=True)
        self._thread.start()
        return self

    def close(self):
        if not self._closed:
            self._closed = True
            if self._thread is not None:
                self.httpd.shutdown()
                self._thread.join(timeout=SOCKET_TIMEOUT + 1)
            self.httpd.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, traceback):
        self.close()
