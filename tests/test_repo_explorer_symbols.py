# -*- coding: utf-8 -*-
"""B3 slice: GET /api/repo-explorer/symbols via the legacy code-facts parser.

Accepted contracts: parser="legacy_code_facts" with end_line=null and an
explicit range-incomplete warning (task book §6.4); status mapping per
R2-Q6 — ok only for successfully parsed files (empty symbols still ok),
unsupported for non-Python, parse_error for decode/syntax failures inside
the collector's skipped list, and content admission shared with open
(R2-Q5): skipped files answer FILE_SKIPPED instead of faking success.
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


class SymbolsEndpointTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "symbols-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "service.py").write_text(
            "def run(count):\n    return count\n\n"
            "class Service:\n    def greet(self, name):\n        return name\n",
            encoding="utf-8",
        )
        (self.repo / "empty.py").write_text("", encoding="utf-8")
        (self.repo / "broken.py").write_text("def oops(:\n", encoding="utf-8")
        (self.repo / "notes.txt").write_text("plain\n", encoding="utf-8")
        (self.repo / "big.log").write_text("y" * (1_048_576 + 1), encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "symbols sample")
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
        self.coverage = opened["coverage"]

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._tmp.cleanup()

    def _symbols(self, path: str):
        from urllib.parse import quote
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/symbols?projectId={self.project_id}"
                            f"&revision={self.head}&path={quote(path)}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_python_file_maps_legacy_entries(self):
        status, body = self._symbols("service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["parser"], "legacy_code_facts")
        self.assertEqual(body["status"], "ok")
        by_qualified = {item["qualified_name"]: item for item in body["symbols"]}
        self.assertEqual(by_qualified["run"]["kind"], "function")
        self.assertEqual(by_qualified["run"]["start_line"], 1)
        self.assertIsNone(by_qualified["run"]["end_line"])
        self.assertIsNone(by_qualified["run"]["docstring"])
        self.assertEqual(by_qualified["Service"]["kind"], "class")
        self.assertEqual(by_qualified["Service.greet"]["kind"], "method")
        self.assertEqual(by_qualified["Service.greet"]["start_line"], 5)
        self.assertIn("legacy_code_facts 不提供结束行", " ".join(body["warnings"]))

    def test_empty_python_file_is_ok_with_no_symbols(self):
        status, body = self._symbols("empty.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["symbols"], [])

    def test_syntax_error_file_is_parse_error_not_empty_success(self):
        status, body = self._symbols("broken.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "parse_error")
        self.assertEqual(body["symbols"], [])
        self.assertTrue(body["warnings"])

    def test_non_python_text_is_unsupported(self):
        status, body = self._symbols("notes.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "unsupported")
        self.assertEqual(body["symbols"], [])

    def test_oversized_file_shares_open_admission(self):
        status, body = self._symbols("big.log")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FILE_SKIPPED")

    def test_unknown_path_is_404(self):
        status, body = self._symbols("nope.py")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "PATH_NOT_IN_REVISION")

    def test_open_capabilities_report_symbols_available(self):
        self.assertTrue(self.coverage is not None)
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo)}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        self.assertEqual(opened["capabilities"]["symbols"], True)


if __name__ == "__main__":
    unittest.main()
