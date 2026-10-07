"""Red/green evidence for the FINAL-1 audit findings (cross-entry residues)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.adapters import AdapterRegistry
from archloop.contract import ContractError
from archloop.service import WorkbenchService
from tests.test_archloop_a_service import dev_sample_graph, run_git, service_with_git, tiny_repo


class FinalAuditRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = service_with_git(Path(self.tmp.name))
        self.repo = tiny_repo(Path(self.tmp.name))

    def create_existing(self) -> str:
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "示例",
            "repoPath": str(self.repo), "description": "说明",
        })
        return envelope["workspace"]["workspaceId"]

    def apply_sample(self, workspace_id: str) -> dict:
        generated = self.service.generate(workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        return self.service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})

    def test_sample_correction_poisons_real_origin_draft(self) -> None:
        # FINAL-1 unverified note: a real (ai_candidate) draft becomes
        # dev_sample after a sample correction and can never be reviewed.
        workspace_id = self.create_existing()
        self.apply_sample(workspace_id)
        record = self.service.store.load_workspace(workspace_id)
        record["draft"]["origin"] = "ai_candidate"
        self.service.store.save_workspace_record(record)
        envelope = self.service.load_draft(workspace_id)
        preview = self.service.correction_preview(workspace_id, {
            "expectedDraftRevision": envelope["identity"]["draftRevision"],
            "instruction": "职责不对", "selectedNodeIds": ["n_a"], "mode": "dev_sample",
        })
        result = self.service.apply_correction(workspace_id, {
            "proposalId": preview["proposalId"],
            "expectedDraftRevision": preview["baseDraftRevision"],
        })
        self.assertEqual(result["draft"]["origin"], "dev_sample")
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(workspace_id, {
                "expectedMapRevision": result["draft"]["graph"]["mapRevision"],
                "decision": "accept", "actor": "tester",
            })
        self.assertEqual(caught.exception.code, "DEV_SAMPLE_DISABLED")

    def test_direct_edit_evidence_checked_against_bound_revision(self) -> None:
        # FINAL-1 finding 3: the guard must use the bound revision, not HEAD.
        workspace_id = self.create_existing()
        self.apply_sample(workspace_id)
        (self.repo / "only-at-head.py").write_text("x = 1\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "add file at head only")
        envelope = self.service.load_draft(workspace_id)
        result = self.service.apply_ops(workspace_id, {
            "expectedDraftRevision": envelope["identity"]["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {
                "evidence": [{"path": "only-at-head.py", "reason": "声称的代码事实", "kind": "code_fact"}]}}],
        })
        kinds = {item["path"]: item["kind"] for item in result["draft"]["graph"]["nodes"][0]["evidence"]}
        self.assertEqual(kinds["only-at-head.py"], "unknown")

    def test_legacy_import_cas_validation_and_guard(self) -> None:
        # FINAL-1 finding 1: legacy import is CAS-guarded, structurally
        # validated and evidence-guarded.
        workspace_id = self.create_existing()
        self.apply_sample(workspace_id)
        envelope = self.service.load_draft(workspace_id)
        legacy = {"note": "旧演示图", "nodes": [
            {"id": "legacy_a", "title": "旧节点", "summary": "旧职责", "entryPoint": "run()",
             "evidence": [{"path": "entry.py", "reason": "真实文件"}]},
            {"id": "legacy_b", "title": "旧节点B", "summary": "旧职责B", "entryPoint": "",
             "evidence": [{"path": "ghost-legacy.py", "reason": "旧图声称", "kind": "code_fact"}]},
        ], "edges": [{"from": "legacy_a", "to": "legacy_b", "label": "协作"}]}
        with self.assertRaises(ContractError) as caught:
            self.service.import_legacy_map(workspace_id, {"legacyMap": legacy})
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")
        result = self.service.import_legacy_map(workspace_id, {
            "legacyMap": legacy, "expectedDraftRevision": envelope["identity"]["draftRevision"]})
        nodes = {node["id"]: node for node in result["draft"]["graph"]["nodes"]}
        self.assertIn("legacy_a", nodes)
        kinds = {item["path"]: item["kind"] for item in nodes["legacy_b"]["evidence"]}
        self.assertEqual(kinds["ghost-legacy.py"], "unknown")
        bad = {"note": "坏图", "nodes": [
            {"id": "id-with-中文", "title": "x", "summary": "y", "entryPoint": "", "evidence": []}],
            "edges": []}
        fresh = self.service.load_draft(workspace_id)
        with self.assertRaises(ContractError):
            self.service.import_legacy_map(workspace_id, {
                "legacyMap": bad, "expectedDraftRevision": fresh["identity"]["draftRevision"]})

    def test_publish_write_back_is_atomically_rechecked(self) -> None:
        # FINAL-1 finding 4: a publish result must not overwrite a draft that
        # changed while the backend transaction ran.
        workspace_id = self.create_existing()
        self.apply_sample(workspace_id)
        record = self.service.store.load_workspace(workspace_id)
        record["draft"]["origin"] = "ai_candidate"
        self.service.store.save_workspace_record(record)

        def backend_call(action, payload):
            if action == "publish_reviewed_graph":
                envelope = self.service.load_draft(workspace_id)
                self.service.apply_ops(workspace_id, {
                    "expectedDraftRevision": envelope["identity"]["draftRevision"],
                    "operations": [{"type": "update_node", "nodeId": "n_a",
                                    "fields": {"summary": "发布期间并发编辑"}}],
                })
                return {"status": "published", "mapSourceRevision": "b" * 40}
            raise AssertionError(action)

        self.service.adapter.register("persistence", {"kind": "extension:test-b", "call": backend_call})
        envelope = self.service.load_draft(workspace_id)
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(workspace_id, {
                "expectedMapRevision": envelope["draft"]["graph"]["mapRevision"],
                "decision": "accept", "actor": "tester", "reason": "并发复核",
            })
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")
        record = self.service.store.load_workspace(workspace_id)
        self.assertIsNone(record["identity"]["mapSourceRevision"])

    def test_fix_task_delegates_to_registered_backend(self) -> None:
        # FINAL-1 finding 9: a registered handoff backend receives the call.
        workspace_id = self.create_existing()
        self.apply_sample(workspace_id)
        seen = {}

        def backend_call(action, payload):
            seen["action"] = action
            seen["payload"] = payload
            return {"taskType": "implementation_fix", "status": "queued",
                    "deviationId": "dev_real", "origin": "extension:handoff"}

        self.service.adapter.register("handoff", {"kind": "extension:handoff", "call": backend_call})
        task = self.service.create_fix_task(workspace_id, {
            "deviation": "步骤顺序", "mode": "production"})
        self.assertEqual(seen["action"], "create_fix_task")
        self.assertEqual(task["deviationId"], "dev_real")

    def test_recheck_flags_renamed_old_paths(self) -> None:
        # FINAL-1 finding 6: renamed evidence keeps the stale flag.
        workspace_id = self.create_existing()
        self.apply_sample(workspace_id)
        (self.repo / "entry.py").write_text("def run():\n    return 3\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "change")
        run_git(self.repo, "mv", "entry.py", "renamed.py")
        run_git(self.repo, "commit", "-m", "rename entry")
        result = self.service.recheck(workspace_id)
        stale_paths = {path for node in result["staleNodes"] for path in node["paths"]}
        self.assertIn("entry.py", stale_paths)

    def test_backend_label_splits_storage_and_version_service(self) -> None:
        # FINAL-1 finding 8: a bare registration must not claim integration.
        workspace_id = self.create_existing()
        label = self.service.load_draft(workspace_id)["backend"]
        self.assertEqual(label["origin"], "dev_sample")
        self.service.adapter.register("persistence", {"kind": "extension:half"})
        label = self.service.load_draft(workspace_id)["backend"]
        self.assertEqual(label["origin"], "dev_sample")
        self.assertFalse(label["versionService"])
        self.service.adapter.register("persistence", {"kind": "extension:full", "call": lambda a, b: {}})
        label = self.service.load_draft(workspace_id)["backend"]
        self.assertEqual(label["origin"], "extension:persistence")
        self.assertTrue(label["versionService"])


if __name__ == "__main__":
    unittest.main()
