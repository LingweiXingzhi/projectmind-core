"""Exercise the public HTTP seam used by independently owned extensions."""

import json
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import MAP_PATH, ROOT, make_handler


class ExtensionHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.extensions_root = Path(self.temp.name)

    def start_server(self, root: Path | None = None) -> str:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(ROOT, MAP_PATH, extensions_root=root or self.extensions_root)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def test_new_directory_provides_api_and_page_without_core_edits(self) -> None:
        folder = self.extensions_root / "team_facts"
        folder.mkdir()
        (folder / "extension.py").write_text(
            "EXTENSION = {'title': '团队事实', 'description': '测试独立接入'}\n"
            "def handle(context, method, data):\n"
            "    return {'method': method, 'revision': context.snapshot()['revision'], "
            "'value': data.get('value', '')}\n",
            encoding="utf-8",
        )
        (folder / "index.html").write_text("<h1>Team facts page</h1>", encoding="utf-8")
        base = self.start_server()

        with urlopen(base + "/api/extensions") as response:
            listing = json.load(response)
        self.assertEqual(listing["extensions"], [{
            "id": "team_facts", "title": "团队事实", "description": "测试独立接入",
            "status": "ready", "pageUrl": "/ext/team_facts", "apiUrl": "/api/extensions/team_facts",
        }])
        with urlopen(base + "/ext/team_facts") as response:
            self.assertIn("Team facts page", response.read().decode("utf-8"))
        with urlopen(base + "/api/extensions/team_facts?value=from-get") as response:
            get_result = json.load(response)
        self.assertEqual(get_result["value"], "from-get")
        self.assertIn(len(get_result["revision"]), (40, 64))

        request = Request(
            base + "/api/extensions/team_facts",
            data=json.dumps({"value": "from-post"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            post_result = json.load(response)
        self.assertEqual(post_result["method"], "POST")
        self.assertEqual(post_result["value"], "from-post")

        wrong_type = Request(base + "/api/extensions/team_facts", data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as invalid:
            urlopen(wrong_type)
        self.assertEqual(invalid.exception.code, 400)

    def test_broken_extension_is_reported_without_breaking_existing_map(self) -> None:
        folder = self.extensions_root / "broken"
        folder.mkdir()
        (folder / "extension.py").write_text("this is invalid python !!!", encoding="utf-8")
        base = self.start_server()

        with urlopen(base + "/api/extensions") as response:
            listing = json.load(response)
        self.assertEqual(listing["extensions"][0]["id"], "broken")
        self.assertEqual(listing["extensions"][0]["status"], "unavailable")
        with urlopen(base + "/api/snapshot") as response:
            snapshot = json.load(response)
        self.assertTrue(snapshot["nodes"])
        with self.assertRaises(HTTPError) as missing:
            urlopen(base + "/api/extensions/broken")
        self.assertEqual(missing.exception.code, 503)

    def test_system_exit_during_load_does_not_stop_core_or_other_extensions(self) -> None:
        exiting = self.extensions_root / "exiting"
        exiting.mkdir()
        (exiting / "extension.py").write_text("import sys\nsys.exit('stop')\n", encoding="utf-8")
        healthy = self.extensions_root / "healthy"
        healthy.mkdir()
        (healthy / "extension.py").write_text(
            "EXTENSION = {'title': '正常扩展', 'description': '仍可运行'}\n"
            "def handle(context, method, data):\n"
            "    return {'ok': True}\n",
            encoding="utf-8",
        )
        try:
            base = self.start_server()
        except SystemExit as exc:
            self.fail(f"Extension loading stopped the core server: {exc}")

        with urlopen(base + "/api/snapshot") as response:
            self.assertTrue(json.load(response)["nodes"])
        with urlopen(base + "/api/extensions") as response:
            listing = {item["id"]: item for item in json.load(response)["extensions"]}
        self.assertEqual(listing["exiting"]["status"], "unavailable")
        self.assertEqual(listing["healthy"]["status"], "ready")
        with urlopen(base + "/api/extensions/healthy") as response:
            self.assertEqual(json.load(response), {"ok": True})

    def test_runtime_failure_is_contained_and_other_routes_still_work(self) -> None:
        folder = self.extensions_root / "runtime_failure"
        folder.mkdir()
        (folder / "extension.py").write_text(
            "EXTENSION = {'title': '会失败', 'description': '验证隔离'}\n"
            "def handle(context, method, data):\n"
            "    raise RuntimeError('private detail')\n",
            encoding="utf-8",
        )
        base = self.start_server()
        with self.assertRaises(HTTPError) as failed:
            urlopen(base + "/api/extensions/runtime_failure")
        self.assertEqual(failed.exception.code, 500)
        self.assertNotIn("private detail", failed.exception.read().decode("utf-8"))
        with urlopen(base + "/api/snapshot") as response:
            self.assertTrue(json.load(response)["nodes"])

    def test_a30_runtime_system_exit_is_contained_as_extension_error(self) -> None:
        # A30/D1 oracle: an extension raising SystemExit at RUNTIME must not
        # escape the host. In-process: run() converts it to ExtensionError.
        folder = self.extensions_root / "exiting_runtime"
        folder.mkdir()
        (folder / "extension.py").write_text(
            "EXTENSION = {'title': '运行期退出', 'description': 'A30'}\n"
            "def handle(context, method, data):\n"
            "    raise SystemExit(7)\n",
            encoding="utf-8",
        )
        healthy = self.extensions_root / "healthy"
        healthy.mkdir()
        (healthy / "extension.py").write_text(
            "EXTENSION = {'title': '正常扩展', 'description': '仍可运行'}\n"
            "def handle(context, method, data):\n"
            "    return {'ok': True}\n",
            encoding="utf-8",
        )
        base = self.start_server()
        # Controlled HTTP failure (pre-fix this escaped run() and the request
        # worker thread died without an HTTP response).
        with self.assertRaises(HTTPError) as failed:
            urlopen(base + "/api/extensions/exiting_runtime")
        self.assertEqual(failed.exception.code, 500)
        self.assertNotIn("扩展目录", failed.exception.read().decode("utf-8"))
        # The healthy extension, the core route and the listing all survive.
        with urlopen(base + "/api/extensions/healthy") as response:
            self.assertEqual(json.load(response), {"ok": True})
        with urlopen(base + "/api/snapshot") as response:
            self.assertTrue(json.load(response)["nodes"])
        with urlopen(base + "/api/extensions") as response:
            listing = {item["id"]: item for item in json.load(response)["extensions"]}
        self.assertEqual(listing["exiting_runtime"]["status"], "ready")

    def test_a30_runtime_base_exception_family_is_contained(self) -> None:
        # KeyboardInterrupt and GeneratorExit raised inside extension code are
        # contained with the same policy; multiple failing extensions coexist.
        cases = {
            "raises_ki": "raise KeyboardInterrupt('extension-local interrupt')\n",
            "raises_ge": "raise GeneratorExit('extension-local close')\n",
        }
        for name, body in cases.items():
            folder = self.extensions_root / name
            folder.mkdir()
            (folder / "extension.py").write_text(
                f"EXTENSION = {{'title': '{name}', 'description': 'A30'}}\n"
                f"def handle(context, method, data):\n"
                f"    {body}",
                encoding="utf-8",
            )
        base = self.start_server()
        for name in cases:
            with self.assertRaises(HTTPError) as failed:
                urlopen(base + "/api/extensions/" + name)
            self.assertEqual(failed.exception.code, 500, name)
        # After every failure the same routes still answer.
        with urlopen(base + "/api/snapshot") as response:
            self.assertTrue(json.load(response)["nodes"])

    def test_a30_d_extension_routes_survive_runtime_system_exit(self) -> None:
        # Coexistence on the real shipped set: inject a runtime-SystemExit
        # extension next to the shipped D extensions; every other extension
        # route (worklog / handoff / continuity / project_summary) and the
        # core routes must remain reachable.
        shipped = Path(self.temp.name) / "shipped"
        shipped.mkdir()
        for source in (ROOT / "extensions").iterdir():
            if source.is_dir() and not source.name.startswith("."):
                shutil.copytree(source, shipped / source.name,
                                ignore=shutil.ignore_patterns("__pycache__"))
        (shipped / "exiting_runtime").mkdir()
        (shipped / "exiting_runtime" / "extension.py").write_text(
            "EXTENSION = {'title': '运行期退出', 'description': 'A30'}\n"
            "def handle(context, method, data):\n"
            "    raise SystemExit(7)\n",
            encoding="utf-8",
        )
        base = self.start_server(shipped)
        with self.assertRaises(HTTPError) as failed:
            urlopen(base + "/api/extensions/exiting_runtime")
        self.assertEqual(failed.exception.code, 500)
        with urlopen(base + "/api/extensions") as response:
            listing = {item["id"]: item["status"]
                       for item in json.load(response)["extensions"]}
        for identifier in ("worklog", "handoff", "continuity", "project_summary"):
            self.assertEqual(listing[identifier], "ready", identifier)
            with urlopen(base + "/api/extensions/" + identifier) as response:
                self.assertTrue(json.load(response))
        with urlopen(base + "/api/snapshot") as response:
            self.assertTrue(json.load(response)["nodes"])

    def test_a30_host_run_contract_direct(self) -> None:
        # Direct probe of the seam (mirrors the A30 audit probe): SystemExit
        # never escapes run(); it surfaces chained as ExtensionError.
        from extension_host import ExtensionContext, ExtensionError, ExtensionHost

        context = ExtensionContext(repo=ROOT, map_path=MAP_PATH,
                                   snapshot=lambda: {}, compare=lambda base, target: {})
        folder = self.extensions_root / "exiting_runtime"
        folder.mkdir()
        (folder / "extension.py").write_text(
            "EXTENSION = {'title': 'x', 'description': 'y'}\n"
            "def handle(context, method, data):\n"
            "    raise SystemExit(7)\n",
            encoding="utf-8",
        )
        host = ExtensionHost(self.extensions_root, context)
        with self.assertRaises(ExtensionError) as contained:
            host.run("exiting_runtime", "GET", {})
        self.assertIsInstance(contained.exception.__cause__, SystemExit)

    def test_shipped_example_is_discovered_and_has_a_default_page(self) -> None:
        base = self.start_server(ROOT / "extensions")
        with urlopen(base + "/") as response:
            self.assertIn('src="/extensions.js"', response.read().decode("utf-8"))
        with urlopen(base + "/extensions.js") as response:
            self.assertIn("/api/extensions", response.read().decode("utf-8"))
        with urlopen(base + "/api/extensions") as response:
            listing = json.load(response)
        self.assertIn("project_summary", [item["id"] for item in listing["extensions"]])
        with urlopen(base + "/api/extensions/project_summary") as response:
            summary = json.load(response)
        with urlopen(base + "/api/snapshot") as response:
            snapshot = json.load(response)
        self.assertEqual(summary["status"], "curated_map_summary")
        self.assertEqual(summary["revision"], snapshot["revision"])
        self.assertGreater(summary["nodeCount"], 0)
        with urlopen(base + "/ext/project_summary") as response:
            self.assertIn("/extension.js", response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
