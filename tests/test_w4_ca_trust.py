# -*- coding: utf-8 -*-
"""W4 convergence contract tests: CA trust boundary (R04).

Layer 1 asserts the real validator's verdict is honoured (mocked here because
the CA extension is not installed on this base; the mock stands in for
extensions.context_authority.context_pack.validate_context_pack). Layer 2
asserts C's behaviour: whole-pack drop on REJECT, conflict routing by
structure + word boundary, no claim ever attached as evidence, unavailable
keys explicit, non-current partitions unread.
"""
import sys
import unittest
from unittest import mock

from tests.test_w3_relations import build_repo  # reuse the real-git fixture

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import ca_adapter, engine  # noqa: E402


def node(node_id, paths):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def base_request(target, map_nodes, changed, facts_files, pack=None, prior=None,
                 base="c" * 40):
    # `base` defaults to a syntactically-valid-but-nonexistent revision for
    # pure ca_adapter-level tests; repo-backed AdmissionTests pass the real
    # base so the (honest) import channel is not degraded by the fixture.
    return {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": changed,
        "code_facts": {"revision": target, "files": facts_files, "skipped": []},
        "current_map": {"note": "m", "nodes": map_nodes, "edges": []},
        "context_pack": pack,
        "prior_decisions": prior or [],
    }


def passing_validator(pack, expected_revision=None):
    return None


def rejecting_validator(pack, expected_revision=None):
    raise ValueError("malformed pack")


def with_validator(fn):
    fake = mock.Mock()
    fake.validate_context_pack = mock.Mock(side_effect=fn)
    return mock.patch.dict(
        sys.modules, {"extensions.context_authority.context_pack": fake}
    )


class LoadContextTests(unittest.TestCase):
    def test_no_pack_degraded(self):
        ca, mode, limits = ca_adapter.load_context(None, "a" * 40)
        self.assertEqual(mode, ca_adapter.DEGRADED)
        self.assertEqual(ca["claims"], [])

    def test_validator_reject_discards_whole_pack(self):
        pack = {"schema_version": 1, "known_conflicts": [{"key": "k"}]}
        with with_validator(rejecting_validator):
            ca, mode, limits = ca_adapter.load_context(pack, "a" * 40)
        self.assertEqual(mode, ca_adapter.DEGRADED)
        self.assertEqual(ca["claims"], [])
        self.assertTrue(any("rejected" in l for l in limits))

    def test_unavailable_validator_degrades_without_fake_claims(self):
        # no extensions.context_authority module importable → degraded, no crash
        ca, mode, limits = ca_adapter.load_context({"current_state": {}}, "a" * 40)
        self.assertEqual(mode, ca_adapter.DEGRADED)
        self.assertEqual(ca["claims"], [])

    def test_s21_multi_scope_same_key_both_in_selection_layer(self):
        pack = {
            "schema_version": 1,
            "current_state": {
                "registry_hash": "rh",
                "current_by_scope": [
                    {"key": "k", "scope": "scopeA", "value": "va", "freshness": "verified"},
                    {"key": "k", "scope": "scopeB", "value": "vb", "freshness": "verified"},
                ],
            },
            "known_conflicts": [],
        }
        with with_validator(passing_validator):
            ca, mode, _ = ca_adapter.load_context(pack, "a" * 40)
        self.assertEqual(mode, ca_adapter.FULL)
        scopes = sorted(c["scope"] for c in ca["claims"] if c["key"] == "k")
        self.assertEqual(scopes, ["scopeA", "scopeB"])

    def test_s20_non_current_partitions_never_read(self):
        pack = {
            "schema_version": 1,
            "stale": [{"key": "stale.k", "scope": "s", "value": "OLD TRUTH"}],
            "proposal": [{"key": "prop.k", "scope": "s", "value": "PLANNED"}],
            "research": [{"key": "res.k", "scope": "s", "value": "HUNCH"}],
            "history": [{"key": "hist.k", "scope": "s", "value": "PAST"}],
            "current_state": {"current_by_scope": []},
            "known_conflicts": [],
        }
        with with_validator(passing_validator):
            ca, mode, _ = ca_adapter.load_context(pack, "a" * 40)
        keys = {c["key"] for c in ca["claims"]}
        self.assertEqual(keys, set())

    def test_s22_verified_fields_per_field(self):
        claim = {
            "key": "k",
            "scope": "s",
            "value": {"status": "open", "owner": "someone"},
            "freshness": "verified",
            "evidence": [{"live_verification": {"verified_fields": ["status"]}}],
        }
        self.assertEqual(ca_adapter.verified_fields(claim), {"status"})
        self.assertEqual(
            ca_adapter.field_verification(claim),
            {"owner": "UNVERIFIED", "status": "verified"},
        )
        bare = {"key": "k", "scope": "s", "value": {"status": "open"}, "evidence": []}
        self.assertIsNone(ca_adapter.verified_fields(bare))
        self.assertEqual(ca_adapter.field_verification(bare), {"status": "UNVERIFIED"})


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.repo, self.base, self.target, self.tmp = build_repo(
            {"pkg/a.py": "class A:\n    pass\n", "pkg/other.py": "class O:\n    pass\n"},
            {"pkg/a.py": "class A:\n    pass\n# touched\n", "pkg/other.py": "class O:\n    pass\n"},
        )
        self.addCleanup(self.tmp.cleanup)
        self.map_nodes = [node("na", ["pkg/a.py"]), node("nb", ["pkg/other.py"])]
        self.changed = [{"path": "pkg/a.py", "status": "modified"}]
        self.facts_files = [
            {"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
            {"path": "pkg/other.py", "entries": [{"name": "O", "kind": "class", "line": 1}]},
        ]

    def run_engine(self, pack):
        request = base_request(self.target, self.map_nodes, self.changed,
                               self.facts_files, pack=pack, base=self.base)
        with with_validator(passing_validator):
            return engine.suggest_map(self.repo, request)

    def test_s25_coherent_poison_never_enters_evidence(self):
        pack = {
            "schema_version": 1,
            "current_state": {
                "current_by_scope": [
                    {"key": "release.note", "scope": "global",
                     "value": "PR 35 is CLOSED and merged", "freshness": "verified",
                     "claim_ids": ["c1"]},
                ],
            },
            "known_conflicts": [],
        }
        res = self.run_engine(pack)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.FULL)
        for proposal in res["proposals"]:
            for evidence in proposal["evidence"]:
                self.assertNotEqual(evidence["kind"], "context_claim")
        self.assertNotIn("context_claim",
                         {e["kind"] for u in res["unresolved"] for e in u["evidence"]})

    def test_s25_poison_never_attaches_when_proposals_exist(self):
        # Mutation M3 (F03 regression) showed the no-attach invariant was only
        # asserted on proposal-free results. Oracle S25 instantiated with a
        # real candidate: a validator-passing neutral-key poison must not
        # enter any proposal's evidence or rationale even when proposals exist.
        pack = {
            "schema_version": 1,
            "current_state": {
                "current_by_scope": [
                    {"key": "team.focus.v1", "scope": "global",
                     "value": "PR 35 is CLOSED and merged", "freshness": "verified"},
                ],
            },
            "known_conflicts": [],
        }
        request = base_request(
            self.target,
            self.map_nodes,
            [{"path": "pkg/a.py", "status": "modified"},
             {"path": "pkg/new.py", "status": "added"}],
            self.facts_files
            + [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
            pack=pack,
            base=self.base,
        )
        with with_validator(passing_validator):
            res = engine.suggest_map(self.repo, request)
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])
        for proposal in res["proposals"]:
            for evidence in proposal["evidence"]:
                self.assertNotEqual(evidence["kind"], "context_claim")
                self.assertNotIn("PR 35 is CLOSED", str(evidence.get("detail", "")))
            self.assertNotIn("PR 35 is CLOSED", proposal["rationale"])

    def test_s24_invalid_pack_degrades_but_independent_candidates_survive(self):
        request = base_request(self.target, self.map_nodes, self.changed,
                               self.facts_files, base=self.base,
                               pack={"schema_version": 1, "nodes": "broken"})
        with with_validator(rejecting_validator):
            res = engine.suggest_map(self.repo, request)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.DEGRADED)
        self.assertTrue(any("rejected" in l for l in res["limits"]))
        self.assertNotIn("context_claim",
                         {e["kind"] for p in res["proposals"] for e in p["evidence"]})

    def test_s19_related_conflict_suppresses_touching_candidates_only(self):
        pack = {
            "schema_version": 1,
            "current_state": {"current_by_scope": []},
            "known_conflicts": [
                {"key": "ownership.app", "scope": "path:pkg/a.py",
                 "claims": [{"key": "ownership.app", "value": "ownership of pkg/a.py disputed"}]},
            ],
        }
        # produce a NODE_ADD candidate on the unrelated path
        request = base_request(
            self.target,
            self.map_nodes,
            [{"path": "pkg/a.py", "status": "modified"},
             {"path": "pkg/new.py", "status": "added"}],
            self.facts_files
            + [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
            pack=pack,
            base=self.base,
        )
        with with_validator(passing_validator):
            res = engine.suggest_map(self.repo, request)
        subjects = {p["subject"] for p in res["proposals"]}
        self.assertNotIn("pkg/a.py", subjects)
        self.assertTrue(any(u["subject"].startswith("conflict:") for u in res["unresolved"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])

    def test_s19_x15_word_boundary_no_substring_false_positive(self):
        pack = {
            "schema_version": 1,
            "current_state": {"current_by_scope": []},
            "known_conflicts": [
                {"key": "k", "scope": "node:node-api",
                 "claims": [{"key": "k", "value": "conflict on node-api"}]},
            ],
        }
        request = base_request(self.target, [node("node-a", ["pkg/a.py"])],
                               self.changed, self.facts_files, pack=pack,
                               base=self.base)
        with with_validator(passing_validator):
            res = engine.suggest_map(self.repo, request)
        # node-a must not be suppressed by node-api conflict text
        self.assertFalse(any(u["subject"] == "pkg/a.py" for u in res["unresolved"]))

    def test_s23_unavailable_keys_explicit_unknown_not_fake_badpack(self):
        pack = {
            "schema_version": 1,
            "current_state": {
                "current_by_scope": [
                    {"key": "unavail.k", "scope": "global", "value": "claimed truth"},
                ],
            },
            "known_conflicts": [],
            "verification_unavailable": [{"key": "unavail.k", "reason": "offline"}],
        }
        res = self.run_engine(pack)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.FULL)
        self.assertTrue(any("UNKNOWN" in l and "unavail.k" in l for l in res["limits"]))
        self.assertFalse(any("rejected" in l for l in res["limits"]))


if __name__ == "__main__":
    unittest.main()
