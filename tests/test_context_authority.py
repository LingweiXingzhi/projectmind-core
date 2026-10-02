"""Context Authority MVP tests: T1-T18 (spec), F1-F5 (real drift fixtures),
constructed conflict/stale scenarios (§28/§29), and the HTTP handle layer.

Run: python -m unittest tests.test_context_authority -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.context_authority.context_pack import build_context_pack  # noqa: E402
from extensions.context_authority.registry import (  # noqa: E402
    RegistryProblems,
    load_registry,
)
from extensions.context_authority.resolver import resolve  # noqa: E402
from extensions.context_authority.schema import (  # noqa: E402
    ClaimValidationError,
    validate_claim,
)

SEED = ROOT / "extensions" / "context_authority" / "data" / "claims.jsonl"


def claim(cid, key, value, ctype, *, scope="test", sup=None, created="2026-01-01",
          source=None, **extra):
    row = {"id": cid, "key": key, "value": value, "type": ctype, "scope": scope,
           "source": source or {"kind": "human", "ref": "test"}}
    if sup:
        row["supersedes"] = sup
    if created:
        row["created_at"] = created
    row.update(extra)
    return row


def write_registry(claims: list[dict]) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "claims.jsonl"
    p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims),
                 encoding="utf-8")
    return p


class SpecTests(unittest.TestCase):
    """T1-T18 from the Context Authority MVP directive."""

    def setUp(self):
        self.problems = RegistryProblems()

    def resolve(self, claims, verifiers=None, problems=None):
        return resolve(claims, verifiers=verifiers,
                       problems=problems if problems is not None else self.problems)

    # ---- T1 single verified fact resolves
    def test_t1_single_verified_fact_resolves(self):
        state = self.resolve([claim("claim-a", "implementation.x", {"v": 1},
                                    "VERIFIED_FACT")])
        self.assertEqual(state["current"]["implementation.x"]["value"], {"v": 1})
        self.assertEqual(state["counts"]["conflicts"], 0)

    # ---- T2 human decision resolves
    def test_t2_human_decision_resolves(self):
        state = self.resolve([claim("claim-a", "team.owner", "someone",
                                    "HUMAN_DECISION")])
        self.assertEqual(state["current"]["team.owner"]["type"], "HUMAN_DECISION")

    # ---- T3 proposal does not enter current state
    def test_t3_proposal_not_in_current(self):
        state = self.resolve([claim("claim-p", "architecture.layout", {"nodes": 3},
                                    "PROPOSAL")])
        self.assertNotIn("architecture.layout", state["current"])
        self.assertEqual(len(state["proposals"]), 1)
        self.assertEqual(state["proposals"][0]["state"], "ACTIVE")

    # ---- T4 research does not enter current state
    def test_t4_research_not_in_current(self):
        state = self.resolve([claim("claim-r", "research.finding", "x is slow",
                                    "RESEARCH")])
        self.assertNotIn("research.finding", state["current"])
        self.assertEqual(len(state["research"]), 1)

    # ---- T5 historical does not enter current state
    def test_t5_historical_not_in_current(self):
        state = self.resolve([claim("claim-h", "implementation.old", "gone",
                                    "HISTORICAL")])
        self.assertNotIn("implementation.old", state["current"])
        self.assertEqual(len(state["historical"]), 1)

    # ---- T6 explicit supersedes removes old claim from current
    def test_t6_supersedes_removes_old_from_current(self):
        state = self.resolve([
            claim("claim-old", "team.roles", {"B": "old"}, "HUMAN_DECISION"),
            claim("claim-new", "team.roles", {"B": "new"}, "HUMAN_DECISION",
                  sup=["claim-old"]),
        ])
        self.assertEqual(state["current"]["team.roles"]["value"], {"B": "new"})
        old_rows = [s for s in state["stale"] if s["claim_id"] == "claim-old"]
        self.assertEqual(old_rows[0]["state"], "SUPERSEDED")

    # ---- T7 two conflicting ACTIVE claims -> CONFLICT / HUMAN_REQUIRED
    def test_t7_conflicting_active_claims(self):
        state = self.resolve([
            claim("claim-a", "team.b_role", "Code Facts", "HUMAN_DECISION"),
            claim("claim-b", "team.b_role", "Architecture Proposal",
                  "HUMAN_DECISION"),
        ])
        self.assertNotIn("team.b_role", state["current"])
        self.assertEqual(len(state["conflicts"]), 1)
        conflict = state["conflicts"][0]
        self.assertEqual(conflict["resolution"], "HUMAN_REQUIRED")
        self.assertEqual({c["claim_id"] for c in conflict["claims"]},
                         {"claim-a", "claim-b"})

    # ---- T8 latest timestamp does NOT silently win
    def test_t8_timestamp_does_not_win(self):
        state = self.resolve([
            claim("claim-old-truth", "team.b_role", "Code Facts",
                  "HUMAN_DECISION", created="2026-01-01"),
            claim("claim-new-shiny", "team.b_role", "Whatever Is Newest",
                  "HUMAN_DECISION", created="2027-12-31"),
        ])
        self.assertEqual(len(state["conflicts"]), 1,
                         "newer timestamp must not pick a winner")

    # ---- T9 stale verified Git/PR fact detected
    def test_t9_stale_verified_fact_detected(self):
        def verifier(c):
            return {"status": "ok", "value": {"head": "live-sha"},
                    "verified_at": "2026-10-02T00:00:00+00:00",
                    "source_kind": "gh_api"}
        state = self.resolve(
            [claim("claim-pr", "implementation.pr_head", {"head": "old-sha"},
                   "VERIFIED_FACT")],
            verifiers={"implementation.pr_head": verifier})
        self.assertNotIn("implementation.pr_head", state["current"]) \
            if False else None
        self.assertEqual(state["current"]["implementation.pr_head"]["value"],
                         {"head": "live-sha"})
        self.assertEqual(state["current"]["implementation.pr_head"]["claim_ids"],
                         ["claim-auto-implementation-pr-head"])
        stale_rows = [s for s in state["stale"] if s["claim_id"] == "claim-pr"]
        self.assertEqual(stale_rows[0]["state"], "STALE")
        self.assertEqual(stale_rows[0]["live_value"], {"head": "live-sha"})

    # ---- T10 OPEN PR never becomes MERGED automatically
    def test_t10_open_never_becomes_merged_automatically(self):
        state = self.resolve([
            claim("claim-open", "implementation.code_facts",
                  {"status": "PR_OPEN", "pr": 22}, "VERIFIED_FACT"),
            claim("claim-merged", "implementation.code_facts",
                  {"status": "MERGED", "pr": 22}, "VERIFIED_FACT",
                  created="2027-01-01"),
        ])
        # no supersedes and no live verifier: the newer MERGED claim must NOT
        # silently win -> CONFLICT / HUMAN_REQUIRED
        self.assertEqual(len(state["conflicts"]), 1)
        self.assertNotIn("implementation.code_facts", state["current"])
        # with explicit supersedes the transition becomes valid
        state2 = self.resolve([
            claim("claim-open", "implementation.code_facts",
                  {"status": "PR_OPEN", "pr": 22}, "VERIFIED_FACT"),
            claim("claim-merged", "implementation.code_facts",
                  {"status": "MERGED", "pr": 22}, "VERIFIED_FACT",
                  sup=["claim-open"]),
        ])
        self.assertEqual(state2["current"]["implementation.code_facts"]["value"],
                         {"status": "MERGED", "pr": 22})

    # ---- T11 Context Pack contains evidence
    def test_t11_pack_contains_evidence(self):
        pack = build_context_pack("team roles", str(ROOT), SEED,
                                  run_verifiers=False)
        self.assertTrue(pack["evidence"])
        for e in pack["evidence"]:
            self.assertIn("source", e)

    # ---- T12 Context Pack contains do_not_assume
    def test_t12_pack_contains_do_not_assume(self):
        pack = build_context_pack("team roles", str(ROOT), SEED,
                                  run_verifiers=False)
        self.assertTrue(any("OPEN does not mean merged" in r
                            for r in pack["do_not_assume"]))
        self.assertTrue(any("RESEARCH" in r for r in pack["do_not_assume"]))

    # ---- T13 same registry -> deterministic CURRENT_STATE
    def test_t13_deterministic(self):
        s1 = self.resolve(load_registry(SEED))
        s2 = self.resolve(load_registry(SEED))
        self.assertEqual(s1, s2)

    # ---- T14 registry reorder -> same semantic CURRENT_STATE
    def test_t14_reorder_same_state(self):
        import random
        claims = load_registry(SEED)
        shuffled = claims[:]
        random.Random(3).shuffle(shuffled)
        self.assertEqual(self.resolve(claims), self.resolve(shuffled))

    # ---- T15 unknown claim type rejected
    def test_t15_unknown_type_rejected(self):
        with self.assertRaises(ClaimValidationError):
            validate_claim(claim("claim-x", "implementation.y", 1, "FACT"))

    # ---- T16 invalid source rejected
    def test_t16_invalid_source_rejected(self):
        with self.assertRaises(ClaimValidationError):
            validate_claim(claim("claim-x", "implementation.y", 1,
                                 "VERIFIED_FACT", source={"kind": "vibes"}))
        with self.assertRaises(ClaimValidationError):
            validate_claim({"id": "claim-x", "key": "implementation.y",
                            "value": 1, "type": "VERIFIED_FACT", "scope": "t"})

    # ---- T17 duplicate claim id rejected
    def test_t17_duplicate_id_rejected(self):
        path = write_registry([
            claim("claim-dup", "implementation.y", 1, "VERIFIED_FACT"),
            claim("claim-dup", "implementation.z", 2, "VERIFIED_FACT"),
        ])
        with self.assertRaises(ValueError) as ctx:
            load_registry(path)
        self.assertIn("duplicate claim id", str(ctx.exception))

    # ---- T18 broken supersedes reference reported
    def test_t18_broken_supersedes_reported(self):
        problems = RegistryProblems()
        self.resolve([claim("claim-a", "team.x", "v", "HUMAN_DECISION",
                            sup=["claim-ghost"])], problems=problems)
        self.assertTrue(any(p["kind"] == "BROKEN_SUPERSEDES"
                            for p in problems.items))


class RealDriftFixtureTests(unittest.TestCase):
    """F1-F5: regressions from ProjectMind's REAL observed drifts (seed)."""

    @classmethod
    def setUpClass(cls):
        cls.state = resolve(load_registry(SEED))

    # ---- F1 old role mapping vs V1
    def test_f1_role_mapping(self):
        cur = self.state["current"]["team.roles.v1"]
        self.assertEqual(cur["value"]["B"], "Code Facts")
        self.assertEqual(cur["type"], "HUMAN_DECISION")
        old = [s for s in self.state["stale"] if s["claim_id"] == "claim-old-role-map"]
        self.assertEqual(old[0]["state"], "SUPERSEDED")
        # the old mapping text must never appear as current anywhere
        self.assertNotIn("集成与体验", json.dumps(self.state["current"]))

    # ---- F2 old B interface description vs delivered shape
    def test_f2_code_facts_shape(self):
        cur = self.state["current"]["contract.code_facts_shape"]
        self.assertEqual(set(cur["value"]["kinds"]),
                         {"function", "async_function", "class", "method",
                          "async_method"})
        self.assertEqual(cur["value"]["qualified_names"],
                         "lexical dotted names (Class.method, outer.inner)")
        self.assertEqual(cur["claim_ids"], ["claim-b-shape"])

    # ---- F3 old report "B NOT IMPLEMENTED" vs PR #22 exists
    def test_f3_code_facts_status(self):
        cur = self.state["current"]["implementation.code_facts"]
        self.assertEqual(cur["value"]["status"], "PR_OPEN")
        hist = [h for h in self.state["historical"]
                if h["claim_id"] == "claim-b-not-implemented"]
        self.assertEqual(hist[0]["value"], "NOT_IMPLEMENTED")
        self.assertNotIn("NOT_IMPLEMENTED", json.dumps(cur))

    # ---- F4 old line reference vs current code line
    def test_f4_line_reference(self):
        self.assertEqual(
            self.state["current"]["implementation.build_snapshot_line"]["value"], 109)
        hist = [h for h in self.state["historical"]
                if h["claim_id"] == "claim-docs-line-106"]
        self.assertEqual(hist[0]["value"], 106)
        self.assertNotIn("106", json.dumps(self.state["current"]))

    # ---- F5 research suggestion vs actual contract
    def test_f5_research_not_promoted(self):
        research_keys = {r["key"] for r in self.state["research"]}
        self.assertIn("research.code_facts.performance", research_keys)
        self.assertNotIn("research.code_facts.performance", self.state["current"])
        shape = self.state["current"]["contract.code_facts_shape"]["value"]
        self.assertNotIn("cat-file", json.dumps(shape),
                         "research suggestion must not leak into contract")


class ConstructedScenarioTests(unittest.TestCase):
    """§28 conflict test and §29 stale test, end to end."""

    def test_conflict_then_resolution(self):
        claims = [
            claim("claim-a", "team.b_role", "Code Facts", "HUMAN_DECISION"),
            claim("claim-b", "team.b_role", "Architecture Proposal",
                  "HUMAN_DECISION"),
        ]
        state = resolve(claims)
        self.assertEqual(state["conflicts"][0]["resolution"], "HUMAN_REQUIRED")
        # add explicit supersedes -> deterministic resolution
        claims[0]["supersedes"] = ["claim-b"]
        state2 = resolve(claims)
        self.assertEqual(state2["conflicts"], [])
        self.assertEqual(state2["current"]["team.b_role"]["value"], "Code Facts")
        old = [s for s in state2["stale"] if s["claim_id"] == "claim-b"]
        self.assertEqual(old[0]["state"], "SUPERSEDED")

    def test_stale_pr_head_flow(self):
        def verifier(c):
            return {"status": "ok", "value": {"status": "PR_OPEN", "pr": 22,
                                              "head": "new-head-sha"},
                    "verified_at": "2026-10-02T04:00:00+00:00",
                    "source_kind": "gh_api"}
        state = resolve(
            [claim("claim-pr22", "implementation.pr_22_head",
                   {"status": "PR_OPEN", "pr": 22, "head": "old-head-sha"},
                   "VERIFIED_FACT")],
            verifiers={"implementation.pr_22_head": verifier})
        self.assertEqual(state["current"]["implementation.pr_22_head"]["value"]["head"],
                         "new-head-sha")
        self.assertEqual([s for s in state["stale"]
                          if s["claim_id"] == "claim-pr22"][0]["state"], "STALE")

    def test_verifier_unavailable_is_reported_not_faked(self):
        def verifier(c):
            return {"status": "unavailable", "reason": "offline"}
        state = resolve(
            [claim("claim-f", "implementation.thing", {"v": 1}, "VERIFIED_FACT")],
            verifiers={"implementation.thing": verifier})
        # An unavailable live check cannot certify the recorded volatile value.
        self.assertNotIn("implementation.thing", state["current"])
        self.assertEqual(state["stale"][0]["value"], {"v": 1})
        self.assertEqual(state["stale"][0]["verification_status"], "unavailable")
        self.assertEqual(state["verification_unavailable"][0]["reason"], "offline")


class HandleLayerTests(unittest.TestCase):
    """HTTP handle behavior per EXTENSION_INTERFACE conventions."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT))
        from extensions.context_authority import extension as ext
        cls.ext = ext
        cls.ctx = type("Ctx", (), {"repo": ROOT,
                                   "map_path": ROOT / "data" / "project-map.json",
                                   "snapshot": staticmethod(lambda: {}),
                                   "compare": staticmethod(lambda b, t: {})})()
        # keep handle tests hermetic: no network verification
        import extensions.context_authority.context_pack as cp
        cls.orig = cp.build_default_verifiers
        cp.build_default_verifiers = lambda repo: {}
        ext.build_default_verifiers = lambda repo: {}

    @classmethod
    def tearDownClass(cls):
        import extensions.context_authority.context_pack as cp
        cp.build_default_verifiers = cls.orig
        cls.ext.build_default_verifiers = cls.orig

    def test_get_state(self):
        out = self.ext.handle(self.ctx, "GET", {"action": "state"})
        self.assertIn("current", out)
        self.assertEqual(out["current"]["team.roles.v1"]["value"]["B"], "Code Facts")

    def test_get_claims_and_conflicts(self):
        claims = self.ext.handle(self.ctx, "GET", {"action": "claims"})
        self.assertEqual(len(claims["claims"]), 23)
        conflicts = self.ext.handle(self.ctx, "GET", {"action": "conflicts"})
        self.assertEqual(conflicts["conflicts"], [])

    def test_post_context_pack(self):
        out = self.ext.handle(self.ctx, "POST",
                              {"action": "context", "task": "Implement C Map Proposal"})
        self.assertEqual(out["task"], "Implement C Map Proposal")
        self.assertIn("architecture", out["task_domains"])
        self.assertTrue(out["do_not_assume"])
        self.assertTrue(out["evidence"])

    def test_post_resolve_state(self):
        out = self.ext.handle(self.ctx, "POST", {"action": "resolve_state"})
        self.assertIn("registry_hash", out)

    def test_strict_key_validation(self):
        from extension_host import ExtensionError
        with self.assertRaises(ExtensionError):
            self.ext.handle(self.ctx, "POST",
                            {"action": "context", "task": "x", "evil": 1})
        with self.assertRaises(ExtensionError):
            self.ext.handle(self.ctx, "POST", {"action": "nuke"})
        with self.assertRaises(ExtensionError):
            self.ext.handle(self.ctx, "GET", {"action": "everything"})

    def test_post_context_requires_task(self):
        from extension_host import ExtensionError
        with self.assertRaises(ExtensionError):
            self.ext.handle(self.ctx, "POST", {"action": "context"})


if __name__ == "__main__":
    unittest.main()
