"""Workbench service tests (A role): drafts, corrections, review, recheck."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.adapters import AdapterRegistry
from archloop.contract import ContractError, semantic_revision
from archloop.service import WorkbenchService


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode("utf-8").strip()


def tiny_repo(root: Path) -> Path:
    repo = root / "sample"
    repo.mkdir(parents=True)
    run_git(repo, "init")
    (repo / "entry.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    run_git(repo, "add", ".")
    run_git(repo, "config", "user.email", "t@example.com")
    run_git(repo, "config", "user.name", "t")
    run_git(repo, "commit", "-m", "first")
    return repo


def service_with_git(tmp: Path) -> WorkbenchService:
    from app import git as app_git
    service = WorkbenchService(tmp / "archloop-data", AdapterRegistry())
    service.bind_git(app_git)
    return service


def dev_sample_graph() -> dict:
    return {
        "nodes": [
            {"id": "n_a", "title": "样例A", "summary": "样例职责", "status": "candidate",
             "provenance": "rule_based", "entryPoints": [], "interfaces": [],
             "evidence": [{"path": "entry.py", "reason": "样例", "kind": "code_fact"}], "process": []},
            {"id": "n_b", "title": "样例B", "summary": "样例职责B", "status": "candidate",
             "provenance": "rule_based", "entryPoints": [], "interfaces": [], "evidence": [], "process": []},
        ],
        "edges": [],
    }


class WorkspaceLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = service_with_git(Path(self.tmp.name))
        self.repo = tiny_repo(Path(self.tmp.name))

    def create_existing(self) -> dict:
        return self.service.create_workspace({
            "context": "existing_project", "title": "示例",
            "repoPath": str(self.repo), "description": "说明",
        })

    def test_existing_workspace_binds_stable_identity(self) -> None:
        envelope = self.create_existing()
        identity = envelope["identity"]
        self.assertTrue(identity["codeRepoId"].startswith("repo-"))
        self.assertEqual(identity["codeRevision"], run_git(self.repo, "rev-parse", "HEAD"))
        self.assertIsNone(identity["verifiedCodeRevision"])
        self.assertEqual(envelope["backend"]["origin"], "dev_sample")

    def test_planning_workspace_has_null_code_identity(self) -> None:
        envelope = self.service.create_workspace({
            "context": "planning", "title": "新设计",
            "goals": "做一个查询服务", "constraints": "Python",
        })
        self.assertIsNone(envelope["identity"]["codeRepoId"])
        self.assertIsNone(envelope["identity"]["codeRevision"])

    def test_generation_without_config_is_honest(self) -> None:
        envelope = self.create_existing()
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("PROJECTMIND_AI_MODEL", None)
            result = self.service.generate(envelope["workspace"]["workspaceId"], {})
        self.assertEqual(result["status"], "NOT_RUN_AWAITING_CONFIGURATION")
        self.assertNotIn("graph", result)

    def test_dev_sample_generation_is_labeled(self) -> None:
        envelope = self.create_existing()
        result = self.service.generate(envelope["workspace"]["workspaceId"],
                                       {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        self.assertEqual(result["status"], "dev_sample")
        self.assertEqual(result["origin"], "dev_sample")
        self.assertIn("演示", result["labeled"])

    def test_dev_sample_without_graph_is_refused(self) -> None:
        envelope = self.create_existing()
        with self.assertRaises(ContractError) as caught:
            self.service.generate(envelope["workspace"]["workspaceId"], {"mode": "dev_sample"})
        self.assertEqual(caught.exception.code, "DEV_SAMPLE_DISABLED")


class DraftEditingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = service_with_git(Path(self.tmp.name))
        envelope = self.service.create_workspace({
            "context": "planning", "title": "设计", "goals": "目标",
        })
        self.workspace_id = envelope["workspace"]["workspaceId"]
        result = self.service.generate(self.workspace_id,
                                       {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        self.service.apply_candidate(self.workspace_id, {"graph": result["graph"], "origin": result["origin"]})
        self.envelope = self.service.load_draft(self.workspace_id)

    @property
    def draft_revision(self) -> str:
        return self.envelope["identity"]["draftRevision"]

    def test_wrong_expected_revision_conflicts(self) -> None:
        with self.assertRaises(ContractError) as caught:
            self.service.apply_ops(self.workspace_id, {
                "expectedDraftRevision": "stale",
                "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "x"}}],
            })
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")

    def test_direct_edit_updates_draft_and_identity(self) -> None:
        result = self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "新职责"}}],
        })
        self.assertEqual(result["draft"]["graph"]["nodes"][0]["summary"], "新职责")
        self.assertNotEqual(result["identity"]["draftRevision"], self.draft_revision)

    def test_remove_referenced_node_requires_force(self) -> None:
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "add_edge",
                            "edge": {"from": "n_a", "to": "n_b", "type": "static_reference", "label": "引用"}}],
        })
        self.envelope = self.service.load_draft(self.workspace_id)
        with self.assertRaises(ContractError) as caught:
            self.service.apply_ops(self.workspace_id, {
                "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
                "operations": [{"type": "remove_node", "nodeId": "n_a"}],
            })
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_process_reorder_keeps_step_ids(self) -> None:
        process = [
            {"stepId": "s1", "title": "第一步", "detail": "", "inputs": [], "outputs": [], "branches": [], "next": ["s2"]},
            {"stepId": "s2", "title": "第二步", "detail": "", "inputs": [], "outputs": [], "branches": [], "next": []},
        ]
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "update_process", "nodeId": "n_a", "process": process}],
        })
        self.envelope = self.service.load_draft(self.workspace_id)
        result = self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
            "operations": [{"type": "update_process", "nodeId": "n_a", "process": list(reversed(process))}],
        })
        steps = result["draft"]["graph"]["nodes"][0]["process"]
        self.assertEqual([step["stepId"] for step in steps], ["s2", "s1"])

    def test_diff_reports_semantic_changes(self) -> None:
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "变化了"}}],
        })
        diff = self.service.draft_diff(self.workspace_id)
        updated = [node for node in diff["nodes"] if node["change"] == "updated"]
        self.assertEqual(len(updated), 1)
        self.assertIn("summary", updated[0]["fields"])


class CorrectionReviewRecheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = service_with_git(Path(self.tmp.name))
        self.repo = tiny_repo(Path(self.tmp.name))
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "示例",
            "repoPath": str(self.repo), "description": "说明",
        })
        self.workspace_id = envelope["workspace"]["workspaceId"]
        result = self.service.generate(self.workspace_id,
                                       {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        self.service.apply_candidate(self.workspace_id, {"graph": result["graph"], "origin": result["origin"]})
        self.envelope = self.service.load_draft(self.workspace_id)

    def test_correction_preview_dev_sample_is_labeled(self) -> None:
        preview = self.service.correction_preview(self.workspace_id, {
            "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
            "instruction": "职责不对",
            "selectedNodeIds": ["n_a"],
            "mode": "dev_sample",
        })
        self.assertEqual(preview["origin"], "dev_sample")
        self.assertTrue(preview["operations"])
        self.assertIn("演示", preview["note"])

    def test_correction_preview_production_without_c_is_unavailable(self) -> None:
        with self.assertRaises(ContractError) as caught:
            self.service.correction_preview(self.workspace_id, {
                "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
                "instruction": "职责不对",
                "selectedNodeIds": ["n_a"],
                "mode": "production",
            })
        self.assertEqual(caught.exception.code, "BACKEND_UNAVAILABLE")

    def test_correction_preview_stale_revision_conflicts(self) -> None:
        with self.assertRaises(ContractError) as caught:
            self.service.correction_preview(self.workspace_id, {
                "expectedDraftRevision": "old",
                "instruction": "职责不对",
                "selectedNodeIds": ["n_a"],
                "mode": "dev_sample",
            })
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")

    def test_review_records_decision_but_produces_no_version(self) -> None:
        map_revision = self.envelope["draft"]["graph"]["mapRevision"]
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(self.workspace_id, {
                "expectedMapRevision": map_revision, "decision": "accept",
                "actor": "tester", "reason": "验收测试", "origin": "dev_sample",
            })
        self.assertEqual(caught.exception.code, "DEV_SAMPLE_DISABLED")

    def test_review_on_real_origin_draft_is_refused_until_b_lands(self) -> None:
        # Simulate the AI-configured path: apply_candidate stores the origin it
        # was given; a draft with a non-sample origin must reach the B seam and
        # be refused there with BACKEND_UNAVAILABLE, recording the decision.
        self.envelope["draft"]["origin"] = "ai_candidate"
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"]["origin"] = "ai_candidate"
        self.service.store.save_workspace_record(record)
        map_revision = self.envelope["draft"]["graph"]["mapRevision"]
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(self.workspace_id, {
                "expectedMapRevision": map_revision, "decision": "accept",
                "actor": "tester", "reason": "验收测试",
            })
        self.assertEqual(caught.exception.code, "BACKEND_UNAVAILABLE")
        history = self.service.store.load_history(self.workspace_id)
        decisions = [entry for entry in history if entry["type"] == "review_decision"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["delivery"], "recorded_locally_pending_b_backend")
        # no version identity may appear anywhere in the workspace record
        envelope = self.service.load_draft(self.workspace_id)
        self.assertIsNone(envelope["identity"]["mapSourceRevision"])
        self.assertIsNone(envelope["identity"]["verifiedCodeRevision"])

    def test_review_rejects_dev_sample_origin(self) -> None:
        self.envelope["draft"]["origin"] = "dev_sample"
        self.service.store.save_workspace_record(self.service.store.load_workspace(self.workspace_id))
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(self.workspace_id, {
                "expectedMapRevision": self.envelope["draft"]["graph"]["mapRevision"],
                "decision": "accept", "actor": "tester", "origin": "dev_sample",
            })
        self.assertEqual(caught.exception.code, "DEV_SAMPLE_DISABLED")

    def test_recheck_detects_new_commit_and_stale_nodes(self) -> None:
        old_head = run_git(self.repo, "rev-parse", "HEAD")
        (self.repo / "entry.py").write_text("def run():\n    return 2\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "change entry")
        result = self.service.recheck(self.workspace_id)
        self.assertTrue(result["changed"])
        self.assertEqual(result["oldCodeRevision"], old_head)
        stale_ids = [node["nodeId"] for node in result["staleNodes"]]
        self.assertIn("n_a", stale_ids)

    def test_fix_task_dev_sample_is_labeled(self) -> None:
        task = self.service.create_fix_task(self.workspace_id, {
            "deviation": "步骤顺序与观察不符", "acceptance": "调整后测试通过",
            "expectedProcessRef": "n_a", "mode": "dev_sample",
        })
        self.assertEqual(task["origin"], "dev_sample")
        self.assertTrue(task["labeled"].startswith("演示"))


if __name__ == "__main__":
    unittest.main()
