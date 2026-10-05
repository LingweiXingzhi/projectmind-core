# -*- coding: utf-8 -*-
"""B1 slice 1: POST /api/repo-explorer/open semantics.

Seams (pre-agreed per task book §6): the repo-explorer HTTP endpoints,
exercised over a real loopback server; the Git facts come from a
separately git-init-ed temp repository, never this checkout.
"""
import json
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app import make_handler
from repo_index.explorer import ExplorerRegistry


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


def make_repo(directory: Path) -> tuple[Path, str]:
    repo = directory / "sample-repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.name", "Explorer Test")
    run_git(repo, "config", "user.email", "test@example.invalid")
    (repo / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (repo / "note.txt").write_text("plain text\n", encoding="utf-8")
    (repo / "data.bin").write_bytes(b"PK\x00\x01binary-ish")
    (repo / "big.txt").write_text("x" * (1_048_576 + 1), encoding="utf-8")
    run_git(repo, "add", "alpha.py", "note.txt", "data.bin", "big.txt")
    run_git(repo, "commit", "-qm", "sample")
    (repo / "untracked.txt").write_text("never committed\n", encoding="utf-8")
    return repo, run_git(repo, "rev-parse", "HEAD")


class ExplorerServerHarness(unittest.TestCase):
    def start_server(self, repo: Path, map_path: Path | None) -> int:
        handler = make_handler(repo, map_path, explorer_registry=ExplorerRegistry())
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._server.server_address[1]

    def tearDown(self):
        if getattr(self, "_server", None) is not None:
            self._server.shutdown()
            self._server.server_close()

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        conn = HTTPConnection("127.0.0.1", self._port, timeout=10)
        payload = None
        if body is not None:
            payload = json.dumps(body)
        conn.request(method, path, body=payload,
                     headers={"Content-Type": "application/json", **(headers or {})})
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        parsed = json.loads(raw) if raw else {}
        return response.status, parsed


class OpenEndpointTests(ExplorerServerHarness):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo, self.head = make_repo(Path(self._tmp.name))
        self._port = self.start_server(self.repo, None)

    def tearDown(self):
        super().tearDown()
        self._tmp.cleanup()

    def test_open_default_head_binds_full_sha(self):
        status, body = self.request("POST", "/api/repo-explorer/open",
                                    {"repoPath": str(self.repo)})
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["revision"], self.head)
        self.assertEqual(body["repositoryName"], "sample-repo")
        self.assertTrue(body["projectId"])

    def test_open_untracked_files_are_not_counted(self):
        status, body = self.request("POST", "/api/repo-explorer/open",
                                    {"repoPath": str(self.repo)})
        self.assertEqual(status, 200)
        self.assertNotIn("untracked", json.dumps(body))

    def test_open_counts_and_skips_per_budget(self):
        status, body = self.request("POST", "/api/repo-explorer/open",
                                    {"repoPath": str(self.repo)})
        self.assertEqual(status, 200)
        coverage = body["coverage"]
        self.assertEqual(coverage["trackedFileCount"], 4)
        self.assertEqual(coverage["indexedFileCount"], 2)
        self.assertTrue(coverage["partial"])
        reasons = {item["path"]: item["reason"] for item in coverage["skipped"]}
        self.assertEqual(reasons.get("data.bin"), "二进制内容，首版不提供源码视图")
        self.assertEqual(reasons.get("big.txt"), "文件超过 1 MiB 上限")
        capabilities = body["capabilities"]
        self.assertEqual(capabilities, {"files": True, "symbols": True,
                                        "imports": False, "changes": False})

    def test_open_rejects_missing_directory(self):
        status, body = self.request("POST", "/api/repo-explorer/open",
                                    {"repoPath": str(Path(self._tmp.name) / "missing")})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "REPO_INVALID")

    def test_open_rejects_empty_and_relative_repo_paths(self):
        # Found by smoke testing: Path("") resolves to the server's cwd,
        # which would silently open the wrong repository.
        for bad in ("", "sample-repo", "./sample-repo"):
            status, body = self.request("POST", "/api/repo-explorer/open", {"repoPath": bad})
            self.assertEqual(status, 400, repr(bad))
            self.assertEqual(body["error"]["code"], "REPO_INVALID", repr(bad))

    def test_open_rejects_non_commit_revisions(self):
        run_git(self.repo, "tag", "v1")
        for bad in ("main", "v1", self.head[:8]):
            status, body = self.request("POST", "/api/repo-explorer/open",
                                        {"repoPath": str(self.repo), "revision": bad})
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"]["code"], "REVISION_INVALID", bad)

    def test_open_accepts_full_sha_and_is_idempotent(self):
        first = self.request("POST", "/api/repo-explorer/open", {"repoPath": str(self.repo)})
        second = self.request("POST", "/api/repo-explorer/open",
                              {"repoPath": str(self.repo), "revision": self.head})
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertEqual(first[1]["projectId"], second[1]["projectId"])


if __name__ == "__main__":
    unittest.main()
