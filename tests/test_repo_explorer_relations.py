# -*- coding: utf-8 -*-
"""GET /api/repo-explorer/relations via C's `parse_imports` (task book §6.5).

Accepted resolution contract (r03 R2-Q7 + r04 R3-Q1, adopted verbatim):

- the package depth d is measured from the file's **search root**, not from the
  repository root (`src/core/mod.py` -> search root `src`, package `core`,
  d = 1);
- a relative import needs `1 <= level <= d`, and the base is the package moved
  up `level - 1` components; `level > d` never matches, even when a file with
  that name happens to exist (`src/core/mod.py`'s `from ..outside` must NOT
  match `src/outside.py`); a file with no package context (d = 0) has no
  resolvable relative import at all;
- `targetPath` is always a concrete source blob (`x.py` or `x/__init__.py`);
  `from pkg import name` never resolves to `pkg/__init__.py`, because a
  package attribute or re-export cannot be confirmed without cross-file
  inference — that case is unresolved;
- several concrete candidates (same-name module file and package) stay
  ambiguous with every candidate listed;
- the reverse scan covers exactly the parsers' supported range, reports its own
  coverage (`importScan`), and never presents a partial scan as complete.

`dependents` only ever lists records that parsed successfully and resolved to
this file. Path admission is shared with the other content endpoints (R2-Q5).
"""
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import make_handler
from repo_index.explorer import ExplorerRegistry

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PYTHON_FILES = 27  # .py/.PY files the open budget indexed (huge.py is over 1 MiB)


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

        def write(relative: str, content: str) -> None:
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        # -- a plain package ---------------------------------------------------
        write("pkg/__init__.py", "")
        write("pkg/helper.py", "VALUE = 1\n")
        write("pkg/consumer.py", "from . import helper\nfrom . import nope\n")
        # R48-02: `pkg/__init__.py` exists but `pkg/absent` does not, so the
        # record may be a package attribute — unresolved, never `__init__.py`.
        write("pkg/attributes.py", "from . import absent\n")
        # same-name module file AND package: a genuine ambiguity
        write("pkg/thing.py", "VALUE = 2\n")
        write("pkg/thing/__init__.py", "VALUE = 3\n")
        write("pkg/ambiguous.py", "from . import thing\n")
        # `from M import name` where only the plain module M exists: the module
        # IS the dependency (D's fixture oracle expects exactly this).
        write("pkg/utils.py", "def helper(value):\n    return value + 1\n")
        write("pkg/frommodule.py", "from .utils import helper as h\n")
        # …and where M exists both as a module and as a package, the statement
        # denotes two real source blobs -> ambiguous (D's `dual` case).
        write("dual.py", "thing = 1\n")
        write("dual/__init__.py", "thing = 2\n")
        write("pkg/dualconsumer.py", "from dual import thing\n")
        # a namespace package: a directory with no `__init__.py`
        write("pkg/ns/inner.py", "VALUE = 4\n")
        # `pkg/ns` is a directory with no `__init__.py` and no `pkg/ns.py`, so
        # it is the PEP 420 namespace-package shape: visible, but no source
        # entry point to point at.
        write("pkg/nsconsumer.py", "from . import ns\n")
        write("pkg/broken.py", "def oops(:\n")
        # -- src layout: the search root is `src`, not the repository root -----
        write("src/outside.py", "VALUE = 5\n")
        write("src/core/__init__.py", "")
        write("src/core/helper.py", "VALUE = 6\n")
        write("src/core/mod.py",
              "from . import helper\nimport core.helper\nfrom ..outside import x\n")
        write("src/core/sub/__init__.py", "")
        write("src/core/sub/mod.py", "from .. import helper\n")
        write("src/tool.py", "from . import helper\n")
        # An absolute import from a file that sits DIRECTLY in a search root:
        # d = 0 kills its relative imports, but its own search root still
        # governs absolute lookups (`src/srcpkg/helper.py`).
        write("src/srcpkg/__init__.py", "")
        write("src/srcpkg/helper.py", "def src_helper():\n    return 4\n")
        write("src/consumer.py", "from srcpkg.helper import src_helper\n")
        # -- repository root: no package context ---------------------------------
        write("service.py", "from . import helper\n")
        # a case-variant Python file: same parser support, so it must be scanned
        write("consumer.PY", "import pkg.helper\n")
        # files that are visible but outside the import scan
        write("huge.py", "#" + "x" * (1_048_576 + 1))
        write("notes.txt", "text\n")
        write("big.log", "y" * (1_048_576 + 1))

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

    # -- resolved / unresolved / ambiguous ------------------------------------
    def test_relative_import_resolves_inside_the_package(self):
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

    def test_missing_candidate_is_unresolved_with_a_reason(self):
        status, body = self._relations("pkg/consumer.py")
        self.assertEqual(status, 200)
        self.assertEqual(self._by_line(body, 2)["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})
        self.assertTrue(any("未解析" in warning for warning in body["warnings"]),
                        body["warnings"])

    def test_package_attribute_is_never_inferred_from_the_package_file(self):
        # R48-02: `pkg/__init__.py` exists, but that does not confirm `absent`.
        status, body = self._relations("pkg/attributes.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})
        self.assertNotIn("pkg/__init__.py", json.dumps(body["imports"]))
        # …and it must not become a confirmed reverse edge either.
        status, dependents = self._relations("pkg/__init__.py")
        self.assertEqual(status, 200)
        self.assertEqual(dependents["dependents"], [])

    def test_from_module_import_resolves_to_the_module_itself(self):
        # r03 R2-Q7 "只有候选文件真实存在才连接": `from .utils import helper`
        # depends on the module `pkg/utils.py`, which is a plain module file.
        status, body = self._relations("pkg/frommodule.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "resolved", "targetPath": "pkg/utils.py",
                          "candidates": ["pkg/utils.py"]})
        status, dependents = self._relations("pkg/utils.py")
        self.assertEqual(dependents["dependents"],
                         [{"path": "pkg/frommodule.py", "line": 1, "end_line": 1}])

    def test_module_existing_as_file_and_package_is_ambiguous(self):
        # The same module name as a plain file AND as a package: two real
        # source blobs, so both stay listed and nothing is confirmed.
        status, body = self._relations("pkg/dualconsumer.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "ambiguous", "targetPath": None,
                          "candidates": ["dual.py", "dual/__init__.py"]})

    def test_same_name_module_file_and_package_stay_ambiguous(self):
        status, body = self._relations("pkg/ambiguous.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "ambiguous", "targetPath": None,
                          "candidates": ["pkg/thing.py", "pkg/thing/__init__.py"]})

    def test_namespace_package_directory_is_unresolved_with_that_reason(self):
        status, body = self._relations("pkg/nsconsumer.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})
        self.assertTrue(any("命名空间包" in warning for warning in body["warnings"]),
                        body["warnings"])

    def test_relative_import_outside_a_package_is_unresolved(self):
        status, body = self._relations("service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})
        self.assertTrue(any("包语境" in warning for warning in body["warnings"]),
                        body["warnings"])

    # -- the src search root (R48-01, r04 R3-Q1 examples) ---------------------
    def test_src_layout_package_depth_is_measured_from_the_search_root(self):
        status, body = self._relations("src/core/mod.py")
        self.assertEqual(status, 200)
        # `src/core/mod.py` is package `core` relative to `src`, so d = 1.
        self.assertEqual(self._by_line(body, 1)["resolution"],
                         {"status": "resolved", "targetPath": "src/core/helper.py",
                          "candidates": ["src/core/helper.py"]})

    def test_absolute_import_also_searches_the_files_own_search_root(self):
        status, body = self._relations("src/core/mod.py")
        self.assertEqual(status, 200)
        self.assertEqual(self._by_line(body, 2)["resolution"],
                         {"status": "resolved", "targetPath": "src/core/helper.py",
                          "candidates": ["src/core/helper.py"]})

    def test_relative_import_beyond_the_top_level_package_never_matches(self):
        # `from ..outside` in package `core` (d = 1) exceeds the top-level
        # package; `src/outside.py` exists but must NOT be matched.
        status, body = self._relations("src/core/mod.py")
        self.assertEqual(status, 200)
        third = self._by_line(body, 3)
        self.assertEqual(third["level"], 2)
        self.assertEqual(third["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})
        self.assertTrue(any("越出顶层包" in warning for warning in body["warnings"]),
                        body["warnings"])

    def test_one_level_relative_import_inside_a_subpackage(self):
        status, body = self._relations("src/core/sub/mod.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "resolved", "targetPath": "src/core/helper.py",
                          "candidates": ["src/core/helper.py"]})

    def test_relative_import_under_the_search_root_has_no_package_context(self):
        status, body = self._relations("src/tool.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})

    def test_absolute_import_uses_the_search_root_of_a_context_free_file(self):
        # `src/consumer.py` has no package context (it sits directly in the
        # search root), but `from srcpkg.helper import src_helper` must still
        # resolve inside `src/`.
        status, body = self._relations("src/consumer.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "resolved", "targetPath": "src/srcpkg/helper.py",
                          "candidates": ["src/srcpkg/helper.py"]})

    # -- reverse scan ---------------------------------------------------------
    def test_dependents_only_count_resolved_records(self):
        status, body = self._relations("pkg/helper.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["dependents"],
                         [{"path": "consumer.PY", "line": 1, "end_line": 1},
                          {"path": "pkg/consumer.py", "line": 1, "end_line": 1}])

    def test_scan_range_matches_the_parser_support_range(self):
        # R48-03: `consumer.PY` is a Python file to the parser, so it must also
        # be scanned — otherwise its resolved import loses the reverse edge.
        status, body = self._relations("pkg/helper.py")
        self.assertEqual(status, 200)
        self.assertIn("consumer.PY", [item["path"] for item in body["dependents"]])

    def test_src_layout_dependents_stay_inside_the_search_root(self):
        status, body = self._relations("src/core/helper.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["dependents"],
                         [{"path": "src/core/mod.py", "line": 1, "end_line": 1},
                          {"path": "src/core/mod.py", "line": 2, "end_line": 2},
                          {"path": "src/core/sub/mod.py", "line": 1, "end_line": 1}])

    def test_ambiguous_target_is_not_a_confirmed_dependent(self):
        for path in ("pkg/thing.py", "pkg/thing/__init__.py"):
            status, body = self._relations(path)
            self.assertEqual(status, 200)
            self.assertEqual(body["dependents"], [], path)

    def test_import_scan_reports_its_own_coverage_and_gaps(self):
        status, body = self._relations("pkg/consumer.py")
        self.assertEqual(status, 200)
        scan = body["importScan"]
        self.assertEqual(scan["total"], ALLOWED_PYTHON_FILES)
        self.assertEqual(scan["parseFailed"], 1)          # pkg/broken.py
        self.assertEqual(scan["scanned"], ALLOWED_PYTHON_FILES - 1)
        warnings = " ".join(body["warnings"])
        self.assertIn("解析失败", warnings)
        self.assertIn("未纳入本次扫描", warnings)          # huge.py, skipped by budget

    def test_parse_error_is_preserved(self):
        status, body = self._relations("pkg/broken.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "parse_error")
        self.assertEqual(body["imports"], [])
        self.assertTrue(body["warnings"])

    # -- frontend jump binding (R48-04) ---------------------------------------
    def test_relation_jumps_keep_the_relations_version_context(self):
        # R48-04: the jump must carry the version context the relations
        # response was produced for; falling back to the live browser revision
        # would open an OLD revision's relation at the current revision. The
        # decision is pinned as a pure function so node can execute it.
        if shutil.which("node") is None:
            self.skipTest("node is not available for the pure-function harness")
        harness = (
            "const fs = require('fs');\n"
            "eval(fs.readFileSync(process.argv[1], 'utf8'));\n"
            "const response = JSON.parse(process.argv[2]);\n"
            "const state = JSON.parse(process.argv[3]);\n"
            "console.log(JSON.stringify("
            "relationJumpParams(response, state, 'pkg/helper.py')));\n"
        )
        old = {"projectId": "old-ctx", "revision": "1" * 40}
        live = {"projectId": "live-ctx", "revision": "2" * 40}
        proc = subprocess.run(
            ["node", "-e", harness, str(ROOT / "web" / "explorer-core.js"),
             json.dumps(old), json.dumps(live)],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        jump = json.loads(proc.stdout)
        self.assertEqual(jump["path"], "pkg/helper.py")
        self.assertEqual(jump["startLine"], 1)
        self.assertEqual(jump["context"], old)
        self.assertNotEqual(jump["context"]["revision"], live["revision"])

    def test_relation_jumps_without_a_response_context_use_the_live_one(self):
        if shutil.which("node") is None:
            self.skipTest("node is not available for the pure-function harness")
        harness = (
            "const fs = require('fs');\n"
            "eval(fs.readFileSync(process.argv[1], 'utf8'));\n"
            "const state = JSON.parse(process.argv[2]);\n"
            "console.log(JSON.stringify(relationJumpParams(null, state, 'x.py')));\n"
        )
        live = {"projectId": "live-ctx", "revision": "2" * 40}
        proc = subprocess.run(
            ["node", "-e", harness, str(ROOT / "web" / "explorer-core.js"), json.dumps(live)],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["context"], live)

    # -- admission and capabilities -------------------------------------------
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


class AcceptedSrcLayoutExamplesTests(unittest.TestCase):
    """The three examples r04 R3-Q1 adopts verbatim as test expectations.

    Quoted from the accepted answer (translated):
      - `src/pkg/mod.py` (package `pkg`) + `from . import helper`
        -> statically matches `src/pkg/helper.py`
      - `src/pkg/sub/mod.py` (package `pkg.sub`) + `from .. import helper`
        -> statically matches `src/pkg/helper.py`
      - `src/pkg/mod.py` (package `pkg`) + `from ..outside import x`
        -> unresolved, must NOT match `src/outside.py`
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "src-layout-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")

        def write(relative: str, content: str) -> None:
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        write("src/pkg/__init__.py", "")
        write("src/pkg/helper.py", "VALUE = 1\n")
        write("src/pkg/sub/__init__.py", "")
        # `src/pkg/mod.py` carries the first and third example side by side.
        write("src/pkg/mod.py", "from . import helper\nfrom ..outside import x\n")
        write("src/pkg/sub/mod.py", "from .. import helper\n")
        # Present so the third example is a real trap, not a vacuous assertion.
        write("src/outside.py", "VALUE = 2\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "src layout sample")
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

    def _relations(self, path: str):
        from urllib.parse import quote
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/relations?projectId={self.project_id}"
                            f"&revision={self.head}&path={quote(path)}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_example_one_dot_import_matches_the_package_helper(self):
        status, body = self._relations("src/pkg/mod.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "resolved", "targetPath": "src/pkg/helper.py",
                          "candidates": ["src/pkg/helper.py"]})

    def test_example_two_double_dot_import_matches_the_parent_package_helper(self):
        status, body = self._relations("src/pkg/sub/mod.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["imports"][0]["resolution"],
                         {"status": "resolved", "targetPath": "src/pkg/helper.py",
                          "candidates": ["src/pkg/helper.py"]})

    def test_example_three_beyond_the_top_level_package_never_matches(self):
        status, body = self._relations("src/pkg/mod.py")
        self.assertEqual(status, 200)
        third = body["imports"][1]
        self.assertEqual(third["module"], "outside")
        self.assertEqual(third["level"], 2)
        self.assertEqual(third["resolution"],
                         {"status": "unresolved", "targetPath": None, "candidates": []})
        self.assertNotIn("src/outside.py", json.dumps(third["resolution"]))
        self.assertTrue((self.repo / "src" / "outside.py").is_file(),
                        "the trap file must really exist on disk")


if __name__ == "__main__":
    unittest.main()
