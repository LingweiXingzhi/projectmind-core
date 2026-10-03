"""Independent acceptance tests; Git writes are confined to disposable fixtures."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.code_facts.facts import CodeFactsError, collect_code_facts
from app import make_handler


SOURCE = """@staticmethod
def decorated():
    def inner():
        pass
    return inner

class Service:
    @property
    def state(self):
        return "ok"

    async def fetch(self):
        return None

    class Child:
        def run(self):
            pass

async def top_async():
    return None

if False:
    def guarded():
        pass

VALUE = 1
"""


class TemporaryRepository(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="code-facts-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.write("sample.py", SOURCE)
        self.write("nested/second.py", "def second():\n    pass\n")
        self.write("README.md", "Fixture only.\n")
        self.revision = self.commit()

    def git(self, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        result = subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=Code Facts Test",
             "-c", "user.email=code-facts-test@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
             "-c", "core.hooksPath=/dev/null", *args],
            capture_output=True, check=True, env=env, timeout=10,
        )
        return result.stdout.decode("utf-8").strip()

    def write(self, relative, content):
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "Disposable acceptance fixture")
        return self.git("rev-parse", "HEAD")


class CollectorAcceptanceTests(TemporaryRepository):
    def test_exact_entries_and_definition_lines(self):
        result = collect_code_facts(self.repo, self.revision, ["sample.py"])
        self.assertEqual(result, {
            "revision": self.revision,
            "files": [{"path": "sample.py", "language": "python", "entries": [
                {"name": "decorated", "kind": "function", "line": 2},
                {"name": "decorated.inner", "kind": "function", "line": 3},
                {"name": "Service", "kind": "class", "line": 7},
                {"name": "Service.state", "kind": "method", "line": 9},
                {"name": "Service.fetch", "kind": "async_method", "line": 12},
                {"name": "Service.Child", "kind": "class", "line": 15},
                {"name": "Service.Child.run", "kind": "method", "line": 16},
                {"name": "top_async", "kind": "async_function", "line": 19},
                {"name": "guarded", "kind": "function", "line": 23},
            ]}],
            "skipped": [],
        })

    def test_historical_commit_ignores_current_worktree(self):
        before = collect_code_facts(self.repo, self.revision)
        self.write("sample.py", "def renamed():\n    return 42\n")
        newer = self.commit()
        self.write("sample.py", "invalid ! current worktree\n")
        self.write("untracked.py", "def not_committed():\n    pass\n")
        self.assertEqual(collect_code_facts(self.repo, self.revision), before)
        latest = collect_code_facts(self.repo, newer, ["sample.py"])
        self.assertEqual(latest["files"][0]["entries"], [
            {"name": "renamed", "kind": "function", "line": 1},
        ])
        self.assertEqual(latest["revision"], newer)

    def test_local_replacement_refs_cannot_change_sha_evidence(self):
        before = collect_code_facts(self.repo, self.revision, ["sample.py"])
        self.write("sample.py", "def replacement():\n    pass\n")
        replacement = self.commit()
        self.git("replace", self.revision, replacement)
        result = collect_code_facts(self.repo, self.revision, ["sample.py"])
        self.assertEqual(result, before)

    def test_none_selects_all_but_empty_paths_selects_nothing(self):
        result = collect_code_facts(self.repo, self.revision)
        self.assertEqual([file["path"] for file in result["files"]],
                         ["nested/second.py", "sample.py"])
        self.assertEqual([item["path"] for item in result["skipped"]], ["README.md"])
        self.assertEqual(collect_code_facts(self.repo, self.revision, []),
                         {"revision": self.revision, "files": [], "skipped": []})

    def test_paths_are_exact_not_globs(self):
        with self.assertRaises(CodeFactsError):
            collect_code_facts(self.repo, self.revision, ["*.py"])
        self.write("*.py", "def literal_name():\n    pass\n")
        current = self.commit()
        result = collect_code_facts(self.repo, current, ["*.py"])
        self.assertEqual([file["path"] for file in result["files"]], ["*.py"])

    def test_selected_paths_are_sorted_and_deduplicated(self):
        result = collect_code_facts(self.repo, self.revision,
                                    ["sample.py", "nested/second.py", "sample.py"])
        self.assertEqual([file["path"] for file in result["files"]],
                         ["nested/second.py", "sample.py"])

    def test_revision_requires_full_lowercase_commit_sha(self):
        invalid = [None, 123, "HEAD", self.revision[:12], "A" * 40,
                   self.revision + "\n", "0" * 40, "0" * 64]
        for revision in invalid:
            with self.subTest(revision=revision), self.assertRaises(CodeFactsError):
                collect_code_facts(self.repo, revision)

    def test_blob_and_annotated_tag_object_are_rejected(self):
        blob = self.git("rev-parse", f"{self.revision}:sample.py")
        self.git("tag", "-a", "fixture-tag", "-m", "Disposable tag")
        tag_object = self.git("rev-parse", "fixture-tag")
        for revision in [blob, tag_object]:
            with self.subTest(revision=revision), self.assertRaises(CodeFactsError):
                collect_code_facts(self.repo, revision)

    def test_missing_file_in_target_commit_rejects_whole_request(self):
        self.write("new.py", "def later():\n    pass\n")
        self.commit()
        with self.assertRaises(CodeFactsError):
            collect_code_facts(self.repo, self.revision, ["sample.py", "new.py"])
        with self.assertRaises(CodeFactsError):
            collect_code_facts(self.repo, self.revision, ["nested"])

    def test_repository_root_is_required(self):
        invalid_roots = [self.repo / "nested", self.repo / "sample.py",
                         Path(self.temp.name), self.repo / "missing"]
        for repo in invalid_roots:
            with self.subTest(repo=repo), self.assertRaises(CodeFactsError):
                collect_code_facts(repo, self.revision)

    def test_invalid_path_inputs_are_rejected(self):
        invalid = ["sample.py", ("sample.py",), [None], [""], ["../sample.py"],
                   ["/sample.py"], ["nested/../sample.py"], ["nested//second.py"],
                   ["./sample.py"], ["nested\\second.py"], ["a\n.py"], ["a\0.py"]]
        for paths in invalid:
            with self.subTest(paths=paths), self.assertRaises(CodeFactsError):
                collect_code_facts(self.repo, self.revision, paths)

    def test_parse_errors_are_skipped_and_other_files_remain_available(self):
        self.write("broken.py", "def broken(\n")
        self.write("encoding.py", b"# coding: utf-8\nNAME = '\xff'\n")
        self.write("empty.py", "# No definitions.\nVALUE = 1\n")
        current = self.commit()
        result = collect_code_facts(self.repo, current)
        self.assertEqual([item["path"] for item in result["skipped"]],
                         ["README.md", "broken.py", "encoding.py"])
        files = {file["path"]: file for file in result["files"]}
        self.assertEqual(files["empty.py"]["entries"], [])
        self.assertEqual(files["sample.py"]["entries"][0]["name"], "decorated")
        self.assertTrue(all(item["reason"] for item in result["skipped"]))

    def test_declared_source_encoding_is_supported(self):
        self.write("latin.py", "# coding: latin-1\n# café\ndef cafe():\n    pass\n".encode("latin-1"))
        current = self.commit()
        result = collect_code_facts(self.repo, current, ["latin.py"])
        self.assertEqual(result["skipped"], [])
        self.assertEqual(result["files"][0]["entries"],
                         [{"name": "cafe", "kind": "function", "line": 3}])

    def test_deep_valid_syntax_is_extracted_or_explicitly_skipped(self):
        self.write("deep.py", "VALUE = " + "+".join(["1"] * 600)
                   + "\ndef still_present():\n    pass\n")
        current = self.commit()
        result = collect_code_facts(self.repo, current, ["deep.py"])
        if result["files"]:
            self.assertEqual(result["files"][0]["entries"],
                             [{"name": "still_present", "kind": "function", "line": 2}])
            self.assertEqual(result["skipped"], [])
        else:
            self.assertEqual([item["path"] for item in result["skipped"]], ["deep.py"])
            self.assertTrue(result["skipped"][0]["reason"])

    def test_symlink_and_gitlink_are_skipped(self):
        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("def secret():\n    pass\n", encoding="utf-8")
        (self.repo / "linked.py").symlink_to(outside)
        self.git("add", "linked.py")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.revision},vendor/lib")
        self.git("commit", "--quiet", "-m", "Disposable link fixture")
        current = self.git("rev-parse", "HEAD")
        result = collect_code_facts(self.repo, current, ["linked.py", "vendor/lib"])
        self.assertEqual(result["files"], [])
        self.assertEqual([item["path"] for item in result["skipped"]], ["linked.py", "vendor/lib"])

    def test_source_is_never_executed(self):
        marker = Path(self.temp.name) / "executed.txt"
        self.write("unsafe.py", f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
                               "raise RuntimeError('must not execute')\n"
                               "def safe_to_find():\n    pass\n")
        current = self.commit()
        result = collect_code_facts(self.repo, current, ["unsafe.py"])
        self.assertFalse(marker.exists())
        self.assertEqual(result["files"][0]["entries"],
                         [{"name": "safe_to_find", "kind": "function", "line": 4}])

    def test_inherited_git_overrides_cannot_switch_repository(self):
        with patch.dict(os.environ, {"GIT_DIR": "/does/not/exist", "GIT_WORK_TREE": "/"}):
            result = collect_code_facts(self.repo, self.revision, ["sample.py"])
        self.assertEqual(result["revision"], self.revision)
        self.assertEqual(result["files"][0]["entries"][0]["name"], "decorated")

    def test_output_is_json_and_evidence_is_checkable_by_consumer(self):
        result = json.loads(json.dumps(collect_code_facts(self.repo, self.revision)))
        self.assertEqual(set(result), {"revision", "files", "skipped"})
        for file in result["files"]:
            self.assertEqual(set(file), {"path", "language", "entries"})
            committed_lines = self.git("show", f"{result['revision']}:{file['path']}").splitlines()
            for entry in file["entries"]:
                self.assertEqual(set(entry), {"name", "kind", "line"})
                declaration = committed_lines[entry["line"] - 1].strip()
                short_name = entry["name"].rsplit(".", 1)[-1]
                self.assertTrue(declaration.startswith((f"def {short_name}(",
                                                       f"async def {short_name}(",
                                                       f"class {short_name}:")))

    def test_sha256_repository_when_supported_by_installed_git(self):
        self.repo = Path(self.temp.name) / "sha256-repo"
        self.repo.mkdir()
        try:
            self.git("init", "--quiet", "--object-format=sha256")
        except subprocess.CalledProcessError as exc:
            error = exc.stderr.decode("utf-8", errors="replace")
            if "unknown option" in error or "unknown hash algorithm" in error:
                self.skipTest("Installed Git does not support SHA-256 repositories")
            raise
        self.write("sha256.py", "def stable():\n    pass\n")
        revision = self.commit()
        self.assertEqual(len(revision), 64)
        result = collect_code_facts(self.repo, revision, ["sha256.py"])
        self.assertEqual(result, {
            "revision": revision,
            "files": [{"path": "sha256.py", "language": "python", "entries": [
                {"name": "stable", "kind": "function", "line": 1},
            ]}],
            "skipped": [],
        })

    def test_oversized_file_is_skipped_without_losing_other_facts(self):
        self.write("too-large.py", b"#" + b"x" * 1_048_575 + b"\n")
        revision = self.commit()
        result = collect_code_facts(self.repo, revision, ["too-large.py", "sample.py"])
        self.assertEqual([file["path"] for file in result["files"]], ["sample.py"])
        self.assertEqual([item["path"] for item in result["skipped"]], ["too-large.py"])
        self.assertIn("1 MiB", result["skipped"][0]["reason"])

    def test_total_python_budget_rejects_request_with_clear_error(self):
        content = b"#" + b"x" * 1_048_574 + b"\n"
        paths = [f"budget-{index:02d}.py" for index in range(17)]
        for path in paths:
            self.write(path, content)
        revision = self.commit()
        with self.assertRaisesRegex(CodeFactsError, "16 MiB"):
            collect_code_facts(self.repo, revision, paths)

    def test_partial_clone_missing_blob_fails_without_fetching_or_writing_packs(self):
        self.git("config", "uploadpack.allowFilter", "true")
        self.git("config", "uploadpack.allowAnySHA1InWant", "true")
        blob = self.git("rev-parse", f"{self.revision}:sample.py")
        partial = Path(self.temp.name) / "partial-clone"
        self.git("clone", "--quiet", "--no-checkout", "--filter=blob:none",
                 self.repo.as_uri(), str(partial))
        self.repo = partial

        def missing_objects():
            return sorted(line for line in self.git(
                "--no-lazy-fetch", "rev-list", "--objects", "--all", "--missing=print"
            ).splitlines() if line.startswith("?"))

        def packs():
            return sorted(path.name for path in (partial / ".git/objects/pack").glob("*.pack"))

        missing_before, packs_before = missing_objects(), packs()
        self.assertIn("?" + blob, missing_before, "Fixture must actually omit the requested blob")
        with self.assertRaisesRegex(CodeFactsError, "对象.*本地不可用"):
            collect_code_facts(partial, self.revision, ["sample.py"])
        self.assertEqual(missing_objects(), missing_before)
        self.assertEqual(packs(), packs_before)


class ExtensionAdapterAcceptanceTests(TemporaryRepository):
    @classmethod
    def setUpClass(cls):
        cls.host = importlib.import_module("extension_host")
        cls.adapter = importlib.import_module("extensions.code_facts.extension")

    def setUp(self):
        super().setUp()
        self.context = SimpleNamespace(repo=self.repo)

    def test_get_and_post_have_equivalent_results(self):
        get = self.adapter.handle(self.context, "GET",
                                  {"revision": self.revision, "paths": "sample.py\nnested/second.py"})
        post = self.adapter.handle(self.context, "POST",
                                   {"revision": self.revision, "paths": ["sample.py", "nested/second.py"]})
        self.assertEqual(get, post)

    def test_empty_post_paths_stays_empty_and_blank_get_selects_all(self):
        empty = self.adapter.handle(self.context, "POST", {"revision": self.revision, "paths": []})
        self.assertEqual(empty["files"], [])
        self.assertEqual(empty["skipped"], [])
        all_files = self.adapter.handle(self.context, "GET", {"revision": self.revision, "paths": ""})
        self.assertEqual(all_files, collect_code_facts(self.repo, self.revision))

    def test_invalid_requests_raise_real_host_extension_error(self):
        requests = [
            ("DELETE", {"revision": self.revision}),
            ("POST", {"revision": self.revision, "repo": "/tmp/other"}),
            ("GET", {"revision": self.revision, "paths": ["sample.py"]}),
            ("POST", {"revision": self.revision, "paths": "sample.py"}),
            ("POST", {"revision": "HEAD"}),
            ("POST", {}),
            ("POST", []),
        ]
        for method, data in requests:
            with self.subTest(method=method, data=data):
                with self.assertRaises(self.host.ExtensionError) as caught:
                    self.adapter.handle(self.context, method, data)
                self.assertEqual(caught.exception.status, 400)


class CoreHttpIntegrationTests(TemporaryRepository):
    """Use the actual Core host and shipped extension without reference substitutes."""

    def setUp(self):
        super().setUp()
        self.initial_revision = self.revision
        self.space_path = "folder with spaces/file name.py"
        self.write(self.space_path, "def exact_space_path():\n    pass\n")
        self.revision = self.commit()
        self.map_path = Path(self.temp.name) / "map.json"
        self.map_path.write_text(json.dumps({
            "note": "Unconfirmed integration fixture.",
            "nodes": [{
                "id": "sample", "title": "Fixture node", "summary": "Human fixture description",
                "entryPoint": "sample.py", "position": {"x": 10, "y": 10},
                "evidence": [{"path": path, "reason": "Known fixture source"} for path in
                             ("sample.py", "nested/second.py", self.space_path)],
            }],
            "edges": [],
        }), encoding="utf-8")
        handler = make_handler(self.repo, self.map_path)

        class QuietHandler(handler):
            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.shutdown)
        self.base_url = f"http://127.0.0.1:{server.server_port}"

    def request(self, path, data=None):
        if data is None:
            request = Request(self.base_url + path)
        else:
            request = Request(self.base_url + path, data=json.dumps(data).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.headers.get_content_type(), response.read()
        except HTTPError as exc:
            with exc:
                return exc.code, exc.headers.get_content_type(), exc.read()

    def request_json(self, path, data=None, status=200):
        actual_status, content_type, raw = self.request(path, data)
        self.assertEqual(actual_status, status, raw.decode("utf-8", errors="replace"))
        self.assertEqual(content_type, "application/json")
        return json.loads(raw)

    def test_real_core_automatically_discovers_and_serves_b_page(self):
        listing = self.request_json("/api/extensions")
        entry = next(item for item in listing["extensions"] if item["id"] == "code_facts")
        self.assertEqual(entry["status"], "ready")
        self.assertEqual(entry["apiUrl"], "/api/extensions/code_facts")
        self.assertEqual(entry["pageUrl"], "/ext/code_facts")
        status, content_type, body = self.request(entry["pageUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        self.assertEqual(body, (PROJECT_ROOT / "extensions/code_facts/index.html").read_bytes())
        self.assertIn("代码事实", body.decode("utf-8"))
        root_status, root_type, root_page = self.request("/")
        self.assertEqual((root_status, root_type), (200, "text/html"))
        self.assertIn(b'/extensions.js', root_page)

    def test_get_post_and_snapshot_share_exact_repository_revision(self):
        snapshot = self.request_json("/api/snapshot")
        self.assertEqual(snapshot["revision"], self.revision)
        query = urlencode({"revision": snapshot["revision"], "paths": "sample.py\nnested/second.py"})
        get_result = self.request_json("/api/extensions/code_facts?" + query)
        post_result = self.request_json("/api/extensions/code_facts", {
            "revision": snapshot["revision"], "paths": ["sample.py", "nested/second.py"],
        })
        self.assertEqual(get_result, post_result)
        self.assertEqual(get_result["revision"], snapshot["revision"])
        self.assertEqual([file["path"] for file in get_result["files"]],
                         ["nested/second.py", "sample.py"])
        facts = next(file for file in get_result["files"] if file["path"] == "sample.py")
        self.assertEqual(facts["entries"][0], {"name": "decorated", "kind": "function", "line": 2})
        self.write("sample.py", "def uncommitted_change():\n    pass\n")
        self.assertEqual(self.request_json("/api/extensions/code_facts?" + query), get_result)
        evidence = self.request_json("/api/evidence?" + urlencode({
            "revision": snapshot["revision"], "path": "sample.py",
        }))
        self.assertEqual(evidence["revision"], get_result["revision"])
        self.assertEqual(evidence["content"], SOURCE)

    def test_space_path_is_exact_for_real_http_get_and_post(self):
        get_result = self.request_json("/api/extensions/code_facts?" + urlencode({
            "revision": self.revision, "paths": self.space_path,
        }))
        post_result = self.request_json("/api/extensions/code_facts", {
            "revision": self.revision, "paths": [self.space_path],
        })
        self.assertEqual(get_result, post_result)
        self.assertEqual(post_result, {
            "revision": self.revision,
            "files": [{"path": self.space_path, "language": "python", "entries": [
                {"name": "exact_space_path", "kind": "function", "line": 1},
            ]}],
            "skipped": [],
        })

    def test_unicode_separator_path_is_exact_for_real_http_get_and_post(self):
        filename = "a\u2028b.py"
        self.write(filename, "def exact_unicode_name():\n    return 1\n")
        revision = self.commit()
        get_result = self.request_json("/api/extensions/code_facts?" + urlencode({
            "revision": revision, "paths": filename,
        }))
        post_result = self.request_json("/api/extensions/code_facts", {
            "revision": revision, "paths": [filename],
        })
        self.assertEqual(get_result, post_result)
        self.assertEqual(post_result, {
            "revision": revision,
            "files": [{"path": filename, "language": "python", "entries": [
                {"name": "exact_unicode_name", "kind": "function", "line": 1},
            ]}],
            "skipped": [],
        })

    def test_bad_b_requests_are_400_and_leave_core_routes_usable(self):
        before = self.request_json("/api/snapshot")
        invalid_requests = [
            {"revision": "HEAD"},
            {"revision": self.revision, "paths": ["../sample.py"]},
            {"revision": self.revision, "paths": ["app.py"]},
            {"revision": self.revision, "repo": "/other/repository"},
            {"revision": self.revision, "paths": "sample.py"},
            [],
        ]
        for data in invalid_requests:
            with self.subTest(data=data):
                error = self.request_json("/api/extensions/code_facts", data, status=400)
                self.assertEqual(set(error), {"error"})
                self.assertTrue(error["error"])
        get_error = self.request_json("/api/extensions/code_facts?revision=HEAD", status=400)
        self.assertTrue(get_error["error"])
        after = self.request_json("/api/snapshot")
        self.assertEqual(after, before)
        comparison = self.request_json("/api/compare?" + urlencode({
            "base": self.initial_revision, "target": self.revision,
        }))
        self.assertEqual(comparison["targetRevision"], self.revision)
        self.assertEqual(comparison["changes"], [{"code": "A", "path": self.space_path}])
        self.assertEqual(comparison["reviewCandidates"],
                         [{"nodeId": "sample", "changedEvidencePaths": [self.space_path]}])
        status, content_type, markdown = self.request("/api/export?" + urlencode({
            "revision": self.revision, "base": self.initial_revision,
        }))
        self.assertEqual((status, content_type), (200, "text/markdown"))
        self.assertIn(self.revision.encode("ascii"), markdown)
        self.assertIn(b"Unconfirmed integration fixture.", markdown)


if __name__ == "__main__":
    unittest.main()
