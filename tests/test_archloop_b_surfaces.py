"""Opt-in B facade boundaries with real Git and durable state.

All actors, proposals and repositories here are isolated fixtures. These tests
do not constitute approval of a real ProjectMind model or A/C/D integration.
"""
from __future__ import annotations

import copy
import json
import subprocess
import unittest
from unittest.mock import patch

from extensions.architecture_workspace import HumanReviewGateway, WorkspaceError, WorkspaceService
from extensions.architecture_workspace.proposals import API_VERSION
from extensions.architecture_workspace.schema import digest
from extensions.architecture_workspace.surfaces import (
    CollaborationAPI, UserWorkspaceAPI, workspace_context,
)
from tests import test_archloop_b_service as fixture_module

all_coverage = fixture_module.all_coverage
git = fixture_module.git
sample_graph = fixture_module.sample_graph


class ArchitectureWorkspaceSurfaceTests(unittest.TestCase):
    # Reuse setup only; inheriting Fixture would silently repeat its full suite.
    setUp = fixture_module.ArchitectureWorkspaceTests.setUp
    tearDown = fixture_module.ArchitectureWorkspaceTests.tearDown
    make_service = fixture_module.ArchitectureWorkspaceTests.make_service

    def request(self, **values):
        return {"apiVersion": API_VERSION, "requestId": "fixture-request", **values}

    def api(self, workspace=None, *, service=None, gateway=None):
        return UserWorkspaceAPI(service or self.service, gateway or self.gateway,
                                (workspace or self.ws)["workspaceId"])

    def invoke(self, api, action, *, auth=None, **values):
        result = api.call(action, self.request(**values), auth=auth or self.auth)
        self.assertEqual(result["apiVersion"], API_VERSION)
        return result

    def ok(self, result):
        self.assertNotIn("error", result, result)
        return result

    def error(self, result, code=None):
        self.assertIn("error", result, result)
        if code is not None:
            self.assertEqual(result["error"]["code"], code, result)
        return result

    def prepare(self, api=None, ws=None, graph=None):
        api = api or self.api()
        return self.ok(self.invoke(api, "prepareDraft", context=workspace_context(ws or self.ws),
                                   graph=graph or self.graph, origin="manual"))

    def documents(self):
        with self.service.store.transaction() as db:
            return list(db.execute("SELECT kind,id,body FROM documents ORDER BY kind,id"))

    def proposal(self, context, candidates, *, kind="patch", proposal_id="fixture-c-patch"):
        proposal = {"apiVersion": API_VERSION, "proposalId": proposal_id, "kind": kind,
                    "basis": copy.deepcopy(context), "generation": {
                        "source": "rule_based", "runId": "fixture-c-run", "fixtureOnly": True},
                    "candidates": copy.deepcopy(candidates), "unknowns": []}
        proposal["proposalDigest"] = digest(proposal)
        return proposal

    def candidates(self):
        return [
            {"candidateId": "c-responsibility", "operations": [{"operationId": "op-role",
                "op": "node.update", "id": "n-main", "changes": {
                    "responsibility": "Proposed fixture responsibility"}, "source": "rule_based"}]},
            {"candidateId": "c-step", "operations": [{"operationId": "op-step",
                "op": "step.update", "id": "s-one", "processId": "p-flow",
                "changes": {"title": "Proposed step"}, "source": "rule_based"}]},
            {"candidateId": "c-remove", "operations": [{"operationId": "op-remove",
                "op": "node.remove", "id": "n-util", "source": "rule_based"}]},
        ]

    def review(self, api, context, *, decision="accept"):
        draft = self.service.get_draft(context["draftId"])
        preview = self.ok(self.invoke(api, "previewReview", context=context,
            reason="TEST ONLY: simulated local operator review", coverage=all_coverage(draft["graph"]),
            limits=["Isolated fixture; not real project approval"], verifyCode=False))
        confirmed = self.ok(self.invoke(api, "confirmReview", context=context,
            previewId=preview["data"]["previewId"], previewDigest=preview["data"]["previewDigest"],
            decision=decision))
        return preview, confirmed

    def publish(self, api, context):
        preview, reviewed = self.review(api, context)
        published = self.ok(self.invoke(api, "publishVersion", context=context,
                                        reviewId=reviewed["data"]["reviewId"]))
        return preview, reviewed, published

    def assert_no_grants(self, public, private_values=()):
        prohibited = {"confirmationToken", "publicationToken", "sessionId", "csrfToken",
                      "tokenHash", "sessionBinding"}

        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & prohibited, value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(public)
        serialized = json.dumps(public, sort_keys=True)
        for secret in private_values:
            self.assertNotIn(secret, serialized)

    def test_c_validation_never_saves_candidate_or_changes_draft_or_git(self):
        prepared = self.prepare()
        context = prepared["context"]
        proposal = self.proposal(context, self.candidates())
        before = self.documents()
        original = self.service.get_draft(context["draftId"])
        heads = [git(repo, "rev-parse", "HEAD") for repo in (self.code, self.arch)]
        worker = CollaborationAPI(self.service, self.ws["workspaceId"], role="C")
        result = self.ok(worker.call("validateProposal", self.request(context=context, proposal=proposal)))
        self.assertFalse(result["data"]["writePerformed"])
        self.assertEqual(result["data"]["selectedPatchGraphValidation"], "deferred_to_atomic_save")
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.service.get_draft(context["draftId"]), original)
        self.assertEqual([git(repo, "rev-parse", "HEAD") for repo in (self.code, self.arch)], heads)

    def test_accept_modify_reject_save_records_actual_selection_and_review_reason(self):
        api = self.api()
        context = self.prepare(api)["context"]
        candidates = self.candidates()
        proposal = self.proposal(context, candidates)
        operations = [copy.deepcopy(candidates[0]["operations"][0]),
                      copy.deepcopy(candidates[1]["operations"][0])]
        operations[1]["source"] = "human"
        operations[1]["changes"] = {"title": "Human corrected step"}
        selection = [
            {"candidateId": "c-responsibility", "decision": "accept", "operationIds": ["op-role"]},
            {"candidateId": "c-step", "decision": "modify", "operationIds": ["op-step"]},
            {"candidateId": "c-remove", "decision": "reject", "operationIds": [],
             "reason": "Utility is still required by the fixture process"},
        ]
        saved = self.ok(self.invoke(api, "saveDraft", context=context, proposal=proposal,
                                    selection=selection, operations=operations))
        self.assertEqual(saved["context"]["draftRevision"], 2)
        draft = saved["data"]["draft"]
        self.assertNotEqual(draft["proposalId"], proposal["proposalId"])
        self.assertEqual(draft["operations"], operations)
        self.assertEqual(draft["graph"]["nodes"][0]["responsibility"], "Proposed fixture responsibility")
        self.assertEqual(draft["graph"]["processes"][0]["steps"][0]["title"], "Human corrected step")
        self.assertIn("n-util", [n["id"] for n in draft["graph"]["nodes"]])
        reopened = self.make_service().get_draft(context["draftId"])
        self.assertEqual(reopened["candidateSelections"][0]["selection"], selection)
        preview, _, published = self.publish(api, saved["context"])
        rejected = preview["data"]["preview"]["rejectedCandidates"]
        self.assertEqual(rejected[0]["reason"], selection[2]["reason"])
        packet = published["data"]["versionEnvelope"]["version"]
        self.assertEqual(packet["review"]["rejectedCandidates"], rejected)
        self.assertEqual(packet["review"]["appliedOperations"], operations)

    def test_all_reject_saves_revision_and_durable_audit_without_changing_graph(self):
        api = self.api()
        prepared = self.prepare(api)
        proposal = self.proposal(prepared["context"], self.candidates())
        selection = [{"candidateId": candidate["candidateId"], "decision": "reject",
                      "operationIds": [], "reason": "TEST fixture candidate rejected"}
                     for candidate in proposal["candidates"]]
        result = self.ok(self.invoke(api, "saveDraft", context=prepared["context"], proposal=proposal,
                                     selection=selection, operations=[]))
        self.assertEqual(result["context"]["draftRevision"], 2)
        draft = self.make_service().get_draft(result["context"]["draftId"])
        self.assertEqual(draft["graph"], prepared["data"]["draft"]["graph"])
        self.assertEqual(draft["operations"], [])
        self.assertEqual(len(draft["candidateSelections"][0]["rejectedCandidates"]), 3)
        self.assertTrue(any(row[0] == "candidate_selection" for row in self.documents()))

    def test_rejected_operation_cannot_be_smuggled_into_save(self):
        api = self.api()
        context = self.prepare(api)["context"]
        candidate = self.candidates()[0]
        proposal = self.proposal(context, [candidate])
        before = self.documents()
        self.error(self.invoke(api, "saveDraft", context=context, proposal=proposal,
            selection=[{"candidateId": candidate["candidateId"], "decision": "reject",
                        "operationIds": [], "reason": "Do not apply"}],
            operations=candidate["operations"]), "INVALID_INPUT")
        self.assertEqual(self.documents(), before)

    def test_bad_batch_rolls_back_draft_and_fixed_proposal_record(self):
        api = self.api()
        context = self.prepare(api)["context"]
        candidates = [self.candidates()[0], self.candidates()[2]]
        proposal = self.proposal(context, candidates)
        before = self.documents()
        head = git(self.arch, "rev-parse", "HEAD")
        result = self.invoke(api, "saveDraft", context=context, proposal=proposal,
            selection=[{"candidateId": c["candidateId"], "decision": "accept",
                        "operationIds": [o["operationId"] for o in c["operations"]]} for c in candidates],
            operations=[o for c in candidates for o in c["operations"]])
        self.error(result, "REFERENCE_CONFLICT")
        self.assertEqual(self.documents(), before)
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), head)

    def test_stale_basis_returns_complete_current_context_for_authorized_scope(self):
        api = self.api()
        old = self.prepare(api)["context"]
        proposal = self.proposal(old, [self.candidates()[0]])
        newer = self.ok(self.invoke(api, "saveDraft", context=old, operations=[{
            "op": "node.update", "id": "n-main", "changes": {"title": "Newer title"}}]))
        worker = CollaborationAPI(self.service, self.ws["workspaceId"], role="C")
        result = self.error(worker.call("validateProposal", self.request(context=old, proposal=proposal)),
                            "REVISION_CONFLICT")
        self.assertEqual(result["currentContext"], newer["context"])
        self.assertEqual(len(result["currentContext"]), 8)
        wrong_proposal = self.error(self.invoke(api, "saveDraft", context=newer["context"],
            proposal=proposal, selection=[{"candidateId": "c-responsibility", "decision": "accept",
                "operationIds": ["op-role"]}], operations=proposal["candidates"][0]["operations"]),
            "STALE_CONTEXT")
        self.assertEqual(wrong_proposal["currentContext"], newer["context"])

    def test_same_session_review_publication_and_replay_never_return_raw_grants(self):
        api = self.api()
        context = self.prepare(api)["context"]
        preview, reviewed, published = self.publish(api, context)
        raw_confirm = api._previews[preview["data"]["previewId"]]["result"]["confirmationToken"]
        raw_publish = api._reviews[reviewed["data"]["reviewId"]]["result"]["publicationToken"]
        public = [preview, reviewed, published,
            self.ok(self.invoke(api, "readView", draftId=context["draftId"])),
            self.ok(self.invoke(api, "publicationStatus", draftId=context["draftId"]))]
        self.assert_no_grants(public, [raw_confirm, raw_publish, self.auth["session_id"], self.auth["csrf_token"]])
        self.assertEqual(published["context"], context)
        self.assertIsNone(published["context"]["baseMapRevision"])
        self.assertIsNotNone(published["data"]["currentVersionRef"]["mapRevision"])
        head = git(self.arch, "rev-parse", "HEAD")
        replay = self.ok(self.invoke(api, "publishVersion", context=context,
                                     reviewId=reviewed["data"]["reviewId"]))
        self.assertEqual(replay["data"], published["data"])
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), head)

    def test_same_actor_other_session_cannot_confirm_preview_or_publish_review(self):
        api = self.api()
        context = self.prepare(api)["context"]
        preview = self.ok(self.invoke(api, "previewReview", context=context, reason="Fixture review",
            coverage=all_coverage(self.graph), limits=["Fixture"], verifyCode=False))
        session = self.gateway.create_session("TEST_HUMAN_FIXTURE", **self.boundary)
        foreign_auth = {**self.boundary, "session_id": session["sessionId"], "csrf_token": session["csrfToken"]}
        confirmation = {"context": context, "previewId": preview["data"]["previewId"],
                        "previewDigest": preview["data"]["previewDigest"], "decision": "accept"}
        self.error(self.invoke(api, "confirmReview", auth=foreign_auth, **confirmation), "REQUEST_FORBIDDEN")
        reviewed = self.ok(self.invoke(api, "confirmReview", **confirmation))
        before = self.documents()
        self.error(self.invoke(api, "publishVersion", auth=foreign_auth, context=context,
                               reviewId=reviewed["data"]["reviewId"]), "REQUEST_FORBIDDEN")
        self.assertEqual(self.documents(), before)
        status = self.ok(self.invoke(api, "publicationStatus", auth=foreign_auth,
                                     draftId=context["draftId"]))
        self.assertFalse(status["data"]["canRetry"])
        self.assertEqual(status["data"]["recovery"], "awaiting_trusted_recovery")

    def test_changed_draft_invalidates_existing_preview(self):
        api = self.api()
        context = self.prepare(api)["context"]
        preview = self.ok(self.invoke(api, "previewReview", context=context, reason="Fixture review",
            coverage=all_coverage(self.graph), limits=["Fixture"], verifyCode=False))
        saved = self.ok(self.invoke(api, "saveDraft", context=context, operations=[{
            "op": "node.update", "id": "n-main", "changes": {"title": "Edited after preview"}}]))
        stale = self.error(self.invoke(api, "confirmReview", context=context,
            previewId=preview["data"]["previewId"], previewDigest=preview["data"]["previewDigest"],
            decision="accept"), "REVISION_CONFLICT")
        self.assertEqual(stale["currentContext"], saved["context"])
        self.error(self.invoke(api, "confirmReview", context=saved["context"],
            previewId=preview["data"]["previewId"], previewDigest=preview["data"]["previewDigest"],
            decision="accept"), "STALE_CONTEXT")

    def test_restart_does_not_restore_publication_authority_from_review_id(self):
        api = self.api()
        context = self.prepare(api)["context"]
        _, reviewed = self.review(api, context)
        restarted_service = self.make_service()
        gateway = HumanReviewGateway(restarted_service, "http://127.0.0.1:18832")
        session = gateway.create_session("TEST_HUMAN_FIXTURE", **self.boundary)
        auth = {**self.boundary, "session_id": session["sessionId"], "csrf_token": session["csrfToken"]}
        restarted = self.api(service=restarted_service, gateway=gateway)
        status = self.ok(self.invoke(restarted, "publicationStatus", auth=auth, draftId=context["draftId"]))
        self.assertEqual(status["data"]["draftStatus"], "review_approved")
        self.assertEqual(status["data"]["recovery"], "awaiting_trusted_recovery")
        self.assertFalse(status["data"]["canRetry"])
        before = self.documents()
        self.error(self.invoke(restarted, "publishVersion", auth=auth, context=context,
                               reviewId=reviewed["data"]["reviewId"]), "REQUEST_FORBIDDEN")
        self.assertEqual(self.documents(), before)
        self.assert_no_grants(status)

    def test_failed_publication_retains_original_journal_and_same_session_retry(self):
        api = self.api()
        context = self.prepare(api)["context"]
        _, reviewed = self.review(api, context)
        with patch.object(self.service.publisher, "publish", side_effect=WorkspaceError("PUBLICATION_FAILED")):
            self.error(self.invoke(api, "publishVersion", context=context,
                                   reviewId=reviewed["data"]["reviewId"]), "PUBLICATION_FAILED")
        status = self.ok(self.invoke(api, "publicationStatus", draftId=context["draftId"]))
        self.assertEqual(status["data"]["draftStatus"], "publishing")
        self.assertEqual(status["data"]["recovery"], "same_session_retry")
        self.assertTrue(status["data"]["canRetry"])
        self.assert_no_grants(status)
        restarted = self.api(service=self.service, gateway=self.gateway)
        no_grant = self.ok(self.invoke(restarted, "publicationStatus", draftId=context["draftId"]))
        self.assertEqual(no_grant["data"]["recovery"], "awaiting_trusted_recovery")
        self.assertFalse(no_grant["data"]["canRetry"])
        result = self.ok(self.invoke(api, "publishVersion", context=context,
                                     reviewId=reviewed["data"]["reviewId"]))
        self.assertEqual(result["status"], "published")
        self.assertEqual(git(self.arch, "rev-list", "--count", "HEAD"), "2")

    def test_worker_roles_cannot_write_or_read_ungranted_latest_or_exact_version(self):
        api = self.api()
        context = self.prepare(api)["context"]
        _, _, published = self.publish(api, context)
        reference = published["data"]["currentVersionRef"]
        for role in ("C", "D"):
            worker = CollaborationAPI(self.service, self.ws["workspaceId"], role=role)
            before = self.documents()
            for action in ("prepareDraft", "saveDraft", "previewReview", "confirmReview", "publishVersion"):
                self.error(worker.call(action, self.request(context=context)), "REQUEST_FORBIDDEN")
            self.error(worker.call("readExactVersion", self.request(versionRef=reference)), "REQUEST_FORBIDDEN")
            self.error(worker.call("readContext", self.request()), "REQUEST_FORBIDDEN")
            self.assertEqual(self.documents(), before)
        allowed = (reference["mapRevision"],)
        c = CollaborationAPI(self.service, self.ws["workspaceId"], role="C", allowed_map_revisions=allowed)
        d = CollaborationAPI(self.service, self.ws["workspaceId"], role="D", allowed_map_revisions=allowed)
        self.error(c.call("exportExactVersion", self.request(versionRef=reference)), "REQUEST_FORBIDDEN")
        c_read = self.ok(c.call("readExactVersion", self.request(versionRef=reference)))
        d_export = self.ok(d.call("exportExactVersion", self.request(versionRef=reference)))
        self.assertEqual(c_read["data"], d_export["data"])
        self.assertEqual(c_read["data"]["versionEnvelope"], published["data"]["versionEnvelope"])
        altered = {**reference, "verifiedCodeRevision": self.revision}
        self.error(d.call("exportExactVersion", self.request(versionRef=altered)), "STALE_CONTEXT")

    def test_foreign_workspace_and_draft_do_not_leak_current_context_or_graph(self):
        api = self.api()
        own = self.prepare(api)["context"]
        foreign_ws = self.service.open_workspace(mode="planning")
        foreign_draft = self.service.create_draft(foreign_ws["workspaceId"], graph=sample_graph())
        foreign_context = workspace_context(foreign_ws, foreign_draft)
        worker = CollaborationAPI(self.service, self.ws["workspaceId"], role="C")
        for result in [
            self.invoke(api, "prepareDraft", context=workspace_context(foreign_ws), graph=sample_graph(), origin="manual"),
            self.invoke(api, "readView", draftId=foreign_draft["draftId"]),
            worker.call("readContext", self.request(draftId=foreign_draft["draftId"])),
            worker.call("validateProposal", self.request(context=foreign_context,
                proposal=self.proposal(foreign_context, [self.candidates()[0]]))),
            self.invoke(api, "saveDraft", context={**own, "draftId": foreign_draft["draftId"]}, operations=[]),
        ]:
            self.error(result, "REQUEST_FORBIDDEN")
            self.assertNotIn("currentContext", result)
            self.assertNotIn("data", result)
            self.assertNotIn("graph", json.dumps(result))

    def test_expired_session_and_bad_transport_deny_reads_and_writes_without_state_change(self):
        api = self.api()
        context = self.prepare(api)["context"]
        before = self.documents()
        for key, value in (("peer", "10.1.2.3"), ("host", "evil.invalid"),
                           ("origin", None), ("csrf_token", "wrong")):
            self.error(self.invoke(api, "readView", auth={**self.auth, key: value},
                                   draftId=context["draftId"]), "REQUEST_FORBIDDEN")
        self.gateway.sessions[self.auth["session_id"]]["expires"] = 0
        for action, values in (("readView", {"draftId": context["draftId"]}),
                               ("saveDraft", {"context": context, "operations": []})):
            self.error(self.invoke(api, action, **values), "REQUEST_FORBIDDEN")
        self.assertEqual(self.documents(), before)

    def test_malformed_and_non_json_requests_return_controlled_errors(self):
        api = self.api()
        worker = CollaborationAPI(self.service, self.ws["workspaceId"], role="C")
        before = self.documents()
        for request in (None, [], "bad", self.request(unexpected=True),
                        self.request(context={}), self.request(requestId=10),
                        self.request(apiVersion="other"), self.request(value=float("nan"))):
            self.error(api.call("prepareDraft", request, auth=self.auth), "INVALID_INPUT")
            self.error(worker.call("validateProposal", request), "INVALID_INPUT")
        self.error(api.call("arbitrary_action", self.request(), auth=self.auth), "REQUEST_FORBIDDEN")
        self.error(worker.call([], self.request()), "REQUEST_FORBIDDEN")
        self.assertEqual(self.documents(), before)

    def test_planning_publish_associate_code_and_prepare_mixed_draft_preserve_design(self):
        planning_ws = self.service.open_workspace(mode="planning")
        api = self.api(planning_ws)
        context = self.prepare(api, ws=planning_ws, graph=sample_graph())["context"]
        _, _, published = self.publish(api, context)
        old = published["data"]["versionEnvelope"]
        self.assertEqual(old["version"]["status"], "confirmed_design")
        self.assertIsNone(old["version"]["codeRevision"])
        view = self.ok(self.invoke(api, "readView"))
        associated = self.ok(self.invoke(api, "associateCode", context=view["context"],
                                         codeRepoId=self.repo_id, codeRevision=self.revision))
        self.assertEqual(associated["context"]["mode"], "mixed")
        self.assertEqual(associated["context"]["codeRepoId"], self.repo_id)
        self.assertEqual(associated["data"]["applicability"], "not_checked")
        self.assertEqual(self.service.get_version(planning_ws["workspaceId"],
                          old["version"]["mapRevision"]), old)
        mixed = self.ok(self.invoke(api, "prepareDraft", context=associated["context"],
                                    graph=self.graph, origin="manual"))
        self.assertEqual(mixed["status"], "unconfirmed")
        self.assertEqual(mixed["context"]["mode"], "mixed")
        self.assertEqual(mixed["context"]["baseMapRevision"], old["version"]["mapRevision"])
        self.assertNotEqual(mixed["context"]["draftId"], context["draftId"])

    def test_bootstrap_validation_and_selected_graph_prepare_are_separate(self):
        planning_ws = self.service.open_workspace(mode="planning")
        context = workspace_context(planning_ws)
        graph = sample_graph()
        alternative = copy.deepcopy(graph)
        alternative["nodes"][0]["title"] = "Alternate planning candidate"
        proposal = self.proposal(context, [
            {"candidateId": "plan-first", "graph": graph},
            {"candidateId": "plan-second", "graph": alternative}], kind="bootstrap",
            proposal_id="fixture-bootstrap")
        worker = CollaborationAPI(self.service, planning_ws["workspaceId"], role="C")
        before = self.documents()
        self.ok(worker.call("validateProposal", self.request(context=context, proposal=proposal)))
        self.assertEqual(self.documents(), before)
        api = self.api(planning_ws)
        selected = self.ok(self.invoke(api, "prepareDraft", context=context, graph=alternative,
            origin="rule_based", proposal=proposal, selectedCandidateId="plan-second"))
        draft = selected["data"]["draft"]
        self.assertEqual(draft["bootstrapSelection"]["candidateId"], "plan-second")
        self.assertEqual(draft["bootstrapSelection"]["decision"], "accept")
        self.assertEqual(draft["origin"], "rule_based")
        self.assertEqual(draft["graph"]["nodes"][0]["title"], "Alternate planning candidate")
        self.assertIsNone(self.service.open_workspace(workspace_id=planning_ws["workspaceId"])["mapRevision"])

    def test_old_accept_replay_after_new_reject_does_not_claim_publish_authority(self):
        api = self.api()
        context = self.prepare(api)["context"]
        first_preview, first_accept = self.review(api, context)
        _, rejected = self.review(api, context, decision="reject")
        self.assertFalse(rejected["data"]["canPublish"])
        replay = self.ok(self.invoke(api, "confirmReview", context=context,
            previewId=first_preview["data"]["previewId"],
            previewDigest=first_preview["data"]["previewDigest"], decision="accept"))
        self.assertEqual(replay["data"]["reviewId"], first_accept["data"]["reviewId"])
        self.assertFalse(replay["data"]["canPublish"])
        before = self.documents()
        self.error(self.invoke(api, "publishVersion", context=context,
                               reviewId=first_accept["data"]["reviewId"]), "STALE_CONTEXT")
        self.assertEqual(self.documents(), before)
        self.assertEqual(self.service.get_draft(context["draftId"])["status"], "review_rejected")

    def test_prepare_checks_full_context_again_inside_durable_transaction(self):
        api = self.api()
        old_context = workspace_context(self.ws)
        (self.code / "util.py").write_text("def helper():\n    return 3\n")
        git(self.code, "add", ".")
        git(self.code, "commit", "-m", "fixture concurrent code revision")
        next_revision = git(self.code, "rev-parse", "HEAD")
        original_create = self.service.create_draft

        def interleave(*args, **kwargs):
            other_service = self.make_service()
            other_service.open_workspace(workspace_id=self.ws["workspaceId"], code_revision=next_revision)
            return original_create(*args, **kwargs)

        with patch.object(self.service, "create_draft", side_effect=interleave):
            result = self.error(self.invoke(api, "prepareDraft", context=old_context,
                graph=self.graph, origin="manual"), "STALE_CONTEXT")
        self.assertEqual(result["currentContext"]["codeRevision"], next_revision)
        self.assertIsNone(result["currentContext"]["draftId"])
        self.assertFalse(any(kind in ("draft", "candidate_proposal") for kind, _, _ in self.documents()))

    def test_open_checks_full_context_before_applying_new_target_revision(self):
        api = self.api()
        old_context = workspace_context(self.ws)
        revisions = []
        for number in (3, 4):
            (self.code / "util.py").write_text(f"def helper():\n    return {number}\n")
            git(self.code, "add", ".")
            git(self.code, "commit", "-m", f"fixture code revision {number}")
            revisions.append(git(self.code, "rev-parse", "HEAD"))
        original_open = self.service.open_workspace

        def interleave(*args, **kwargs):
            self.make_service().open_workspace(workspace_id=self.ws["workspaceId"], code_revision=revisions[0])
            return original_open(*args, **kwargs)

        with patch.object(self.service, "open_workspace", side_effect=interleave):
            result = self.error(self.invoke(api, "openWorkspace", context=old_context,
                                            targetCodeRevision=revisions[1]), "STALE_CONTEXT")
        self.assertEqual(result["currentContext"]["codeRevision"], revisions[0])
        self.assertEqual(self.service.open_workspace(workspace_id=self.ws["workspaceId"])["codeRevision"], revisions[0])

    def test_actual_second_clone_import_checks_entire_exact_reference_before_writes(self):
        api = self.api()
        context = self.prepare(api)["context"]
        _, _, published = self.publish(api, context)
        reference = published["data"]["currentVersionRef"]
        clone = self.root / "facade-receiver"
        subprocess.run(["git", "clone", str(self.arch), str(clone)], check=True, capture_output=True)
        receiver_service = WorkspaceService(self.root / "facade-receiver-state", code_repositories=[self.code],
            architecture_repo=clone, architecture_branch="architecture/candidates/fixture")
        receiver_ws = receiver_service.open_workspace(mode="existing_project", map_id=self.ws["mapId"],
            code_repo_id=self.repo_id, code_revision=self.revision)
        receiver_gateway = HumanReviewGateway(receiver_service, "http://127.0.0.1:18832")
        session = receiver_gateway.create_session("TEST_RECEIVER_FIXTURE", **self.boundary)
        auth = {**self.boundary, "session_id": session["sessionId"], "csrf_token": session["csrfToken"]}
        receiver = UserWorkspaceAPI(receiver_service, receiver_gateway, receiver_ws["workspaceId"],
                                     source_registration_id="fixture-architecture-source")
        request = {"context": workspace_context(receiver_ws),
                   "sourceRegistrationId": "fixture-architecture-source", "versionRef": reference}

        def receiver_documents():
            with receiver_service.store.transaction() as db:
                return list(db.execute("SELECT kind,id,body FROM documents ORDER BY kind,id"))

        before = receiver_documents()
        self.error(self.invoke(receiver, "importExactVersion", auth=auth,
            **{**request, "sourceRegistrationId": "unregistered-source"}), "REQUEST_FORBIDDEN")
        for key, bad in (("verifiedCodeRevision", self.revision), ("mapSourceRevision", "0" * 40),
                         ("mapId", "foreign-map"), ("codeRevision", "0" * 40),
                         ("codeRepoId", "foreign-code-source")):
            altered = {**reference, key: bad}
            self.error(self.invoke(receiver, "importExactVersion", auth=auth, **{**request, "versionRef": altered}))
            self.assertEqual(receiver_documents(), before, key)
        imported = self.ok(self.invoke(receiver, "importExactVersion", auth=auth, **request))
        self.assertEqual(imported["status"], "imported")
        self.assertEqual(imported["data"]["currentVersionRef"], reference)
        received = imported["data"]["versionEnvelope"]
        self.assertEqual(received["version"], published["data"]["versionEnvelope"]["version"])
        self.assertEqual(received["provenance"]["mapSourceRevision"], reference["mapSourceRevision"])
        # Reader-local trust limits are provenance, not immutable packet data.
        self.assertTrue(received["provenance"]["limits"])
        self.assertEqual(git(clone, "rev-parse", "HEAD"), reference["mapSourceRevision"])
        self.assert_no_grants(imported)


if __name__ == "__main__":
    unittest.main()
