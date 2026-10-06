# -*- coding: utf-8 -*-
"""Final-audit regression tests (F3/F4/F5).

F3: an empty file must not bypass file-API line-range validation.
F4: two distinct non-UTF-8 Git paths must keep distinct identities (base64
    of the original bytes), and must not collide with a legal path whose
    name literally spells the same escaped text; source jumps stay
    forbidden. The fixtures are built with Git plumbing (hash-object +
    update-index -z --stdin) so raw byte paths exist in the object database
    regardless of the local filesystem's naming rules.
F5: the code-facts collector's object-missing failure maps to
    OBJECT_MISSING, not REPO_UNREADABLE.
"""
import json
import os
import stat
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import make_handler
from repo_index.explorer import ExplorerRegistry


def run_git(repo: Path, *args: str, data: bytes | None = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], input=data,
                          capture_output=True, check=True).stdout.decode().strip()


class FinalAuditRegressionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "final-audit-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")

        def blob(content: bytes) -> str:
            return subprocess.run(
                ["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"],
                input=content, capture_output=True, check=True).stdout.decode().strip()

        # F4 fixtures are built with Git plumbing (mktree -z + commit-tree):
        # raw byte paths and a literal-backslash name exist in the object
        # database regardless of what the local filesystem allows.
        names = [
            (b"empty.py", b""),
            (b"alpha.py", b"def alpha():\n    return 1\n"),
            (b"bad-\xff.py", b"invalid one\n"),
            (b"bad-\xfe.py", b"invalid two\n"),
            # The display-text collision pair: the invalid name's
            # backslashreplace text ("a\xffb.py") is exactly the plain text
            # of the legal name containing a literal backslash.
            (b"a\xffb.py", b"invalid display collision\n"),
            (b"a\\xffb.py", b"legal lookalike\n"),
        ]
        tree_input = b"".join(
            b"100644 blob " + blob(content).encode("ascii") + b"\t" + name + b"\0"
            for name, content in names)
        # r24 F4 residual: two COLLIDING DIRECTORIES — different raw byte
        # dir names whose display texts are identical. Each subtree is built
        # separately, then referenced from the root tree (mktree entry names
        # cannot contain "/").
        one_oid = blob(b"print('one')\n")
        two_oid = blob(b"print('two')\n")
        sub_invalid = subprocess.run(
            ["git", "-C", str(self.repo), "mktree", "-z"],
            input=b"100644 blob " + one_oid.encode("ascii") + b"\t" + b"one.py" + b"\0",
            capture_output=True, check=True).stdout.decode().strip()
        sub_legal = subprocess.run(
            ["git", "-C", str(self.repo), "mktree", "-z"],
            input=b"100644 blob " + two_oid.encode("ascii") + b"\t" + b"two.py" + b"\0",
            capture_output=True, check=True).stdout.decode().strip()
        tree_input += (b"040000 tree " + sub_invalid.encode("ascii") + b"\t" + b"dir-\xff" + b"\0")
        tree_input += (b"040000 tree " + sub_legal.encode("ascii") + b"\t" + b"dir-\\xff" + b"\0")
        tree = subprocess.run(
            ["git", "-C", str(self.repo), "mktree", "-z"],
            input=tree_input, capture_output=True, check=True).stdout.decode().strip()
        env = {**os.environ,
               "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        commit = subprocess.run(
            ["git", "-C", str(self.repo), "commit-tree", tree],
            input=b"final audit sample\n", capture_output=True, check=True,
            env=env).stdout.decode().strip()
        run_git(self.repo, "update-ref", "refs/heads/main", commit)
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

    def _get(self, path_query: str):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path_query)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def _file(self, path: str, start: int, end: int):
        from urllib.parse import quote
        return self._get(f"/api/repo-explorer/file?projectId={self.project_id}"
                         f"&revision={self.head}&path={quote(path)}"
                         f"&startLine={start}&endLine={end}")

    # ---- F3 ----
    def test_empty_file_does_not_bypass_range_validation(self):
        for start, end, expected in ((0, 200, "LINE_RANGE_INVALID"),
                                     (-1, 5, "LINE_RANGE_INVALID"),
                                     (5, 2, "LINE_RANGE_INVALID"),
                                     (1, 502, "LINE_RANGE_TOO_LARGE")):
            status, body = self._file("empty.py", start, end)
            self.assertEqual(status, 400, (start, end))
            self.assertEqual(body["error"]["code"], expected, (start, end))

    def test_empty_file_still_answers_zero_range_for_legal_params(self):
        status, body = self._file("empty.py", 1, 200)
        self.assertEqual(status, 200)
        self.assertEqual((body["startLine"], body["endLine"], body["totalLines"]), (0, 0, 0))

    # ---- F4 ----
    def test_distinct_non_utf8_paths_keep_distinct_identities(self):
        status, body = self._get(f"/api/repo-explorer/tree?projectId={self.project_id}&revision={self.head}")
        self.assertEqual(status, 200)
        undecodable = [entry for entry in body["entries"] if entry.get("pathUndecodable")
                       and entry["kind"] == "file"]
        # bad-\xff.py, bad-\xfe.py, a\xffb.py, dir-\xff/one.py — two.py's dir
        # name is legal ASCII, so its raw path decodes and stays a plain path
        self.assertEqual(len(undecodable), 4)
        identities = {entry["pathIdentity"] for entry in undecodable}
        self.assertEqual(len(identities), 4, "different raw byte paths must not merge")
        for entry in undecodable:
            self.assertTrue(entry["pathIdentity"].startswith("b64:"))
            self.assertEqual(entry["skippedReason"], "文件名不是 UTF-8，首版不支持")

    def test_undecodable_display_text_does_not_collide_with_legal_name(self):
        status, body = self._get(f"/api/repo-explorer/tree?projectId={self.project_id}&revision={self.head}")
        entries = [entry for entry in body["entries"]
                   if entry.get("displayPath") == "a\\xffb.py" or entry.get("path") == "a\\xffb.py"]
        self.assertEqual(len(entries), 2,
                         "legal name and escaped invalid name share the display text")
        legal = [entry for entry in entries if "pathUndecodable" not in entry]
        escaped = [entry for entry in entries if entry.get("pathUndecodable")]
        self.assertEqual(len(legal), 1)
        self.assertEqual(len(escaped), 1)
        self.assertNotIn("pathIdentity", legal[0])
        self.assertTrue(escaped[0]["pathIdentity"].startswith("b64:"))
        # The two share the display text but carry different identities —
        # the escaped one must never be openable as the legal file.
        self.assertNotEqual(legal[0]["path"], escaped[0].get("pathIdentity"))

    def test_open_coverage_reports_identities_too(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo)}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        flagged = [item for item in opened["coverage"]["skipped"]
                   if item.get("pathUndecodable")]
        self.assertEqual(len(flagged), 4)
        self.assertEqual(len({item["pathIdentity"] for item in flagged}), 4)

    # ---- F4 residual (r24): colliding DIRECTORY display texts ----
    def test_colliding_directories_stay_distinct_with_their_own_children(self):
        status, body = self._get(f"/api/repo-explorer/tree?projectId={self.project_id}&revision={self.head}")
        self.assertEqual(status, 200)
        entries = body["entries"]
        dirs = [entry for entry in entries
                if entry["kind"] == "directory"
                and "dir-\\xff" in (entry.get("displayPath"), entry.get("path"))]
        self.assertEqual(len(dirs), 2, "two raw byte dirs share the display text")
        self.assertEqual(len({entry["path"] for entry in dirs}), 2,
                         "their link identities must differ (one b64, one plain)")
        escaped_dirs = [entry for entry in dirs if entry.get("pathUndecodable")]
        legal_dirs = [entry for entry in dirs if "pathUndecodable" not in entry]
        self.assertEqual(len(escaped_dirs), 1)
        self.assertEqual(len(legal_dirs), 1)
        self.assertTrue(escaped_dirs[0]["path"].startswith("b64:"))
        self.assertEqual(legal_dirs[0]["path"], "dir-\\xff")
        by_parent = {}
        for entry in entries:
            if entry["kind"] != "file":
                continue
            name = (entry.get("displayPath") or entry["path"]).split("/")[-1]
            if name in ("one.py", "two.py"):
                by_parent.setdefault(entry["parentPath"], []).append(name)
        for directory in dirs:
            children = by_parent.get(directory["path"], [])
            self.assertEqual(len(children), 1,
                             f"directory {directory['path'][:20]}… must own exactly its own child")
        self.assertEqual(sorted(children for children in by_parent.values()),
                         [["one.py"], ["two.py"]])

    # ---- F5 ----
    def test_object_missing_maps_to_object_missing_not_repo_unreadable(self):
        # Remove a blob object behind the server's back: the collector must
        # surface the loss as OBJECT_MISSING (500), never REPO_UNREADABLE.
        blob_oid = run_git(self.repo, "rev-parse", f"{self.head}:alpha.py")
        object_path = self.repo / ".git" / "objects" / blob_oid[:2] / blob_oid[2:]
        os.chmod(object_path, stat.S_IWRITE)  # Git stores objects read-only
        object_path.unlink()
        status, body = self._get(f"/api/repo-explorer/symbols?projectId={self.project_id}"
                                 f"&revision={self.head}&path=alpha.py")
        self.assertEqual(status, 500)
        self.assertEqual(body["error"]["code"], "OBJECT_MISSING")


if __name__ == "__main__":
    unittest.main()
