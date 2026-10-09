"""Regression tests for the BATCH-1 review findings (each one reproduces the
reviewer's scenario, then asserts the repaired behaviour).

Findings covered: A-01 (step id / next / branch round-trip), A-02 (duplicated
process/step operations), A-03 (field deletions), A-04 (metadata chunking),
A-05 (design coverage must not claim the metadata carrier), SYNC-01 (stale sync
must not overwrite another writer), B-01 (confirmation token stays server-side),
B-02 (publish requires the live review session), C-01 (published identity),
LEGACY-01 (nested import target refused).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.backend_b import (META_EVIDENCE_ID, a_to_b_graph, b_to_a_graph,
                                coverage_for, diff_to_operations)
from archloop.contract import ContractError
from tests.test_archloop_a_backend_b import (META, RealBackendFlowTests, vector_graph,
                                             workspace_setup)


def project(graph: dict, code_revision: str = "a" * 40) -> dict:
    return a_to_b_graph(graph, code_repo_id="repo-x", code_revision=code_revision)["graph"]


class RoundTripRepairTests(unittest.TestCase):
    def test_forward_step_references_survive(self) -> None:
        # reviewer A-01: a forward reference must not be dropped when its own
        # step id is only known later in the same process
        graph = {
            "nodes": [{"id": "n_a", "title": "A", "summary": "职责", "status": "candidate",
                       "provenance": "human_input", "entryPoints": [], "interfaces": [],
                       "evidence": [], "process": [
                           {"stepId": "s1", "title": "一步", "detail": "", "inputs": [], "outputs": [],
                            "branches": [], "next": ["s3"]},
                           {"stepId": "s2", "title": "二步", "detail": "", "inputs": [], "outputs": [],
                            "branches": [], "next": []},
                           {"stepId": "s3", "title": "三步", "detail": "", "inputs": [], "outputs": [],
                            "branches": [], "next": ["s2"]}], "assumptions": []}],
            "edges": [],
        }
        back = b_to_a_graph(project(graph), {"origin": "manual"})
        steps = {step["stepId"]: step for step in back["nodes"][0]["process"]}
        self.assertEqual(steps["s1"]["next"], ["s3"])
        self.assertEqual(steps["s3"]["next"], ["s2"])

    def test_duplicate_step_ids_across_nodes_round_trip(self) -> None:
        graph = vector_graph()
        graph["nodes"][1]["process"] = [
            {"stepId": "s1", "title": "第二节点的一步", "detail": "", "inputs": [], "outputs": [],
             "branches": [], "next": []}]
        projected = project(graph)
        ids = [step["id"] for process in projected["processes"] for step in process["steps"]]
        self.assertEqual(len(ids), len(set(ids)))
        back = b_to_a_graph(projected, {"origin": "ai_generated"})
        # the second node's next must reference its own (renamed) step again
        second_process = back["nodes"][1]["process"]
        self.assertEqual([step["stepId"] for step in second_process], ["s1"])
        # and the first node's next still points at its own s2
        first_next = {step["stepId"]: step["next"] for step in back["nodes"][0]["process"]}
        self.assertEqual(first_next["s1"], ["s2"])

    def test_branch_targets_are_not_dropped(self) -> None:
        graph = vector_graph()
        # a branch that targets a later step must still be visible after the
        # round trip (data, not decoration)
        graph["nodes"][0]["process"][0]["branches"] = ["异常→跳到 s2"]
        projected = project(graph)
        back = b_to_a_graph(projected, {"origin": "ai_generated"})
        steps = {step["stepId"]: step for step in back["nodes"][0]["process"]}
        self.assertEqual(steps["s1"]["branches"], ["异常→跳到 s2"])


class OperationDiffRepairTests(unittest.TestCase):
    def test_new_process_is_added_once(self) -> None:
        # reviewer A-02: process.add already carries steps; extra step.add made
        # B reject the whole batch
        graph = vector_graph()
        first = project(graph)
        graph2 = vector_graph()
        graph2["nodes"][1]["process"] = [
            {"stepId": "t1", "title": "新步骤", "detail": "", "inputs": [], "outputs": [],
             "branches": [], "next": []}]
        second = project(graph2)
        operations = diff_to_operations(first, second)
        process_adds = [op for op in operations if op["op"] == "process.add"]
        step_adds = [op for op in operations if op["op"] == "step.add"]
        self.assertEqual(len(process_adds), 1)
        self.assertEqual(step_adds, [])

    def test_field_deletion_is_expressed_as_replace(self) -> None:
        # reviewer A-03: B's update cannot delete a key
        graph = vector_graph()
        graph["nodes"][0]["evidence"] = [
            {"path": "entry.py", "reason": "入口", "kind": "code_fact",
             "codeRevision": "b" * 40, "lineStart": 1, "lineEnd": 2}]
        first = project(graph)
        entry_evidence = next(item for item in first["evidence"] if item.get("path") == "entry.py")
        self.assertIn("unknownReason", entry_evidence)
        graph2 = vector_graph()
        graph2["nodes"][0]["evidence"] = [
            {"path": "entry.py", "reason": "入口", "kind": "code_fact"}]
        second = project(graph2)
        entry_evidence2 = next(item for item in second["evidence"] if item.get("path") == "entry.py")
        self.assertNotIn("unknownReason", entry_evidence2)
        operations = diff_to_operations(first, second)
        kinds = [op["op"] for op in operations]
        self.assertIn("evidence.remove", kinds)
        self.assertIn("evidence.add", kinds)

    def test_large_metadata_round_trips(self) -> None:
        # reviewer A-04: chunk ids must sort in payload order
        graph = vector_graph()
        graph["nodes"][0]["assumptions"] = [f"假设 {index} " + "x" * 200 for index in range(400)]
        projected = project(graph)
        carriers = [item["id"] for item in projected["evidence"]
                    if str(item.get("unknownReason", "")).startswith("A_projection_metadata")]
        self.assertGreater(len(carriers), 1)
        back = b_to_a_graph(projected, {"origin": "ai_generated"})
        self.assertEqual(back["nodes"][0]["assumptions"], graph["nodes"][0]["assumptions"])
        self.assertEqual(back["nodes"][0]["provenance"], "ai_candidate")

    def test_corrupted_metadata_is_refused_not_silently_dropped(self) -> None:
        graph = vector_graph()
        projected = project(graph)
        for item in projected["evidence"]:
            if item["id"].startswith(META_EVIDENCE_ID):
                item["content"] = "{ this is not json"
        with self.assertRaises(ContractError) as ctx:
            b_to_a_graph(projected, {"origin": "ai_generated"})
        self.assertEqual(ctx.exception.code, "EVIDENCE_MISMATCH")

    def test_design_coverage_never_claims_the_carrier(self) -> None:
        # reviewer A-05
        graph = vector_graph()
        projected = project(graph)
        coverage = coverage_for({"identity": {"codeRevision": None}}, projected, verify_code=False)
        self.assertEqual(coverage["scope"], "partial")
        self.assertNotIn(META_EVIDENCE_ID, coverage["evidence"])
        self.assertEqual(sorted(coverage["nodes"]), sorted(n["id"] for n in projected["nodes"]))


class SyncGuardRepairTests(unittest.TestCase):
    """SYNC-01: a stale A binding must not overwrite another writer's B draft."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "同步守卫", "repoPath": str(self.code)})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)

    def test_external_b_edit_is_not_overwritten(self) -> None:
        self.service.sync_draft_to_backend(self.workspace_id, {})
        record = self.service.store.load_workspace(self.workspace_id)
        binding = record["backendB"]
        # another writer edits the shared B draft directly
        draft = self.backend.service.get_draft(binding["draftId"])
        self.backend.service.apply_draft_operations(
            binding["draftId"],
            operations=[{"op": "node.update", "id": "n_store",
                         "changes": {"responsibility": "外部写入者的职责"}}],
            expected_draft_revision=draft["draftRevision"],
            base_map_revision=draft["baseMapRevision"], proposal_id=draft["proposalId"])
        # the A side still holds the old binding: syncing must refuse
        with self.assertRaises(ContractError) as ctx:
            self.service.sync_draft_to_backend(self.workspace_id, {})
        self.assertEqual(ctx.exception.code, "REVISION_CONFLICT")
        # ... and the external edit is still there
        current = self.backend.service.get_draft(binding["draftId"])
        changed = next(node for node in current["graph"]["nodes"] if node["id"] == "n_store")
        self.assertEqual(changed["responsibility"], "外部写入者的职责")

    def test_explicit_rebase_is_possible_after_reading(self) -> None:
        self.service.sync_draft_to_backend(self.workspace_id, {})
        record = self.service.store.load_workspace(self.workspace_id)
        binding = dict(record["backendB"])
        draft = self.backend.service.get_draft(binding["draftId"])
        self.backend.service.apply_draft_operations(
            binding["draftId"],
            operations=[{"op": "node.update", "id": "n_store",
                         "changes": {"responsibility": "外部写入者的职责"}}],
            expected_draft_revision=draft["draftRevision"],
            base_map_revision=draft["baseMapRevision"], proposal_id=draft["proposalId"])
        fresh = self.backend.service.get_draft(binding["draftId"])
        binding["bDraftRevision"] = fresh["draftRevision"]
        record["backendB"] = binding
        self.service.store.save_workspace_record(record)
        # after adopting the observed revision, syncing is allowed again
        result = self.service.sync_draft_to_backend(self.workspace_id, {})
        self.assertTrue(result["bDraftRevision"])


class HumanReviewBoundaryRepairTests(unittest.TestCase):
    """B-01 (no token to the client) and B-02 (publish needs a live session)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.code, self.arch, self.backend, self.service = workspace_setup(root)
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "边界", "repoPath": str(self.code)})
        self.workspace_id = envelope["workspace"]["workspaceId"]
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"] = self.service._new_draft(record, vector_graph(), origin="ai_candidate")
        self.service.store.save_workspace_record(record)

    def _preview(self) -> dict:
        self.service.sync_draft_to_backend(self.workspace_id, {})
        return self.service.review_preview(self.workspace_id,
                                           {"actor": "边界操作者", "reason": "核对"}, META)

    def test_confirmation_token_never_reaches_the_client(self) -> None:
        preview = self._preview()
        self.assertNotIn("confirmationToken", preview)
        self.assertTrue(preview["previewDigest"])
        # confirming with only the digest (plus decision) works
        confirm = self.service.review_confirm(self.workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        self.assertTrue(confirm["publicationAuthorized"])

    def test_publish_requires_a_live_review_session(self) -> None:
        preview = self._preview()
        self.service.review_confirm(self.workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        # the session is invalidated (expired/dropped) after the confirmation:
        # publication must refuse instead of publishing on a dead session
        record = self.service.store.load_workspace(self.workspace_id)
        record["backendB"]["sessionSecret"] = {}
        self.service.store.save_workspace_record(record)
        with self.assertRaises(ContractError) as ctx:
            self.service.publish_version(self.workspace_id, {}, META)
        self.assertEqual(ctx.exception.code, "REQUEST_FORBIDDEN")

    def test_published_identity_is_visible_then_expires_with_the_draft(self) -> None:
        # C-01: after publishing, the identity must show the real source SHA
        preview = self._preview()
        self.service.review_confirm(self.workspace_id, {
            "previewDigest": preview["previewDigest"], "decision": "accept"}, META)
        published = self.service.publish_version(self.workspace_id, {}, META)
        identity = published["envelope"]["identity"]
        self.assertEqual(identity["mapSourceRevision"],
                         published["provenance"]["mapSourceRevision"])
        self.assertEqual(identity["mapRevision"], published["version"]["mapRevision"])
        self.assertEqual(identity["verifiedCodeRevision"],
                         published["version"]["verifiedCodeRevision"])
        # a further edit makes the published facts stop applying to the draft
        record = self.service.store.load_workspace(self.workspace_id)
        draft = record["draft"]
        edited = self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": draft["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_store",
                            "fields": {"summary": "发布后又改了"}}]})
        self.assertIsNone(edited["identity"]["mapSourceRevision"])
        self.assertIsNone(edited["identity"]["verifiedCodeRevision"])
        self.assertEqual(edited["lastPublish"]["mapRevision"],
                         published["version"]["mapRevision"])


class LegacyImportRepairTests(unittest.TestCase):
    def test_nested_target_is_refused(self) -> None:
        # reviewer LEGACY-01: a target inside the source root would write into
        # the tree that must stay read-only
        from archloop.legacy_import import plan_import
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_root = root / "old-data"
            (old_root / "workspaces").mkdir(parents=True)
            with self.assertRaises(ContractError) as ctx:
                plan_import(old_root, old_root / "nested-target")
            self.assertEqual(ctx.exception.code, "VALIDATION_FAILED")
            with self.assertRaises(ContractError) as ctx2:
                plan_import(old_root / "inner" / "deeper", old_root)
            self.assertEqual(ctx2.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()