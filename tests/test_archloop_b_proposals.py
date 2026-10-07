"""Adversarial checks for pure proposal validation and deterministic selection."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from extensions.architecture_workspace.errors import WorkspaceError
from extensions.architecture_workspace.proposals import (
    API_VERSION, validate_context, validate_proposal, compile_selection)
from extensions.architecture_workspace.schema import digest


def signed(proposal):
    proposal = copy.deepcopy(proposal)
    proposal["proposalDigest"] = digest({k: v for k, v in proposal.items()
                                         if k != "proposalDigest"})
    return proposal


def node(value_id="node-added"):
    return {"id": value_id, "title": "Candidate title", "responsibility": "Candidate purpose",
            "implementationStatus": "planned", "interfaces": [], "evidenceIds": []}


class ProposalContractTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "extensions" / "architecture_workspace" / "examples" / "two-surface-v2-design.json"
        sample = json.loads(path.read_text())
        self.proposal = sample["proposalFromC"]
        self.context = sample["saveFromA"]["context"]
        self.selection = sample["saveFromA"]["selection"]
        self.operations = sample["saveFromA"]["operations"]
        self.bootstrap = sample["proposalBootstrapFromC"]

    def assert_error(self, fn, code="INVALID_INPUT"):
        with self.assertRaises(WorkspaceError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def single(self, operation):
        return signed({**self.proposal, "candidates": [{"candidateId": "candidate-single",
                                                       "operations": [operation]}]})

    def decision(self, operation, decision="accept"):
        return [{"candidateId": "candidate-single", "decision": decision,
                 "operationIds": [operation["operationId"]]}]

    def test_illustrated_patch_selection_and_bootstrap_validate(self):
        self.assertEqual(validate_proposal(self.proposal, self.context), self.proposal)
        self.assertEqual(validate_proposal(self.bootstrap, self.bootstrap["basis"]), self.bootstrap)
        result = compile_selection(self.proposal, self.context, self.selection, self.operations)
        self.assertEqual(result["operations"], self.operations)
        self.assertEqual(result["selection"], self.selection)
        self.assertEqual(result["rejectedCandidates"], [{"proposalId": "proposal-demo",
            "candidateId": "candidate-remove", "reason": "Keep the functional boundary"}])

    def test_context_strict_fields_and_copy(self):
        result = validate_context(self.context)
        result["workspaceId"] = "another-workspace"
        self.assertEqual(self.context["workspaceId"], "workspace-demo")
        for key in self.context:
            with self.subTest(missing=key):
                value = {k: v for k, v in self.context.items() if k != key}
                self.assert_error(lambda: validate_context(value))
        self.assert_error(lambda: validate_context({**self.context, "authority": True}))

    def test_context_rejects_invalid_identity_sha_draft_and_hash(self):
        for key, value in (("workspaceId", "../workspace"), ("mapId", ""),
                           ("codeRepoId", None), ("codeRevision", "HEAD"),
                           ("baseMapRevision", "sha256:1"), ("draftRevision", True),
                           ("draftRevision", 0), ("draftRevision", None),
                           ("mode", "unknown")):
            with self.subTest(key=key, value=value):
                self.assert_error(lambda: validate_context({**self.context, key: value}))
        self.assert_error(lambda: validate_context({**self.context, "draftId": None}))

    def test_planning_context_has_null_code_and_no_draft_pair(self):
        context = self.bootstrap["basis"]
        self.assertEqual(validate_context(context), context)
        self.assert_error(lambda: validate_context({**context, "codeRepoId": "repo"}), "STALE_CONTEXT")
        self.assert_error(lambda: validate_context({**context, "codeRevision": "1" * 40}), "STALE_CONTEXT")
        self.assert_error(lambda: validate_context({**context, "draftRevision": 1}))

    def test_mixed_context_after_code_association_requires_fixed_code_identity(self):
        context = {**self.context, "mode": "mixed"}
        self.assertEqual(validate_context(context), context)
        for change in ({"codeRepoId": None}, {"codeRevision": None},
                       {"codeRevision": "main"}, {"codeRepoId": "../repo"}):
            self.assert_error(lambda: validate_context({**context, **change}))
        proposal = signed({**self.proposal, "basis": context})
        self.assertEqual(validate_proposal(proposal, context), proposal)

    def test_mixed_bootstrap_retains_design_and_accepts_bound_code_evidence(self):
        context = {**self.context, "mode": "mixed", "draftId": None, "draftRevision": None,
                   "baseMapRevision": "sha256:" + "3" * 64}
        proposal = copy.deepcopy(self.bootstrap)
        proposal["basis"] = context
        graph = proposal["candidates"][0]["graph"]
        graph["evidence"].append({"id": "code-bound", "kind": "code", "path": "main.py",
            "codeRepoId": context["codeRepoId"], "codeRevision": context["codeRevision"],
            "reason": "Fixed code association; not proof of runtime behavior"})
        graph["nodes"][0]["evidenceIds"].append("code-bound")
        self.assertEqual(validate_proposal(signed(proposal), context)["basis"], context)
        graph["evidence"][-1]["codeRepoId"] = "another-repository"
        self.assert_error(lambda: validate_proposal(signed(proposal), context), "EVIDENCE_MISMATCH")

    def test_packet_tamper_fails_digest_without_mutation(self):
        original = copy.deepcopy(self.proposal)
        tampered = copy.deepcopy(self.proposal)
        tampered["unknowns"] = []
        self.assert_error(lambda: validate_proposal(tampered, self.context), "EVIDENCE_MISMATCH")
        self.assertEqual(original, self.proposal)
        self.assertEqual(tampered["unknowns"], [])

    def test_every_basis_field_must_match_current_context(self):
        replacements = {"workspaceId": "other", "mapId": "other", "codeRepoId": "other",
                        "codeRevision": "2" * 40, "baseMapRevision": "sha256:" + "2" * 64,
                        "draftId": "other", "draftRevision": 2}
        for key, value in replacements.items():
            with self.subTest(key=key):
                proposal = copy.deepcopy(self.proposal)
                proposal["basis"][key] = value
                self.assert_error(lambda: validate_proposal(signed(proposal), self.context), "STALE_CONTEXT")

    def test_packet_and_generation_unknown_fields_are_rejected(self):
        self.assert_error(lambda: validate_proposal(signed({**self.proposal, "publish": True}), self.context))
        for key, value in (("source", "human"), ("source", "legacy"),
                           ("runId", None), ("fixtureOnly", "false")):
            proposal = copy.deepcopy(self.proposal)
            proposal["generation"][key] = value
            self.assert_error(lambda: validate_proposal(signed(proposal), self.context))
        proposal = copy.deepcopy(self.proposal)
        proposal["generation"]["model"] = "unfrozen-field"
        self.assert_error(lambda: validate_proposal(signed(proposal), self.context))

    def test_wrong_api_version_and_nonlist_unknowns(self):
        self.assert_error(lambda: validate_proposal(signed({**self.proposal, "apiVersion": "v1"}), self.context))
        self.assert_error(lambda: validate_proposal(signed({**self.proposal, "unknowns": "unknown"}), self.context))

    def test_ai_generation_requires_matching_operation_sources(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["generation"]["source"] = "ai_generated"
        self.assert_error(lambda: validate_proposal(signed(proposal), self.context))
        for candidate in proposal["candidates"]:
            for operation in candidate["operations"]:
                operation["source"] = "ai_generated"
        self.assertEqual(validate_proposal(signed(proposal), self.context)["generation"]["source"], "ai_generated")

    def test_candidate_and_operation_ids_are_global_unique(self):
        for target in ("candidate", "operation"):
            proposal = copy.deepcopy(self.proposal)
            if target == "candidate":
                proposal["candidates"][1]["candidateId"] = proposal["candidates"][0]["candidateId"]
            else:
                proposal["candidates"][1]["operations"][0]["operationId"] = proposal["candidates"][0]["operations"][0]["operationId"]
            self.assert_error(lambda: validate_proposal(signed(proposal), self.context))

    def test_patch_requires_draft_but_bootstrap_does_not(self):
        context = {**self.context, "draftId": None, "draftRevision": None}
        proposal = signed({**self.proposal, "basis": context})
        self.assert_error(lambda: validate_proposal(proposal, context), "STALE_CONTEXT")
        self.assert_error(lambda: compile_selection(self.bootstrap, self.bootstrap["basis"], [], []))

    def test_bootstrap_cannot_mix_operations_or_invalid_graph(self):
        for kind in ("mix", "invalid"):
            proposal = copy.deepcopy(self.bootstrap)
            if kind == "mix":
                proposal["candidates"][0]["operations"] = []
            else:
                proposal["candidates"][0]["graph"]["nodes"][0]["implementationStatus"] = "implemented"
            self.assert_error(lambda: validate_proposal(signed(proposal), proposal["basis"]),
                              "EVIDENCE_MISMATCH" if kind == "invalid" else "INVALID_INPUT")

    def test_bootstrap_cannot_reuse_an_existing_draft_context(self):
        for mode in ("planning", "existing_project", "mixed"):
            with self.subTest(mode=mode):
                context = {**self.bootstrap["basis"], "draftId": "already-existing", "draftRevision": 1}
                if mode != "planning":
                    context.update(mode=mode, codeRepoId=self.context["codeRepoId"],
                                   codeRevision=self.context["codeRevision"])
                proposal = signed({**self.bootstrap, "basis": context})
                self.assert_error(lambda: validate_proposal(proposal, context), "STALE_CONTEXT")

    def test_operation_shape_no_unknown_fields_or_missing_stable_ids(self):
        original = self.proposal["candidates"][0]["operations"][0]
        bad = [{**original, "value": {}}, {k: v for k, v in original.items() if k != "operationId"},
               {**original, "op": "node.reorder", "value": []},
               {"operationId": "add", "source": "rule_based", "op": "node.add", "value": {}}]
        for operation in bad:
            self.assert_error(lambda: validate_proposal(self.single(operation), self.context))

    def test_add_values_are_typed_without_existing_reference_assumptions(self):
        operation = {"operationId": "add", "source": "rule_based", "op": "node.add", "value": node()}
        proposal = self.single(operation)
        self.assertEqual(validate_proposal(proposal, self.context), proposal)
        # References may be satisfied by other selected operations; no write or
        # fake dependency inference belongs to structural candidate validation.
        operation = {"operationId": "edge", "source": "rule_based", "op": "edge.add",
                     "value": {"id": "edge-new", "from": "node-added", "to": "node-later",
                               "type": "functional_collaboration", "label": "Depends", "evidenceIds": []}}
        self.assertEqual(validate_proposal(self.single(operation), self.context)["candidates"][0]["operations"][0], operation)

    def test_unknown_or_stable_id_update_fields_are_rejected(self):
        for changes in ({"id": "new"}, {"authority": True}, {}, {"evidenceIds": ["same", "same"]},
                        {"interfaces": [{"id": "bad"}]}):
            operation = {"operationId": "update", "source": "rule_based", "op": "node.update",
                         "id": "node-demo", "changes": changes}
            self.assert_error(lambda: validate_proposal(self.single(operation), self.context))

    def test_code_evidence_shape_and_identity_mismatch(self):
        value = {"id": "e-code", "kind": "code", "reason": "Fixed source", "path": "src/main.py",
                 "codeRepoId": self.context["codeRepoId"], "codeRevision": self.context["codeRevision"],
                 "lineStart": 1, "lineEnd": 2}
        operation = {"operationId": "add-evidence", "source": "rule_based", "op": "evidence.add", "value": value}
        validate_proposal(self.single(operation), self.context)
        for change in ({"path": "../main.py"}, {"codeRepoId": "other"}, {"codeRevision": "HEAD"},
                       {"lineEnd": 0}, {"lineEnd": 1, "lineStart": 2}):
            modified = {**operation, "value": {**value, **change}}
            self.assert_error(lambda: validate_proposal(self.single(modified), self.context), "EVIDENCE_MISMATCH")

    def test_layout_boolean_negative_nonfinite_and_nonjson_are_controlled(self):
        operation = {"operationId": "layout", "source": "rule_based", "op": "layout.set",
                     "value": {"node-demo": {"x": 1, "y": 2}}}
        validate_proposal(self.single(operation), self.context)
        for value in (True, -1, 10 ** 500):
            modified = {**operation, "value": {"node-demo": {"x": value, "y": 2}}}
            self.assert_error(lambda: validate_proposal(self.single(modified), self.context))
        for value in (float("nan"), float("inf"), object()):
            proposal = copy.deepcopy(self.proposal)
            proposal["unknowns"] = [value]
            self.assert_error(lambda: validate_proposal(proposal, self.context))

    def test_oversize_and_recursive_values_are_controlled(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["unknowns"] = ["x" * 2_000_001]
        self.assert_error(lambda: validate_proposal(proposal, self.context))
        nested = []
        nested.append(nested)
        self.assert_error(lambda: validate_proposal(nested, self.context))
        nested = None
        for _ in range(1100):
            nested = [nested]
        self.assert_error(lambda: validate_proposal(nested, self.context))

    def test_total_operations_are_bounded_by_service_batch_limit(self):
        proposal = copy.deepcopy(self.proposal)
        prototype = proposal["candidates"][0]["operations"][0]
        proposal["candidates"] = [{"candidateId": "many", "operations": [
            {**prototype, "operationId": "operation-" + str(n)} for n in range(129)]}]
        self.assert_error(lambda: validate_proposal(signed(proposal), self.context))

    def test_every_candidate_decided_once(self):
        for selection in (self.selection[:-1], self.selection + [self.selection[0]],
                          [{**self.selection[0], "candidateId": "unknown"}, *self.selection[1:]]):
            self.assert_error(lambda: compile_selection(self.proposal, self.context, selection, self.operations))

    def test_accept_cannot_silently_change_candidate(self):
        operations = copy.deepcopy(self.operations)
        operations[0]["changes"]["responsibility"] = "Different"
        self.assert_error(lambda: compile_selection(self.proposal, self.context, self.selection, operations))

    def test_accept_numeric_bool_equality_cannot_replace_json_identity(self):
        operation = {"operationId": "layout", "source": "rule_based", "op": "layout.set",
                     "value": {"node-demo": {"x": 1, "y": 2}}}
        proposal = self.single(operation)
        applied = copy.deepcopy(operation); applied["value"]["node-demo"]["x"] = True
        self.assert_error(lambda: compile_selection(proposal, self.context, self.decision(operation), [applied]))

    def test_modify_requires_human_source_and_preserves_target(self):
        for change in ({"source": "rule_based"}, {"id": "other-step"},
                       {"processId": "other-process"}, {"op": "node.update"},
                       {"operationId": "other-operation"}):
            operations = copy.deepcopy(self.operations)
            operations[1].update(change)
            self.assert_error(lambda: compile_selection(self.proposal, self.context, self.selection, operations))

    def test_modify_reason_optional_but_present_reason_must_be_meaningful(self):
        selection = copy.deepcopy(self.selection)
        del selection[1]["reason"]
        compile_selection(self.proposal, self.context, selection, self.operations)
        selection[1]["reason"] = ""
        self.assert_error(lambda: compile_selection(self.proposal, self.context, selection, self.operations))

    def test_modify_add_preserves_new_object_id(self):
        original = {"operationId": "add", "source": "rule_based", "op": "node.add", "value": node()}
        proposal = self.single(original)
        applied = {**original, "source": "human", "value": {**original["value"], "title": "Corrected"}}
        self.assertEqual(compile_selection(proposal, self.context, self.decision(original, "modify"), [applied])["operations"], [applied])
        applied["value"]["id"] = "node-other"
        self.assert_error(lambda: compile_selection(proposal, self.context, self.decision(original, "modify"), [applied]))

    def test_modify_reorder_preserves_process_and_can_change_order(self):
        original = {"operationId": "order", "source": "rule_based", "op": "step.reorder",
                    "processId": "process-demo", "value": ["step-one", "step-two"]}
        applied = {**original, "source": "human", "value": ["step-two", "step-one"]}
        result = compile_selection(self.single(original), self.context, self.decision(original, "modify"), [applied])
        self.assertEqual(result["operations"], [applied])

    def test_operation_group_cannot_be_partially_accepted(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["candidates"][0]["operations"].append(
            {**proposal["candidates"][0]["operations"][0], "operationId": "group-second"})
        self.assert_error(lambda: compile_selection(signed(proposal), self.context, self.selection, self.operations))

    def test_sequential_same_target_group_cannot_reverse_accepted_or_modified_operations(self):
        first = {"operationId": "title-first", "source": "rule_based", "op": "node.update",
                 "id": "node-demo", "changes": {"title": "First title"}}
        second = {**first, "operationId": "title-second", "changes": {"title": "Final title"}}
        proposal = signed({**self.proposal, "candidates": [{"candidateId": "sequential-titles",
                                                           "operations": [first, second]}]})
        for decision in ("accept", "modify"):
            with self.subTest(decision=decision):
                choice = [{"candidateId": "sequential-titles", "decision": decision,
                           "operationIds": [first["operationId"], second["operationId"]]}]
                operations = copy.deepcopy([first, second])
                if decision == "modify":
                    for operation in operations:
                        operation["source"] = "human"
                    operations[1]["changes"]["title"] = "Human final title"
                result = compile_selection(proposal, self.context, choice, operations)
                self.assertEqual(result["operations"], operations)
                # Both operations remain individually valid; reversing them
                # would nevertheless replace the intended final title.
                self.assert_error(lambda: compile_selection(proposal, self.context, choice,
                                                             list(reversed(operations))))

    def test_cross_candidate_operations_can_interleave_with_group_order_preserved(self):
        operations = [{"operationId": "ordered-" + str(n), "source": "rule_based",
                       "op": "node.update", "id": "node-demo",
                       "changes": {"title": "Title " + str(n)}} for n in range(4)]
        proposal = signed({**self.proposal, "candidates": [
            {"candidateId": "group-a", "operations": operations[:2]},
            {"candidateId": "group-b", "operations": operations[2:]}]})
        selection = [{"candidateId": candidate["candidateId"], "decision": "accept",
                      "operationIds": [o["operationId"] for o in candidate["operations"]]}
                     for candidate in proposal["candidates"]]
        interleaved = [operations[2], operations[0], operations[3], operations[1]]
        result = compile_selection(proposal, self.context, selection, interleaved)
        self.assertEqual(result["operations"], interleaved)

    def test_reject_requires_reason_and_no_applied_operations(self):
        for change in ({"reason": ""}, {"operationIds": ["operation-remove"]}):
            selection = copy.deepcopy(self.selection); selection[2].update(change)
            self.assert_error(lambda: compile_selection(self.proposal, self.context, selection, self.operations))
        operations = self.operations + self.proposal["candidates"][2]["operations"]
        self.assert_error(lambda: compile_selection(self.proposal, self.context, self.selection, operations))

    def test_no_manual_or_duplicate_operation_can_be_smuggled(self):
        for extra in (self.operations[0], {**self.operations[0], "operationId": "manual-extra", "source": "human"}):
            self.assert_error(lambda: compile_selection(self.proposal, self.context, self.selection, self.operations + [extra]))

    def test_actual_operation_order_preserved_and_output_copied(self):
        operations = list(reversed(self.operations))
        result = compile_selection(self.proposal, self.context, list(reversed(self.selection)), operations)
        self.assertEqual(result["operations"], operations)
        result["operations"][0]["changes"]["title"] = "Changed returned copy"
        result["selection"][0]["reason"] = "Changed returned copy"
        self.assertNotEqual(result["operations"], operations)
        self.assertEqual(self.selection[2]["reason"], "Keep the functional boundary")

    def test_all_rejected_is_valid_no_write_batch(self):
        selection = [{"candidateId": c["candidateId"], "decision": "reject", "operationIds": [],
                      "reason": "User declined"} for c in self.proposal["candidates"]]
        result = compile_selection(self.proposal, self.context, selection, [])
        self.assertEqual(result["operations"], [])
        self.assertEqual(len(result["rejectedCandidates"]), 3)

    def test_failures_do_not_mutate_proposal_selection_or_operations(self):
        proposal = copy.deepcopy(self.proposal)
        selection = copy.deepcopy(self.selection)
        operations = copy.deepcopy(self.operations)
        operations[1]["source"] = "ai_generated"
        before = copy.deepcopy((proposal, selection, operations))
        self.assert_error(lambda: compile_selection(proposal, self.context, selection, operations))
        self.assertEqual((proposal, selection, operations), before)

    def test_malformed_packet_types_never_escape_machine_error(self):
        for value in (None, [], "proposal", 1, True):
            with self.subTest(value=value):
                self.assert_error(lambda: validate_context(value))
                self.assert_error(lambda: validate_proposal(value, self.context))
        self.assert_error(lambda: compile_selection(self.proposal, self.context, None, self.operations))
        self.assert_error(lambda: compile_selection(self.proposal, self.context, self.selection, None))


if __name__ == "__main__":
    unittest.main()
