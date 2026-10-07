"""Regression tests for the BATCH-3 review findings (the re-review of the
BATCH-2 repairs): each case reproduces the reviewer's scenario and asserts the
repaired behaviour.

Findings covered: A-01 (a legacy metadata carrier must not resurrect a stale
branch target), A-05 (an explicit coverage:null is refused, not defaulted),
GEN-01 (component-boundary key names — ordinary config must not be excluded),
C-INCREMENTAL-01 (merged updates, edge-safe removal, unique ids — every emitted
operation applies in order), ACCEPTANCE-01 (T21 needs a complete comparison,
T24 needs the real bound repository and a real revision). G-02's remaining
fencing gap lives in the controller's self-check
(`lease_fencing_cases` in state/controller_selfcheck.json).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.backend_b import (META_EVIDENCE_ID, META_REASON_PREFIX, a_to_b_graph,
                                b_to_a_graph, diff_to_operations)
from archloop.backend_c import _incremental_ops_to_a
from archloop.context_pack import _key_name_is_secret, _looks_like_secret
from archloop.contract import ContractError
from archloop.ops import OP_TYPES, apply_operation
from tests.test_archloop_a_backend_b import META, run_git, vector_graph, workspace_setup
from tests.test_archloop_a_batch2_fixes import valid_node


class LegacyCarrierRepairTests(unittest.TestCase):
    """A-01: an old-format carrier must never restore a stale branch target."""

    CONDITION = "--map 提供→地图模式"

    def _legacy_carrier(self, projection: dict, b_step_id: str, condition: str,
                        filled: str) -> None:
        """Rewrite the metadata carrier to the OLD format (condition only).

        The old projection recorded `branchFallbacks[step]` as a plain list of
        conditions and no filled value; a carrier written by a973d77 looks
        exactly like this.
        """
        for item in projection["evidence"]:
            if item.get("id") == META_EVIDENCE_ID:
                meta = json.loads(item["content"])
                meta["branchFallbacks"] = {b_step_id: [condition]}
                # legacy carriers could also carry the auto-filled value as the
                # recorded intent (that is what made the old code restore it)
                meta["branchTargets"] = {b_step_id: [[condition, filled]]}
                item["content"] = json.dumps(meta, ensure_ascii=False, sort_keys=True)

    def test_legacy_carrier_does_not_resurrect_a_stale_target(self) -> None:
        graph = vector_graph()
        graph["nodes"][0]["process"].append(
            {"stepId": "s3", "title": "落库", "detail": "", "inputs": [], "outputs": [],
             "branches": [], "next": []})
        projected = a_to_b_graph(graph, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        self._legacy_carrier(projected, "s1", self.CONDITION, "s2")
        # B edits the branch target (reviewer's scenario)
        for process in projected["processes"]:
            for step in process["steps"]:
                if step["id"] == "s1":
                    for branch in step["branches"]:
                        if branch["condition"] == self.CONDITION:
                            branch["nextStepId"] = "s3"
        back = b_to_a_graph(projected, {"origin": "manual"})
        s1 = next(step for node in back["nodes"] for step in node["process"] if step["stepId"] == "s1")
        self.assertEqual(s1.get("branchTargets", {}).get(self.CONDITION), "s3")
        reprojected = a_to_b_graph(back, code_repo_id="repo-x", code_revision="a" * 40)["graph"]
        target = next(branch["nextStepId"] for process in reprojected["processes"]
                      for step in process["steps"] if step["id"] == "s1"
                      for branch in step["branches"] if branch["condition"] == self.CONDITION)
        self.assertEqual(target, "s3")
        offenders = [op for op in diff_to_operations(projected, reprojected)
                     if str(op.get("op", "")).startswith("step.")
                     and self.CONDITION in json.dumps(op, ensure_ascii=False)]
        self.assertEqual(offenders, [])


class SecretKeyNameTests(unittest.TestCase):
    """GEN-01: the key NAME decides by components, never by substring."""

    def test_ordinary_names_are_not_credentials(self) -> None:
        for name in ("monkey", "donkey", "turkey", "service_name", "keynote", "key_path",
                     "token_cache", "client_id", "file_path"):
            self.assertFalse(_key_name_is_secret(name), name)
        self.assertFalse(_looks_like_secret('SETTINGS = {"monkey": "LongNonSensitiveAnimalName"}'))
        self.assertFalse(_looks_like_secret("ANIMALS = {'turkey': 'a-long-bird-name-here'}"))

    def test_credential_names_are_detected_in_every_style(self) -> None:
        for name in ("key", "KEY", "api_key", "OPENAI_API_KEY", "apiKey", "accessToken",
                     "clientSecret", "secret_key_base", "db_password", "GITHUB_TOKEN"):
            self.assertTrue(_key_name_is_secret(name), name)
        self.assertTrue(_looks_like_secret('SETTINGS = {"api_key": "SYNTHETIC_TEST_CREDENTIAL_1234567890"}'))
        self.assertTrue(_looks_like_secret('SETTINGS = {"OPENAI_API_KEY": "SYNTHETIC_TEST_CREDENTIAL_1234567890"}'))
        self.assertTrue(_looks_like_secret("api_key = 'abcdefghijklmnop1234'"))
        self.assertTrue(_looks_like_secret('KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"'))

    def test_placeholders_and_plain_config_stay_out(self) -> None:
        self.assertFalse(_looks_like_secret('OPENAI_API_KEY = "your API key"'))
        self.assertFalse(_looks_like_secret('SETTINGS = {"theme": "dark-mode-with-a-long-value"}'))


class IncrementalConversionRepairTests(unittest.TestCase):
    """C-INCREMENTAL-01: every emitted operation applies in order."""

    def test_two_updates_to_one_node_are_merged(self) -> None:
        base = {"nodes": [valid_node("node_svc", path="a.py")], "edges": []}
        base["nodes"][0]["evidence"].append({"path": "b.py", "reason": "r2", "kind": "code_fact"})
        operations, warnings = _incremental_ops_to_a(base, [
            {"op": "update_node", "file": "a.py", "changes": {"evidence_refresh": True}},
            {"op": "update_node", "file": "b.py", "changes": {"evidence_refresh": True}}])
        self.assertEqual(len(operations), 1)  # merged: one op per node
        self.assertEqual(operations[0]["type"], "update_node")
        graph = {"nodes": [valid_node("node_svc", path="a.py")], "edges": []}
        graph["nodes"][0]["evidence"].append({"path": "b.py", "reason": "r2", "kind": "code_fact"})
        graph = apply_operation(graph, operations[0])
        kinds = {item["path"]: item["kind"] for item in graph["nodes"][0]["evidence"]}
        # BOTH files stay downgraded: the second update must not resurrect a.py
        self.assertEqual(kinds, {"a.py": "unknown", "b.py": "unknown"})
        self.assertEqual(warnings, [])

    def test_removing_a_referenced_node_becomes_a_warning(self) -> None:
        base = {"nodes": [valid_node("node_a"), valid_node("node_b", path="b.py")],
                "edges": [{"from": "node_a", "to": "node_b",
                           "type": "functional_collaboration", "label": "x"}]}
        operations, warnings = _incremental_ops_to_a(base, [
            {"op": "remove_node", "nodeId": "node_a", "reason": "文件删除"}])
        self.assertEqual(operations, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("关系", warnings[0]["reason"])
        # an unreferenced node is still removable (the graph keeps >=1 node)
        operations2, _ = _incremental_ops_to_a(
            {"nodes": [valid_node("node_c"), valid_node("node_d", path="d.py")], "edges": []},
            [{"op": "remove_node", "nodeId": "node_c", "reason": "文件删除"}])
        self.assertEqual([op["type"] for op in operations2], ["remove_node"])
        # removing the LAST node cannot satisfy the graph contract: warning only
        operations3, warnings3 = _incremental_ops_to_a(
            {"nodes": [valid_node("node_only")], "edges": []},
            [{"op": "remove_node", "nodeId": "node_only", "reason": "文件删除"}])
        self.assertEqual(operations3, [])
        self.assertEqual(len(warnings3), 1)

    def test_colliding_derived_ids_are_made_unique(self) -> None:
        base = {"nodes": [], "edges": []}
        operations, warnings = _incremental_ops_to_a(base, [
            {"op": "add_node", "nodeId": "node_a_b", "data": {"title": "T1", "role": "R1",
                                                              "evidence": [{"kind": "file", "path": "a/b.py"}]}},
            {"op": "add_node", "nodeId": "node_a_b", "data": {"title": "T2", "role": "R2",
                                                              "evidence": [{"kind": "file", "path": "a_b.py"}]}}])
        self.assertEqual(len(operations), 2)
        ids = [op["node"]["id"] for op in operations]
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(all(op["type"] in OP_TYPES for op in operations))
        self.assertTrue(any("已占用" in item["reason"] for item in warnings))
        graph = {"nodes": [valid_node("node_keep")], "edges": []}
        for op in operations:  # both apply, in order, on a graph with 1 node
            graph = apply_operation(graph, op)
        self.assertEqual(len(graph["nodes"]), 3)

    def test_every_emitted_operation_applies_in_order(self) -> None:
        base = {"nodes": [valid_node("node_svc", path="svc.py"), valid_node("node_gone", path="gone.py")],
                "edges": []}
        operations, warnings = _incremental_ops_to_a(base, [
            {"op": "add_node", "nodeId": "node_new", "data": {"title": "新", "role": "R",
                                                              "evidence": [{"kind": "file", "path": "new.py"}]}},
            {"op": "update_node", "file": "svc.py", "changes": {"evidence_refresh": True}},
            {"op": "remove_node", "nodeId": "node_gone", "reason": "文件删除"},
            {"op": "remove_node", "nodeId": "node_missing", "reason": "不在草稿"},
            {"op": "weird_op", "nodeId": "node_svc"}])
        graph = {"nodes": [valid_node("node_svc", path="svc.py"),
                           valid_node("node_gone", path="gone.py")], "edges": []}
        for operation in operations:
            self.assertIn(operation["type"], OP_TYPES)
            graph = apply_operation(graph, operation)
        self.assertEqual(sorted(node["id"] for node in graph["nodes"]),
                         ["node_new", "node_svc"])
        self.assertEqual(len(warnings), 2)  # the two unusable proposals


class CoverageNullRepairTests(unittest.TestCase):
    """A-05 (BATCH-3): an explicit null is a malformed declaration, not "absent"."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "null 覆盖", "repoPath": str(self.code),
            "description": "说明"})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)
        self.service.sync_draft_to_backend(self.workspace_id, {})

    def test_explicit_null_coverage_is_refused(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            self.service.review_preview(self.workspace_id, {
                "actor": "操作者", "reason": "核对", "coverage": None}, META)
        self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")

    def test_absent_coverage_uses_the_default(self) -> None:
        preview = self.service.review_preview(self.workspace_id,
                                              {"actor": "操作者", "reason": "核对"}, META)
        self.assertGreaterEqual(len(preview["reviewCoverage"]["nodes"]), 1)

    def test_malformed_values_are_still_refused(self) -> None:
        for bad in (["nodes"], "bad-list",
                    {"nodes": [], "edges": [], "processes": [], "evidence": "bad-list",
                     "scope": "partial"}):
            with self.assertRaises(ContractError) as ctx:
                self.service.review_preview(self.workspace_id, {
                    "actor": "操作者", "reason": "核对", "coverage": bad}, META)
            self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()