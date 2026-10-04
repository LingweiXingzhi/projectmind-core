"""Independent adversarial resolver tests; no frozen experiment verdicts used."""
from __future__ import annotations

import copy
import json
import random
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from extensions.context_authority.registry import load_registry, save_registry
from extensions.context_authority.resolver import resolve
from extensions.context_authority.schema import ClaimValidationError, validate_claim
from extensions.context_authority.verifiers import (
    build_default_verifiers, make_main_head_verifier, make_pr_head_verifier,
)


def row(cid, value="v", *, key="team.owner", scope="team", ctype="HUMAN_DECISION", **extra):
    return {"id": "claim-" + cid, "key": key, "scope": scope, "type": ctype,
            "value": value, "source": {"kind": "human", "ref": cid}, **extra}


def fact(cid="fact", value=None, **extra):
    return row(cid, {"head": "old"} if value is None else value,
               key=extra.pop("key", "implementation.pr_head"),
               ctype="VERIFIED_FACT", **extra)


def ok(value, **extra):
    return lambda c: {"status": "ok", "value": value, "source_kind": "gh_api",
                      "source_ref": "repos/example/core/pulls/22", "verified_at": "fixed", **extra}


class ResolverAdversarialTests(unittest.TestCase):
    def blocked(self, claims, kind):
        state = resolve(claims)
        self.assertFalse(state["current"])
        self.assertTrue(any(p["kind"] == kind for p in state["registry_problems"]))
        self.assertTrue(state["conflicts"])
        self.assertEqual(state["conflicts"][0]["resolution"], "HUMAN_REQUIRED")
        return state

    def test_a01_three_active_different_values_keep_every_claim(self):
        state = resolve([row("a", 1), row("b", 2), row("c", 3)])
        self.assertFalse(state["current"])
        self.assertEqual(len(state["conflicts"][0]["claims"]), 3)

    def test_a02_two_equal_plus_one_conflicting_does_not_majority_vote(self):
        state = resolve([row("a", 1), row("b", 1), row("c", 2)])
        self.assertFalse(state["current"])
        self.assertEqual(len(state["conflicts"][0]["claims"]), 3)

    def test_a03_supersedes_chain_has_one_survivor_and_full_provenance(self):
        state = resolve([row("a", 1), row("b", 2, supersedes=["claim-a"]),
                         row("c", 3, supersedes=["claim-b"])])
        self.assertEqual(state["current"]["team.owner"]["value"], 3)
        self.assertEqual({s["claim_id"] for s in state["stale"]}, {"claim-a", "claim-b"})

    def test_a04_two_node_cycle_requires_human(self):
        self.blocked([row("a", 1, supersedes=["claim-b"]),
                      row("b", 2, supersedes=["claim-a"])], "CYCLIC_SUPERSEDES")

    def test_a05_three_node_cycle_and_tail_cannot_erase_group(self):
        state = self.blocked([row("a", 1, supersedes=["claim-b"]),
                              row("b", 2, supersedes=["claim-c"]),
                              row("c", 3, supersedes=["claim-a", "claim-d"]),
                              row("d", 4)], "CYCLIC_SUPERSEDES")
        self.assertEqual(len(state["conflicts"][0]["claims"]), 4)

    def test_a06_self_supersedes_requires_human(self):
        self.blocked([row("a", supersedes=["claim-a"])], "SELF_SUPERSEDES")

    def test_a07_broken_edge_cannot_supply_unqualified_current(self):
        self.blocked([row("a", supersedes=["claim-missing"])], "BROKEN_SUPERSEDES")

    def test_a08_duplicate_ids_rejected_by_direct_resolve(self):
        with self.assertRaisesRegex(ValueError, "duplicate claim id"):
            resolve([row("a", 1), row("a", 2)])

    def test_a09_two_distinct_scopes_both_survive_without_global_winner(self):
        state = resolve([row("a", 1, scope="main"), row("b", 2, scope="branch")])
        self.assertNotIn("team.owner", state["current"])
        self.assertEqual({r["scope"]: r["value"] for r in state["current_by_scope"]},
                         {"main": 1, "branch": 2})

    def test_a10_equal_values_in_two_scopes_do_not_erase_scope(self):
        state = resolve([row("a", 1, scope="main"), row("b", 1, scope="branch")])
        self.assertEqual(len(state["current_by_scope"]), 2)
        self.assertNotIn("team.owner", state["current"])

    def test_a11_conflict_in_one_scope_does_not_mask_another_scope(self):
        state = resolve([row("a", 1, scope="a"), row("b", 2, scope="a"), row("c", 3, scope="b")])
        self.assertNotIn("team.owner", state["current"])
        self.assertEqual(state["current_by_scope"][0]["scope"], "b")
        self.assertEqual(state["conflicts"][0]["scope"], "a")

    def test_a12_cross_scope_supersedes_cannot_remove_current(self):
        self.blocked([row("a", 1, scope="a"),
                      row("b", 2, scope="b", supersedes=["claim-a"])], "CROSS_SCOPE_SUPERSEDES")

    def test_a13_cross_key_supersedes_cannot_hide_unrelated_truth(self):
        self.blocked([row("a", 1), row("b", 2, key="team.other", supersedes=["claim-a"])],
                     "CROSS_KEY_SUPERSEDES")

    def test_a14_historical_cannot_supersede_confirmed_decision(self):
        self.blocked([row("a", 1), row("history", 2, ctype="HISTORICAL", supersedes=["claim-a"])],
                     "INVALID_AUTHORITY_SUPERSEDES")

    def test_a15_proposal_cannot_supersede_confirmed_architecture(self):
        self.blocked([row("a", 1, key="architecture.layout"),
                      row("p", 2, key="architecture.layout", ctype="PROPOSAL", supersedes=["claim-a"])],
                     "INVALID_AUTHORITY_SUPERSEDES")

    def test_a16_cross_scope_historical_supersession_keeps_real_superseder(self):
        state = resolve([row("a", 1, scope="old", ctype="HISTORICAL"),
                         row("b", 2, scope="team", supersedes=["claim-a"])])
        self.assertEqual(state["stale"][0]["superseded_by"], ["claim-b"])
        self.assertEqual(state["current"]["team.owner"]["value"], 2)

    def test_a17_many_historical_values_do_not_create_current_conflict(self):
        state = resolve([row("h" + str(i), i, ctype="HISTORICAL") for i in range(100)] + [row("a", 999)])
        self.assertFalse(state["conflicts"])
        self.assertEqual(len(state["historical"]), 100)

    def test_a18_wrong_domain_authority_rejected_in_direct_resolve(self):
        with self.assertRaises(ClaimValidationError):
            resolve([row("a", ctype="VERIFIED_FACT")])

    def test_a19_equal_contract_and_human_sources_are_both_preserved(self):
        state = resolve([row("a"), row("b", ctype="CONTRACT")])
        self.assertEqual({e["source"]["ref"] for e in state["current"]["team.owner"]["evidence"]}, {"a", "b"})

    def test_a20_empty_registry_is_deterministic_and_json_serializable(self):
        self.assertEqual(resolve([]), resolve([]))
        self.assertEqual(resolve([])["counts"]["current"], 0)
        json.dumps(resolve([]), allow_nan=False)

    def test_a21_unavailable_verifier_withholds_current_and_keeps_evidence(self):
        state = resolve([fact()], verifiers={"implementation.pr_head": lambda c: {"status": "unavailable", "reason": "offline"}})
        self.assertFalse(state["current"])
        self.assertEqual(state["verification_unavailable"][0]["source"]["ref"], "fact")
        self.assertEqual(state["stale"][0]["claim_id"], "claim-fact")

    def test_a22_verifier_timeout_is_explicit_unavailable(self):
        def timeout(c):
            raise subprocess.TimeoutExpired("gh", 15)
        state = resolve([fact()], verifiers={"implementation.pr_head": timeout})
        self.assertFalse(state["current"])
        self.assertTrue(state["verification_unavailable"])

    def test_a23_non_dict_verifier_result_is_unavailable(self):
        state = resolve([fact()], verifiers={"implementation.pr_head": lambda c: None})
        self.assertFalse(state["current"])
        self.assertTrue(state["verification_unavailable"])

    def test_a24_missing_value_verifier_result_is_unavailable(self):
        state = resolve([fact()], verifiers={"implementation.pr_head": lambda c: {"status": "ok"}})
        self.assertFalse(state["current"])

    def test_a25_non_json_live_value_is_unavailable(self):
        state = resolve([fact()], verifiers={"implementation.pr_head": ok({"v": float("nan")})})
        self.assertFalse(state["current"])

    def test_a26_live_replacement_keeps_exact_source_and_original_claim(self):
        state = resolve([fact()], verifiers={"implementation.pr_head": ok({"head": "new"})})
        evidence = state["current"]["implementation.pr_head"]["evidence"][0]
        self.assertEqual(evidence["source"]["ref"], "repos/example/core/pulls/22")
        self.assertEqual(evidence["derived_from_ids"], ["claim-fact"])

    def test_a27_matching_live_value_keeps_verification_metadata(self):
        state = resolve([fact()], verifiers={"implementation.pr_head": ok({"head": "old"})})
        self.assertEqual(state["current"]["implementation.pr_head"]["verified_at"], "fixed")
        self.assertEqual(state["current"]["implementation.pr_head"]["evidence"][0]["live_verification"]["source"]["ref"],
                         "repos/example/core/pulls/22")

    def test_a28_sanitized_key_auto_id_collision_cannot_alias_evidence(self):
        state = resolve([fact("a", key="implementation.a_b"), fact("b", key="implementation.a.b")],
                        verifiers={"implementation.a_b": ok(2), "implementation.a.b": ok(3)})
        ids = [r["claim_ids"][0] for r in state["current"].values()]
        self.assertEqual(len(set(ids)), 2)

    def test_a29_auto_id_cannot_impersonate_registered_claim(self):
        state = resolve([fact(), row("auto-implementation-pr-head", key="team.real")],
                        verifiers={"implementation.pr_head": ok(2)})
        self.assertNotEqual(state["current"]["implementation.pr_head"]["claim_ids"], ["claim-auto-implementation-pr-head"])

    def test_a30_two_stale_equal_live_claims_deduplicate_auto_id_with_all_sources(self):
        state = resolve([fact("a"), fact("b")], verifiers={"implementation.pr_head": ok(2)})
        current = state["current"]["implementation.pr_head"]
        self.assertEqual(len(current["claim_ids"]), 1)
        self.assertEqual(current["evidence"][0]["derived_from_ids"], ["claim-a", "claim-b"])

    def test_a31_reordered_invalid_edges_produce_identical_problem_order(self):
        claims = [row("b", supersedes=["claim-x"]), row("a", supersedes=["claim-y"])]
        self.assertEqual(resolve(claims), resolve(claims[::-1]))

    def test_a32_nested_dict_order_and_distinct_sources_semantic_duplicate(self):
        state = resolve([row("a", {"a": 1, "b": {"x": 2, "y": 3}}),
                         row("b", {"b": {"y": 3, "x": 2}, "a": 1})])
        self.assertFalse(state["conflicts"])
        self.assertEqual(state["current"]["team.owner"]["claim_ids"], ["claim-a", "claim-b"])

    def test_a33_json_boolean_is_not_same_as_integer(self):
        self.assertTrue(resolve([row("a", True), row("b", 1)])["conflicts"])

    def test_a34_stored_state_is_rejected_in_direct_resolve(self):
        with self.assertRaises(ClaimValidationError):
            resolve([row("a", state="ACTIVE")])

    def test_a35_unknown_source_kind_rejected_in_direct_resolve(self):
        c = row("a"); c["source"] = {"kind": "invented", "ref": "x"}
        with self.assertRaises(ClaimValidationError):
            resolve([c])

    def test_a36_unknown_type_rejected_in_direct_resolve(self):
        with self.assertRaises(ClaimValidationError):
            resolve([row("a", ctype="FACT")])

    def test_a37_nested_non_json_value_explicit_validation_error(self):
        with self.assertRaises(ClaimValidationError):
            resolve([row("a", {"bad": {1, 2}})])

    def test_a38_nan_in_registry_is_rejected_with_line_number(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "claims.jsonl"; p.write_text(json.dumps(row("a", float("nan"))), encoding="utf-8")
            with self.assertRaisesRegex(ClaimValidationError, "line 1"):
                load_registry(p)

    def test_a39_null_is_a_valid_json_value(self):
        self.assertIsNone(resolve([row("a", None)])["current"]["team.owner"]["value"])

    def test_a40_5000_claims_reorder_without_loss_or_recursion_failure(self):
        claims = [row(str(i), i, key="team.item_" + str(i)) for i in range(5000)]
        shuffled = claims[:]; random.Random(721).shuffle(shuffled)
        state = resolve(claims)
        self.assertEqual(state["counts"]["current"], 5000)
        self.assertEqual(state, resolve(shuffled))

    def test_a41_5000_node_chain_does_not_recurse(self):
        claims = [row(str(i), i, supersedes=["claim-" + str(i - 1)] if i else []) for i in range(5000)]
        state = resolve(claims)
        self.assertEqual(state["current"]["team.owner"]["value"], 4999)
        self.assertEqual(len(state["stale"]), 4999)

    def test_a42_save_batch_validation_does_not_write_partial_records(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "claims.jsonl"
            bad = row("bad", state="ACTIVE")
            with self.assertRaises(ClaimValidationError):
                save_registry(p, [row("good"), bad])
            self.assertTrue(not p.exists() or not p.read_text(encoding="utf-8"))

    def test_a43_save_append_duplicate_fails_before_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "claims.jsonl"; save_registry(p, [row("a")]); before = p.read_bytes()
            with self.assertRaisesRegex(ValueError, "duplicate claim id"):
                save_registry(p, [row("a", 2)])
            self.assertEqual(p.read_bytes(), before)

    def test_a44_input_not_mutated_by_live_resolution(self):
        claims = [fact()]; before = copy.deepcopy(claims)
        resolve(claims, verifiers={"implementation.pr_head": ok(2)})
        self.assertEqual(claims, before)

    def test_a54_research_source_cannot_masquerade_as_current_authority(self):
        for ctype, key in (("CONTRACT", "contract.foo"),
                           ("HUMAN_DECISION", "team.owner"),
                           ("VERIFIED_FACT", "implementation.foo")):
            with self.subTest(ctype=ctype):
                c = row("forged", "research suggestion", key=key, ctype=ctype)
                c["source"] = {"kind": "research_artifact", "ref": "experiment.md"}
                with self.assertRaisesRegex(ClaimValidationError, "research_artifact"):
                    resolve([c])

    def test_a55_distinct_human_confirmation_preserves_research_provenance(self):
        research = row("research", "use batch mode", key="research.finding", ctype="RESEARCH")
        research["source"] = {"kind": "research_artifact", "ref": "experiment.md"}
        human = row("confirmed", "use batch mode", key="contract.foo")
        human["source"] = {"kind": "human", "ref": "owner explicitly confirmed batch mode"}
        state = resolve([research, human])
        self.assertEqual(state["current"]["contract.foo"]["claim_ids"], ["claim-confirmed"])
        self.assertEqual(state["current"]["contract.foo"]["source"]["kind"], "human")
        self.assertEqual(state["research"][0]["source"]["ref"], "experiment.md")


class VerifierAdversarialTests(unittest.TestCase):
    def pr(self, payload, claim=None):
        with patch("extensions.context_authority.verifiers._gh_json", return_value=(payload, "")):
            return make_pr_head_verifier(22)(claim or fact(value={"pr": 22}))

    def test_a45_open_to_closed_transition(self):
        result = self.pr({"state": "closed", "merged": False, "head": {"sha": "b" * 40}})
        self.assertEqual(result["value"]["status"], "CLOSED")

    def test_a46_open_to_merged_transition_distinguishes_merged(self):
        result = self.pr({"state": "closed", "merged": True, "head": {"sha": "b" * 40}})
        self.assertEqual(result["value"]["status"], "MERGED")

    def test_a47_malformed_pr_payload_is_unavailable(self):
        for payload in ([], {}, {"state": 9, "head": {"sha": "x"}},
                        {"state": "closed", "head": {"sha": "x"}},
                        {"state": "open", "head": {"sha": ""}}):
            with self.subTest(payload=payload):
                self.assertEqual(self.pr(payload)["status"], "unavailable")

    def test_a48_gh_network_failure_is_reported(self):
        with patch("extensions.context_authority.verifiers._run", side_effect=OSError("network unavailable")):
            self.assertEqual(make_pr_head_verifier(22)(fact())["status"], "unavailable")

    def test_a49_default_verifies_code_facts_status_and_head(self):
        verifier = build_default_verifiers(".").get("implementation.code_facts")
        self.assertIsNotNone(verifier)
        with patch("extensions.context_authority.verifiers._gh_json", return_value=({"state": "closed", "merged": True, "head": {"sha": "b" * 40}}, "")):
            state = resolve([fact("code", {"status": "PR_OPEN", "pr": 22, "head": "old", "evaluated": "old-only"}, key="implementation.code_facts")],
                            verifiers={"implementation.code_facts": verifier})
        self.assertEqual(state["current"]["implementation.code_facts"]["value"]["status"], "MERGED")
        self.assertNotIn("evaluated", state["current"]["implementation.code_facts"]["value"])

    def test_a50_main_head_drift_stales_claim(self):
        with patch("extensions.context_authority.verifiers._run", return_value=(0, "b" * 40, "")):
            state = resolve([fact("main", {"sha": "a" * 40}, key="implementation.main_head")],
                            verifiers={"implementation.main_head": make_main_head_verifier(".")})
        self.assertEqual(state["current"]["implementation.main_head"]["value"]["sha"], "b" * 40)
        self.assertEqual(state["stale"][0]["state"], "STALE")

    def test_a51_main_missing_remote_ref_does_not_fallback_to_local_branch(self):
        with patch("extensions.context_authority.verifiers._run", side_effect=[(1, "", "unknown remote"), (0, "b" * 40, "")]) as run:
            outcome = make_main_head_verifier(".")(fact())
        self.assertEqual(outcome["status"], "unavailable")
        self.assertEqual(run.call_count, 1)

    def test_a52_main_malformed_sha_is_unavailable(self):
        with patch("extensions.context_authority.verifiers._run", return_value=(0, "HEAD", "")):
            self.assertEqual(make_main_head_verifier(".")(fact())["status"], "unavailable")

    def test_a53_disabled_verification_performs_no_live_calls(self):
        def unexpected(c):
            raise AssertionError("live call must not run")
        state = resolve([fact()], verifiers={"implementation.pr_head": unexpected}, run_verifiers=False)
        self.assertEqual(state["current"]["implementation.pr_head"]["value"], {"head": "old"})


if __name__ == "__main__":
    unittest.main()
