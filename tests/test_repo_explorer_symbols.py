# -*- coding: utf-8 -*-
"""GET /api/repo-explorer/symbols via B's `parse_symbols` (task book §6.4/§5).

Accepted contract after the parser hand-off: `parser="python_ast_v1"` with
inclusive `end_line` and cleaned docstrings — the legacy code-facts
transition (null end_line plus a range-incomplete warning) is withdrawn.
Status mapping is preserved: ok only for successfully parsed files (empty
symbols still ok), unsupported for non-Python, parse_error for syntax or
decode failures — never a wrapped empty success — and content admission is
shared with open (R2-Q5): skipped files answer FILE_SKIPPED.
"""
import json
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
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
            "class Service:\n"
            "    \"\"\"服务说明。\"\"\"\n"
            "    def greet(self, name):\n        return name\n",
            encoding="utf-8",
        )
        (self.repo / "empty.py").write_text("", encoding="utf-8")
        (self.repo / "broken.py").write_text("def oops(:\n", encoding="utf-8")
        (self.repo / "notes.txt").write_text("plain\n", encoding="utf-8")
        # A browsable text file whose first line looks like a coding cookie: it
        # must answer `unsupported`, not a 500 decoding failure (R48-08).
        (self.repo / "cookie.txt").write_text(
            "# coding: nonexistent-charset\n说明\n", encoding="utf-8")
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

    def _file(self, path: str):
        from urllib.parse import quote
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/file?projectId={self.project_id}"
                            f"&revision={self.head}&path={quote(path)}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_python_file_returns_full_python_ast_ranges(self):
        status, body = self._symbols("service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["parser"], "python_ast_v1")
        self.assertEqual(body["status"], "ok")
        by_qualified = {item["qualified_name"]: item for item in body["symbols"]}
        self.assertEqual(by_qualified["run"]["kind"], "function")
        self.assertEqual(by_qualified["run"]["start_line"], 1)
        self.assertEqual(by_qualified["run"]["end_line"], 2)
        self.assertIsNone(by_qualified["run"]["docstring"])
        self.assertEqual(by_qualified["Service"]["kind"], "class")
        self.assertEqual(by_qualified["Service"]["start_line"], 4)
        self.assertEqual(by_qualified["Service"]["end_line"], 7)
        self.assertEqual(by_qualified["Service.greet"]["kind"], "method")
        self.assertEqual(by_qualified["Service.greet"]["start_line"], 6)
        self.assertEqual(by_qualified["Service.greet"]["end_line"], 7)
        for item in body["symbols"]:
            self.assertEqual(set(item), {"name", "qualified_name", "kind",
                                         "start_line", "end_line", "docstring"})

    def test_docstrings_are_cleaned_and_reported(self):
        status, body = self._symbols("service.py")
        self.assertEqual(status, 200)
        by_qualified = {item["qualified_name"]: item for item in body["symbols"]}
        self.assertEqual(by_qualified["Service"]["docstring"], "服务说明。")
        self.assertIsNone(by_qualified["Service.greet"]["docstring"])

    def test_symbol_ranges_stay_inside_the_file_line_count(self):
        # The symbols ranges must address the very same pinned source `file`
        # serves, so a UI jump built from them can never leave the file.
        status, symbols = self._symbols("service.py")
        self.assertEqual(status, 200)
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/file?projectId={self.project_id}"
                            f"&revision={self.head}&path=service.py")
        file_body = json.loads(conn.getresponse().read())
        conn.close()
        total = file_body["totalLines"]
        for item in symbols["symbols"]:
            self.assertGreaterEqual(item["start_line"], 1)
            self.assertLessEqual(item["start_line"], item["end_line"])
            self.assertLessEqual(item["end_line"], total)

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

    def test_coding_cookie_in_a_non_python_file_stays_browsable(self):
        # R48-08: PEP 263 applies to Python sources only. A UTF-8 text file
        # whose first line merely looks like a cookie must stay browsable by
        # `file`, and symbols must answer `unsupported` for it — not a 500
        # raised by the Python encoding reader.
        status, file_body = self._file("cookie.txt")
        self.assertEqual(status, 200)
        self.assertIn("说明", file_body["content"])
        status, body = self._symbols("cookie.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "unsupported")
        self.assertEqual(body["symbols"], [])

    def test_non_python_symbols_never_consult_the_pep263_reader(self):
        # The same boundary at the reader itself: making the Python encoding
        # reader unusable must not change the answer for a non-Python file,
        # while a Python file still goes through it.
        import repo_index.explorer as explorer
        with mock.patch.object(explorer, "read_source",
                               side_effect=AssertionError("PEP 263 reader used on a text file")):
            status, body = self._symbols("notes.txt")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "unsupported")
        with mock.patch.object(explorer, "read_source",
                               wraps=explorer.read_source) as reader:
            status, body = self._symbols("service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["parser"], "python_ast_v1")
        self.assertTrue(reader.called)

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
