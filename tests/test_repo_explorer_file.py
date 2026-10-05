# -*- coding: utf-8 -*-
"""B1 slice 3: GET /api/repo-explorer/file semantics."""
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


class FileEndpointTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "file-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        self.multiline = "".join(f"line {i}\n" for i in range(1, 11))
        (self.repo / "multiline.py").write_text(self.multiline, encoding="utf-8")
        (self.repo / "empty.py").write_text("", encoding="utf-8")
        (self.repo / "nested").mkdir()
        (self.repo / "nested" / "note.txt").write_text("hello\n", encoding="utf-8")
        (self.repo / "data.bin").write_bytes(b"B\x00in")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "file sample")
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

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._tmp.cleanup()

    def _file(self, query: str):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/file?{query}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_file_returns_committed_content_with_default_range(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=multiline.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["revision"], self.head)
        self.assertEqual(body["path"], "multiline.py")
        self.assertEqual((body["startLine"], body["endLine"]), (1, 10))
        self.assertEqual(body["totalLines"], 10)
        self.assertEqual(body["content"], self.multiline)
        self.assertFalse(body["truncated"])

    def test_file_slices_requested_lines(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=multiline.py&startLine=2&endLine=3")
        self.assertEqual(status, 200)
        self.assertEqual((body["startLine"], body["endLine"]), (2, 3))
        self.assertEqual(body["content"], "line 2\nline 3\n")
        # "truncated" is file-oriented per the interface contract: lines
        # 4-10 of the file remain unreturned by this window.
        self.assertTrue(body["truncated"])

    def test_file_end_line_beyond_total_is_clipped(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=multiline.py&startLine=9&endLine=99")
        self.assertEqual(status, 200)
        self.assertEqual((body["startLine"], body["endLine"]), (9, 10))
        self.assertEqual(body["content"], "line 9\nline 10\n")
        # Accepted Q5 definition (B1-a-04): lines 1-8 remain unreturned.
        self.assertTrue(body["truncated"])

    def test_file_truncated_is_true_while_any_line_is_unreturned(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=multiline.py&startLine=5&endLine=6")
        self.assertEqual(status, 200)
        self.assertEqual((body["startLine"], body["endLine"]), (5, 6))
        self.assertTrue(body["truncated"])

    def test_file_lines_follow_physical_newlines_not_unicode_breaks(self):
        # B1-a-05: U+2028 inside a string literal must not count as a line
        # break — Python's AST sees one physical line, so must the file
        # endpoint (str.splitlines would double-count it).
        separator = chr(0x2028)
        (self.repo / "u2028.py").write_text(f's = "a{separator}b"\n', encoding="utf-8")
        run_git(self.repo, "add", "u2028.py")
        run_git(self.repo, "commit", "-qm", "u2028")
        head2 = run_git(self.repo, "rev-parse", "HEAD")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo)}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        pid = opened["projectId"]
        status, body = self._file(f"projectId={pid}&revision={head2}&path=u2028.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["totalLines"], 1)
        self.assertIn(separator, body["content"])

    def test_file_start_line_beyond_total_is_rejected(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=multiline.py&startLine=11&endLine=20")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "LINE_RANGE_INVALID")

    def test_file_window_over_500_lines_is_rejected(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=multiline.py&startLine=1&endLine=501")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "LINE_RANGE_TOO_LARGE")

    def test_file_empty_file_has_zero_range(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=empty.py&startLine=1&endLine=200")
        self.assertEqual(status, 200)
        self.assertEqual((body["startLine"], body["endLine"], body["totalLines"]), (0, 0, 0))
        self.assertEqual(body["content"], "")
        self.assertFalse(body["truncated"])

    def test_file_rejects_paths_outside_the_revision(self):
        for bad in ("/etc/passwd", "C:/windows", "..%2Fsecret", "a/../b", "nested\\note.txt"):
            status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path={bad}")
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"]["code"], "PATH_INVALID", bad)

    def test_file_rejects_unknown_paths(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=nope.py")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "PATH_NOT_IN_REVISION")

    def test_file_skipped_content_is_named_not_silent(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}&path=data.bin")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FILE_SKIPPED")
        self.assertIn("二进制", body["error"]["message"])

    def test_file_missing_params_are_rejected(self):
        status, body = self._file(f"projectId={self.project_id}&revision={self.head}")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
