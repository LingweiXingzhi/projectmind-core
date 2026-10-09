"""Independent acceptance tests; Git writes are confined to disposable fixtures."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROTOTYPE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTOTYPE_ROOT))
sys.path.insert(0, str(PROTOTYPE_ROOT / "reference"))

from extensions.code_facts.facts import CodeFactsError, collect_code_facts


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


class ExtensionAdapterAcceptanceTests(TemporaryRepository):
    @classmethod
    def setUpClass(cls):
        try:
            cls.host = importlib.import_module("extension_host")
        except ModuleNotFoundError:
            raise unittest.SkipTest("Parent has not supplied the real reference host yet")
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


if __name__ == "__main__":
    unittest.main()
