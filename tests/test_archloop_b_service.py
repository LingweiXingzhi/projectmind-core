"""Real Git, durable state and adversarial review tests. Human actors are fixtures."""
from __future__ import annotations

import copy
import json
import multiprocessing
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from extensions.architecture_workspace import WorkspaceService, HumanReviewGateway, WorkspaceError
from extensions.architecture_workspace.git_publication import GitPublisher, code_identity
from extensions.architecture_workspace.schema import canonical
from extension_host import ExtensionContext, ExtensionHost, ExtensionError


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()


def init_repo(path, branch):
    path.mkdir()
    git(path, "init", "-b", branch)
    git(path, "config", "user.name", "B test fixture")
    git(path, "config", "user.email", "fixture@example.invalid")
    (path / "README.md").write_text("Isolated architecture test fixture.\n")
    git(path, "add", "."); git(path, "commit", "-m", "fixture root")


def sample_graph(repo_id=None, revision=None):
    evidence = [{"id": "e-goal", "kind": "user_goal", "content": "Test fixture goal",
                 "reason": "Explicit fixture requirement"}]
    refs = ["e-goal"]
    if repo_id is not None:
        evidence += [{"id": "e-code", "kind": "code", "path": "main.py",
                      "codeRepoId": repo_id, "codeRevision": revision,
                      "lineStart": 1, "lineEnd": 2, "reason": "Fixture function"},
                     {"id": "e-util", "kind": "code", "path": "util.py",
                      "codeRepoId": repo_id, "codeRevision": revision,
                      "reason": "Fixture utility"}]
        refs += ["e-code"]
    nodes = [{"id": "n-main", "title": "Main", "responsibility": "Orchestrate fixture",
              "implementationStatus": "planned" if repo_id is None else "unknown",
              "interfaces": [{"id": "i-main", "name": "run", "kind": "team_contract",
                              "description": "Fixture interface", "evidenceIds": refs}],
              "evidenceIds": refs},
             {"id": "n-util", "title": "Utility", "responsibility": "Help fixture",
              "implementationStatus": "planned", "interfaces": [],
              "evidenceIds": ["e-util"] if repo_id else ["e-goal"]}]
    steps = [{"id": "s-one", "nodeId": "n-main", "title": "Begin", "inputs": [],
              "outputs": ["value"], "condition": "", "branches": [],
              "nextStepIds": ["s-two"], "allowedFailures": ["invalid input"], "evidenceIds": refs},
             {"id": "s-two", "nodeId": "n-util", "title": "Continue", "inputs": ["value"],
              "outputs": [], "condition": "value exists", "branches": [{"condition": "retry",
              "nextStepId": "s-one"}], "nextStepIds": [], "allowedFailures": [],
              "evidenceIds": ["e-util"] if repo_id else ["e-goal"]}]
    return {"schemaVersion": "architecture_graph_v1", "nodes": nodes, "evidence": evidence,
            "edges": [{"id": "r-one", "from": "n-main", "to": "n-util",
                       "type": "functional_collaboration", "label": "Delegates", "evidenceIds": []}],
            "processes": [{"id": "p-flow", "title": "Expected fixture process", "kind": "expected",
                           "steps": steps, "evidenceIds": []}]}


def all_coverage(graph):
    return {"scope": "all", **{k: [o["id"] for o in graph[k]]
            for k in ("nodes", "edges", "processes", "evidence")}}


def cas_writer(root, repo, draft, barrier, queue):
    try:
        service = WorkspaceService(root, code_repositories=[repo])
        barrier.wait(timeout=15)
        value = service.apply_draft_operations(
            draft["draftId"], operations=[{"op": "node.update", "id": "n-main",
                                          "changes": {"title": "Writer " + str(multiprocessing.current_process().pid)}}],
            expected_draft_revision=1, base_map_revision=None, proposal_id=draft["proposalId"])
        queue.put(("ok", value["draftRevision"]))
    except WorkspaceError as exc:
        queue.put(("error", exc.code))


class ArchitectureWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archloop-b-")
        self.root = Path(self.temporary.name).resolve()
        self.code = self.root / "code"; self.arch = self.root / "architecture"
        init_repo(self.code, "main"); init_repo(self.arch, "architecture/candidates/fixture")
        # Distinct clone-independent identities without any remote access.
        git(self.code, "remote", "add", "origin", "https://example.invalid/" + secrets.token_hex(8) + ".git")
        (self.code / "main.py").write_text("def run():\n    return 1\n")
        (self.code / "util.py").write_text("def helper():\n    return 2\n")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "code fixture")
        self.revision = git(self.code, "rev-parse", "HEAD")
        self.repo_id = code_identity(self.code)
        self.service = self.make_service()
        self.ws = self.service.open_workspace(mode="existing_project",
                                             code_repo_id=self.repo_id, code_revision=self.revision)
        self.graph = sample_graph(self.repo_id, self.revision)
        self.gateway = HumanReviewGateway(self.service, "http://127.0.0.1:18832")
        self.boundary = {"peer": "127.0.0.1", "host": "127.0.0.1:18832",
                         "origin": "http://127.0.0.1:18832"}
        session = self.gateway.create_session("TEST_HUMAN_FIXTURE", **self.boundary)
        self.auth = {**self.boundary, "session_id": session["sessionId"],
                     "csrf_token": session["csrfToken"]}

    def tearDown(self):
        self.temporary.cleanup()

    def make_service(self):
        return WorkspaceService(self.root / "state", code_repositories=[self.code],
                                architecture_repo=self.arch,
                                architecture_branch="architecture/candidates/fixture")

    def draft(self, ws=None, graph=None, base=None):
        ws = ws or self.ws
        return self.service.create_draft(ws["workspaceId"], graph=graph or self.graph,
                                         origin="ai_generated", base_map_revision=base)

    def update(self, draft, operations, revision=None):
        return self.service.apply_draft_operations(
            draft["draftId"], operations=operations,
            expected_draft_revision=draft["draftRevision"] if revision is None else revision,
            base_map_revision=draft["baseMapRevision"], proposal_id=draft["proposalId"])

    def preview(self, draft, **overrides):
        request = {"reason": "TEST ONLY: simulated operator review",
                   "expected_draft_revision": draft["draftRevision"],
                   "expected_map_revision": draft["baseMapRevision"],
                   "proposal_id": draft["proposalId"], "code_repo_id": draft["codeRepoId"],
                   "code_revision": draft["codeRevision"], "coverage": all_coverage(draft["graph"]),
                   "limits": ["Test fixture; not a real ProjectMind owner approval"],
                   "verify_code": False, "rejected_candidates": []}
        request.update(overrides)
        return self.gateway.preview_review(draft["draftId"], auth=self.auth, **request)

    def review(self, draft, preview=None, decision="accept", **overrides):
        preview = preview or self.preview(draft)
        request = {"confirmation_token": preview["confirmationToken"],
                   "preview_digest": preview["previewDigest"], "decision": decision,
                   "expected_draft_revision": draft["draftRevision"],
                   "expected_map_revision": draft["baseMapRevision"],
                   "proposal_id": draft["proposalId"], "code_repo_id": draft["codeRepoId"],
                   "code_revision": draft["codeRevision"]}
        request.update(overrides)
        return self.gateway.confirm_review(draft["draftId"], auth=self.auth, **request)

    def publish(self, draft, review=None):
        review = review or self.review(draft)
        return self.service.publish_reviewed_graph(
            draft["draftId"], publication_token=review["publicationToken"],
            expected_map_revision=draft["baseMapRevision"])

    def assert_error(self, code, fn):
        with self.assertRaises(WorkspaceError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def test_ai_candidate_edit_reopen_stable_ids_and_step_order(self):
        draft = self.draft()
        edited = self.update(draft, [
            {"op": "node.update", "id": "n-main", "changes": {"title": "Renamed", "responsibility": "Corrected"}},
            {"op": "step.reorder", "processId": "p-flow", "value": ["s-two", "s-one"]}])
        reopened = self.make_service().get_draft(draft["draftId"])
        self.assertEqual(reopened, edited)
        self.assertEqual(reopened["graph"]["nodes"][0]["id"], "n-main")
        self.assertEqual([s["id"] for s in reopened["graph"]["processes"][0]["steps"]], ["s-two", "s-one"])
        self.assertEqual(reopened["status"], "unconfirmed")

    def test_two_processes_cas_exactly_one_success(self):
        draft = self.draft(); ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        workers = [ctx.Process(target=cas_writer, args=(self.root / "state", self.code,
                   draft, barrier, queue)) for _ in range(2)]
        for worker in workers: worker.start()
        results = [queue.get(timeout=30) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
            if worker.is_alive(): worker.terminate(); worker.join()
            self.assertEqual(worker.exitcode, 0)
        self.assertCountEqual(results, [("ok", 2), ("error", "REVISION_CONFLICT")])
        self.assertEqual(self.service.get_draft(draft["draftId"])["draftRevision"], 2)

    def test_planning_confirmation_has_null_code_and_design_only(self):
        ws = self.service.open_workspace(mode="planning")
        draft = self.draft(ws=ws, graph=sample_graph())
        packet = self.publish(draft)["version"]
        self.assertEqual(packet["status"], "confirmed_design")
        for key in ("codeRepoId", "codeRevision", "verifiedCodeRevision"):
            self.assertIsNone(packet[key])
        self.assertEqual(self.service.graph_snapshot(ws["workspaceId"])["applicability"], "design_only")
        self.assertTrue(all(n["implementationStatus"] == "planned" for n in packet["graph"]["nodes"]))

    def test_planning_cannot_claim_implemented_or_verified(self):
        ws = self.service.open_workspace(mode="planning"); graph = sample_graph()
        graph["nodes"][0]["implementationStatus"] = "implemented"
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.draft(ws=ws, graph=graph))
        draft = self.draft(ws=ws, graph=sample_graph())
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.review(draft, self.preview(draft, verify_code=True)))

    def test_associate_code_retains_design_history_and_requires_new_check(self):
        ws = self.service.open_workspace(mode="planning")
        draft = self.draft(ws=ws, graph=sample_graph()); old = self.publish(draft)
        linked = self.service.associate_code(ws["workspaceId"], code_repo_id=self.repo_id,
                                            code_revision=self.revision,
                                            expected_map_revision=old["version"]["mapRevision"])
        self.assertEqual(linked["mode"], "mixed")
        self.assertEqual(linked["designHistory"], [old["version"]["mapRevision"]])
        self.assertEqual(self.service.get_version(ws["workspaceId"], old["version"]["mapRevision"]), old)
        snapshot = self.service.graph_snapshot(ws["workspaceId"])
        self.assertCountEqual(snapshot["pendingNodeIds"], ["n-main", "n-util"])
        self.assertEqual(snapshot["applicability"], "not_checked")

    def test_no_review_no_formal_write(self):
        draft = self.draft(); head = git(self.arch, "rev-parse", "HEAD")
        self.assert_error("HUMAN_REVIEW_REQUIRED", lambda: self.service.publish_reviewed_graph(
            draft["draftId"], publication_token="x" * 43, expected_map_revision=None))
        self.assert_error("REQUEST_FORBIDDEN", lambda: self.review(draft, {
            "confirmationToken": "x" * 43, "previewDigest": "fake"}))
        self.assertEqual(head, git(self.arch, "rev-parse", "HEAD"))
        self.assertIsNone(self.service.open_workspace(workspace_id=self.ws["workspaceId"])["mapRevision"])

    def test_real_git_export_and_second_clone_match(self):
        draft = self.draft(); original = self.publish(draft)
        clone = self.root / "receiver"
        subprocess.run(["git", "clone", str(self.arch), str(clone)], check=True, capture_output=True)
        received = GitPublisher.read_version(clone, draft["mapId"],
                                             original["version"]["mapRevision"],
                                             original["provenance"]["mapSourceRevision"])
        self.assertEqual(received["version"], original["version"])
        self.assertEqual(self.service.export_version(self.ws["workspaceId"],
                                                    original["version"]["mapRevision"]), original)
        raw = git(clone, "show", received["provenance"]["mapSourceRevision"] + ":" +
                  GitPublisher.relative_path(draft["mapId"], original["version"]["mapRevision"]))
        self.assertNotIn("mapSourceRevision", json.loads(raw))
        self.assertNotIn("publicationToken", raw); self.assertNotIn("confirmationToken", raw)

    def test_origin_host_peer_and_csrf_are_enforced(self):
        draft = self.draft()
        for key, value in [("origin", "https://evil.invalid"), ("host", "evil.invalid"),
                           ("peer", "10.1.2.3"), ("csrf_token", "bad")]:
            auth = {**self.auth, key: value}
            self.assert_error("REQUEST_FORBIDDEN", lambda: self.gateway.preview_review(
                draft["draftId"], auth=auth))

    def test_confirmation_is_bound_to_session_even_same_actor(self):
        draft = self.draft(); preview = self.preview(draft)
        second = self.gateway.create_session("TEST_HUMAN_FIXTURE", **self.boundary)
        original_auth = self.auth
        self.auth = {**self.boundary, "session_id": second["sessionId"], "csrf_token": second["csrfToken"]}
        self.assert_error("REQUEST_FORBIDDEN", lambda: self.review(draft, preview))
        self.auth = original_auth
        self.review(draft, preview)

    def test_expired_and_changed_draft_previews_rejected(self):
        draft = self.draft(); preview = self.preview(draft, ttl=1)
        with patch("extensions.architecture_workspace.service.time.time", return_value=time.time() + 5):
            self.assert_error("REVIEW_EXPIRED", lambda: self.review(draft, preview))
        preview = self.preview(draft)
        self.update(draft, [{"op": "node.update", "id": "n-main", "changes": {"title": "Changed"}}])
        self.assert_error("REVISION_CONFLICT", lambda: self.review(draft, preview))

    def test_wrong_graph_repo_proposal_and_digest_rejected(self):
        draft = self.draft(); preview = self.preview(draft)
        for overrides in ({"code_repo_id": "repo-other"}, {"proposal_id": "proposal-other"},
                          {"code_revision": "a" * 40}):
            self.assert_error("STALE_CONTEXT", lambda: self.review(draft, preview, **overrides))
        self.assert_error("HUMAN_REVIEW_REQUIRED",
                          lambda: self.review(draft, preview, preview_digest="sha256:" + "a" * 64))
        other = self.draft()
        self.assert_error("STALE_CONTEXT", lambda: self.review(other, preview))

    def test_replay_idempotency_and_reject_does_not_publish(self):
        draft = self.draft(); preview = self.preview(draft)
        review = self.review(draft, preview)
        self.assertEqual(self.review(draft, preview), review)
        self.assert_error("REVIEW_REPLAY", lambda: self.review(draft, preview, decision="reject"))
        packet = self.publish(draft, review); source = packet["provenance"]["mapSourceRevision"]
        self.assertEqual(self.publish(draft, review), packet)
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), source)
        other = self.draft(base=packet["version"]["mapRevision"])
        rejected = self.review(other, decision="reject")
        self.assertIsNone(rejected["publicationToken"])
        self.assert_error("HUMAN_REVIEW_REQUIRED", lambda: self.publish(other, rejected))

    def test_partial_coverage_does_not_extend_to_new_head(self):
        draft = self.draft()
        coverage = {"scope": "partial", "nodes": ["n-main"], "edges": [],
                    "processes": [], "evidence": ["e-code", "e-goal"]}
        packet = self.publish(draft, self.review(draft, self.preview(
            draft, verify_code=True, coverage=coverage)))
        self.assertEqual(packet["version"]["verifiedCodeRevision"], self.revision)
        self.assertEqual(packet["version"]["confirmation"]["nodes"]["unconfirmed"], ["n-util"])
        (self.code / "util.py").write_text("def helper():\n    return 3\n")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "real change")
        target = git(self.code, "rev-parse", "HEAD")
        self.service.open_workspace(workspace_id=self.ws["workspaceId"], code_revision=target)
        snapshot = self.service.graph_snapshot(self.ws["workspaceId"])
        self.assertEqual(snapshot["pendingNodeIds"], ["n-util"])
        self.assertEqual(snapshot["applicability"], "not_checked")
        self.assertEqual(snapshot["versionEnvelope"]["version"]["verifiedCodeRevision"], self.revision)
        self.assertEqual(self.service.get_version(self.ws["workspaceId"], packet["version"]["mapRevision"]), packet)

    def test_unknown_and_incomplete_coverage_cannot_verify(self):
        graph = copy.deepcopy(self.graph)
        graph["evidence"].append({"id": "e-unknown", "kind": "unknown",
                                 "content": "Unobserved runtime", "unknownReason": "No trace",
                                 "reason": "Fixture unknown"})
        draft = self.draft(graph=graph)
        self.assert_error("EVIDENCE_MISMATCH",
                          lambda: self.review(draft, self.preview(draft, verify_code=True)))
        coverage = {"scope": "partial", "nodes": ["n-main"], "edges": [],
                    "processes": [], "evidence": ["e-code"]}
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.review(
            draft, self.preview(draft, verify_code=True, coverage=coverage)))

    def test_two_approved_drafts_cannot_overwrite_current_version(self):
        first, second = self.draft(), self.draft()
        one, two = self.review(first), self.review(second)
        self.publish(first, one)
        self.assert_error("REVISION_CONFLICT", lambda: self.publish(second, two))

    def test_reference_rejection_rolls_back_whole_batch(self):
        draft = self.draft()
        self.assert_error("REFERENCE_CONFLICT",
                          lambda: self.update(draft, [{"op": "node.remove", "id": "n-util"}]))
        self.assertEqual(self.service.get_draft(draft["draftId"]), draft)
        changed = self.update(draft, [{"op": "edge.remove", "id": "r-one"},
            {"op": "process.remove", "id": "p-flow"}, {"op": "node.remove", "id": "n-util"}])
        self.assertEqual(len(changed["graph"]["nodes"]), 1)

    def test_unsafe_paths_missing_line_and_cross_repo_evidence_fail(self):
        for invalid in ("../secret", "/etc/passwd", "a\\b", "main.py\x00x", "./main.py", "missing.py"):
            graph = copy.deepcopy(self.graph); graph["evidence"][1]["path"] = invalid
            self.assert_error("EVIDENCE_MISMATCH", lambda: self.draft(graph=graph))
        graph = copy.deepcopy(self.graph); graph["evidence"][1]["lineEnd"] = 500
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.draft(graph=graph))
        graph = copy.deepcopy(self.graph); graph["evidence"][1]["codeRepoId"] = "repo-other"
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.draft(graph=graph))

    def test_worktree_text_is_not_fixed_commit_evidence(self):
        (self.code / "main.py").write_text("UNCOMMITTED")
        draft = self.draft()
        preview = self.preview(draft, verify_code=True)
        self.assertEqual(self.publish(draft, self.review(draft, preview))["version"]["verifiedCodeRevision"], self.revision)
        self.assertEqual((self.code / "main.py").read_text(), "UNCOMMITTED")

    def test_dirty_architecture_repo_refused_without_overwrite(self):
        draft = self.draft(); review = self.review(draft)
        unrelated = self.arch / "someone-else.txt"; unrelated.write_text("Keep")
        self.assert_error("DIRTY_ARCHITECTURE_REPO", lambda: self.publish(draft, review))
        self.assertEqual(unrelated.read_text(), "Keep")
        unrelated.unlink()
        self.publish(draft, review)

    def test_git_failure_retry_exactly_one_commit_and_frozen_draft(self):
        draft = self.draft(); review = self.review(draft)
        base = git(self.arch, "rev-parse", "HEAD")
        with patch.object(self.service.publisher, "_commit", side_effect=WorkspaceError("PUBLICATION_FAILED")):
            self.assert_error("PUBLICATION_FAILED", lambda: self.publish(draft, review))
        self.assertEqual(self.service.get_draft(draft["draftId"])["status"], "publishing")
        self.assert_error("VERSION_CONFLICT", lambda: self.update(draft, [
            {"op": "node.update", "id": "n-main", "changes": {"title": "Race"}}]))
        self.assertIsNone(self.service.open_workspace(workspace_id=self.ws["workspaceId"])["mapRevision"])
        self.service = self.make_service()
        packet = self.publish(draft, review)
        self.assertEqual(git(self.arch, "rev-list", "--count", base + "..HEAD"), "1")
        self.assertEqual(packet["provenance"]["mapSourceRevision"], git(self.arch, "rev-parse", "HEAD"))

    def test_interruption_after_commit_recovers_on_new_service(self):
        draft = self.draft(); review = self.review(draft)
        base = git(self.arch, "rev-parse", "HEAD")
        with patch.object(self.service, "_finalize", side_effect=OSError("TEST crash after commit")):
            with self.assertRaises(OSError): self.publish(draft, review)
        source = git(self.arch, "rev-parse", "HEAD")
        self.service = self.make_service()
        packet = self.publish(draft, review)
        self.assertEqual(packet["provenance"]["mapSourceRevision"], source)
        self.assertEqual(git(self.arch, "rev-list", "--count", base + "..HEAD"), "1")

    def test_recovery_refuses_unrelated_changes(self):
        draft = self.draft(); review = self.review(draft)
        with patch.object(self.service.publisher, "_commit", side_effect=WorkspaceError("PUBLICATION_FAILED")):
            self.assert_error("PUBLICATION_FAILED", lambda: self.publish(draft, review))
        extra = self.arch / "unrelated.txt"; extra.write_text("Must keep")
        self.assert_error("DIRTY_ARCHITECTURE_REPO", lambda: self.publish(draft, review))
        self.assertEqual(extra.read_text(), "Must keep")
        extra.unlink(); self.publish(draft, review)

    def test_layout_is_not_semantic_version_and_history_restore_new_draft(self):
        first = self.draft(); one = self.publish(first); one_rev = one["version"]["mapRevision"]
        layout = self.draft(base=one_rev)
        layout = self.update(layout, [{"op": "layout.set", "value": {"n-main": {"x": 1, "y": 2}}}])
        same = self.publish(layout)
        self.assertEqual(same, one)
        changed = self.draft(base=one_rev)
        changed = self.update(changed, [{"op": "node.update", "id": "n-main",
                                         "changes": {"responsibility": "New responsibility"}}])
        two = self.publish(changed)
        restored = self.service.create_draft(self.ws["workspaceId"], base_map_revision=two["version"]["mapRevision"],
                                             from_map_revision=one_rev)
        self.assertEqual(restored["graph"], one["version"]["graph"])
        self.assertEqual(restored["status"], "unconfirmed")
        self.assertNotEqual(restored["draftId"], first["draftId"])
        self.assertEqual(self.service.get_version(self.ws["workspaceId"], one_rev), one)

    def test_source_identity_change_and_incompatible_branch_rejected(self):
        draft = self.draft()
        original = git(self.code, "config", "remote.origin.url")
        git(self.code, "remote", "set-url", "origin", "https://example.invalid/other.git")
        self.assert_error("STALE_CONTEXT", lambda: self.update(draft, [
            {"op": "node.update", "id": "n-main", "changes": {"title": "Wrong repo"}}]))
        git(self.code, "remote", "set-url", "origin", original)
        git(self.code, "checkout", "--orphan", "unrelated")
        git(self.code, "commit", "-m", "unrelated root")
        target = git(self.code, "rev-parse", "HEAD")
        self.assert_error("STALE_CONTEXT", lambda: self.service.open_workspace(
            workspace_id=self.ws["workspaceId"], code_revision=target))

    def test_data_root_and_write_repo_cannot_overlap_code(self):
        self.assert_error("INVALID_INPUT", lambda: WorkspaceService(self.code / "state",
                            code_repositories=[self.code]))
        self.assert_error("INVALID_INPUT", lambda: WorkspaceService(self.root / "other-state",
                            code_repositories=[self.code], architecture_repo=self.code,
                            architecture_branch="architecture/candidates/fixture"))

    def test_legacy_import_unconfirmed_and_layout_separate(self):
        legacy = {"note": "Curated demo, not approved",
                  "nodes": [{"id": "legacy-node", "title": "Legacy", "summary": "Old responsibility",
                             "entryPoint": "main.py run", "position": {"x": 10, "y": 10},
                             "evidence": [{"path": "main.py", "reason": "Old mapping"}]}],
                  "edges": []}
        draft = self.service.create_draft(self.ws["workspaceId"], legacy=legacy)
        self.assertEqual(draft["origin"], "legacy")
        self.assertEqual(draft["status"], "unconfirmed")
        self.assertEqual(draft["layout"], {"legacy-node": {"x": 10, "y": 10}})
        self.assertNotIn("position", canonical(draft["graph"]))

    def test_legacy_extension_loads_read_only_and_blocks_post(self):
        context = ExtensionContext(self.code, self.root / "unused-map", lambda: {}, lambda a,b: {})
        host = ExtensionHost(Path(__file__).resolve().parents[1] / "extensions", context)
        self.assertIn("architecture_workspace", host.loaded)
        response = host.run("architecture_workspace", "GET", {})
        self.assertEqual(response["status"], "integration_pending")
        with self.assertRaises(ExtensionError) as caught:
            host.run("architecture_workspace", "POST", {})
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(str(caught.exception), "PUBLIC_ADAPTER_REQUIRED")

    def test_second_client_imports_git_version_and_reopens(self):
        draft = self.draft(); original = self.publish(draft)
        clone = self.root / "client-two"
        subprocess.run(["git", "clone", str(self.arch), str(clone)], check=True, capture_output=True)
        receiver = WorkspaceService(self.root / "receiver-state", code_repositories=[self.code],
                    architecture_repo=clone, architecture_branch="architecture/candidates/fixture")
        ws = receiver.open_workspace(mode="existing_project", map_id=draft["mapId"],
                                      code_repo_id=self.repo_id, code_revision=self.revision)
        imported = receiver.import_git_version(ws["workspaceId"],
                    map_revision=original["version"]["mapRevision"],
                    map_source_revision=original["provenance"]["mapSourceRevision"],
                    expected_map_revision=None)
        self.assertEqual(imported["version"], original["version"])
        self.assertEqual(receiver.graph_snapshot(ws["workspaceId"])["versionEnvelope"], imported)
        self.assertNotEqual(ws["workspaceId"], self.ws["workspaceId"])

    def test_real_git_commit_error_and_retry_preserve_single_version(self):
        draft = self.draft(); review = self.review(draft)
        head = git(self.arch, "rev-parse", "HEAD")
        git(self.arch, "config", "user.name", "")
        git(self.arch, "config", "user.email", "")
        self.assert_error("PUBLICATION_FAILED", lambda: self.publish(draft, review))
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), head)
        git(self.arch, "config", "user.name", "B test fixture")
        git(self.arch, "config", "user.email", "fixture@example.invalid")
        self.publish(draft, review)
        self.assertEqual(git(self.arch, "rev-list", "--count", head + "..HEAD"), "1")

    def test_file_write_failure_is_not_success_and_is_recoverable(self):
        draft = self.draft(); review = self.review(draft)
        with patch.object(self.service.publisher, "_write_file", side_effect=OSError("TEST write failure")):
            self.assert_error("PUBLICATION_FAILED", lambda: self.publish(draft, review))
        self.assertIsNone(self.service.graph_snapshot(self.ws["workspaceId"])["versionEnvelope"])
        self.publish(draft, review)

    def test_semantic_rename_creates_new_version_old_bytes_immutable(self):
        first = self.draft(); one = self.publish(first)
        draft = self.draft(base=one["version"]["mapRevision"])
        draft = self.update(draft, [{"op": "node.update", "id": "n-main", "changes": {"title": "Renamed"}}])
        two = self.publish(draft)
        self.assertNotEqual(one["version"]["mapRevision"], two["version"]["mapRevision"])
        self.assertEqual(one["version"]["graph"]["nodes"][0]["id"], two["version"]["graph"]["nodes"][0]["id"])
        historical = GitPublisher.read_version(self.arch, first["mapId"],
                        one["version"]["mapRevision"], one["provenance"]["mapSourceRevision"])
        self.assertEqual(historical["version"], one["version"])

    def test_code_context_change_invalidates_preview(self):
        draft = self.draft(); preview = self.preview(draft)
        (self.code / "new.py").write_text("value = 1\n")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "new target")
        self.service.open_workspace(workspace_id=self.ws["workspaceId"],
                                    code_revision=git(self.code, "rev-parse", "HEAD"))
        self.assert_error("STALE_CONTEXT", lambda: self.review(draft, preview))

    def test_malformed_json_shapes_get_controlled_errors(self):
        for key, value in (("nodes", {}), ("edges", [None]), ("evidence", [True]), ("processes", 1)):
            graph = copy.deepcopy(self.graph); graph[key] = value
            self.assert_error("INVALID_INPUT", lambda: self.draft(graph=graph))
        self.assert_error("INVALID_INPUT", lambda: self.service.open_workspace(
            mode="existing_project", code_repo_id={}, code_revision=self.revision))
        draft = self.draft()
        self.assert_error("INVALID_INPUT", lambda: self.preview(draft, expected_draft_revision=True))

    def test_code_symlink_is_not_evidence(self):
        (self.code / "link.py").symlink_to("main.py")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "symlink")
        target = git(self.code, "rev-parse", "HEAD")
        self.ws = self.service.open_workspace(workspace_id=self.ws["workspaceId"], code_revision=target)
        graph = sample_graph(self.repo_id, target); graph["evidence"][1]["path"] = "link.py"
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.draft(graph=graph))

    def test_git_version_reader_rejects_tampered_review(self):
        draft = self.draft(); packet = self.publish(draft)["version"]
        forged = copy.deepcopy(packet); forged["review"]["actor"] = "Forged"
        relative = GitPublisher.relative_path(draft["mapId"], packet["mapRevision"])
        (self.arch / relative).write_text(canonical(forged))
        git(self.arch, "add", "."); git(self.arch, "commit", "-m", "tampered fixture")
        self.assert_error("EVIDENCE_MISMATCH", lambda: GitPublisher.read_version(self.arch,
            draft["mapId"], packet["mapRevision"], git(self.arch, "rev-parse", "HEAD")))

    def test_unknown_legacy_path_is_not_silently_verified(self):
        legacy = {"note": "Legacy unknown", "nodes": [{"id": "old-node", "title": "Unknown",
            "summary": "Unproven mapping", "entryPoint": "missing.py", "position": {"x": 0, "y": 0},
            "evidence": [{"path": "missing.py", "reason": "Old claim"}]}], "edges": []}
        self.assert_error("EVIDENCE_MISMATCH", lambda: self.service.create_draft(self.ws["workspaceId"], legacy=legacy))

    def test_stale_preview_after_other_version_published(self):
        first, second = self.draft(), self.draft()
        preview = self.preview(second)
        self.publish(first)
        self.assert_error("REVISION_CONFLICT", lambda: self.review(second, preview))


if __name__ == "__main__":
    unittest.main()
