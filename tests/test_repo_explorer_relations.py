# -*- coding: utf-8 -*-
"""B4 placeholder slice: GET /api/repo-explorer/relations before C lands.

Task book §6.5: with no import parser integrated the endpoint must return
status="unavailable" — never a wrapped empty success. Path admission is
shared with the other content endpoints (R2-Q5).
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


class RelationsEndpointTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "relations-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "service.py").write_text("from . import helper\n", encoding="utf-8")
        (self.repo / "notes.txt").write_text("text\n", encoding="utf-8")
        (self.repo / "big.log").write_text("y" * (1_048_576 + 1), encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "relations sample")
        self.head = run_git(self.repo, "rev-parse", "HEAD")

        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.repo, None, explorer_registry=ExplorerRegistry()))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.port = self._server.server_address[1]
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo)}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        self.project_id = opened["projectId"]
        self.capabilities = opened["capabilities"]

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._tmp.cleanup()

    def _relations(self, path: str):
        from urllib.parse import quote
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/relations?projectId={self.project_id}"
                            f"&revision={self.head}&path={quote(path)}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_relations_are_unavailable_before_parser_integration(self):
        status, body = self._relations("service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["status"], "unavailable")
        self.assertEqual(body["imports"], [])
        self.assertEqual(body["dependents"], [])
        self.assertTrue(body["warnings"])

    def test_capabilities_keep_imports_false(self):
        self.assertEqual(self.capabilities["imports"], False)

    def test_unknown_path_is_404(self):
        status, body = self._relations("nope.py")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "PATH_NOT_IN_REVISION")

    def test_skipped_files_share_admission(self):
        status, body = self._relations("big.log")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FILE_SKIPPED")


if __name__ == "__main__":
    unittest.main()
