"""HTTP tests for the architecture workbench routes (A role).

Runs the real ThreadingHTTPServer on an ephemeral loopback port with an
isolated data root, then drives the actual user path: create workspace →
labeled dev-sample candidate → apply → edit with CAS → conflict → preview →
review refusal → fix task → legacy snapshot still intact.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import app as app_module
from archloop.web_session import CSRF_HEADER
from tests.archloop_http_session import establish_session


def demo_node(node_id: str, paths: list[str]) -> dict:
    return {"id": node_id, "title": node_id, "summary": "s", "entryPoint": "e",
            "position": {"x": 10, "y": 10},
            "evidence": [{"path": path, "reason": "r"} for path in paths]}


class ArchLoopHTTPTests(unittest.TestCase):
    _session = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(cls.tmp.name)
        map_path = tmp_path / "map.json"
        map_path.write_text(json.dumps({"note": "test",
                                        "nodes": [demo_node("alpha", ["app.py"])],
                                        "edges": []}), encoding="utf-8")
        data_root = tmp_path / "archloop-data"
        service = app_module.WorkbenchService(data_root, app_module.AdapterRegistry())
        cls.handler = app_module.make_handler(app_module.ROOT, map_path, archloop_service=service)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls._session = None

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None,
                origin: str | None = "same", session: bool = True):
        headers = {}
        if origin == "same":
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        elif origin:
            headers["Origin"] = origin
        data = json.dumps(body).encode("utf-8") if body is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        if data is not None and session:
            # the public write seam requires a live server-side session and its
            # anti-forgery header (D-A-02); tests drive it like the browser
            if self.__class__._session is None:
                self.__class__._session = establish_session(f"http://127.0.0.1:{self.port}")
            cookie, csrf = self.__class__._session
            if cookie:
                headers["Cookie"] = cookie
            if csrf:
                headers[CSRF_HEADER] = csrf
        request = Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                          headers=headers, method=method)
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_service_info_and_sample_graph_are_labeled(self) -> None:
        status, info = self.request("GET", "/api/archloop")
        self.assertEqual(status, 200)
        self.assertEqual(info["service"], "architecture-workbench")
        status, sample = self.request("GET", "/api/archloop/sample-graph")
        self.assertEqual(status, 200)
        self.assertEqual(sample["origin"], "dev_sample")

    def test_cross_origin_write_is_rejected(self) -> None:
        status, payload = self.request("POST", "/api/archloop/workspaces",
                                       {"context": "planning", "title": "x", "goals": "y"},
                                       origin="http://evil.example")
        self.assertEqual(status, 403)

    def test_full_user_story_over_http(self) -> None:
        status, envelope = self.request("POST", "/api/archloop/workspaces",
                                        {"context": "planning", "title": "HTTP 故事", "goals": "目标"})
        self.assertEqual(status, 200)
        workspace_id = envelope["workspace"]["workspaceId"]
        self.assertIsNone(envelope["identity"]["codeRevision"])

        status, sample = self.request("GET", "/api/archloop/sample-graph?context=planning")
        status, generated = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/generate",
                                         {"mode": "dev_sample", "sampleGraph": sample["graph"]})
        self.assertEqual(generated["status"], "dev_sample")

        status, applied = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/apply-candidate",
                                       {"candidateId": generated["candidateId"]})
        self.assertEqual(status, 200)
        draft_revision = applied["identity"]["draftRevision"]

        status, edited = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/apply-ops", {
            "expectedDraftRevision": draft_revision,
            "operations": [{"type": "update_node", "nodeId": applied["draft"]["graph"]["nodes"][0]["id"],
                            "fields": {"summary": "HTTP 修改后的职责"}}],
        })
        self.assertEqual(status, 200)
        new_revision = edited["identity"]["draftRevision"]
        self.assertNotEqual(new_revision, draft_revision)

        status, conflict = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/apply-ops", {
            "expectedDraftRevision": draft_revision,
            "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "并发写"}}],
        })
        self.assertEqual(status, 409)
        self.assertEqual(conflict["error"]["code"], "REVISION_CONFLICT")

        status, preview = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/correction-preview", {
            "expectedDraftRevision": new_revision,
            "instruction": "职责不对",
            "selectedNodeIds": [edited["draft"]["graph"]["nodes"][0]["id"]],
            "mode": "dev_sample",
        })
        self.assertEqual(status, 200)
        self.assertEqual(preview["origin"], "dev_sample")

        # applying the correction by proposalId with its own basis revision
        status, corrected = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/apply-correction", {
            "proposalId": preview["proposalId"],
            "expectedDraftRevision": preview["baseDraftRevision"],
        })
        self.assertEqual(status, 200)

        status, review = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/review", {
            "expectedMapRevision": corrected["draft"]["graph"]["mapRevision"],
            "decision": "accept", "actor": "http-tester", "reason": "测试",
        })
        # sample-derived draft: publishing is refused outright (403), no version.
        self.assertEqual(status, 403)
        self.assertEqual(review["error"]["code"], "DEV_SAMPLE_DISABLED")

        status, task = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/fix-task", {
            "deviation": "步骤顺序", "mode": "dev_sample",
        })
        self.assertEqual(status, 200)
        self.assertEqual(task["origin"], "dev_sample")

        status, reopened = self.request("GET", f"/api/archloop/workspaces/{workspace_id}")
        self.assertEqual(status, 200)
        self.assertEqual(reopened["identity"]["draftRevision"], corrected["identity"]["draftRevision"])

    def test_recheck_is_post_only(self) -> None:
        # MID-1 finding 12: the mutating recheck must not be reachable via an
        # unprotected GET.
        status, envelope = self.request("POST", "/api/archloop/workspaces",
                                        {"context": "planning", "title": "POSTonly", "goals": "目标"})
        workspace_id = envelope["workspace"]["workspaceId"]
        status, refused = self.request("GET", f"/api/archloop/workspaces/{workspace_id}/recheck")
        self.assertEqual(status, 404)  # GET removed: recheck is POST-only now
        status, guarded = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/recheck", {})
        self.assertEqual(status, 400)  # planning workspace has no bound code
        self.assertEqual(guarded["error"]["code"], "VALIDATION_FAILED")

    def test_bad_input_returns_json_error_not_crash(self) -> None:
        # MID-1 finding 10: malformed bodies get machine-coded JSON errors.
        status, payload = self.request("POST", "/api/archloop/workspaces",
                                       {"context": "existing_project", "title": "x",
                                        "repoPath": "G:/definitely/not/a/repo"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "VALIDATION_FAILED")
        self.assertIn("检查路径", payload["error"]["message"])
        self.assertNotIn("fatal:", payload["error"]["message"])
        status, payload2 = self.request("POST", "/api/archloop/workspaces",
                                        {"context": "existing_project", "title": {"nested": "object"},
                                         "repoPath": None})
        self.assertEqual(status, 400)
        self.assertEqual(payload2["error"]["code"], "BAD_REQUEST")

    def test_legacy_snapshot_still_works(self) -> None:
        status, snapshot = self.request("GET", "/api/snapshot", origin=None)
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["mapOrigin"], "curated_demo")

    def test_ai_status_reports_unconfigured_here(self) -> None:
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("PROJECTMIND_AI_MODEL", None)
            status, info = self.request("GET", "/api/ai-status", origin=None)
        self.assertEqual(status, 200)
        self.assertFalse(info["configured"])

    def test_generate_without_config_is_honest_over_http(self) -> None:
        status, envelope = self.request("POST", "/api/archloop/workspaces",
                                        {"context": "planning", "title": "无配置", "goals": "目标"})
        workspace_id = envelope["workspace"]["workspaceId"]
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("PROJECTMIND_AI_MODEL", None)
            status, result = self.request("POST", f"/api/archloop/workspaces/{workspace_id}/generate", {})
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "NOT_RUN_AWAITING_CONFIGURATION")
        self.assertNotIn("graph", result)
        self.assertNotIn("candidateId", result)


if __name__ == "__main__":
    unittest.main()
