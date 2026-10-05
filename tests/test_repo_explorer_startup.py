# -*- coding: utf-8 -*-
"""B1 slice 4: startup mode split, MAP_REQUIRED, and extension blocking.

Accepted contracts: Q2 (three startup modes), R2-Q1 (extensions blocked
before any handler runs in no-map mode; browsing a repo must not create
its Worklog/Continuity stores).
"""
import json
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import MAP_PATH, ROOT, make_handler, resolve_runtime
from repo_index.explorer import ExplorerRegistry


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


def make_sample_repo(directory: Path) -> Path:
    repo = directory / "mode-repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    run_git(repo, "config", "user.name", "T")
    run_git(repo, "config", "user.email", "t@example.invalid")
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-qm", "mode sample")
    return repo


def minimal_map(path: Path) -> Path:
    path.write_text(json.dumps({
        "note": "isolation fixture",
        "nodes": [{"id": "n1", "title": "n", "summary": "s", "entryPoint": "x.py",
                   "position": {"x": 0, "y": 0},
                   "evidence": [{"path": "x.py", "reason": "r"}]}],
        "edges": [],
    }), encoding="utf-8")
    return path


class ResolveRuntimeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = make_sample_repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_map_argument_keeps_legacy_map_mode_without_explorer(self):
        map_path = minimal_map(Path(self._tmp.name) / "map.json")
        repo, map_resolved, explorer = resolve_runtime(self.repo, map_path)
        self.assertEqual(repo, self.repo.resolve())
        self.assertEqual(map_resolved, map_path.resolve())
        self.assertFalse(explorer)

    def test_repo_without_map_starts_explorer_mode(self):
        repo, map_resolved, explorer = resolve_runtime(self.repo, None)
        self.assertEqual(repo, self.repo.resolve())
        self.assertIsNone(map_resolved)
        self.assertTrue(explorer)

    def test_default_startup_is_demo_map_plus_explorer(self):
        repo, map_resolved, explorer = resolve_runtime(None, None)
        self.assertEqual(repo, ROOT)
        self.assertEqual(map_resolved, MAP_PATH)
        self.assertTrue(explorer)

    def test_missing_repo_directory_is_rejected_in_every_mode(self):
        missing = Path(self._tmp.name) / "missing"
        with self.assertRaises(ValueError):
            resolve_runtime(missing, minimal_map(Path(self._tmp.name) / "m2.json"))
        with self.assertRaises(Exception):
            resolve_runtime(missing, None)


class StartupHarness(unittest.TestCase):
    def start(self, repo: Path, map_path: Path | None) -> None:
        registry = ExplorerRegistry() if map_path is None else None
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(repo, map_path, explorer_registry=registry))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.port = self._server.server_address[1]

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()

    def request(self, method: str, path: str, body: dict | None = None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        payload = json.dumps(body) if body is not None else None
        conn.request(method, path, body=payload,
                     headers={"Content-Type": "application/json"} if body else {})
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        return response.status, parsed


class NoMapModeTests(StartupHarness):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = make_sample_repo(Path(self._tmp.name))
        self.start(self.repo, None)

    def tearDown(self):
        super().tearDown()
        self._tmp.cleanup()

    def test_legacy_map_endpoints_require_a_map(self):
        for method, path in (("GET", "/api/snapshot"),
                             ("GET", "/api/evidence?path=x.py&revision=HEAD"),
                             ("GET", "/api/compare?base=1&target=2"),
                             ("GET", "/api/export")):
            status, body = self.request(method, path)
            self.assertEqual(status, 400, path)
            self.assertEqual(body["error"]["code"], "MAP_REQUIRED", path)
        status, body = self.request("POST", "/api/explain", {"base": "1", "target": "2", "nodeId": "n"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "MAP_REQUIRED")

    def test_ai_status_survives_without_a_map(self):
        status, body = self.request("GET", "/api/ai-status")
        self.assertEqual(status, 200)
        self.assertIn("configured", body)

    def test_extension_routes_are_blocked_before_handlers_run(self):
        for method, path in (("GET", "/api/extensions"),
                             ("GET", "/api/extensions/worklog"),
                             ("POST", "/api/extensions/worklog"),
                             ("GET", "/ext/worklog")):
            status, body = self.request(method, path, {} if method == "POST" else None)
            self.assertEqual(status, 503, path)
            self.assertEqual(body["error"]["code"], "EXTENSIONS_UNAVAILABLE", path)

    def test_browsing_does_not_create_extension_stores_in_the_repo(self):
        self.request("GET", "/")
        for method, path in (("GET", "/api/extensions"),
                             ("GET", "/api/extensions/worklog"),
                             ("POST", "/api/extensions/worklog", ),
                             ("GET", "/ext/worklog"),
                             ("GET", "/api/snapshot")):
            body = {} if method == "POST" else None
            self.request(method, path, body)
        git_dir = Path(run_git(self.repo, "rev-parse", "--absolute-git-dir"))
        self.assertFalse((git_dir / "projectmind-worklog").exists(),
                         "worklog store must not be created in the browsed repo")
        self.assertFalse((git_dir / "projectmind-continuity").exists(),
                         "continuity store must not be created in the browsed repo")

    def test_no_map_mode_does_not_even_import_extension_modules(self):
        # B1-b-02: blocking the routes is not enough — ExtensionHost
        # construction exec_module()s every extension, so a no-map instance
        # must load none at all.
        marker = Path(self._tmp.name) / "import-marker.txt"
        extensions_root = Path(self._tmp.name) / "exts"
        folder = extensions_root / "marker_ext"
        folder.mkdir(parents=True)
        (folder / "extension.py").write_text(
            "import pathlib\n"
            f"pathlib.Path(r'{marker}').write_text('imported', encoding='utf-8')\n"
            "EXTENSION = {'title': 'm', 'description': 'm'}\n"
            "def handle(context, method, data):\n    return {}\n",
            encoding="utf-8")
        make_handler(self.repo, None, extensions_root=extensions_root, explorer_registry=ExplorerRegistry())
        self.assertFalse(marker.exists(), "no-map mode must not import extension modules")
        make_handler(self.repo, minimal_map(Path(self._tmp.name) / "m3.json"), extensions_root=extensions_root)
        self.assertTrue(marker.exists(), "map mode keeps loading extensions normally")

    def test_explorer_still_serves_in_no_map_mode(self):
        status, body = self.request("POST", "/api/repo-explorer/open",
                                    {"repoPath": str(self.repo)})
        self.assertEqual(status, 200)
        self.assertTrue(body["projectId"])


class MapModeUnchangedTests(StartupHarness):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = make_sample_repo(Path(self._tmp.name))
        self.map = minimal_map(Path(self._tmp.name) / "map.json")
        self.start(self.repo, self.map)

    def tearDown(self):
        super().tearDown()
        self._tmp.cleanup()

    def test_map_mode_snapshot_still_works(self):
        status, body = self.request("GET", "/api/snapshot")
        self.assertEqual(status, 200)
        self.assertTrue(body["nodes"])

    def test_map_mode_has_no_explorer_routes(self):
        status, _ = self.request("POST", "/api/repo-explorer/open", {"repoPath": str(self.repo)})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
