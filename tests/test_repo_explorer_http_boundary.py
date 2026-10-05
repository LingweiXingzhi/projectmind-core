# -*- coding: utf-8 -*-
"""B1 slice 5: Host/Origin boundary for the repo-explorer endpoints.

Accepted contract R2-Q4: Host must be this loopback service; an Origin
header, when present, must be this same service; no CORS is offered.
"""
import json
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import make_handler
from repo_index.explorer import ExplorerRegistry


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


class HttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "boundary-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "x.py").write_text("x = 1\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "boundary")
        self.head = run_git(self.repo, "rev-parse", "HEAD")

        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.repo, None, explorer_registry=ExplorerRegistry()))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.port = self._server.server_address[1]

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._tmp.cleanup()

    def send(self, method: str, path: str, host: str | None = None,
             origin: str | None = None, body: dict | None = None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {}
        if host is not None:
            headers["Host"] = host
        if origin is not None:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw) if raw else {}

    def test_open_with_default_host_and_no_origin_is_allowed(self):
        status, body = self.send("POST", "/api/repo-explorer/open", body={"repoPath": str(self.repo)})
        self.assertEqual(status, 200)

    def test_foreign_host_is_rejected(self):
        status, body = self.send("POST", "/api/repo-explorer/open", host="evil.example:1234",
                                 body={"repoPath": str(self.repo)})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FORBIDDEN_HOST")

    def test_foreign_origin_is_rejected(self):
        status, body = self.send("POST", "/api/repo-explorer/open", origin="http://evil.example",
                                 body={"repoPath": str(self.repo)})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FORBIDDEN_ORIGIN")

    def test_null_origin_is_rejected(self):
        status, body = self.send("POST", "/api/repo-explorer/open", origin="null",
                                 body={"repoPath": str(self.repo)})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FORBIDDEN_ORIGIN")

    def test_same_service_origin_is_allowed(self):
        origin = f"http://127.0.0.1:{self.port}"
        status, _ = self.send("POST", "/api/repo-explorer/open", origin=origin,
                              body={"repoPath": str(self.repo)})
        self.assertEqual(status, 200)

    def test_boundary_applies_to_read_endpoints(self):
        project_id = self.send("POST", "/api/repo-explorer/open", body={"repoPath": str(self.repo)})[1]["projectId"]
        for path in (f"/api/repo-explorer/tree?projectId={project_id}&revision={self.head}",
                     f"/api/repo-explorer/file?projectId={project_id}&revision={self.head}&path=x.py"):
            status, body = self.send("GET", path, origin="http://evil.example")
            self.assertEqual(status, 403, path)
            self.assertEqual(body["error"]["code"], "FORBIDDEN_ORIGIN", path)


if __name__ == "__main__":
    unittest.main()
