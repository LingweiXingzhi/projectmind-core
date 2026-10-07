"""A<->B integration tests: real B version service behind the A workbench.

Covers the first review batch scope: the single adapter layer (backend_b.py),
real draft persistence through B, the human-review boundary (session + preview
+ explicit confirmation), immutable version production, a second independent
copy reading the same version, conflict/refusal paths and the HTTP seam.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.adapters import AdapterRegistry
from archloop.backend_b import (BackendB, a_to_b_graph, b_to_a_graph, coverage_for,
                                diff_to_operations)
from archloop.contract import ContractError
from archloop.service import WorkbenchService

ORIGIN = "http://127.0.0.1:8899"
META = {"peer": "127.0.0.1", "host": "127.0.0.1:8899", "origin": ORIGIN}


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode("utf-8").strip()


def tiny_code_repo(root: Path, remote: str | None = "https://example.invalid/demo-source.git") -> Path:
    repo = root / "code"
    repo.mkdir(parents=True)
    (repo / "entry.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (repo / "service.py").write_text("def serve():\n    return 2\n", encoding="utf-8")
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "t@example.com")
    run_git(repo, "config", "user.name", "t")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "first")
    if remote:
        run_git(repo, "remote", "add", "origin", remote)
    return repo


def architecture_repo(root: Path, branch: str = "architecture/candidates/archloop-test") -> Path:
    repo = root / "arch-repo"
    repo.mkdir(parents=True)
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "arch@example.com")
    run_git(repo, "config", "user.name", "arch")
    (repo / "README.md").write_text("architecture versions\n", encoding="utf-8")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "init")
    run_git(repo, "checkout", "-b", branch)
    return repo


def vector_graph() -> dict:
    """A-shaped draft graph with provenance, assumptions, branches, failures."""
    return {
        "nodes": [
            {"id": "n_entry", "title": "入口与路由", "summary": "提供 HTTP 入口", "status": "candidate",
             "provenance": "ai_candidate", "entryPoints": ["app.py::main"],
             "interfaces": ["GET /api/snapshot"],
             "evidence": [{"path": "entry.py", "reason": "入口文件", "kind": "code_fact"}],
             "assumptions": ["假设所有访问都来自本机"],
             "process": [
                 {"stepId": "s1", "title": "解析参数", "detail": "resolve_runtime 决定模式",
                  "inputs": ["命令行参数"], "outputs": ["repo"], "branches": ["--map 提供→地图模式"],
                  "next": ["s2"]},
                 {"stepId": "s2", "title": "启动服务", "detail": "ThreadingHTTPServer",
                  "inputs": ["handler"], "outputs": ["监听端口"], "branches": [],
                  "next": [], "allowedFailures": ["端口被占用→报告并退出"],
                  "condition": "已通过参数校验"},
             ]},
            {"id": "n_store", "title": "存储", "summary": "保存版本", "status": "confirmed_design",
             "provenance": "human_input", "entryPoints": [], "interfaces": [],
             "evidence": [{"path": "service.py", "reason": "服务实现", "kind": "code_fact"}],
             "assumptions": [], "process": []},
        ],
        "edges": [
            {"from": "n_entry", "to": "n_store", "type": "functional_collaboration", "label": "写入"},
            {"from": "n_entry", "to": "n_store", "type": "expected_sequence", "label": "先入口后存储"},
        ],
        "mapRevision": "maprev-test",
    }


def workspace_setup(tmp: Path, *, remote="https://example.invalid/demo-source.git"):
    code = tiny_code_repo(tmp, remote=remote)
    arch = architecture_repo(tmp)
    backend = BackendB(tmp / "b-data", code_repositories=[code], architecture_repo=arch,
                       architecture_branch="architecture/candidates/archloop-test",
                       allowed_origin=ORIGIN)
    from app import git as app_git
    service = WorkbenchService(tmp / "a-data", AdapterRegistry())
    service.bind_git(app_git)
    service.bind_backend_b(backend)
    return code, arch, backend, service


class ConversionTests(unittest.TestCase):
    def test_round_trip_preserves_a_content(self) -> None:
        a_graph = vector_graph()
        projection = a_to_b_graph(a_graph, code_repo_id="repo-x", code_revision="a" * 40)
        back = b_to_a_graph(projection["graph"], {"origin": "ai_generated"})
        by_id = {node["id"]: node for node in back["nodes"]}
        original = {node["id"]: node for node in a_graph["nodes"]}
        for node_id, source in original.items():
            restored = by_id[node_id]
            self.assertEqual(restored["title"], source["title"])
            self.assertEqual(restored["summary"], source["summary"])
            self.assertEqual(restored["status"], source["status"])
            self.assertEqual(restored["provenance"], source["provenance"])
            self.assertEqual(restored["entryPoints"], source["entryPoints"])
            self.assertEqual(restored["interfaces"], source["interfaces"])
            self.assertEqual(restored["assumptions"], source["assumptions"])
            self.assertEqual(len(restored["evidence"]), len(source["evidence"]))
            for got, want in zip(restored["evidence"], source["evidence"]):
                self.assertEqual((got["path"], got["reason"], got["kind"]),
                                 (want["path"], want["reason"], want["kind"]))
            self.assertEqual(len(restored["process"]), len(source["process"]))
            for got, want in zip(restored["process"], source["process"]):
                self.assertEqual(got["stepId"], want["stepId"])
                self.assertEqual(got["title"], want["title"])
                self.assertEqual(got["detail"], want["detail"])
                self.assertEqual(got["inputs"], want["inputs"])
                self.assertEqual(got["outputs"], want["outputs"])
                self.assertEqual(got["branches"], want["branches"])
                self.assertEqual(got["next"], want["next"])
                self.assertEqual(got.get("allowedFailures", []), want.get("allowedFailures", []))
                self.assertEqual(got.get("condition", ""), want.get("condition", ""))
        self.assertEqual({(edge["from"], edge["to"], edge["type"], edge["label"]) for edge in back["edges"]},
                         {(edge["from"], edge["to"], edge["type"], edge["label"]) for edge in a_graph["edges"]})

    def test_edge_type_enum_mapping(self) -> None:
        projection = a_to_b_graph(vector_graph(), code_repo_id="repo-x", code_revision="a" * 40)
        types = sorted(item["type"] for item in projection["graph"]["edges"])
        self.assertIn("expected_order", types)
        back = b_to_a_graph(projection["graph"])
        self.assertIn("expected_sequence", sorted(item["type"] for item in back["edges"]))

    def test_planning_graph_has_no_code_evidence_and_no_repo(self) -> None:
        graph = {"nodes": [{"id": "n_a", "title": "设计A", "summary": "职责",
                            "status": "candidate", "provenance": "ai_candidate",
                            "entryPoints": [], "interfaces": [],
                            "evidence": [{"path": "用户目标：可维护架构", "reason": "目标", "kind": "requirement"},
                                         {"path": "entry.py", "reason": "不该出现的代码事实", "kind": "code_fact"}],
                            "process": [], "assumptions": []}],
                 "edges": [], "mapRevision": "m"}
        projection = a_to_b_graph(graph, code_repo_id=None, code_revision=None)
        # page-projection metadata is machine-marked and excluded from the
        # semantic evidence list
        kinds = sorted(item["kind"] for item in projection["graph"]["evidence"]
                       if not str(item.get("unknownReason", "")).startswith("A_projection_metadata"))
        self.assertEqual(kinds, ["unknown", "user_goal"])

    def test_step_id_collision_across_nodes_is_reversible(self) -> None:
        graph = vector_graph()
        graph["nodes"][1]["process"] = [{"stepId": "s1", "title": "同名步骤", "detail": "d",
                                         "inputs": [], "outputs": [], "branches": [], "next": []}]
        projection = a_to_b_graph(graph, code_repo_id="repo-x", code_revision="a" * 40)
        ids = [step["id"] for process in projection["graph"]["processes"] for step in process["steps"]]
        self.assertEqual(len(ids), len(set(ids)))
        back = b_to_a_graph(projection["graph"])
        restored = {node["id"]: [step["stepId"] for step in node["process"]] for node in back["nodes"]}
        self.assertEqual(restored, {"n_entry": ["s1", "s2"], "n_store": ["s1"]})

    def test_diff_to_operations_minimal(self) -> None:
        first = a_to_b_graph(vector_graph(), code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        edited = vector_graph()
        edited["nodes"][0]["summary"] = "新的职责描述"
        second = a_to_b_graph(edited, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        operations = diff_to_operations(first, second)
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["op"], "node.update")
        self.assertEqual(operations[0]["id"], "n_entry")
        self.assertEqual(operations[0]["changes"], {"responsibility": "新的职责描述"})


class RealBackendFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        self.assertTrue(self.backend.available, self.backend.reason)

    def create_workspace_with_draft(self) -> dict:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "真实项目", "repoPath": str(self.code),
            "description": "说明"})
        workspace_id = envelope["workspace"]["workspaceId"]
        self.service._apply_ops_locked = self.service._apply_ops_locked  # no-op for clarity
        record = self.service.store.load_workspace(workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        return envelope

    def test_create_workspace_uses_origin_identity_not_local_path(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "复制仓库", "repoPath": str(self.code)})
        second_root = Path(self.tmp.name) / "code-second"
        run_git(Path(self.tmp.name), "clone", str(self.code), str(second_root))
        # the copy's source URL is the same registered source, so its identity
        # must match even though the local directory differs
        run_git(second_root, "remote", "set-url", "origin", "https://example.invalid/demo-source.git")
        envelope2 = self.service.create_workspace({
            "context": "existing_project", "title": "第二副本", "repoPath": str(second_root)})
        self.assertEqual(envelope["identity"]["codeRepoId"], envelope2["identity"]["codeRepoId"])

    def test_sync_save_reopen_and_conflict(self) -> None:
        envelope = self.create_workspace_with_draft()
        workspace_id = envelope["workspace"]["workspaceId"]
        synced = self.service.sync_draft_to_backend(workspace_id, {})
        self.assertTrue(synced["bDraftId"])
        record = self.service.store.load_workspace(workspace_id)
        binding = record["backendB"]
        self.assertEqual(binding["bBaseMapRevision"], None)
        # B's draft equals the A graph (round trip through the projection)
        b_draft = self.backend.draft_state(record)
        self.assertEqual(len(b_draft["graph"]["nodes"]), 2)
        back = b_to_a_graph(b_draft["graph"], {"origin": "ai_generated"})
        self.assertEqual([node["id"] for node in back["nodes"]], ["n_entry", "n_store"])
        # an edit flows as operations, not as a full rewrite
        draft = record["draft"]
        edited = self.service.apply_ops(workspace_id, {
            "expectedDraftRevision": draft["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_store",
                            "fields": {"summary": "保存不可变版本"}}]})
        reopened = self.service.open_workspace(workspace_id)
        self.assertEqual(reopened["draft"]["graph"]["nodes"][1]["summary"], "保存不可变版本")
        second_sync = self.service.sync_draft_to_backend(workspace_id, {})
        ops = second_sync["operations"]
        self.assertEqual([item["op"] for item in ops], ["node.update"])
        # stale CAS from a second writer is refused with a machine code
        with self.assertRaises(ContractError) as ctx:
            self.service.apply_ops(workspace_id, {
                "expectedDraftRevision": record["draft"]["draftRevision"],
                "operations": [{"type": "update_node", "nodeId": "n_store", "fields": {"summary": "旧值"}}]})
        self.assertEqual(ctx.exception.code, "REVISION_CONFLICT")

    def _sync_and_preview(self, workspace_id: str, **overrides):
        self.service.sync_draft_to_backend(workspace_id, {})
        # verifyCode is decided per context by the adapter (planning has no code)
        request = {"actor": "测试操作者", "reason": "核对职责"}
        request.update(overrides)
        if "verifyCode" not in overrides:
            request["verifyCode"] = None if overrides.get("verifyCode") is None else None
        request.update(overrides)
        return self.service.review_preview(workspace_id, request, META)

    def test_review_preview_confirm_publish_produces_immutable_version(self) -> None:
        envelope = self.create_workspace_with_draft()
        workspace_id = envelope["workspace"]["workspaceId"]
        preview = self._sync_and_preview(workspace_id)
        self.assertTrue(preview["previewDigest"])
        self.assertEqual(preview["origin"], "ai_generated")
        self.assertIn("reviewCoverage", preview)
        self.assertGreaterEqual(len(preview["reviewCoverage"]["nodes"]), 1)
        self.assertEqual(len(preview["afterGraph"]["nodes"]), 2)
        confirm = self.service.review_confirm(workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        self.assertTrue(confirm["publicationAuthorized"])
        self.assertEqual(confirm["verifiedCodeRevision"], envelope["identity"]["codeRevision"])
        # the publication token never reaches the client payload
        self.assertNotIn("publicationToken", confirm)
        published = self.service.publish_version(workspace_id, {}, META)
        self.assertTrue(published["version"]["mapRevision"].startswith("sha256:"))
        self.assertEqual(published["version"]["status"], "confirmed_cognition")
        provenance = published["provenance"]
        self.assertEqual(provenance["sourceKind"], "git_commit")
        map_source = provenance["mapSourceRevision"]
        self.assertEqual(run_git(self.arch, "rev-parse", "HEAD"), map_source)
        shown = run_git(self.arch, "show", "--stat", "--oneline", map_source)
        self.assertIn("architecture: publish", shown)
        # the version graph is the confirmed content, restored to A's shape
        self.assertEqual([node["id"] for node in published["graph"]["nodes"]], ["n_entry", "n_store"])
        # history + detail read back through the service
        history = self.service.version_history(workspace_id)
        self.assertEqual(history["versions"][-1]["mapRevision"], published["version"]["mapRevision"])
        detail = self.service.version_detail(workspace_id, published["version"]["mapRevision"])
        self.assertEqual(detail["version"]["mapRevision"], published["version"]["mapRevision"])
        self.assertEqual(detail["provenance"]["mapSourceRevision"], map_source)
        # a second publish attempt without a new review is refused
        with self.assertRaises(ContractError) as ctx:
            self.service.publish_version(workspace_id, {}, META)
        self.assertEqual(ctx.exception.code, "HUMAN_REVIEW_REQUIRED")

    def test_second_copy_imports_same_version(self) -> None:
        envelope = self.create_workspace_with_draft()
        workspace_id = envelope["workspace"]["workspaceId"]
        preview = self._sync_and_preview(workspace_id)
        self.service.review_confirm(workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        published = self.service.publish_version(workspace_id, {}, META)
        map_revision = published["version"]["mapRevision"]
        map_source = published["provenance"]["mapSourceRevision"]

        # a genuinely independent second copy: own clone of the same source URL
        root = Path(self.tmp.name)
        second_code = root / "code-second-import"
        run_git(root, "clone", str(self.code), str(second_code))
        run_git(second_code, "remote", "set-url", "origin", "https://example.invalid/demo-source.git")
        second_arch = root / "arch-second-import"
        run_git(root, "clone", str(self.arch), str(second_arch))
        backend2 = BackendB(root / "b-data-2", code_repositories=[second_code],
                            architecture_repo=second_arch,
                            architecture_branch="architecture/candidates/archloop-test",
                            allowed_origin=ORIGIN)
        self.assertTrue(backend2.available, backend2.reason)
        from app import git as app_git
        service2 = WorkbenchService(root / "a-data-2", AdapterRegistry())
        service2.bind_git(app_git)
        service2.bind_backend_b(backend2)
        imported = service2.open_from_version({
            "title": "第二副本", "repoPath": str(second_code),
            "mapId": published["version"]["mapId"],
            "mapRevision": map_revision, "mapSourceRevision": map_source,
            "expectedMapRevision": None})
        self.assertEqual(imported["identity"]["codeRepoId"], envelope["identity"]["codeRepoId"])
        self.assertEqual(imported["version"]["mapId"], published["version"]["mapId"])
        self.assertEqual(imported["version"]["mapRevision"], map_revision)
        self.assertEqual(imported["provenance"]["mapSourceRevision"], map_source)
        self.assertEqual([node["id"] for node in imported["graph"]["nodes"]], ["n_entry", "n_store"])
        # a wrong source revision is refused, not silently accepted
        workspace2 = imported["workspace"]["workspaceId"]
        with self.assertRaises(ContractError) as ctx:
            service2.import_version(workspace2, {
                "mapRevision": map_revision, "mapSourceRevision": "0" * 40,
                "expectedMapRevision": map_revision})
        self.assertEqual(ctx.exception.code, "STALE_CONTEXT")

    def test_confirmation_without_preview_or_with_wrong_digest_is_refused(self) -> None:
        envelope = self.create_workspace_with_draft()
        workspace_id = envelope["workspace"]["workspaceId"]
        self.service.sync_draft_to_backend(workspace_id, {})
        with self.assertRaises(ContractError) as ctx:
            self.service.review_confirm(workspace_id, {"previewDigest": "x",
                                                       "decision": "accept"}, META)
        self.assertEqual(ctx.exception.code, "HUMAN_REVIEW_REQUIRED")
        preview = self._sync_and_preview(workspace_id)
        with self.assertRaises(ContractError) as ctx:
            self.service.review_confirm(workspace_id, {
                "previewDigest": "sha256:forged",
                "decision": "accept"}, META)
        self.assertEqual(ctx.exception.code, "HUMAN_REVIEW_REQUIRED")

    def test_preview_after_edit_invalidates_old_preview(self) -> None:
        envelope = self.create_workspace_with_draft()
        workspace_id = envelope["workspace"]["workspaceId"]
        preview = self._sync_and_preview(workspace_id)
        record = self.service.store.load_workspace(workspace_id)
        draft = record["draft"]
        self.service.apply_ops(workspace_id, {
            "expectedDraftRevision": draft["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_store", "fields": {"summary": "改了"}}]})
        # confirming the older preview must fail: the draft moved on
        with self.assertRaises(ContractError) as ctx:
            self.service.review_confirm(workspace_id, {
                "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        self.assertLegacy = None
        self.assertIn(ctx.exception.code, ("HUMAN_REVIEW_REQUIRED", "STALE_CONTEXT", "REVISION_CONFLICT"))

    def test_sample_draft_can_never_be_reviewed(self) -> None:
        envelope = self.service.create_workspace({
            "context": "planning", "title": "规划", "description": "目标"})
        workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(workspace_id)
        graph = vector_graph()
        for node in graph["nodes"]:
            node["evidence"] = [{"path": "用户目标", "reason": "目标", "kind": "requirement"}]
        record["draft"] = self.service._new_draft(record, graph, origin="dev_sample")
        record["draft"]["lineage"] = ["dev_sample"]
        self.service.store.save_workspace_record(record)
        with self.assertRaises(ContractError) as ctx:
            self.service.review_preview(workspace_id, {"actor": "a"}, META)
        self.assertEqual(ctx.exception.code, "DEV_SAMPLE_DISABLED")

    def test_unavailable_backend_reports_reason_instead_of_faking(self) -> None:
        backend = BackendB(Path(self.tmp.name) / "b-broken",
                           architecture_repo=Path(self.tmp.name) / "arch-repo",
                           architecture_branch="main")  # branch rule violated on purpose
        self.assertFalse(backend.available)
        self.assertTrue(backend.reason)
        status = backend.status()
        self.assertEqual(status["kind"], "unavailable")
        self.assertIn("不可用", status["labeled"])

    def test_associate_code_keeps_design_history(self) -> None:
        envelope = self.service.create_workspace({
            "context": "planning", "title": "规划", "description": "目标", "goals": "目标"})
        workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(workspace_id)
        graph = vector_graph()
        for node in graph["nodes"]:
            node["evidence"] = [{"path": "用户目标", "reason": "目标", "kind": "requirement"}]
        record["draft"] = self.service._new_draft(record, graph, origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        self.service.sync_draft_to_backend(workspace_id, {})
        preview = self._sync_and_preview(workspace_id)
        self.service.review_confirm(workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        published = self.service.publish_version(workspace_id, {}, META)
        self.assertEqual(published["version"]["status"], "confirmed_design")
        self.assertIsNone(published["version"]["codeRevision"])
        updated = self.service.associate_code(workspace_id, {
            "repoPath": str(self.code), "expectedMapRevision": published["version"]["mapRevision"]})
        self.assertEqual(updated["workspace"]["context"], "mixed")
        self.assertEqual(updated["identity"]["codeRevision"], run_git(self.code, "rev-parse", "HEAD"))
        record = self.service.store.load_workspace(workspace_id)
        self.assertIn(published["version"]["mapRevision"], record["designHistory"])


class HttpSeamTests(unittest.TestCase):
    """Real HTTP calls: server-side sessions, loopback/origin checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.code, cls.arch, cls.backend, cls.service = workspace_setup(root)
        from app import make_handler
        handler = make_handler(cls.code, None, explorer_registry=None, archloop_service=cls.service)
        cls.server = __import__("http.server", fromlist=["ThreadingHTTPServer"]).ThreadingHTTPServer(
            ("127.0.0.1", 0), handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        # the backend Gateway origin was configured for 8899; rebuild for the
        # real port so the loopback origin check is exercised for real
        cls.backend.allowed_origin = f"http://127.0.0.1:{cls.port}"
        from extensions.architecture_workspace import HumanReviewGateway
        cls.backend.gateway = HumanReviewGateway(cls.backend.service, cls.backend.allowed_origin)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def call(self, method: str, path: str, payload: dict | None = None, origin: str | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if origin is not None:
            request.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_http_review_flow_with_real_sessions(self) -> None:
        origin = f"http://127.0.0.1:{self.port}"
        status, envelope = self.call("POST", "/api/archloop/workspaces", {
            "context": "existing_project", "title": "HTTP 项目", "repoPath": str(self.code)})
        self.assertEqual(status, 200)
        workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        status, synced = self.call("POST", f"/api/archloop/workspaces/{workspace_id}/sync", {})
        self.assertEqual(status, 200, synced)
        # backend status is visible and real
        status, backend = self.call("GET", "/api/archloop/backend")
        self.assertEqual(status, 200)
        self.assertTrue(backend["versionService"]["available"])
        # review preview with a foreign Origin is refused by the loopback guard
        status, refused = self.call("POST", f"/api/archloop/workspaces/{workspace_id}/review-preview",
                                    {"actor": "操作者"}, origin="http://evil.example")
        self.assertEqual(status, 403)
        self.assertEqual(refused["error"]["code"], "FORBIDDEN_ORIGIN")
        status, preview = self.call("POST", f"/api/archloop/workspaces/{workspace_id}/review-preview",
                                    {"actor": "HTTP 操作者", "reason": "核对"}, origin=origin)
        self.assertEqual(status, 200, preview)
        self.assertTrue(preview["previewDigest"])
        status, confirm = self.call("POST", f"/api/archloop/workspaces/{workspace_id}/review-confirm",
                                    {"previewDigest": preview["previewDigest"],
                                     "decision": "accept"}, origin=origin)
        self.assertEqual(status, 200, confirm)
        self.assertTrue(confirm["publicationAuthorized"])
        status, published = self.call("POST", f"/api/archloop/workspaces/{workspace_id}/publish",
                                      {}, origin=origin)
        self.assertEqual(status, 200, published)
        self.assertTrue(published["version"]["mapRevision"].startswith("sha256:"))
        status, history = self.call("GET", f"/api/archloop/workspaces/{workspace_id}/versions")
        self.assertEqual(status, 200)
        self.assertEqual(len(history["versions"]), 1)

    def test_publish_without_review_is_refused(self) -> None:
        status, envelope = self.call("POST", "/api/archloop/workspaces", {
            "context": "existing_project", "title": "HTTP 项目 2", "repoPath": str(self.code)})
        workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        origin = f"http://127.0.0.1:{self.port}"
        status, denied = self.call("POST", f"/api/archloop/workspaces/{workspace_id}/publish",
                                   {}, origin=origin)
        self.assertEqual(status, 403)
        self.assertEqual(denied["error"]["code"], "HUMAN_REVIEW_REQUIRED")


class LegacyDraftImportTests(unittest.TestCase):
    """Explicit import of a previous round's local draft (source stays read-only)."""

    def test_import_copies_draft_keeps_sample_mark_and_source_intact(self) -> None:
        from archloop.legacy_import import apply_import, diff_summary, plan_import, scan
        import hashlib
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        old_root = root / "old-data"
        new_root = root / "new-data"
        envelope = self.service_fixture(old_root)
        old_files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted((old_root / "workspaces").rglob("*")) if path.is_file()}
        listing = scan(old_root)
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["draftOrigin"], "dev_sample")
        plan = plan_import(old_root, new_root)
        self.assertEqual(plan["action"], "import")
        self.assertTrue(plan["sampleMarked"])
        self.assertEqual(plan["diffAgainstTargetExistingDraft"], None)
        applied = apply_import(old_root, new_root)
        self.assertTrue(applied["applied"])
        new_store = __import__("archloop.store", fromlist=["DraftStore"]).DraftStore(new_root)
        record = new_store.load_workspace(applied["target"]["workspaceId"])
        self.assertEqual(record["draft"]["origin"], "dev_sample")
        self.assertIn("dev_sample", record["draft"]["lineage"])
        self.assertIsNone(record["lastPublish"])
        self.assertEqual(record["importedFrom"]["workspaceId"], applied["source"]["workspaceId"])
        # the source root is byte-identical after the import
        after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted((old_root / "workspaces").rglob("*")) if path.is_file()}
        self.assertEqual(old_files, after)
        self.assertEqual(diff_summary(record["draft"]["graph"], record["draft"]["graph"])["nodes"]["updated"], [])

    def service_fixture(self, old_root: Path):
        from app import git as app_git
        from archloop.adapters import AdapterRegistry
        from archloop.service import WorkbenchService
        service = WorkbenchService(old_root, AdapterRegistry())
        repo = Path(tempfile.mkdtemp()) / "legacy-code"
        repo.mkdir()
        run_git(repo, "init")
        run_git(repo, "config", "user.email", "t@example.com")
        run_git(repo, "config", "user.name", "t")
        (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
        run_git(repo, "add", ".")
        run_git(repo, "commit", "-m", "init")
        service.bind_git(app_git)
        envelope = service.create_workspace({
            "context": "existing_project", "title": "旧工作区", "repoPath": str(repo)})
        workspace_id = envelope["workspace"]["workspaceId"]
        record = service.store.load_workspace(workspace_id)
        graph = vector_graph()
        record["draft"] = service._new_draft(record, graph, origin="dev_sample")
        record["draft"]["lineage"] = ["dev_sample"]
        service.store.save_workspace_record(record)
        return envelope


if __name__ == "__main__":
    unittest.main()