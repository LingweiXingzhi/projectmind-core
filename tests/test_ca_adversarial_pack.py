"""Fresh adversarial pack/consumer tests; fixtures use an independent Git repo.

Mutations recompute the unkeyed checksum unless the checksum itself is tested.
Thus rejection cannot be credited merely to checksum mismatch.
"""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from extension_host import ExtensionError
from extensions.context_authority import extension
from extensions.context_authority.context_pack import (
    ContextPackValidationError, build_context_pack, context_pack_digest, validate_context_pack,
)


def claim(cid, key, value, ctype, scope="team", source=None, **extra):
    return {"id": cid, "key": key, "value": value, "type": ctype, "scope": scope,
            "source": source or {"kind": "human", "ref": "independent fixture approval"}, **extra}


class AdversarialPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="ca-pack-redteam-")
        cls.repo = Path(cls.workspace.name)
        def git(*args):
            return subprocess.run(["git", *args], cwd=cls.repo, capture_output=True, text=True, check=True).stdout.strip()
        git("init", "--quiet")
        git("config", "user.name", "Independent Pack Fixture")
        git("config", "user.email", "fixture@example.invalid")
        (cls.repo / "code.py").write_text("def first():\n    pass\n", encoding="utf-8")
        git("add", "code.py")
        git("commit", "--quiet", "-m", "first independent fixture")
        cls.old_revision = git("rev-parse", "HEAD")
        (cls.repo / "code.py").write_text("def second():\n    pass\n", encoding="utf-8")
        git("add", "code.py")
        git("commit", "--quiet", "-m", "second independent fixture")
        cls.revision = git("rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ca-pack-claims-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "claims.jsonl"
        self.ctx = type("Ctx", (), {"repo": self.repo})()

    def build(self, rows=None, task="unknown task", **kwargs):
        if rows is None:
            rows = self.fixture()
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return build_context_pack(task, str(self.repo), self.path, **{"run_verifiers": False, **kwargs})

    def fixture(self):
        return [
            claim("claim-owner", "team.owner", "C", "HUMAN_DECISION"),
            claim("claim-contract", "contract.code_facts", {"kinds": ["function"]}, "CONTRACT",
                  source={"kind": "doc", "ref": "OPEN PR delivery contract", "revision": self.old_revision}),
            claim("claim-open", "implementation.code_facts", {"status": "PR_OPEN", "pr": 22}, "VERIFIED_FACT",
                  source={"kind": "gh_api", "ref": "pulls/22"}),
            claim("claim-proposal", "architecture.map", {"status": "confirmed", "plan": "candidate"}, "PROPOSAL"),
            claim("claim-research", "research.perf", "use a batch API", "RESEARCH",
                  source={"kind": "research_artifact", "ref": "unconfirmed experiment"}),
            claim("claim-history", "implementation.old", "NOT_IMPLEMENTED", "HISTORICAL"),
            claim("claim-old", "team.roles", "old", "HUMAN_DECISION"),
            claim("claim-new", "team.roles", "V1", "HUMAN_DECISION", supersedes=["claim-old"]),
            claim("claim-conflict-a", "team.disputed", "A", "HUMAN_DECISION"),
            claim("claim-conflict-b", "team.disputed", "B", "HUMAN_DECISION"),
        ]

    def assertRejected(self, pack, mutate, *, rehash=True):
        poisoned = copy.deepcopy(pack)
        mutate(poisoned)
        if rehash:
            poisoned["integrity"]["digest"] = context_pack_digest(poisoned)
        with self.assertRaises(ContextPackValidationError):
            validate_context_pack(poisoned, self.revision)

    def test_p01_arbitrary_revision_rejected(self):
        with self.assertRaises(ValueError):
            self.build(revision="definitely-not-a-commit")

    def test_p02_nonexistent_full_revision_rejected(self):
        with self.assertRaises(ValueError):
            self.build(revision="f" * 40)

    def test_p03_short_revision_rejected(self):
        with self.assertRaises(ValueError):
            self.build(revision=self.revision[:10])

    def test_p04_head_alias_rejected_for_saved_pack(self):
        with self.assertRaises(ValueError):
            self.build(revision="HEAD")

    def test_p05_uppercase_revision_rejected(self):
        with self.assertRaises(ValueError):
            self.build(revision=self.revision.upper())

    def test_p06_default_revision_is_actual_head(self):
        self.assertEqual(self.build()["project_revision"], self.revision)

    def test_p07_explicit_old_code_revision_is_stale(self):
        rows = [claim("claim-oldcode", "implementation.symbol", "first", "VERIFIED_FACT", revision=self.old_revision)]
        pack = self.build(rows, revision=self.revision)
        self.assertFalse(pack["verified_facts"])
        self.assertEqual(pack["known_stale_sources"][0]["claim_id"], "claim-oldcode")
        self.assertEqual(pack["evidence"][0]["claim_revision"], self.old_revision)

    def test_p08_repo_source_commit_cannot_be_current_at_another_commit(self):
        rows = [claim("claim-oldcode", "implementation.symbol", "first", "VERIFIED_FACT",
                      source={"kind": "repo", "ref": "code.py", "revision": self.old_revision})]
        pack = self.build(rows)
        self.assertFalse(pack["verified_facts"])
        self.assertEqual(pack["evidence"][0]["source_revision"], self.old_revision)

    def test_p09_contract_source_revision_remains_provenance(self):
        pack = self.build()
        self.assertEqual(pack["relevant_contracts"][0]["source"]["revision"], self.old_revision)
        evidence = next(e for e in pack["evidence"] if e["claim_id"] == "claim-contract")
        self.assertEqual(evidence["revision"], self.old_revision)
        self.assertIsNone(evidence["claim_revision"])

    def test_p10_collapsed_claims_preserve_each_source(self):
        rows = [claim("claim-a", "team.owner", "C", "HUMAN_DECISION", source={"kind": "human", "ref": "Alice"}),
                claim("claim-b", "team.owner", "C", "HUMAN_DECISION", source={"kind": "human", "ref": "Bob"})]
        pack = self.build(rows)
        self.assertEqual({e["claim_id"]: e["source"]["ref"] for e in pack["evidence"]}, {"claim-a": "Alice", "claim-b": "Bob"})

    def test_p11_evidence_covers_every_section(self):
        pack = self.build()
        self.assertEqual({e["claim_id"] for e in pack["evidence"]}, {r["id"] for r in self.fixture()})
        self.assertTrue(pack["historical_sources"])
        self.assertIs(validate_context_pack(pack, self.revision), pack)

    def test_p12_scalar_implementation_value_does_not_crash(self):
        pack = self.build([claim("claim-scalar", "implementation.code_facts", "pending", "VERIFIED_FACT")])
        self.assertEqual(pack["verified_facts"][0]["value"], "pending")

    def test_p13_open_pr_at_generic_key_keeps_warning(self):
        pack = self.build([claim("claim-open", "implementation.pr_99", {"status": "OPEN", "pr": 99}, "VERIFIED_FACT")])
        self.assertTrue(any("PR #99 is OPEN" in warning for warning in pack["do_not_assume"]))
        self.assertEqual(pack["verified_facts"][0]["value"]["status"], "OPEN")

    def test_p14_proposal_saying_confirmed_remains_proposal(self):
        pack = self.build()
        self.assertEqual(pack["proposals"][0]["type"], "PROPOSAL")
        self.assertNotIn("architecture.map", pack["current_state"]["current"])

    def test_p15_research_masquerading_as_contract_rejected(self):
        rows = [claim("claim-fake", "contract.optimization", "must batch", "RESEARCH")]
        with self.assertRaises(ValueError):
            self.build(rows)

    def test_p16_missing_source_locator_rejected(self):
        with self.assertRaises(ValueError):
            self.build([claim("claim-empty", "team.owner", "C", "HUMAN_DECISION", source={"kind": "human", "ref": " "})])

    def test_p17_c_task_gets_team_and_contract(self):
        pack = self.build(task="Implement C Map Proposal")
        self.assertTrue(pack["human_decisions"])
        self.assertTrue(pack["relevant_contracts"])
        self.assertTrue(pack["research_notes"])

    def test_p18_task_filter_excludes_unrelated_evidence_and_counts(self):
        pack = self.build(task="team roles")
        self.assertFalse(pack["verified_facts"])
        self.assertFalse(pack["research_notes"])
        self.assertEqual(pack["current_state"]["counts"]["research"], 0)
        self.assertTrue(all(e["key"].startswith("team.") for e in pack["evidence"]))

    def test_p19_pr_substring_does_not_filter_unknown_task(self):
        pack = self.build(task="improve experience")
        self.assertEqual(pack["task_domains"], "all")
        self.assertTrue(pack["relevant_contracts"])

    def test_p20_multi_scope_does_not_pick_a_scope(self):
        pack = self.build([claim("claim-a", "team.owner", "A", "HUMAN_DECISION", scope="repo-a"),
                           claim("claim-b", "team.owner", "B", "HUMAN_DECISION", scope="repo-b")])
        self.assertNotIn("team.owner", pack["current_state"]["current"])
        self.assertEqual({r["scope"] for r in pack["human_decisions"]}, {"repo-a", "repo-b"})

    def test_p21_live_verifier_unavailable_is_not_current(self):
        with patch("extensions.context_authority.context_pack.build_default_verifiers", return_value={
                "implementation.code_facts": lambda c: {"status": "unavailable", "reason": "offline"}}):
            pack = self.build(run_verifiers=True)
        self.assertFalse(pack["verified_facts"])
        self.assertEqual(pack["verification_unavailable"][0]["reason"], "offline")
        self.assertIn("claim-open", {e["claim_id"] for e in pack["evidence"]})

    def test_p22_live_stale_replacement_keeps_both_evidence(self):
        with patch("extensions.context_authority.context_pack.build_default_verifiers", return_value={
                "implementation.code_facts": lambda c: {"status": "ok", "value": {"status": "PR_OPEN", "pr": 22, "head": self.revision},
                "source_kind": "gh_api", "source_ref": "pulls/22/live", "verified_at": "2026-10-02"}}):
            pack = self.build(run_verifiers=True)
        self.assertIn("claim-open", {e["claim_id"] for e in pack["evidence"]})
        current = pack["verified_facts"][0]
        self.assertNotIn("claim-open", current["claim_ids"])
        self.assertEqual(current["value"]["head"], self.revision)

    def test_p23_consumer_expected_revision_mismatch_rejected(self):
        with self.assertRaises(ContextPackValidationError):
            validate_context_pack(self.build(), self.old_revision)

    def test_p24_missing_evidence_rejected_even_after_rehash(self):
        self.assertRejected(self.build(), lambda p: p["evidence"].pop())

    def test_p25_duplicate_evidence_rejected_even_after_rehash(self):
        self.assertRejected(self.build(), lambda p: p["evidence"].append(copy.deepcopy(p["evidence"][0])))

    def test_p26_modified_source_revision_rejected(self):
        self.assertRejected(self.build(), lambda p: p["evidence"][0].update(source_revision=self.revision))

    def test_p27_contract_section_cannot_smuggle_research(self):
        self.assertRejected(self.build(), lambda p: p["relevant_contracts"].append(copy.deepcopy(p["research_notes"][0])))

    def test_p28_proposal_cannot_be_human_decision(self):
        self.assertRejected(self.build(), lambda p: p["human_decisions"].append(copy.deepcopy(p["proposals"][0])))

    def test_p29_conflict_requires_human_resolution(self):
        self.assertRejected(self.build(), lambda p: p["known_conflicts"][0].update(resolution="AUTO_RESOLVED"))

    def test_p30_stale_cannot_be_current(self):
        def mutate(p):
            row = copy.deepcopy(p["known_stale_sources"][0])
            row["claim_ids"] = [row.pop("claim_id")]
            row["evidence"] = [next(e for e in p["evidence"] if e["claim_id"] == row["claim_ids"][0])]
            p["current_state"]["current_by_scope"].append(row)
        self.assertRejected(self.build(), mutate)

    def test_p31_wrong_schema_rejected(self):
        self.assertRejected(self.build(), lambda p: p.update(schema_version="99"))

    def test_p32_current_projection_cannot_drop_scope(self):
        self.assertRejected(self.build(), lambda p: p["current_state"]["current"].pop("team.owner"))

    def test_p33_count_cannot_hide_conflict(self):
        self.assertRejected(self.build(), lambda p: p["current_state"]["counts"].update(conflicts=0))

    def test_p34_open_warning_cannot_be_removed(self):
        self.assertRejected(self.build(), lambda p: p.update(do_not_assume=[w for w in p["do_not_assume"] if "OPEN" not in w]))

    def test_p35_task_domain_cannot_be_rewritten(self):
        self.assertRejected(self.build(task="team roles"), lambda p: p.update(task_domains="all"))

    def test_p36_checksum_detects_accidental_modification(self):
        self.assertRejected(self.build(), lambda p: p["registry_problems"].append({"kind": "new", "detail": "tampered"}), rehash=False)

    def test_p37_coherent_wrong_human_claim_requires_external_authority(self):
        pack = self.build([claim("claim-owner", "team.owner", "C", "HUMAN_DECISION")])
        def rewrite(obj):
            if isinstance(obj, dict):
                if obj.get("value") == "C":
                    obj["value"] = "forged owner"
                for value in obj.values():
                    rewrite(value)
            elif isinstance(obj, list):
                for value in obj:
                    rewrite(value)
        rewrite(pack)
        pack["integrity"]["digest"] = context_pack_digest(pack)
        self.assertIs(validate_context_pack(pack, self.revision), pack)
        self.assertTrue(any("semantic truth require source review" in w for w in pack["do_not_assume"]))

    def test_p38_extension_exposes_actual_consumer_validator(self):
        pack = self.build()
        self.assertIs(extension.handle(self.ctx, "POST", {"action": "validate_context", "pack": pack,
                      "expected_revision": self.revision}), pack)

    def test_p39_extension_rejects_poisoned_pack_as_bad_request(self):
        pack = self.build()
        pack["evidence"] = []
        with self.assertRaises(ExtensionError) as error:
            extension.handle(self.ctx, "POST", {"action": "validate_context", "pack": pack})
        self.assertEqual(error.exception.status, 400)

    def test_p40_extension_wrong_revision_is_bad_request(self):
        self.build()
        with patch.object(extension, "REGISTRY_PATH", self.path):
            with self.assertRaises(ExtensionError):
                extension.handle(self.ctx, "POST", {"action": "context", "task": "map", "revision": "HEAD", "verify": False})

    def test_p41_registry_reordering_preserves_pack(self):
        rows = self.fixture()
        self.assertEqual(self.build(rows), self.build(list(reversed(rows))))

    def test_p42_snapshot_commit_is_independent_of_dirty_worktree(self):
        (self.repo / "code.py").write_text("def uncommitted():\n    pass\n", encoding="utf-8")
        self.assertEqual(self.build()["project_revision"], self.revision)

    def test_p43_conflicted_alternate_scope_blocks_unqualified_projection(self):
        rows = [claim("claim-a", "team.owner", "A", "HUMAN_DECISION", scope="repo-a"),
                claim("claim-b", "team.owner", "B", "HUMAN_DECISION", scope="repo-b"),
                claim("claim-c", "team.owner", "C", "HUMAN_DECISION", scope="repo-b")]
        pack = self.build(rows)
        self.assertNotIn("team.owner", pack["current_state"]["current"])
        self.assertEqual(pack["current_state"]["current_by_scope"][0]["scope"], "repo-a")
        self.assertEqual(len(pack["known_conflicts"]), 1)

    def test_p44_unavailable_alternate_scope_blocks_unqualified_projection(self):
        rows = [claim("claim-a", "implementation.symbol", "A", "VERIFIED_FACT", scope="repo-a"),
                claim("claim-b", "implementation.symbol", "B", "VERIFIED_FACT", scope="repo-b")]
        def verifier(c):
            return {"status": "ok", "value": "A"} if c["scope"] == "repo-a" else {"status": "unavailable", "reason": "offline"}
        with patch("extensions.context_authority.context_pack.build_default_verifiers", return_value={"implementation.symbol": verifier}):
            pack = self.build(rows, run_verifiers=True)
        self.assertNotIn("implementation.symbol", pack["current_state"]["current"])
        self.assertEqual(len(pack["verified_facts"]), 1)

    def test_p45_valid_replacement_across_code_revisions_not_broken(self):
        rows = [claim("claim-old", "implementation.symbol", "first", "VERIFIED_FACT", revision=self.old_revision),
                claim("claim-new", "implementation.symbol", "second", "VERIFIED_FACT", revision=self.revision, supersedes=["claim-old"])]
        pack = self.build(rows)
        self.assertEqual(pack["verified_facts"][0]["value"], "second")
        self.assertFalse(pack["registry_problems"])
        self.assertEqual(pack["known_stale_sources"][0]["state"], "SUPERSEDED")

    def test_p46_invalid_graph_single_claim_is_human_required(self):
        pack = self.build([claim("claim-broken", "team.owner", "C", "HUMAN_DECISION", supersedes=["claim-missing"])])
        self.assertFalse(pack["human_decisions"])
        self.assertEqual(pack["known_conflicts"][0]["resolution"], "HUMAN_REQUIRED")
        self.assertTrue(pack["registry_problems"])

    def test_p47_live_matching_value_preserves_verifier_locator(self):
        rows = [claim("claim-x", "implementation.symbol", "A", "VERIFIED_FACT")]
        with patch("extensions.context_authority.context_pack.build_default_verifiers", return_value={
                "implementation.symbol": lambda c: {"status": "ok", "value": "A", "source_ref": "exact endpoint", "verified_at": "2026-10-03"}}):
            pack = self.build(rows, run_verifiers=True)
        self.assertEqual(pack["evidence"][0]["live_verification"]["source"]["ref"], "exact endpoint")
        self.assertEqual(pack["evidence"][0]["verified_at"], "2026-10-03")

    def test_p48_cached_origin_reference_is_not_reported_live_remote(self):
        rows = [claim("claim-x", "implementation.symbol", "A", "VERIFIED_FACT")]
        with patch("extensions.context_authority.context_pack.build_default_verifiers", return_value={
                "implementation.symbol": lambda c: {"status": "ok", "value": "A", "source_kind": "repo", "source_ref": "origin/main", "freshness": "local_reference"}}):
            pack = self.build(rows, run_verifiers=True)
        self.assertEqual(pack["verified_facts"][0]["freshness"], "local_reference")
        self.assertTrue(any("cached" in rule for rule in pack["do_not_assume"]))

    def test_p49_false_freshness_claim_rejected(self):
        def mutate(p):
            for row in [p["current_state"]["current"]["team.owner"], p["current_state"]["current_by_scope"][0], p["human_decisions"][0]]:
                row["freshness"] = "verified"
        self.assertRejected(self.build(), mutate)

    def test_p50_fake_current_type_list_rejected(self):
        self.assertRejected(self.build(), lambda p: p["current_state"]["current_by_scope"][0].update(types=["PROPOSAL"]))

    def test_p51_unknown_confirmed_field_rejected(self):
        self.assertRejected(self.build(), lambda p: p["proposals"][0].update(confirmed=True))

    def test_p52_unknown_source_field_rejected(self):
        self.assertRejected(self.build(), lambda p: p["evidence"][0]["source"].update(human_approved=True))

    def test_p53_malformed_nested_pack_is_value_error(self):
        for field in ("current_state", "evidence", "known_conflicts", "verification_unavailable"):
            with self.subTest(field=field):
                self.assertRejected(self.build(), lambda p: p.update({field: [None]}))

    def test_p54_unknown_evidence_type_rejected(self):
        self.assertRejected(self.build(), lambda p: p["evidence"][0].update(type="BOGUS"))

    def test_p55_generic_unavailable_record_needs_matching_evidence(self):
        self.assertRejected(self.build(), lambda p: p["verification_unavailable"].append({"key": "implementation.missing", "scope": "repo", "claim_id": "claim-ghost", "source": {"kind": "repo", "ref": "ghost.py"}, "reason": "offline"}))

    def test_p56_generated_fact_derivation_cannot_be_erased(self):
        with patch("extensions.context_authority.context_pack.build_default_verifiers", return_value={
                "implementation.code_facts": lambda c: {"status": "ok", "value": {"status": "PR_OPEN", "pr": 22, "head": self.revision}}}):
            pack = self.build(run_verifiers=True)
        generated = next(i for i, e in enumerate(pack["evidence"]) if "derived_from_ids" in e)
        self.assertRejected(pack, lambda p: p["evidence"][generated].update(derived_from_sources=[]))

    def test_p57_coherent_research_artifact_cannot_authorize_contract(self):
        pack = self.build([claim("claim-contract", "contract.optimization", "must batch", "CONTRACT",
                               source={"kind": "doc", "ref": "delivery contract"})])
        def mutate(obj):
            if isinstance(obj, dict):
                if obj.get("kind") == "doc":
                    obj["kind"] = "research_artifact"
                for value in obj.values():
                    mutate(value)
            elif isinstance(obj, list):
                for value in obj:
                    mutate(value)
        self.assertRejected(pack, mutate)

    def test_p58_research_confirmation_requires_distinct_human_evidence(self):
        rows = [claim("claim-research", "research.optimization", "use batch", "RESEARCH",
                      source={"kind": "research_artifact", "ref": "experiment"}),
                claim("claim-decision", "contract.optimization", "use batch", "HUMAN_DECISION",
                      source={"kind": "human", "ref": "explicit approval of batch contract"})]
        pack = self.build(rows)
        self.assertEqual(pack["human_decisions"][0]["claim_ids"], ["claim-decision"])
        self.assertEqual(pack["research_notes"][0]["claim_id"], "claim-research")

    def test_p59_superseded_record_needs_replacement_edge(self):
        self.assertRejected(self.build(), lambda p: p["known_stale_sources"][0].update(superseded_by=["claim-owner"]))

    def test_p60_stale_record_cannot_omit_reason(self):
        pack = self.build([claim("claim-code", "implementation.symbol", "old", "VERIFIED_FACT", revision=self.old_revision)])
        self.assertRejected(pack, lambda p: p["known_stale_sources"][0].pop("stale_reason"))


if __name__ == "__main__":
    unittest.main()
