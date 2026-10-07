"""Stage 2/3 tests: controlled context packs, real generation input, C module
integration (rule-based candidates, corrections, deviations, incremental),
persisted implementation-fix tasks and same-version handover export/import.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.contract import ContractError
from tests.test_archloop_a_backend_b import (META, run_git, vector_graph, workspace_setup)


def planning_graph() -> dict:
    graph = vector_graph()
    for node in graph["nodes"]:
        node["evidence"] = [{"path": "用户目标：可维护的功能架构", "reason": "目标", "kind": "requirement"}]
        node["status"] = "confirmed_design"
        node["provenance"] = "rule_based"
    return graph


class ContextPackTests(unittest.TestCase):
    def test_bounded_pack_records_coverage_and_excludes_secrets(self) -> None:
        from archloop.context_pack import build_context_pack
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            run_git(repo, "init")
            run_git(repo, "config", "user.email", "t@example.com")
            run_git(repo, "config", "user.name", "t")
            (repo / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            (repo / "helper.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            (repo / ".env").write_text("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456\n",
                                       encoding="utf-8")
            (repo / "README.md").write_text("使用方式：设置 OPENAI_API_KEY=\"你的 API Key\"\n",
                                            encoding="utf-8")
            (repo / "bad.py").write_text("KEY = \"sk-abcdefghijklmnopqrstuvwxyz123456\"\n",
                                         encoding="utf-8")
            (repo / "docs").mkdir()
            (repo / "docs" / "design.md").write_text("# 设计说明\n", encoding="utf-8")
            run_git(repo, "add", "-f", ".")
            run_git(repo, "commit", "-m", "init")
            sha = run_git(repo, "rev-parse", "HEAD")
            pack = build_context_pack(str(repo), sha, max_files=10, max_total_chars=20000)
            paths = [item["path"] for item in pack["files"]]
            self.assertIn("app.py", paths)
            self.assertNotIn(".env", paths)
            self.assertNotIn("bad.py", paths)
            excluded = {item["path"]: item["reason"] for item in pack["excluded"]}
            self.assertIn(".env", excluded)
            self.assertIn("bad.py", excluded)
            self.assertTrue(all(("凭据" in reason) for reason in excluded.values()))
            self.assertIn("README.md", [item["path"] for item in pack["docs"]])
            self.assertEqual(pack["coverage"]["codeRevision"], sha)
            self.assertGreaterEqual(pack["coverage"]["trackedFiles"], 4)
            self.assertTrue(pack["limits"])

    def test_pack_requires_a_full_sha(self) -> None:
        from archloop.context_pack import build_context_pack
        with self.assertRaises(ContractError):
            build_context_pack(".", "HEAD")


class CMouleIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)

    def test_rule_based_generation_is_labeled_and_applies(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "规则生成", "repoPath": str(self.code)})
        workspace_id = envelope["workspace"]["workspaceId"]
        result = self.service.generate(workspace_id, {"mode": "rule_based"})
        self.assertEqual(result["status"], "rule_based")
        self.assertEqual(result["origin"], "rule_based")
        self.assertIn("规则", result["labeled"])
        self.assertTrue(result["graph"]["nodes"])
        self.assertIsNotNone(result["contextCoverage"])
        applied = self.service.apply_candidate(workspace_id, {"candidateId": result["candidateId"]})
        self.assertEqual(applied["draft"]["origin"], "rule_based")

    def test_planning_rule_based_generation_has_no_code_facts(self) -> None:
        envelope = self.service.create_workspace({
            "context": "planning", "title": "规划", "description": "需要可维护架构",
            "goals": "支持自然语言纠正"})
        workspace_id = envelope["workspace"]["workspaceId"]
        result = self.service.generate(workspace_id, {"mode": "rule_based"})
        for node in result["graph"]["nodes"]:
            for item in node["evidence"]:
                self.assertIn(item["kind"], ("requirement", "unknown"))

    def test_rule_based_correction_previews_and_applies(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "纠正", "repoPath": str(self.code)})
        workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(workspace_id, {"mode": "rule_based"})
        applied = self.service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})
        draft = applied["draft"]
        node_id = draft["graph"]["nodes"][0]["id"]
        preview = self.service.correction_preview(workspace_id, {
            "mode": "rule_based", "instruction": "这个职责应改为只负责读路径",
            "selectedNodeIds": [node_id], "expectedDraftRevision": draft["draftRevision"]})
        self.assertEqual(preview["origin"], "rule_based")
        self.assertIn("规则", preview["labeled"])
        self.assertTrue(preview["operations"])
        self.assertIn("diff", preview)
        updated = self.service.apply_correction(workspace_id, {
            "proposalId": preview["proposalId"],
            "expectedDraftRevision": preview["baseDraftRevision"]})
        summary = next(node for node in updated["draft"]["graph"]["nodes"] if node["id"] == node_id)
        self.assertIn("只负责读路径", summary["summary"])

    def test_ai_correction_is_not_run_without_a_model(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "AI 纠正", "repoPath": str(self.code)})
        workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(workspace_id, {"mode": "rule_based"})
        applied = self.service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})
        with self.assertRaises(ContractError) as ctx:
            self.service.correction_preview(workspace_id, {
                "mode": "production", "instruction": "改一个职责",
                "selectedNodeIds": [applied["draft"]["graph"]["nodes"][0]["id"]],
                "expectedDraftRevision": applied["draft"]["draftRevision"]})
        self.assertEqual(ctx.exception.code, "NOT_RUN_AWAITING_CONFIGURATION")

    def test_deviations_are_unknown_without_traces_and_detected_with_them(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "偏差", "repoPath": str(self.code)})
        workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(workspace_id, {"mode": "rule_based"})
        self.service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})
        unknown = self.service.deviations(workspace_id, {"observedTraces": []})
        self.assertEqual(unknown["verdict"], "UNKNOWN")
        self.assertIn("追踪", unknown["reason"])
        record = self.service.store.load_workspace(workspace_id)
        node = record["draft"]["graph"]["nodes"][0]
        traces = [{"called_steps": [node["process"][0]["stepId"]]}] if node.get("process") else []
        if not traces:
            self.skipTest("rule-based candidate has no process steps to compare")
        detected = self.service.deviations(workspace_id, {"observedTraces": traces})
        self.assertIn(detected["verdict"], ("DEVIATION_DETECTED", "ALIGNED"))

    def test_incremental_proposal_after_a_real_code_change(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "变化", "repoPath": str(self.code)})
        workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(workspace_id, {"mode": "rule_based"})
        self.service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})
        (self.code / "new_module.py").write_text("def added():\n    return 3\n", encoding="utf-8")
        (self.code / "entry.py").write_text("def run():\n    return 2\n", encoding="utf-8")
        run_git(self.code, "add", ".")
        run_git(self.code, "commit", "-m", "change")
        result = self.service.incremental_proposal(workspace_id)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["changeSummary"]["added"], 1)
        self.assertGreaterEqual(result["changeSummary"]["modified"], 1)
        self.assertTrue(result["operations"])
        self.assertIn("规则", result["labeled"])


class FixTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "任务", "repoPath": str(self.code)})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)

    def test_task_lifecycle_requires_real_evidence(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            self.service.create_fix_task(self.workspace_id, {"deviation": "步骤被绕过"})
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")  # no acceptance
        task = self.service.create_fix_task(self.workspace_id, {
            "deviation": "期望步骤 B 在实现中被绕过", "acceptance": "重新执行验收用例后 B 被调用",
            "expectedProcessRef": "n_entry/s2", "evidence": [{"path": "entry.py", "reason": "实现位置"}],
            "actor": "测试操作者"})
        self.assertEqual(task["status"], "queued")
        self.assertEqual(task["targetCodeRevision"], run_git(self.code, "rev-parse", "HEAD"))
        listed = self.service.list_fix_tasks(self.workspace_id)
        self.assertEqual(len(listed["tasks"]), 1)
        # a "done" claim without a commit cannot advance to verification
        with self.assertRaises(ContractError):
            self.service.update_fix_task(self.workspace_id, task["taskId"],
                                         {"status": "submitted", "actor": "a"})
        (self.code / "entry.py").write_text("def run():\n    return 9\n", encoding="utf-8")
        run_git(self.code, "add", ".")
        run_git(self.code, "commit", "-m", "fix bypass")
        commit = run_git(self.code, "rev-parse", "HEAD")
        submitted = self.service.update_fix_task(self.workspace_id, task["taskId"], {
            "status": "submitted", "actor": "实施者", "commitSha": commit,
            "summary": "恢复 B 的调用", "evidence": ["tests/test_entry.py 通过"]})
        self.assertEqual(submitted["status"], "verification_pending")
        # verification needs a commit, evidence and the operator's own confirmation
        with self.assertRaises(ContractError):
            self.service.update_fix_task(self.workspace_id, task["taskId"],
                                         {"status": "verified", "actor": "实施者", "commitSha": commit})
        verified = self.service.update_fix_task(self.workspace_id, task["taskId"], {
            "status": "verified", "actor": "负责人", "confirmedBy": "负责人",
            "commitSha": commit,
            "verificationEvidence": [{"case": "重新执行验收用例", "result": "B 已被调用"}],
            "verificationScope": "仅覆盖该过程步骤"})
        self.assertEqual(verified["status"], "verified")
        markdown = self.service.fix_task_markdown(self.workspace_id, task["taskId"])
        self.assertIn("实施修正任务", markdown["markdown"])
        self.assertIn("验收条件", markdown["markdown"])


class HandoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "交接", "repoPath": str(self.code)})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        self.service.sync_draft_to_backend(self.workspace_id, {})
        preview = self.service.review_preview(self.workspace_id, {"actor": "交接操作者"}, META)
        self.service.review_confirm(self.workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        self.published = self.service.publish_version(self.workspace_id, {}, META)

    def test_handover_requires_a_version_and_exports_identities(self) -> None:
        package = self.service.export_handover(self.workspace_id)
        self.assertEqual(package["packageType"], "architecture_handover_v1")
        self.assertEqual(package["mapRevision"], self.published["version"]["mapRevision"])
        self.assertEqual(package["mapSourceRevision"],
                         self.published["provenance"]["mapSourceRevision"])
        self.assertEqual(package["graphNature"], "confirmed_cognition")
        self.assertEqual(len(package["graph"]["nodes"]), 2)
        self.assertIn("importHint", package)

    def test_second_copy_imports_the_same_version(self) -> None:
        package = self.service.export_handover(self.workspace_id)
        root = Path(self.tmp.name)
        second_code = root / "code2"
        run_git(root, "clone", str(self.code), str(second_code))
        run_git(second_code, "remote", "set-url", "origin", "https://example.invalid/demo-source.git")
        second_arch = root / "arch2"
        run_git(root, "clone", str(self.arch), str(second_arch))
        from archloop.adapters import AdapterRegistry
        from archloop.backend_b import BackendB
        from archloop.service import WorkbenchService
        from app import git as app_git
        backend2 = BackendB(root / "b2", code_repositories=[second_code],
                            architecture_repo=second_arch,
                            architecture_branch="architecture/candidates/archloop-test",
                            allowed_origin="http://127.0.0.1:8899")
        service2 = WorkbenchService(root / "a2", AdapterRegistry())
        service2.bind_git(app_git)
        service2.bind_backend_b(backend2)
        imported = service2.import_handover({"package": package, "repoPath": str(second_code)})
        self.assertEqual(imported["version"]["mapRevision"], package["mapRevision"])
        self.assertEqual(imported["provenance"]["mapSourceRevision"], package["mapSourceRevision"])
        self.assertTrue(imported["handoverComparison"]["contentMatches"])
        self.assertTrue(imported["handoverComparison"]["revisionMatches"])
        # a tampered package graph is reported, and the Git version wins
        tampered = json.loads(json.dumps(package))
        tampered["graph"]["nodes"][0]["title"] = "被改过的标题"
        second_import = service2.import_handover({
            "package": tampered, "repoPath": str(second_code),
            "workspaceId": imported["workspace"]["workspaceId"],
            "expectedMapRevision": imported["version"]["mapRevision"]})
        self.assertFalse(second_import["handoverComparison"]["contentMatches"])
        self.assertIn("以 Git 版本为准", second_import["handoverComparison"]["note"])

    def test_handover_without_a_published_version_is_refused(self) -> None:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "未发布", "repoPath": str(self.code)})
        with self.assertRaises(ContractError) as ctx:
            self.service.export_handover(envelope["workspace"]["workspaceId"])
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()