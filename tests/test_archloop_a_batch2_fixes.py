"""Regression tests for the BATCH-2 review findings (each one reproduces the
reviewer's scenario, then asserts the repaired behaviour).

Findings covered: A-01 (auto-filled branch metadata must not shadow B's real
edit), A-05 (malformed explicit coverage must be refused, not widened), GEN-01
(quoted credential keys must be filtered), CORRECTION-01 (the correction
payload carries the controlled pack of the CURRENT binding), C-INCREMENTAL-01
(C's incremental patch is converted to applicable CONTRACT_V1 operations),
FIX-01 (verified needs a real commit and recorded evidence), ACCEPTANCE-01
(T01/T21/T24 criteria must not pass on unrelated evidence). G-02/G-03 live in
the controller's own self-check (state/controller_selfcheck.json).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop import ai_transport
from archloop.acceptance import (ai_generation_verdict, handover_tamper_verdict,
                                 self_coverage_verdict)
from archloop.backend_b import a_to_b_graph, b_to_a_graph, diff_to_operations
from archloop.contract import ContractError
from archloop.ops import OP_TYPES, apply_operation
from tests.test_archloop_a_backend_b import (META, run_git, vector_graph,
                                             workspace_setup)


def branch_target(projection: dict, step_id: str, condition: str):
    for process in projection.get("processes", []):
        for step in process.get("steps", []):
            if step["id"] == step_id:
                for branch in step.get("branches", []):
                    if branch.get("condition") == condition:
                        return branch.get("nextStepId")
    raise AssertionError(f"branch not found: {step_id}/{condition}")


def valid_node(node_id: str, path: str = "svc.py", title: str = "服务",
               summary: str = "提供能力") -> dict:
    return {"id": node_id, "title": title, "summary": summary, "status": "candidate",
            "provenance": "rule_based", "entryPoints": [], "interfaces": [], "assumptions": [],
            "process": [], "evidence": [{"path": path, "reason": "实现", "kind": "code_fact"}]}


class BranchFallbackRepairTests(unittest.TestCase):
    """A-01: an auto-filled branch target must never shadow B's real edit."""

    CONDITION = "--map 提供→地图模式"

    def test_b_edited_branch_target_survives_round_trip(self) -> None:
        graph = vector_graph()
        graph["nodes"][0]["process"].append(
            {"stepId": "s3", "title": "落库", "detail": "", "inputs": [], "outputs": [],
             "branches": [], "next": []})
        projected = a_to_b_graph(graph, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        # the branch had no explicit target: the projection auto-fills s2
        self.assertEqual(branch_target(projected, "s1", self.CONDITION), "s2")
        # B edits the target through its own service (reviewer's scenario)
        for process in projected["processes"]:
            for step in process["steps"]:
                if step["id"] == "s1":
                    for branch in step["branches"]:
                        if branch["condition"] == self.CONDITION:
                            branch["nextStepId"] = "s3"
        back = b_to_a_graph(projected, {"origin": "manual"})
        s1 = next(step for node in back["nodes"] for step in node["process"] if step["stepId"] == "s1")
        # the A view must show B's real value, not lose the branch target
        self.assertEqual(s1.get("branchTargets", {}).get(self.CONDITION), "s3")
        # re-projecting must keep s3, and the next sync must produce no
        # step-level operation that would restore the old auto-filled s2
        reprojected = a_to_b_graph(back, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        self.assertEqual(branch_target(reprojected, "s1", self.CONDITION), "s3")
        # no step-level operation may rewrite that branch (the metadata carrier
        # itself is expected to change: the placeholder became a real target)
        offenders = [op for op in diff_to_operations(projected, reprojected)
                     if str(op.get("op", "")).startswith("step.")
                     and self.CONDITION in json.dumps(op, ensure_ascii=False)]
        self.assertEqual(offenders, [])

    def test_untouched_auto_filled_branch_stays_stable(self) -> None:
        graph = vector_graph()
        projected = a_to_b_graph(graph, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        back = b_to_a_graph(projected, {"origin": "manual"})
        s1 = next(step for node in back["nodes"] for step in node["process"] if step["stepId"] == "s1")
        # an auto-fill is not user intent: it is not kept as a branchTarget
        self.assertNotIn("branchTargets", s1)
        reprojected = a_to_b_graph(back, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        self.assertEqual(branch_target(reprojected, "s1", self.CONDITION), "s2")
        offenders = [op for op in diff_to_operations(projected, reprojected)
                     if str(op.get("op", "")).startswith("step.")
                     and self.CONDITION in json.dumps(op, ensure_ascii=False)]
        self.assertEqual(offenders, [])


class CoverageRefusalRepairTests(unittest.TestCase):
    """A-05: an explicit but malformed coverage widens nothing."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "覆盖", "repoPath": str(self.code),
            "description": "说明"})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        self.service.sync_draft_to_backend(self.workspace_id, {})

    def test_malformed_explicit_coverage_is_refused(self) -> None:
        # reviewer's payload: empty lists plus a non-list evidence value
        with self.assertRaises(ContractError) as ctx:
            self.service.review_preview(self.workspace_id, {
                "actor": "操作者", "reason": "核对",
                "coverage": {"nodes": [], "edges": [], "processes": [],
                             "evidence": "bad-list", "scope": "partial"}}, META)
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")
        # a non-object coverage is refused too, not silently replaced
        with self.assertRaises(ContractError) as ctx2:
            self.service.review_preview(self.workspace_id, {
                "actor": "操作者", "reason": "核对", "coverage": ["nodes"]}, META)
        self.assertEqual(ctx2.exception.code, "VALIDATION_FAILED")

    def test_absent_coverage_still_selects_the_default(self) -> None:
        preview = self.service.review_preview(self.workspace_id,
                                              {"actor": "操作者", "reason": "核对"}, META)
        self.assertGreaterEqual(len(preview["reviewCoverage"]["nodes"]), 1)
        self.assertNotIn("confirmationToken", preview)


class CredentialFilterRepairTests(unittest.TestCase):
    """GEN-01: a quoted dict key must not smuggle a credential into the pack."""

    def _pack_for(self, config_text: str) -> dict:
        from archloop.context_pack import build_context_pack
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        repo.mkdir()
        run_git(repo, "init")
        run_git(repo, "config", "user.email", "t@example.com")
        run_git(repo, "config", "user.name", "t")
        (repo / "config.py").write_text(config_text, encoding="utf-8")
        (repo / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
        run_git(repo, "add", ".")
        run_git(repo, "commit", "-m", "init")
        return build_context_pack(str(repo), run_git(repo, "rev-parse", "HEAD"))

    def test_quoted_credential_key_is_excluded(self) -> None:
        # reviewer's reproduction: the same value as a plain assignment was
        # caught, but the quoted dict key was not
        pack = self._pack_for('SETTINGS = {"api_key": "SYNTHETIC_TEST_CREDENTIAL_1234567890"}\n')
        self.assertNotIn("config.py", [item["path"] for item in pack["files"]])
        excluded = {item["path"]: item["reason"] for item in pack["excluded"]}
        self.assertIn("config.py", excluded)
        self.assertIn("凭据", excluded["config.py"])

    def test_prefixed_quoted_credential_key_is_excluded(self) -> None:
        pack = self._pack_for('SETTINGS = {"OPENAI_API_KEY": "SYNTHETIC_TEST_CREDENTIAL_1234567890"}\n')
        self.assertNotIn("config.py", [item["path"] for item in pack["files"]])

    def test_plain_config_stays_included(self) -> None:
        # no over-blocking: a quoted key without a credential value is fine
        pack = self._pack_for('SETTINGS = {"theme": "dark-mode-with-a-long-value"}\n')
        self.assertIn("config.py", [item["path"] for item in pack["files"]])


class CorrectionPackRepairTests(unittest.TestCase):
    """CORRECTION-01: the correction input carries the controlled pack, always
    from the CURRENT code binding."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "纠正输入", "repoPath": str(self.code),
            "description": "说明"})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(self.workspace_id, {"mode": "rule_based"})
        applied = self.service.apply_candidate(self.workspace_id,
                                              {"candidateId": generated["candidateId"]})
        self.node_id = applied["draft"]["graph"]["nodes"][0]["id"]
        self.revision = applied["draft"]["draftRevision"]

    def _capture(self) -> dict:
        captured = {}

        def fake_call(instructions, payload, schema_name, schema, timeout=60):
            captured["payload"] = payload
            return {"operations": [{"type": "update_node", "nodeId": self.node_id,
                                    "fields": {"summary": "按指令修正"}}],
                    "explanation": "已按要求修正局部职责", "unknowns": [], "openQuestions": []}

        with mock.patch.object(ai_transport, "call_model", fake_call):
            preview = self.service.correction_preview(self.workspace_id, {
                "mode": "production", "instruction": "职责改为只读",
                "selectedNodeIds": [self.node_id], "expectedDraftRevision": self.revision})
        return captured["payload"], preview

    def test_payload_carries_excerpts_docs_and_the_missing_list(self) -> None:
        payload, preview = self._capture()
        source = payload["sourceContext"]
        self.assertTrue(source["files"] and all(item["excerpt"] for item in source["files"]))
        self.assertIsInstance(source["skipped"], list)
        self.assertIsInstance(source["excluded"], list)
        self.assertTrue(source["coverage"])
        self.assertTrue(source["limits"])
        self.assertEqual(preview["origin"], "ai_generated")
        self.assertTrue(preview["operations"])

    def test_rebind_refreshes_the_pack_revision(self) -> None:
        before, _ = self._capture()
        identity_revision = self.service.store.load_workspace(
            self.workspace_id)["identity"]["codeRevision"]
        self.assertEqual(before["sourceContext"]["codeRevision"], identity_revision)
        (self.code / "extra.py").write_text("def extra():\n    return 5\n", encoding="utf-8")
        run_git(self.code, "add", ".")
        run_git(self.code, "commit", "-m", "advance")
        new_head = run_git(self.code, "rev-parse", "HEAD")
        self.service.rebind_code_revision(self.workspace_id, {
            "expectedNewCodeRevision": new_head, "actor": "测试操作者"})
        record = self.service.store.load_workspace(self.workspace_id)
        self.assertEqual(record["lastContextPack"]["codeRevision"], new_head)
        after, _ = self._capture()
        self.assertEqual(after["sourceContext"]["codeRevision"], new_head)


class IncrementalConversionRepairTests(unittest.TestCase):
    """C-INCREMENTAL-01: C's patch vocabulary is converted to CONTRACT_V1 ops."""

    def test_conversion_covers_add_update_remove_and_all_apply(self) -> None:
        from archloop.backend_c import _incremental_ops_to_a
        base = {"nodes": [valid_node("node_svc")], "edges": []}
        operations, warnings = _incremental_ops_to_a(base, [
            {"op": "add_node", "nodeId": "node_new_file",
             "data": {"title": "新增模块 new_file.py", "role": "新增职责",
                      "evidence": [{"kind": "file", "path": "new_file.py"}]}},
            {"op": "update_node", "file": "svc.py", "changes": {"evidence_refresh": True},
             "reason": "源码文件 svc.py 发生修改，需更新事实证据"},
            {"op": "remove_node", "nodeId": "node_svc", "reason": "文件已删除"}])
        self.assertEqual([op["type"] for op in operations],
                         ["add_node", "update_node", "remove_node"])
        self.assertTrue(all(op["type"] in OP_TYPES for op in operations))
        self.assertTrue(all("op" not in op and "data" not in op for op in operations))
        graph = {"nodes": [valid_node("node_svc")], "edges": []}
        graph = apply_operation(graph, operations[0])  # add_node
        self.assertIn("node_new_file", [node["id"] for node in graph["nodes"]])
        graph = apply_operation(graph, operations[1])  # update_node
        refreshed = next(node for node in graph["nodes"] if node["id"] == "node_svc")
        self.assertEqual(refreshed["evidence"][0]["kind"], "unknown")
        self.assertIn("需按新提交复核", refreshed["evidence"][0]["reason"])
        graph = apply_operation(graph, operations[2])  # remove_node
        self.assertNotIn("node_svc", [node["id"] for node in graph["nodes"]])
        self.assertEqual(warnings, [])

    def test_unmatched_changes_become_warnings_not_broken_ops(self) -> None:
        from archloop.backend_c import _incremental_ops_to_a
        base = {"nodes": [valid_node("node_svc")], "edges": []}
        operations, warnings = _incremental_ops_to_a(base, [
            {"op": "remove_node", "nodeId": "node_missing"},
            {"op": "update_node", "file": "other.py", "changes": {"evidence_refresh": True}},
            {"op": "add_node", "nodeId": "node_svc", "data": {}}])
        self.assertEqual(operations, [])
        self.assertEqual(len(warnings), 3)
        self.assertTrue(all(item.get("reason") for item in warnings))

    def test_service_incremental_proposal_returns_applicable_ops(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        code, arch, backend, service = workspace_setup(root)
        envelope = service.create_workspace({
            "context": "existing_project", "title": "增量", "repoPath": str(code),
            "description": "说明"})
        workspace_id = envelope["workspace"]["workspaceId"]
        generated = service.generate(workspace_id, {"mode": "rule_based"})
        service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})
        (code / "new_module.py").write_text("def added():\n    return 3\n", encoding="utf-8")
        (code / "entry.py").write_text("def run():\n    return 2\n", encoding="utf-8")
        run_git(code, "add", ".")
        run_git(code, "commit", "-m", "change")
        result = service.incremental_proposal(workspace_id)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["operations"])
        graph = service.store.load_workspace(workspace_id)["draft"]["graph"]
        for operation in result["operations"]:
            self.assertIn(operation["type"], OP_TYPES)
            graph = apply_operation(graph, operation)
        self.assertTrue(all(item.get("reason") for item in result["warnings"]))


class FixTaskVerificationRepairTests(unittest.TestCase):
    """FIX-01: verified requires a real commit and recorded evidence."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "任务", "repoPath": str(self.code),
            "description": "说明"})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        self.task = self.service.create_fix_task(self.workspace_id, {
            "deviation": "期望步骤在实现中被绕过", "acceptance": "重新执行用例并通过",
            "expectedProcessRef": "n_entry/s1", "evidence": [{"path": "entry.py", "reason": "实现位置"}],
            "actor": "操作者"})
        (self.code / "fix.py").write_text("def fixed():\n    return 1\n", encoding="utf-8")
        run_git(self.code, "add", ".")
        run_git(self.code, "commit", "-m", "fix")
        self.commit = run_git(self.code, "rev-parse", "HEAD")
        self.service.update_fix_task(self.workspace_id, self.task["taskId"], {
            "status": "submitted", "actor": "实施者", "commitSha": self.commit,
            "summary": "恢复调用"})

    def _verify(self, **overrides) -> dict:
        payload = {"status": "verified", "actor": "负责人", "confirmedBy": "负责人",
                   "commitSha": self.commit,
                   "verificationEvidence": [{"case": "用例", "result": "通过"}]}
        payload.update(overrides)
        return self.service.update_fix_task(self.workspace_id, self.task["taskId"], payload)

    def test_boolean_evidence_is_refused(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            self._verify(verificationEvidence=True)
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(ContractError):
            self._verify(verificationEvidence=[])

    def test_nonexistent_commit_is_refused(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            self._verify(commitSha="f" * 40)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_real_commit_and_recorded_evidence_verifies(self) -> None:
        verified = self._verify()
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["verification"]["commitSha"], self.commit)
        self.assertEqual(verified["verification"]["evidenceType"], "recorded_results")
        self.assertIsInstance(verified["verification"]["evidence"], list)


class AcceptanceCriteriaRepairTests(unittest.TestCase):
    """ACCEPTANCE-01: the criteria pass only on their own evidence."""

    def test_t01_failed_generation_is_not_a_pass(self) -> None:
        status, evidence = ai_generation_verdict(200, {"status": "AI_GENERATION_FAILED",
                                                       "note": "额度不足", "origin": "none"})
        self.assertEqual(status, "FAIL")
        self.assertEqual(evidence["status"], "AI_GENERATION_FAILED")
        status, _ = ai_generation_verdict(200, {"status": "ai_generated", "origin": "ai_generated",
                                                "graph": {"nodes": []}})
        self.assertEqual(status, "FAIL")  # empty graph is not a first graph

    def test_t01_real_generation_passes_and_unconfigured_is_not_run(self) -> None:
        status, _ = ai_generation_verdict(200, {
            "status": "ai_generated", "origin": "ai_generated", "model": "m",
            "graph": {"nodes": [{"id": "n1", "provenance": "ai_candidate"}], "mapRevision": "r"}})
        self.assertEqual(status, "PASS")
        status, _ = ai_generation_verdict(200, {"status": "NOT_RUN_AWAITING_CONFIGURATION"})
        self.assertEqual(status, "NOT_RUN")

    def test_t21_unrelated_refusal_is_not_tamper_detection(self) -> None:
        # the first run recorded exactly this: the map identity already belonged
        # to another workspace (STALE_CONTEXT, comparison=null) and it was
        # counted as a PASS although no content was ever compared
        status, evidence = handover_tamper_verdict(409, {
            "error": {"code": "STALE_CONTEXT", "message": "版本服务拒绝：地图身份已经属于另一工作区"},
            "handoverComparison": None})
        self.assertEqual(status, "FAIL")
        self.assertIsNone(evidence["comparison"])
        status, _ = handover_tamper_verdict(409, {"error": {"code": "REFERENCE_CONFLICT"}})
        self.assertEqual(status, "FAIL")

    def test_t21_content_mismatch_and_integrity_refusals_pass(self) -> None:
        status, _ = handover_tamper_verdict(200, {"handoverComparison": {
            "contentMatches": False, "revisionMatches": True, "mapIdMatches": True}})
        self.assertEqual(status, "PASS")
        status, _ = handover_tamper_verdict(409, {"error": {"code": "EVIDENCE_MISMATCH"}})
        self.assertEqual(status, "PASS")

    def test_t24_requires_this_repository_and_real_coverage(self) -> None:
        status, evidence = self_coverage_verdict(200, {
            "graph": {"nodes": [{"id": "n1"}]},
            "contextCoverage": {"codeRevision": "a" * 40, "trackedFiles": 2}}, "G:/somewhere/demo-repo")
        self.assertEqual(status, "FAIL")
        self.assertEqual(evidence["trackedFiles"], 2)
        status, _ = self_coverage_verdict(200, {
            "graph": {"nodes": [{"id": "n1"}]},
            "contextCoverage": {"codeRevision": "a" * 40, "trackedFiles": 320,
                                "filesIncluded": 48}}, "G:/projectmind-core")
        self.assertEqual(status, "PASS")
        status, _ = self_coverage_verdict(200, {"graph": {"nodes": []},
                                                "contextCoverage": {"trackedFiles": 320}},
                                          "G:/projectmind-core")
        self.assertEqual(status, "FAIL")


if __name__ == "__main__":
    unittest.main()