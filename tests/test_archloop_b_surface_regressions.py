"""Focused adversarial regressions for the opt-in B candidate surfaces.

All sessions, selections and Git repositories are isolated test fixtures. These
checks provide no real project approval or public HTTP integration evidence.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tests import test_archloop_b_surfaces as surface_fixture
from tests import test_archloop_b_service as service_fixture


class ArchitectureSurfaceRegressionTests(unittest.TestCase):
    # Reuse helpers without inheriting/discovering the original test methods.
    setUp = surface_fixture.ArchitectureWorkspaceSurfaceTests.setUp
    tearDown = surface_fixture.ArchitectureWorkspaceSurfaceTests.tearDown
    make_service = surface_fixture.ArchitectureWorkspaceSurfaceTests.make_service
    request = surface_fixture.ArchitectureWorkspaceSurfaceTests.request
    api = surface_fixture.ArchitectureWorkspaceSurfaceTests.api
    invoke = surface_fixture.ArchitectureWorkspaceSurfaceTests.invoke
    ok = surface_fixture.ArchitectureWorkspaceSurfaceTests.ok
    error = surface_fixture.ArchitectureWorkspaceSurfaceTests.error
    prepare = surface_fixture.ArchitectureWorkspaceSurfaceTests.prepare
    documents = surface_fixture.ArchitectureWorkspaceSurfaceTests.documents
    proposal = surface_fixture.ArchitectureWorkspaceSurfaceTests.proposal
    candidates = surface_fixture.ArchitectureWorkspaceSurfaceTests.candidates
    review = surface_fixture.ArchitectureWorkspaceSurfaceTests.review
    publish = surface_fixture.ArchitectureWorkspaceSurfaceTests.publish

    def reject_batch(self, api, context, *, number, count=1):
        candidates = [{"candidateId": f"fixture-reject-{number}-{i}", "operations": [{
            "operationId": f"fixture-operation-{number}-{i}", "op": "node.update",
            "id": "n-main", "changes": {"title": f"Unapplied fixture {number}/{i}"},
            "source": "rule_based"}]} for i in range(count)]
        proposal = self.proposal(context, candidates, proposal_id=f"fixture-packet-{number}")
        selection = [{"candidateId": item["candidateId"], "decision": "reject",
                      "operationIds": [], "reason": f"Fixture rejection {number}"}
                     for item in candidates]
        return self.invoke(api, "saveDraft", context=context, proposal=proposal,
                           selection=selection, operations=[])

    def preview(self, api, context):
        draft = self.service.get_draft(context["draftId"])
        return self.invoke(api, "previewReview", context=context,
            reason="TEST ONLY: fixture review", coverage=service_fixture.all_coverage(draft["graph"]),
            limits=["Isolated regression fixture"], verifyCode=False)

    def test_other_draft_publication_invalidates_editability_and_retry_projection(self):
        api = self.api()
        older = self.prepare(api)["context"]
        newer = self.prepare(api)["context"]
        self.review(api, older)
        self.publish(api, newer)
        view = self.ok(self.invoke(api, "readView", draftId=older["draftId"]))
        self.assertFalse(view["data"]["contextCurrent"])
        self.assertFalse(view["data"]["canEditThisDraft"])
        self.assertNotEqual(view["context"]["baseMapRevision"],
                            view["data"]["workspaceContext"]["baseMapRevision"])
        status = self.ok(self.invoke(api, "publicationStatus", draftId=older["draftId"]))
        self.assertFalse(status["data"]["contextCurrent"])
        self.assertFalse(status["data"]["canRetry"])
        self.assertEqual(status["data"]["recovery"], "context_refresh_required")
        before = self.documents()
        self.error(self.invoke(api, "saveDraft", context=older, operations=[{
            "op": "node.update", "id": "n-main", "changes": {"title": "Stale edit"}}]),
            "REVISION_CONFLICT")
        self.assertEqual(self.documents(), before)

    def test_reject_all_after_accept_invalidates_approval_and_retains_review_reasons(self):
        api = self.api()
        prepared = self.prepare(api)
        context = prepared["context"]
        _, accepted = self.review(api, context)
        saved = self.ok(self.reject_batch(api, context, number=1, count=2))
        self.assertEqual(saved["context"]["draftRevision"], 2)
        self.assertEqual(saved["data"]["draft"]["status"], "unconfirmed")
        self.assertNotIn("reviewId", saved["data"]["draft"])
        self.assertEqual(saved["data"]["draft"]["graph"], prepared["data"]["draft"]["graph"])
        self.assertEqual(saved["data"]["draft"]["operations"], [])
        before = self.documents()
        self.error(self.invoke(api, "publishVersion", context=context,
            reviewId=accepted["data"]["reviewId"]), "REVISION_CONFLICT")
        self.assertEqual(self.documents(), before)
        preview = self.ok(self.preview(api, saved["context"]))
        reasons = preview["data"]["preview"]["rejectedCandidates"]
        self.assertEqual(len(reasons), 2)
        self.assertEqual({item["reason"] for item in reasons}, {"Fixture rejection 1"})

    def test_reused_proposal_id_with_second_draft_basis_rolls_back_atomically(self):
        api = self.api()
        first = self.prepare(api)["context"]
        second = self.prepare(api)["context"]
        original = self.proposal(first, self.candidates()[:1], proposal_id="fixture-fixed-packet")
        reject = [{"candidateId": "c-responsibility", "decision": "reject", "operationIds": [],
                   "reason": "Fixture decline original"}]
        self.ok(self.invoke(api, "saveDraft", context=first, proposal=original,
                            selection=reject, operations=[]))
        changed = copy.deepcopy(self.candidates()[:1])
        changed[0]["operations"][0]["changes"]["responsibility"] = "Replaced fixture body"
        replacement = self.proposal(second, changed, proposal_id="fixture-fixed-packet")
        before = self.documents()
        self.error(self.invoke(api, "saveDraft", context=second, proposal=replacement,
            selection=reject, operations=[]), "VERSION_CONFLICT")
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.service.get_draft(second["draftId"])["draftRevision"], 1)
        with self.service.store.transaction() as db:
            from extensions.architecture_workspace.storage import Store
            fixed = Store.get(db, "candidate_proposal", self.ws["workspaceId"] + "/fixture-fixed-packet")
        self.assertEqual(fixed, original)

    def test_expired_preview_is_pruned_and_cannot_confirm_or_change_state(self):
        api = self.api()
        context = self.prepare(api)["context"]
        with patch("extensions.architecture_workspace.surfaces.time.time", return_value=100):
            preview = self.ok(self.preview(api, context))
        preview_id = preview["data"]["previewId"]
        self.assertIn(preview_id, api._previews)
        before = self.documents()
        with patch("extensions.architecture_workspace.surfaces.time.time", return_value=401):
            self.error(self.invoke(api, "confirmReview", context=context, previewId=preview_id,
                previewDigest=preview["data"]["previewDigest"], decision="accept"),
                "REQUEST_FORBIDDEN")
        self.assertNotIn(preview_id, api._previews)
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.service.get_draft(context["draftId"])["status"], "unconfirmed")

    def test_full_preview_cache_refuses_before_write_then_prunes_expired_slot(self):
        api = self.api()
        context = self.prepare(api)["context"]
        # Cache metadata only: avoids creating 128 previews or Git publications.
        api._previews = {f"fixture-handle-{i}": {"expiresAt": 1000} for i in range(128)}
        before = self.documents()
        with patch("extensions.architecture_workspace.surfaces.time.time", return_value=100):
            self.error(self.preview(api, context), "INVALID_INPUT")
            self.assertEqual(self.documents(), before)
            api._previews["fixture-handle-0"]["expiresAt"] = 99
            preview = self.ok(self.preview(api, context))
        self.assertNotIn("fixture-handle-0", api._previews)
        self.assertIn(preview["data"]["previewId"], api._previews)
        self.assertEqual(len(api._previews), 128)

    def test_cumulative_rejection_limit_refuses_second_batch_without_trapping_review(self):
        api = self.api()
        first = self.ok(self.reject_batch(api, self.prepare(api)["context"], number=1, count=65))
        before = self.documents()
        self.error(self.reject_batch(api, first["context"], number=2, count=65), "INVALID_INPUT")
        self.assertEqual(self.documents(), before)
        current = self.service.get_draft(first["context"]["draftId"])
        self.assertEqual(current["draftRevision"], 2)
        self.assertEqual(sum(len(item["rejectedCandidates"]) for item in current["candidateSelections"]), 65)
        preview = self.ok(self.preview(api, first["context"]))
        self.assertEqual(len(preview["data"]["preview"]["rejectedCandidates"]), 65)


if __name__ == "__main__":
    unittest.main()
