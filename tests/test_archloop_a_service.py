"""Workbench service tests (A role): drafts, corrections, review, recheck.

Includes the red/green evidence for the MID-1 audit findings: CAS races,
candidate expiry, sample-origin laundering, evidence honesty, process
reference cascades and preview expiry.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
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


def planning_sample_graph() -> dict:
    """Requirement-based sample for planning workspaces (no code facts)."""
    return {
        "nodes": [
            {"id": "n_a", "title": "样例A", "summary": "样例职责", "status": "candidate",
             "provenance": "rule_based", "entryPoints": [], "interfaces": [],
             "evidence": [{"path": "需求.md", "reason": "样例需求依据", "kind": "requirement"}], "process": []},
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

    def apply_sample(self, workspace_id: str) -> dict:
        generated = self.service.generate(workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        return self.service.apply_candidate(workspace_id, {"candidateId": generated["candidateId"]})

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

    def test_planning_rejects_code_fact_evidence(self) -> None:
        # MID-1 finding 5 (green: rejected outright)
        envelope = self.service.create_workspace({"context": "planning", "title": "规划", "goals": "目标"})
        bad = dev_sample_graph()
        bad["nodes"][0]["evidence"] = [{"path": "somewhere.py", "reason": "伪造代码事实", "kind": "code_fact"}]
        with self.assertRaises(ContractError) as caught:
            self.service.generate(envelope["workspace"]["workspaceId"],
                                  {"mode": "dev_sample", "sampleGraph": bad})
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_unverifiable_code_fact_downgrades_to_unknown(self) -> None:
        # MID-1 finding 5 (paths not at the bound revision lose code_fact)
        envelope = self.create_existing()
        graph = dev_sample_graph()
        graph["nodes"][0]["evidence"].append({"path": "ghost.py", "reason": "模型声称", "kind": "code_fact"})
        result = self.service.generate(envelope["workspace"]["workspaceId"],
                                       {"mode": "dev_sample", "sampleGraph": graph})
        node = result["graph"]["nodes"][0]
        kinds = {item["path"]: item["kind"] for item in node["evidence"]}
        self.assertEqual(kinds["entry.py"], "code_fact")      # real file stays a fact
        self.assertEqual(kinds["ghost.py"], "unknown")        # invented path downgraded
        downgraded = result["graph"].get("evidenceDowngrades")
        self.assertTrue(downgraded and downgraded[0]["path"] == "ghost.py")


class CandidateApplicationTests(unittest.TestCase):
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

    def test_apply_requires_stored_candidate_id(self) -> None:
        # no candidate stored yet
        with self.assertRaises(ContractError) as empty:
            self.service.apply_candidate(self.workspace_id, {"candidateId": "cand_missing"})
        self.assertEqual(empty.exception.code, "VALIDATION_FAILED")
        self.service.generate(self.workspace_id, {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        with self.assertRaises(ContractError) as caught:
            self.service.apply_candidate(self.workspace_id, {"candidateId": "cand_missing"})
        self.assertEqual(caught.exception.code, "STALE_CONTEXT")

    def test_apply_cas_on_existing_draft(self) -> None:
        # MID-1 finding 2: a stale candidate application must not overwrite
        generated = self.service.generate(self.workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        self.service.apply_candidate(self.workspace_id, {"candidateId": generated["candidateId"]})
        envelope = self.service.load_draft(self.workspace_id)
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": envelope["identity"]["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "手工编辑"}}],
        })
        fresh = self.service.generate(self.workspace_id,
                                      {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        with self.assertRaises(ContractError) as caught:
            self.service.apply_candidate(self.workspace_id, {"candidateId": fresh["candidateId"]})
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")
        result = self.service.apply_candidate(self.workspace_id, {
            "candidateId": fresh["candidateId"],
            "expectedDraftRevision": self.service.load_draft(self.workspace_id)["identity"]["draftRevision"],
        })
        self.assertEqual(result["draft"]["graph"]["nodes"][0]["summary"], "样例职责")

    def test_candidate_source_revision_must_match_binding(self) -> None:
        # MID-1 finding 4: the candidate's generation basis is frozen; a
        # workspace bound to another revision gets STALE_CONTEXT.
        generated = self.service.generate(self.workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        self.assertEqual(generated["sourceCodeRevision"], run_git(self.repo, "rev-parse", "HEAD"))
        record = self.service.store.load_workspace(self.workspace_id)
        record["identity"]["codeRevision"] = "a" * 40
        self.service.store.save_workspace_record(record)
        with self.assertRaises(ContractError) as caught:
            self.service.apply_candidate(self.workspace_id, {"candidateId": generated["candidateId"]})
        self.assertEqual(caught.exception.code, "STALE_CONTEXT")
        self.assertIn("candidateBasis", caught.exception.details)

    def test_generation_meta_persists_unknowns(self) -> None:
        # MID-1 finding 8: unknowns/openQuestions survive into the draft
        generated = self.service.generate(self.workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        result = self.service.apply_candidate(self.workspace_id, {"candidateId": generated["candidateId"]})
        meta = result["draft"]["generationMeta"]
        self.assertEqual(meta["origin"], "dev_sample")
        self.assertEqual(meta["generatedFromCodeRevision"], generated["sourceCodeRevision"])
        self.assertTrue(meta["unknowns"])


class DraftEditingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = service_with_git(Path(self.tmp.name))
        envelope = self.service.create_workspace({
            "context": "planning", "title": "设计", "goals": "目标",
        })
        self.workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(self.workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": planning_sample_graph()})
        self.service.apply_candidate(self.workspace_id, {"candidateId": generated["candidateId"]})
        self.envelope = self.service.load_draft(self.workspace_id)

    @property
    def draft_revision(self) -> str:
        return self.envelope["identity"]["draftRevision"]

    def refresh(self) -> None:
        self.envelope = self.service.load_draft(self.workspace_id)

    def test_wrong_expected_revision_conflicts(self) -> None:
        with self.assertRaises(ContractError) as caught:
            self.service.apply_ops(self.workspace_id, {
                "expectedDraftRevision": "stale",
                "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "x"}}],
            })
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")

    def test_concurrent_writers_cas_exactly_one_wins(self) -> None:
        # MID-1 finding 1 (red→green): two writers racing on the same revision
        # must end with exactly one success and no lost lock window.
        outcomes = {"ok": 0, "conflict": 0}
        barrier = threading.Barrier(2)

        def writer(tag):
            barrier.wait()
            try:
                self.service.apply_ops(self.workspace_id, {
                    "expectedDraftRevision": self.draft_revision,
                    "operations": [{"type": "update_node", "nodeId": "n_a",
                                    "fields": {"summary": f"并发写 {tag}"}}],
                })
                outcomes["ok"] += 1
            except ContractError as exc:
                if exc.code == "REVISION_CONFLICT":
                    outcomes["conflict"] += 1

        threads = [threading.Thread(target=writer, args=(tag,)) for tag in ("甲", "乙")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes["ok"], 1)
        self.assertEqual(outcomes["conflict"], 1)
        self.refresh()
        final_summary = self.envelope["draft"]["graph"]["nodes"][0]["summary"]
        self.assertIn(final_summary, ("并发写 甲", "并发写 乙"))

    def test_direct_edit_updates_draft_and_identity(self) -> None:
        result = self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "update_node", "nodeId": "n_a", "fields": {"summary": "新职责"}}],
        })
        self.assertEqual(result["draft"]["graph"]["nodes"][0]["summary"], "新职责")
        self.assertNotEqual(result["identity"]["draftRevision"], self.draft_revision)

    def test_remove_node_with_process_references(self) -> None:
        # MID-1 finding 6: process references block removal and force cleans.
        process = [{"stepId": "s1", "title": "产出", "detail": "", "inputs": [],
                    "outputs": ["node:n_a"], "branches": [], "next": []}]
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "update_process", "nodeId": "n_b", "process": process}],
        })
        self.refresh()
        with self.assertRaises(ContractError) as caught:
            self.service.apply_ops(self.workspace_id, {
                "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
                "operations": [{"type": "remove_node", "nodeId": "n_a"}],
            })
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        result = self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
            "operations": [{"type": "remove_node", "nodeId": "n_a", "force": True}],
        })
        ids = {node["id"] for node in result["draft"]["graph"]["nodes"]}
        self.assertNotIn("n_a", ids)
        for node in result["draft"]["graph"]["nodes"]:
            for step in node.get("process", []):
                for entry in step.get("outputs", []) + step.get("inputs", []):
                    self.assertNotIn("n_a", entry.split(":", 1)[-1])

    def test_process_reorder_keeps_step_ids(self) -> None:
        process = [
            {"stepId": "s1", "title": "第一步", "detail": "", "inputs": [], "outputs": [], "branches": [], "next": ["s2"]},
            {"stepId": "s2", "title": "第二步", "detail": "", "inputs": [], "outputs": [], "branches": [], "next": []},
        ]
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.draft_revision,
            "operations": [{"type": "update_process", "nodeId": "n_a", "process": process}],
        })
        self.refresh()
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
        generated = self.service.generate(self.workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": dev_sample_graph()})
        self.service.apply_candidate(self.workspace_id, {"candidateId": generated["candidateId"]})
        self.envelope = self.service.load_draft(self.workspace_id)

    def refresh(self) -> None:
        self.envelope = self.service.load_draft(self.workspace_id)

    def preview(self, **overrides) -> dict:
        payload = {
            "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
            "instruction": "职责不对",
            "selectedNodeIds": ["n_a"],
            "mode": "dev_sample",
        }
        payload.update(overrides)
        return self.service.correction_preview(self.workspace_id, payload)

    def test_correction_preview_dev_sample_is_labeled(self) -> None:
        preview = self.preview()
        self.assertEqual(preview["origin"], "dev_sample")
        self.assertTrue(preview["operations"])
        self.assertIn("演示", preview["note"])

    def test_correction_preview_production_without_c_is_unavailable(self) -> None:
        # production correction is the real model path: with no model
        # configured it is honestly NOT_RUN (never a demo note), and the
        # labeled rule-based route is explicitly selectable instead.
        with self.assertRaises(ContractError) as caught:
            self.preview(mode="production")
        self.assertEqual(caught.exception.code, "NOT_RUN_AWAITING_CONFIGURATION")
        # the rule-based route is C's real module: it either returns a labeled
        # preview or fails machine-coded; it never claims to be AI
        try:
            rule_preview = self.preview(mode="rule_based")
        except ContractError as exc:
            self.assertIn(exc.code, ("BACKEND_UNAVAILABLE", "STALE_CONTEXT", "EVIDENCE_MISMATCH"))
        else:
            self.assertEqual(rule_preview["origin"], "rule_based")
            self.assertIn("规则", rule_preview["labeled"])

    def test_correction_preview_stale_revision_conflicts(self) -> None:
        with self.assertRaises(ContractError) as caught:
            self.preview(expectedDraftRevision="old")
        self.assertEqual(caught.exception.code, "REVISION_CONFLICT")

    def test_apply_correction_by_proposal_and_expiry(self) -> None:
        # MID-1 finding 9: the preview is applied by proposalId and expires
        # when the draft moved on — regeneration is the only way forward.
        preview = self.preview()
        # direct edit moves the draft forward behind the preview's back
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_b", "fields": {"summary": "别的修改"}}],
        })
        with self.assertRaises(ContractError) as caught:
            self.service.apply_correction(self.workspace_id, {
                "proposalId": preview["proposalId"],
                "expectedDraftRevision": preview["baseDraftRevision"],
            })
        self.assertEqual(caught.exception.code, "STALE_CONTEXT")
        # a stale preview cannot be smuggled through with another basis value
        with self.assertRaises(ContractError):
            self.service.apply_correction(self.workspace_id, {
                "proposalId": preview["proposalId"],
                "expectedDraftRevision": self.service.load_draft(self.workspace_id)["identity"]["draftRevision"],
            })
        # regenerate on the current draft, then apply
        self.refresh()
        fresh_preview = self.preview()
        result = self.service.apply_correction(self.workspace_id, {
            "proposalId": fresh_preview["proposalId"],
            "expectedDraftRevision": fresh_preview["baseDraftRevision"],
        })
        self.assertIn("演示纠正", result["draft"]["graph"]["nodes"][0]["summary"])

    def test_sample_correction_marks_draft_origin(self) -> None:
        # MID-1 finding 3 (part 2): sample-derived edits keep the sample mark.
        preview = self.preview()
        self.envelope = self.service.apply_correction(self.workspace_id, {
            "proposalId": preview["proposalId"],
            "expectedDraftRevision": preview["baseDraftRevision"],
        })
        self.assertEqual(self.envelope["draft"]["origin"], "dev_sample")
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(self.workspace_id, {
                "expectedMapRevision": self.envelope["draft"]["graph"]["mapRevision"],
                "decision": "accept", "actor": "tester", "origin": "dev_sample",
            })
        self.assertEqual(caught.exception.code, "DEV_SAMPLE_DISABLED")

    def test_review_records_decision_but_produces_no_version(self) -> None:
        map_revision = self.envelope["draft"]["graph"]["mapRevision"]
        with self.assertRaises(ContractError) as caught:
            self.service.submit_review(self.workspace_id, {
                "expectedMapRevision": map_revision, "decision": "accept",
                "actor": "tester", "reason": "验收测试", "origin": "dev_sample",
            })
        self.assertEqual(caught.exception.code, "DEV_SAMPLE_DISABLED")

    def test_review_on_real_origin_draft_is_refused_until_b_lands(self) -> None:
        # Simulate the AI-configured path: the draft with a non-sample origin
        # must reach the B seam and be refused there with BACKEND_UNAVAILABLE,
        # recording the decision.
        record = self.service.store.load_workspace(self.workspace_id)
        record["draft"]["origin"] = "ai_candidate"
        record["draft"]["lineage"] = ["ai_candidate"]  # simulate a real-AI draft
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
