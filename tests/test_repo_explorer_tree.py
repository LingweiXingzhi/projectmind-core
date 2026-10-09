# -*- coding: utf-8 -*-
"""B1 slice 2: GET /api/repo-explorer/tree semantics."""
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


class TreeEndpointTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "tree-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "pkg" / "sub").mkdir(parents=True)
        (self.repo / "pkg" / "sub" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "pkg" / "helper.py").write_text("y = 2\n", encoding="utf-8")
        (self.repo / "top.py").write_text("z = 3\n", encoding="utf-8")
        (self.repo / "note.txt").write_text("text\n", encoding="utf-8")
        (self.repo / "data.bin").write_bytes(b"B\x00in")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "tree sample")
        (self.repo / "untracked.txt").write_text("u\n", encoding="utf-8")
        self.head = run_git(self.repo, "rev-parse", "HEAD")

        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.repo, None, explorer_registry=ExplorerRegistry()))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.port = self._server.server_address[1]
        self.project_id = self._open()

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._tmp.cleanup()

    def _open(self) -> str:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        body = json.dumps({"repoPath": str(self.repo)})
        conn.request("POST", "/api/repo-explorer/open", body=body,
                     headers={"Content-Type": "application/json"})
        response = json.loads(conn.getresponse().read())
        conn.close()
        return response["projectId"]

    def _tree(self, query: str):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/tree?{query}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_tree_entries_structure_and_order(self):
        status, body = self._tree(f"projectId={self.project_id}&revision={self.head}")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["revision"], self.head)
        entries = body["entries"]
        paths = [entry["path"] for entry in entries]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn("", paths)  # no synthetic empty root node
        self.assertNotIn("untracked.txt", paths)
        by_path = {entry["path"]: entry for entry in entries}
        self.assertEqual(by_path["pkg"]["kind"], "directory")
        self.assertEqual(by_path["pkg"]["parentPath"], "")
        self.assertIsNone(by_path["pkg"]["language"])
        self.assertEqual(by_path["pkg/sub"]["parentPath"], "pkg")
        self.assertEqual(by_path["pkg/sub/mod.py"]["kind"], "file")
        self.assertEqual(by_path["pkg/sub/mod.py"]["parentPath"], "pkg/sub")
        self.assertEqual(by_path["pkg/sub/mod.py"]["language"], "python")
        self.assertIsNone(by_path["note.txt"]["language"])

    def test_tree_marks_skipped_files_with_reason(self):
        status, body = self._tree(f"projectId={self.project_id}&revision={self.head}")
        self.assertEqual(status, 200)
        by_path = {entry["path"]: entry for entry in body["entries"]}
        self.assertEqual(by_path["data.bin"]["kind"], "file")
        self.assertIn("二进制", by_path["data.bin"]["skippedReason"])
        self.assertNotIn("skippedReason", by_path["top.py"])

    def test_tree_rejects_unknown_context(self):
        status, body = self._tree(f"projectId=deadbeef&revision={self.head}")
        self.assertEqual(status, 410)
        self.assertEqual(body["error"]["code"], "CONTEXT_EVICTED")

    def test_tree_rejects_revision_mismatch(self):
        other = self.head[0:4] + "0" * 36
        status, body = self._tree(f"projectId={self.project_id}&revision={other}")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "REVISION_MISMATCH")

    def test_tree_rejects_missing_params(self):
        status, body = self._tree(f"projectId={self.project_id}")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
