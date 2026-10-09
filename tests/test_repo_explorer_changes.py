# -*- coding: utf-8 -*-
"""B5 slice: GET /api/repo-explorer/changes between two full SHAs.

Accepted contracts (task book §6.6 + gate Q3): base/target must be full
commit SHAs of the projectId's repository, echoed back as resolved; A/M/D
carry oldPath=null, R (Git rename detection, -M) carries the old path; any
other Git status letter is returned as-is, never dropped.
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


class ChangesEndpointTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "changes-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
        (self.repo / "old.txt").write_text("to be deleted\n", encoding="utf-8")
        (self.repo / "notes.md").write_text("# notes\ncontent shared enough for rename\n" * 8,
                                            encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "c1")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        (self.repo / "alpha.py").write_text("def alpha():\n    return 2\n", encoding="utf-8")
        (self.repo / "added.txt").write_text("new\n", encoding="utf-8")
        (self.repo / "old.txt").unlink()
        run_git(self.repo, "add", "-A")
        run_git(self.repo, "commit", "-qm", "c2 modify+add+delete")
        self.mid = run_git(self.repo, "rev-parse", "HEAD")
        run_git(self.repo, "mv", "notes.md", "docs.md")
        run_git(self.repo, "commit", "-qm", "c3 rename")
        self.target = run_git(self.repo, "rev-parse", "HEAD")

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

    def _changes(self, query: str):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/changes?{query}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_changes_between_full_shas(self):
        status, body = self._changes(f"projectId={self.project_id}&base={self.base}&target={self.target}")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["baseRevision"], self.base)
        self.assertEqual(body["targetRevision"], self.target)
        by_path = {item["path"]: item for item in body["changes"]}
        self.assertEqual(by_path["alpha.py"]["status"], "M")
        self.assertIsNone(by_path["alpha.py"]["oldPath"])
        self.assertEqual(by_path["added.txt"]["status"], "A")
        self.assertEqual(by_path["old.txt"]["status"], "D")
        self.assertEqual(by_path["docs.md"]["status"], "R")
        self.assertEqual(by_path["docs.md"]["oldPath"], "notes.md")

    def test_identical_shas_yield_empty_changes(self):
        status, body = self._changes(f"projectId={self.project_id}&base={self.target}&target={self.target}")
        self.assertEqual(status, 200)
        self.assertEqual(body["changes"], [])

    def test_non_full_sha_revisions_are_rejected(self):
        for bad in ("HEAD", "main", self.base[:8]):
            status, body = self._changes(f"projectId={self.project_id}&base={bad}&target={self.target}")
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"]["code"], "REVISION_INVALID", bad)

    def test_unknown_full_sha_is_rejected(self):
        ghost = "0" * 40
        status, body = self._changes(f"projectId={self.project_id}&base={ghost}&target={self.target}")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "REVISION_INVALID")

    def test_missing_params_are_rejected(self):
        status, body = self._changes(f"projectId={self.project_id}&base={self.base}")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "BAD_REQUEST")

    def test_name_status_parser_preserves_non_utf8_identity(self):
        # B3B5-07: errors="replace" would collapse distinct invalid names
        # into one string; backslashreplace keeps them distinct and the
        # entry is flagged so the UI refuses to open them.
        # 终审 F4（changes 侧）：entry 另带 raw bytes 派生的 machine
        # identity（与 tree 同一 helper：可解码=明文自身，不可解码=NUL+b64）。
        from repo_index.explorer import parse_name_status
        raw = b"M\0ok.py\0M\0bad-\xff.py\0R100\0bad-\xff-old.py\0renamed.py\0"
        changes = parse_name_status(raw)
        self.assertEqual(changes[0], {"status": "M", "path": "ok.py",
                                      "identity": "ok.py", "oldPath": None})
        self.assertEqual(changes[1]["path"], r"bad-\xff.py")
        self.assertTrue(changes[1]["pathUndecodable"])
        self.assertTrue(changes[1]["identity"].startswith("\x00b64:"))
        self.assertNotEqual(changes[1]["identity"], changes[1]["path"])
        self.assertEqual(changes[2]["status"], "R")
        self.assertEqual(changes[2]["path"], "renamed.py")
        self.assertEqual(changes[2]["oldPath"], r"bad-\xff-old.py")
        self.assertEqual(changes[2]["identity"], "renamed.py")
        self.assertEqual(changes[2]["newIdentity"], "renamed.py")
        self.assertEqual(changes[2]["newPath"], "renamed.py")
        self.assertTrue(changes[2]["oldIdentity"].startswith("\x00b64:"))
        self.assertTrue(changes[2]["pathUndecodable"])
        # Two distinct invalid names never collapse.
        raw2 = b"M\0bad-\xfe.py\0M\0bad-\xff.py\0"
        parsed2 = parse_name_status(raw2)
        self.assertNotEqual(parsed2[0]["path"], parsed2[1]["path"])
        self.assertNotEqual(parsed2[0]["identity"], parsed2[1]["identity"])


if __name__ == "__main__":
    unittest.main()
