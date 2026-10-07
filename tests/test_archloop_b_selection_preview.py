"""Selected-patch preview uses real fixed Git facts and never issues review authority."""
import copy
import unittest
from unittest.mock import patch

from extensions.architecture_workspace.surfaces import CollaborationAPI, workspace_context
from extensions.architecture_workspace.schema import digest
from tests import test_archloop_b_surfaces as fixture_module

git = fixture_module.git


class CandidatePreviewTests(unittest.TestCase):
    setUp = fixture_module.ArchitectureWorkspaceSurfaceTests.setUp
    tearDown = fixture_module.ArchitectureWorkspaceSurfaceTests.tearDown
    make_service = fixture_module.ArchitectureWorkspaceSurfaceTests.make_service
    request = fixture_module.ArchitectureWorkspaceSurfaceTests.request
    api = fixture_module.ArchitectureWorkspaceSurfaceTests.api
    invoke = fixture_module.ArchitectureWorkspaceSurfaceTests.invoke
    ok = fixture_module.ArchitectureWorkspaceSurfaceTests.ok
    error = fixture_module.ArchitectureWorkspaceSurfaceTests.error
    prepare = fixture_module.ArchitectureWorkspaceSurfaceTests.prepare
    documents = fixture_module.ArchitectureWorkspaceSurfaceTests.documents
    proposal = fixture_module.ArchitectureWorkspaceSurfaceTests.proposal
    candidates = fixture_module.ArchitectureWorkspaceSurfaceTests.candidates
    review = fixture_module.ArchitectureWorkspaceSurfaceTests.review
    publish = fixture_module.ArchitectureWorkspaceSurfaceTests.publish
    assert_no_grants = fixture_module.ArchitectureWorkspaceSurfaceTests.assert_no_grants

    def selection(self, context, candidates=None):
        candidates = candidates or self.candidates()[:2]
        proposal = self.proposal(context, candidates)
        selected = [{"candidateId": c["candidateId"], "decision": "accept",
                     "operationIds": [o["operationId"] for o in c["operations"]]}
                    for c in candidates]
        operations = [copy.deepcopy(o) for c in candidates for o in c["operations"]]
        return {"context": context, "proposal": proposal,
                "selection": selected, "operations": operations}

    def evidence_candidate(self, context, path="main.py", **extra):
        return [{"candidateId": "c-evidence", "operations": [
            {"op": "evidence.add", "operationId": "op-evidence", "source": "rule_based",
             "value": {"id": "e-new", "kind": "code", "path": path,
                       "codeRepoId": context["codeRepoId"], "codeRevision": context["codeRevision"],
                       "reason": "Isolated fixed-code fixture", **extra}}]}]

    def test_preview_equals_save_and_does_not_change_sqlite_git_or_authority(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context)
        original = self.service.get_draft(context["draftId"])
        before = self.documents()
        db_bytes = self.service.store.path.read_bytes()
        heads = [git(repo, "rev-parse", "HEAD") for repo in (self.code, self.arch)]
        previews = []
        for _ in range(2):
            result = self.ok(self.invoke(api, "previewSelection", **request))
            previews.append(result["data"])
            self.assertEqual(result["status"], "selection_preview")
            self.assertFalse(result["data"]["writePerformed"])
            self.assertFalse(result["data"]["reviewAuthorizationIssued"])
            self.assertEqual(result["context"], context)
            self.assert_no_grants(result)
        self.assertEqual(previews[0], previews[1])
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.service.store.path.read_bytes(), db_bytes)
        self.assertEqual(self.service.get_draft(context["draftId"]), original)
        self.assertEqual([git(repo, "rev-parse", "HEAD") for repo in (self.code, self.arch)], heads)
        self.assertEqual(api._previews, {})
        self.assertEqual(api._reviews, {})
        saved = self.ok(self.invoke(api, "saveDraft", **request))["data"]["draft"]
        self.assertEqual(saved["graph"], previews[0]["afterGraph"])
        self.assertEqual(saved["layout"], previews[0]["afterLayout"])
        self.assertEqual(saved["candidateSelections"][0]["selection"], previews[0]["selection"])

    def test_missing_fixed_code_fails_preview_even_when_structure_is_valid(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context, self.evidence_candidate(context, "missing.py"))
        c = CollaborationAPI(self.service, self.ws["workspaceId"], role="C")
        self.ok(c.call("validateProposal", self.request(context=context, proposal=request["proposal"])))
        before = self.documents()
        self.error(self.invoke(api, "previewSelection", **request), "EVIDENCE_MISMATCH")
        self.assertEqual(self.documents(), before)

    def test_worktree_shadow_does_not_repair_missing_fixed_evidence(self):
        api = self.api()
        context = self.prepare(api)["context"]
        (self.code / "missing.py").write_text("def present_only_in_worktree(): pass\n")
        request = self.selection(context, self.evidence_candidate(context, "missing.py"))
        before = self.documents()
        status = git(self.code, "status", "--porcelain")
        self.error(self.invoke(api, "previewSelection", **request), "EVIDENCE_MISMATCH")
        self.assertEqual(self.documents(), before)
        self.assertEqual(git(self.code, "status", "--porcelain"), status)

    def test_bad_fixed_line_range_fails_before_save(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context, self.evidence_candidate(context, lineStart=99, lineEnd=99))
        self.error(self.invoke(api, "previewSelection", **request), "EVIDENCE_MISMATCH")

    def test_deleting_referenced_node_is_rejected_without_partial_state(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context, self.candidates()[2:])
        before = self.documents()
        self.error(self.invoke(api, "previewSelection", **request), "REFERENCE_CONFLICT")
        self.assertEqual(self.documents(), before)

    def test_all_reject_previews_unchanged_graph_and_does_not_issue_review(self):
        api = self.api()
        prepared = self.prepare(api)
        request = self.selection(prepared["context"])
        request["selection"] = [{"candidateId": c["candidateId"], "decision": "reject",
                                  "operationIds": [], "reason": "TEST fixture rejected"}
                                 for c in request["proposal"]["candidates"]]
        request["operations"] = []
        before = self.documents()
        result = self.ok(self.invoke(api, "previewSelection", **request))["data"]
        self.assertEqual(result["beforeGraph"], result["afterGraph"])
        self.assertEqual(len(result["rejectedCandidates"]), 2)
        self.assertEqual(self.documents(), before)

    def test_previews_do_not_hold_a_revision_lock_for_later_save(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context)
        self.ok(self.invoke(api, "previewSelection", **request))
        saved = self.ok(self.invoke(api, "saveDraft", context=context,
            operations=[{"op": "node.update", "id": "n-main",
                         "changes": {"title": "Concurrent human edit"}}]))
        before = self.documents()
        result = self.error(self.invoke(api, "saveDraft", **request), "REVISION_CONFLICT")
        self.assertEqual(result["currentContext"], saved["context"])
        self.assertEqual(self.documents(), before)

    def test_stale_formal_base_is_rejected_by_worker_and_preview(self):
        api = self.api()
        old_context = self.prepare(api)["context"]
        request = self.selection(old_context)
        fresh_context = self.prepare(api)["context"]
        self.publish(api, fresh_context)
        before = self.documents()
        c = CollaborationAPI(self.service, self.ws["workspaceId"], role="C")
        self.error(c.call("validateProposal",
            self.request(context=old_context, proposal=request["proposal"])), "REVISION_CONFLICT")
        refused = self.error(self.invoke(api, "previewSelection", **request), "REVISION_CONFLICT")
        self.assertIsNone(refused["currentContext"]["draftId"])
        self.assertEqual(refused["currentContext"]["baseMapRevision"],
                         self.service.open_workspace(workspace_id=self.ws["workspaceId"])["mapRevision"])
        self.assertEqual(self.documents(), before)

    def test_stale_code_context_is_rejected(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context)
        (self.code / "main.py").write_text("def run():\n    return 3\n")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "TEST fixture next code")
        self.service.open_workspace(workspace_id=self.ws["workspaceId"],
                                    code_revision=git(self.code, "rev-parse", "HEAD"))
        self.error(self.invoke(api, "previewSelection", **request), "STALE_CONTEXT")

    def test_transaction_rechecks_context_after_facade_preflight(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context)
        actual = self.service.preview_candidate_selection

        def race(*args, **kwargs):
            self.service.apply_draft_operations(context["draftId"], operations=[
                {"op": "node.update", "id": "n-main", "changes": {"title": "Another writer"}}],
                expected_draft_revision=context["draftRevision"],
                base_map_revision=context["baseMapRevision"],
                proposal_id=self.service.get_draft(context["draftId"])["proposalId"])
            return actual(*args, **kwargs)

        with patch.object(self.service, "preview_candidate_selection", side_effect=race):
            self.error(self.invoke(api, "previewSelection", **request), "REVISION_CONFLICT")

    def test_immutable_proposal_reuse_is_refused_in_preview(self):
        api = self.api()
        first = self.prepare(api)["context"]
        request = self.selection(first)
        self.ok(self.invoke(api, "saveDraft", **request))
        second = self.prepare(api)["context"]
        reused = self.selection(second)
        before = self.documents()
        self.error(self.invoke(api, "previewSelection", **reused), "VERSION_CONFLICT")
        self.assertEqual(self.documents(), before)

    def test_unknown_evidence_is_kept_unverified(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context, [{"candidateId": "c-unknown", "operations": [
            {"op": "evidence.add", "operationId": "op-unknown", "source": "rule_based",
             "value": {"id": "e-unknown", "kind": "unknown", "content": "Unverified fixture",
                       "reason": "Explicit unknown", "unknownReason": "Not yet checked"}}]}])
        result = self.ok(self.invoke(api, "previewSelection", **request))["data"]
        evidence = next(e for e in result["afterGraph"]["evidence"] if e["id"] == "e-unknown")
        self.assertEqual(evidence["unknownReason"], "Not yet checked")
        self.assert_no_grants(result)

    def test_worker_and_forged_user_cannot_request_selection_preview(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context)
        before = self.documents()
        for role in ("C", "D"):
            worker = CollaborationAPI(self.service, self.ws["workspaceId"], role=role)
            self.error(worker.call("previewSelection", self.request(**request)), "REQUEST_FORBIDDEN")
        self.error(self.invoke(api, "previewSelection",
            auth={**self.auth, "csrf_token": "forged"}, **request), "REQUEST_FORBIDDEN")
        self.assertEqual(self.documents(), before)

    def test_direct_preview_malformed_context_is_controlled(self):
        api = self.api()
        context = self.prepare(api)["context"]
        request = self.selection(context)
        from extensions.architecture_workspace.errors import WorkspaceError
        with self.assertRaises(WorkspaceError) as caught:
            self.service.preview_candidate_selection(context["draftId"],
                proposal=request["proposal"], selection=request["selection"],
                operations=request["operations"], expected_context=[])
        self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_read_only_selection_preview_does_not_revoke_existing_review(self):
        api = self.api()
        context = self.prepare(api)["context"]
        _, reviewed = self.review(api, context)
        before = self.documents()
        self.ok(self.invoke(api, "previewSelection", **self.selection(context)))
        self.assertEqual(self.documents(), before)
        self.ok(self.invoke(api, "publishVersion", context=context,
                            reviewId=reviewed["data"]["reviewId"]))


if __name__ == "__main__":
    unittest.main()
