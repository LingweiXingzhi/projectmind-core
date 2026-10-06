# -*- coding: utf-8 -*-
"""GET /api/repo-explorer/relations via C's `parse_imports` (task book §6.5).

Accepted contract after the parser hand-off: `status="unavailable"` is gone —
the response carries C's original import fields plus A's own
`resolution{status, targetPath, candidates}` (resolved / unresolved /
ambiguous), and `dependents` only from records that parsed successfully and
resolved to the current file. Path admission is shared with the other content
endpoints (R2-Q5); a parse failure keeps `parse_error`, never a wrapped empty
success.
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
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "pkg" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
        # `. import helper` resolves against the file's own package; `. import
        # nope` has no candidate at all (unresolved).
        (self.repo / "pkg" / "consumer.py").write_text(
            "from . import helper\nfrom . import nope\n", encoding="utf-8")
        # Both `pkg/utils.py` and the submodule `pkg/utils/thing.py` exist, so
        # `from .utils import thing` is genuinely ambiguous.
        (self.repo / "pkg" / "utils.py").write_text(
            "def thing():\n    return 1\n", encoding="utf-8")
        (self.repo / "pkg" / "utils").mkdir()
        (self.repo / "pkg" / "utils" / "thing.py").write_text("VALUE = 2\n", encoding="utf-8")
        (self.repo / "pkg" / "ambiguous.py").write_text(
            "from .utils import thing\n", encoding="utf-8")
        (self.repo / "pkg" / "broken.py").write_text("def oops(:\n", encoding="utf-8")
        # A relative import from a file that is not inside a package has no
        # search root; an absolute import reaches into the package normally.
        (self.repo / "service.py").write_text("from . import helper\n", encoding="utf-8")
        (self.repo / "app.py").write_text("import pkg.helper\n", encoding="utf-8")
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

    def _by_line(self, body, line):
        return next(item for item in body["imports"] if item["line"] == line)

    def test_imports_keep_parser_fields_and_gain_resolution(self):
        status, body = self._relations("pkg/consumer.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["schemaVersion"], 1)
        self.assertEqual(body["status"], "ok")
        resolved = self._by_line(body, 1)
        self.assertEqual(resolved["kind"], "from")
        self.assertEqual(resolved["module"], "")
        self.assertEqual(resolved["level"], 1)
        self.assertEqual(resolved["name"], "helper")
        self.assertEqual(resolved["end_line"], 1)
        self.assertEqual(resolved["resolution"],
                         {"status": "resolved", "targetPath": "pkg/helper.py",
                          "candidates": ["pkg/helper.py"]})

    def test_no_candidate_is_unresolved_with_empty_candidates(self):
        status, body = self._relations("pkg/consumer.py")
        self.assertEqual(status, 200)
        self.assertEqual(self._by_line(body, 2)["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})

    def test_relative_import_outside_a_package_is_unresolved(self):
        # `service.py` sits at the repository root: level 1 exceeds the package
        # depth, so there is no search root — never a guessed target.
        status, body = self._relations("service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})

    def test_multiple_known_candidates_are_ambiguous(self):
        status, body = self._relations("pkg/ambiguous.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "ambiguous", "targetPath": None,
                          "candidates": ["pkg/utils.py", "pkg/utils/thing.py"]})

    def test_dependents_only_count_resolved_records(self):
        status, body = self._relations("pkg/helper.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["dependents"],
                         [{"path": "app.py", "line": 1, "end_line": 1},
                          {"path": "pkg/consumer.py", "line": 1, "end_line": 1}])

    def test_ambiguous_target_is_not_a_confirmed_dependent(self):
        # `from .utils import thing` is ambiguous, so `pkg/utils.py` must not
        # claim a confirmed reverse edge from it.
        status, body = self._relations("pkg/utils.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["dependents"], [])
        status, body = self._relations("pkg/utils/thing.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["dependents"], [])

    def test_parse_error_is_preserved_and_flagged_in_dependent_scans(self):
        status, body = self._relations("pkg/broken.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "parse_error")
        self.assertEqual(body["imports"], [])
        self.assertTrue(body["warnings"])
        # The unparseable file participates in every dependents scan, which
        # must say explicitly that the answer is a partial-range one.
        status, body = self._relations("pkg/helper.py")
        self.assertEqual(status, 200)
        self.assertTrue(any("已解析范围内" in warning for warning in body["warnings"]))

    def test_capabilities_now_report_imports_available(self):
        self.assertEqual(self.capabilities["imports"], True)

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
