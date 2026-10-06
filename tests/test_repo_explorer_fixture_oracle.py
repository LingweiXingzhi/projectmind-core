# -*- coding: utf-8 -*-
"""Execute D's independent fixture oracle against the live endpoints.

`tests/repo_explorer_acceptance/fixture.py` declares what it generates
(SYMBOLS / IMPORTS) from the task book, independently of the implementation —
that declaration is D's oracle, and the acceptance runner compares against it.

This test does the same comparison inside the unit suite: generate a real
fixture, serve its base revision, and check symbols/relations field by field.
It exists because a resolution rule change (R48-02's over-correction) once
disagreed with the oracle in a way only D's live run could see; from now on the
disagreement fails here too.
"""
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from app import make_handler
from repo_index.explorer import ExplorerRegistry

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "repo_explorer_acceptance"


def _oracle():
    if str(FIXTURE_DIR) not in sys.path:
        sys.path.insert(0, str(FIXTURE_DIR))
    import fixture  # noqa: PLC0415
    return fixture


@unittest.skipIf(shutil.which("git") is None, "git is required to build the fixture")
class FixtureOracleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _oracle()
        self._tmp = tempfile.TemporaryDirectory()
        parent = Path(self._tmp.name) / "parent"
        parent.mkdir()
        self.manifest = self.fixture.generate(parent)
        self.repo = Path(self.manifest["repository"])
        self.base = self.manifest["baseRevision"]
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.repo, None, explorer_registry=ExplorerRegistry()))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.port = self._server.server_address[1]
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo), "revision": self.base}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        self.project_id = opened["projectId"]

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        try:
            self.fixture.cleanup(self.manifest)
        finally:
            self._tmp.cleanup()

    def _get(self, action: str, **params):
        params.update({"projectId": self.project_id, "revision": self.base})
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/{action}?{urlencode(params)}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def test_symbols_match_the_oracle(self):
        status, body = self._get("symbols", path="pkg/service.py")
        self.assertEqual(status, 200)
        self.assertEqual(body["parser"], "python_ast_v1")
        actual = [(item["name"], item["qualified_name"], item["kind"], item["start_line"],
                   item["end_line"], item["docstring"]) for item in body["symbols"]]
        self.assertEqual(actual, [tuple(entry) for entry in self.fixture.SYMBOLS])

    def test_relations_match_the_oracle(self):
        status, body = self._get("relations", path="pkg/service.py")
        self.assertEqual(status, 200)
        actual = [(item["kind"], item["module"], item["level"], item["name"], item["alias"],
                   item["line"], item["end_line"], item["resolution"]["status"],
                   item["resolution"]["targetPath"]) for item in body["imports"]]
        self.assertEqual(actual, [tuple(entry) for entry in self.fixture.IMPORTS])

    def test_target_revision_reverse_relation_matches_the_oracle(self):
        # D05: the second fixture version adds `pkg/new.py` with
        # `from .utils import helper`, so the target revision must show the new
        # reverse relation on pkg/utils.py and no stale index from the base.
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo),
                                      "revision": self.manifest["targetRevision"]}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        params = {"projectId": opened["projectId"],
                  "revision": self.manifest["targetRevision"], "path": "pkg/utils.py"}
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/relations?{urlencode(params)}")
        body = json.loads(conn.getresponse().read())
        conn.close()
        self.assertIn("pkg/new.py", [item["path"] for item in body["dependents"]])


if __name__ == "__main__":
    unittest.main()
