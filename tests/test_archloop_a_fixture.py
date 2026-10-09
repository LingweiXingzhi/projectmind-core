"""P4 loop demo on a real fixture repository (A-level, D pending).

Demonstrates the full change-correction cycle against a temporary Git repo:
workspace → sample draft → real commit changes code → recheck reports stale
nodes → cognition corrected in draft → implementation-fix task (labeled
sample until D lands) → rebind to the new HEAD (local record) → recheck
clean. verifiedCodeRevision stays null: nothing claims human verification.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from archloop.adapters import AdapterRegistry
from archloop.contract import ContractError
from archloop.service import WorkbenchService


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode("utf-8").strip()


def fixture_repo(root: Path) -> Path:
    repo = root / "fixture"
    repo.mkdir(parents=True)
    run_git(repo, "init")
    (repo / "billing.py").write_text("def charge(amount):\n    return amount\n", encoding="utf-8")
    (repo / "report.py").write_text("def render(rows):\n    return len(rows)\n", encoding="utf-8")
    run_git(repo, "add", ".")
    run_git(repo, "config", "user.email", "fixture@example.com")
    run_git(repo, "config", "user.name", "fixture")
    run_git(repo, "commit", "-m", "initial billing and report")
    return repo


SAMPLE = {
    "nodes": [
        {"id": "n_billing", "title": "计费", "summary": "负责金额计算", "status": "candidate",
         "provenance": "rule_based", "entryPoints": [], "interfaces": [],
         "evidence": [{"path": "billing.py", "reason": "计费实现", "kind": "code_fact"}], "process": []},
        {"id": "n_report", "title": "报表", "summary": "负责结果呈现", "status": "candidate",
         "provenance": "rule_based", "entryPoints": [], "interfaces": [],
         "evidence": [{"path": "report.py", "reason": "报表实现", "kind": "code_fact"}], "process": []},
    ],
    "edges": [],
}


class FixtureLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        from app import git as app_git
        self.service = WorkbenchService(Path(self.tmp.name) / "data", AdapterRegistry())
        self.service.bind_git(app_git)
        self.repo = fixture_repo(Path(self.tmp.name))
        envelope = self.service.create_workspace({
            "context": "existing_project", "title": "fixture 演示",
            "repoPath": str(self.repo), "description": "两个功能的演示仓库",
        })
        self.workspace_id = envelope["workspace"]["workspaceId"]
        generated = self.service.generate(self.workspace_id,
                                          {"mode": "dev_sample", "sampleGraph": SAMPLE})
        self.service.apply_candidate(self.workspace_id, {"candidateId": generated["candidateId"]})

    def test_full_change_correction_rebind_cycle(self) -> None:
        old_head = run_git(self.repo, "rev-parse", "HEAD")

        # real code change on the fixture repo
        (self.repo / "billing.py").write_text("def charge(amount):\n    return amount * 2\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "billing doubles the amount")
        new_head = run_git(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(old_head, new_head)

        # recheck detects the change and flags the stale node
        recheck = self.service.recheck(self.workspace_id)
        self.assertTrue(recheck["changed"])
        self.assertEqual([node["nodeId"] for node in recheck["staleNodes"]], ["n_billing"])
        self.assertIn("不代表架构已变化", recheck["note"])

        # cognition correction: the responsibility text updates in the draft
        self.envelope = self.service.load_draft(self.workspace_id)
        self.service.apply_ops(self.workspace_id, {
            "expectedDraftRevision": self.envelope["identity"]["draftRevision"],
            "operations": [{"type": "update_node", "nodeId": "n_billing",
                            "fields": {"summary": "负责金额计算并按规则翻倍"}}],
        })

        # implementation-fix task: labeled sample until D lands
        task = self.service.create_fix_task(self.workspace_id, {
            "deviation": "计费职责描述与实现不符", "acceptance": "职责描述与 billing.py 一致",
            "expectedProcessRef": "n_billing", "mode": "dev_sample",
        })
        self.assertEqual(task["origin"], "dev_sample")

        # rebind to the reviewed new HEAD: local record, verified stays null
        envelope = self.service.rebind_code_revision(self.workspace_id, {
            "expectedNewCodeRevision": new_head, "actor": "fixture-operator",
            "note": "计费变化已人工复核",
        })
        self.assertEqual(envelope["identity"]["codeRevision"], new_head)
        self.assertIsNone(envelope["identity"]["verifiedCodeRevision"])

        # recheck is clean against the rebound revision
        recheck2 = self.service.recheck(self.workspace_id)
        self.assertFalse(recheck2["changed"])

        # a stale rebind target is refused
        with self.assertRaises(ContractError) as caught:
            self.service.rebind_code_revision(self.workspace_id, {
                "expectedNewCodeRevision": old_head, "actor": "fixture-operator"})
        self.assertEqual(caught.exception.code, "STALE_CONTEXT")


if __name__ == "__main__":
    unittest.main()
