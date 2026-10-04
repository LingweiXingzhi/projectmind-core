# -*- coding: utf-8 -*-
"""W1 convergence contract tests: pins, B gate, skipped eligibility, path
safety, canonical result, stable identity, no-map-write.

Oracles: S14/S15/S26/S27/S28/S29 subset + model identity units. Historical
behaviors that the convergence contract rejects (implicit HEAD fallback,
empty-map intake, mode-keyed ai_candidate) are asserted as controlled
rejections now (C_CONVERGENCE_PLAN §7/§8).
"""
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, extension, facts_adapter, model  # noqa: E402
from extensions.map_proposal.facts_adapter import FactsMismatch  # noqa: E402

REPO = Path(".").resolve()


def valid_map():
    return {
        "note": "test map",
        "nodes": [
            {
                "id": "n1",
                "title": "Node One",
                "summary": "s",
                "entryPoint": "app.py · main()",
                "evidence": [{"path": "app.py", "reason": "r"}],
            }
        ],
        "edges": [],
    }


def supplied_facts(rev, files=None, skipped=None):
    return {"revision": rev, "files": files or [], "skipped": skipped or []}


def make_request(rev, **overrides):
    request = {
        "base_revision": rev,
        "target_revision": rev,
        "changed_paths": [],
        "code_facts": supplied_facts(rev),
        "current_map": valid_map(),
    }
    request.update(overrides)
    return request


class FakeContext:
    repo = REPO


CTX = FakeContext()
SHA40 = "a" * 40
SHA64 = "b" * 64


class PinGateTests(unittest.TestCase):
    def test_missing_pins_controlled_rejection_no_snapshot_fallback(self):
        with self.assertRaises(Exception) as ctx_exc:
            extension.handle(CTX, "POST", {"code_facts": supplied_facts(SHA40)})
        self.assertIn("pin", str(ctx_exc.exception))

    def test_head_and_short_sha_rejected(self):
        for bad in ("HEAD", SHA40[:8], "main", SHA40.upper()):
            with self.assertRaises(Exception):
                model.validate_request(make_request(bad))

    def test_full_40_and_64_hex_accepted(self):
        for rev in (SHA40, SHA64):
            res = extension.handle(CTX, "POST", make_request(rev))
            self.assertEqual(res["request"]["target_revision"], rev)

    def test_base_equals_target_zero_proposal_after_gates(self):
        res = extension.handle(CTX, "POST", make_request(SHA40))
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(n["reason"] == "same_revision" for n in res["no_proposal"]))

    def test_empty_changes_with_different_pins_rejected(self):
        with self.assertRaises(Exception):
            model.validate_request(make_request(SHA40, base_revision="c" * 40))


class BGateTests(unittest.TestCase):
    def base_req(self, facts):
        return make_request(SHA40, base_revision="c" * 40,
                            changed_paths=[{"path": "app.py", "status": "modified"}],
                            code_facts=facts)

    def test_supplied_mismatch_rejected_on_normal_path(self):
        with self.assertRaises(Exception):
            extension.handle(CTX, "POST", self.base_req(supplied_facts("d" * 40)))

    def test_supplied_mismatch_rejected_on_same_revision(self):
        with self.assertRaises(Exception):
            extension.handle(CTX, "POST", make_request(SHA40, code_facts=supplied_facts("d" * 40)))

    def test_supplied_mismatch_rejected_on_empty_changes(self):
        with self.assertRaises(Exception):
            extension.handle(CTX, "POST", make_request(SHA40, code_facts=supplied_facts("d" * 40)))

    def test_supplied_non_dict_shape_controlled_rejection(self):
        with self.assertRaises(Exception):
            extension.handle(CTX, "POST", make_request(SHA40, code_facts=[1, 2]))

    def test_installed_b_mismatch_rejected(self):
        fake = mock.Mock()
        fake.collect_code_facts = mock.Mock(return_value={"revision": "d" * 40, "files": [], "skipped": []})
        with mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake}):
            with self.assertRaises(FactsMismatch):
                engine.suggest_map(REPO, make_request(SHA40, code_facts=None))

    def test_installed_b_shape_exception_degraded_not_crash(self):
        fake = mock.Mock()
        fake.collect_code_facts = mock.Mock(return_value=["not", "a", "dict"])
        with mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake}):
            res = engine.suggest_map(REPO, make_request(SHA40, code_facts=None))
        self.assertEqual(res["status"], "degraded")
        self.assertTrue(res["limits"])

    def test_b_unavailable_degraded_with_limits_no_fabricated_fact(self):
        res = engine.suggest_map(REPO, make_request(SHA40, code_facts=None))
        self.assertEqual(res["status"], "degraded")
        self.assertTrue(any("code facts" in l for l in res["limits"]))
        for proposal in res["proposals"]:
            for ev in proposal["evidence"]:
                self.assertNotEqual(ev["kind"], "code_fact")


class SkippedEligibilityTests(unittest.TestCase):
    def test_changed_skipped_becomes_human_required(self):
        facts = supplied_facts(SHA40, skipped=[{"path": "app.py", "reason": "syntax"}])
        res = extension.handle(
            CTX, "POST",
            make_request(SHA40, base_revision="c" * 40,
                         changed_paths=[{"path": "app.py", "status": "modified"}],
                         code_facts=facts),
        )
        self.assertTrue(any(u["subject"] == "app.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))

    def test_unchanged_skipped_not_reported(self):
        facts = supplied_facts(SHA40, skipped=[{"path": "other.py", "reason": "syntax"}])
        res = extension.handle(
            CTX, "POST",
            make_request(SHA40, base_revision="c" * 40,
                         changed_paths=[{"path": "app.py", "status": "modified"}],
                         code_facts=facts),
        )
        self.assertFalse(any(u["subject"] == "other.py" for u in res["unresolved"]))

    def test_unified_eligibility(self):
        facts = {"files": {"a.py": []}, "skipped": {"b.py"}}
        self.assertEqual(facts_adapter.path_eligibility("a.py", facts), "eligible")
        self.assertEqual(facts_adapter.path_eligibility("b.py", facts), "skipped")
        self.assertEqual(facts_adapter.path_eligibility("c.py", facts), "missing")
        self.assertEqual(facts_adapter.domain_eligibility(["a.py", "b.py"], facts), "skipped")
        self.assertEqual(facts_adapter.domain_eligibility(["c.py"], facts), "missing")


class PathSafetyTests(unittest.TestCase):
    def test_unsafe_changed_paths_rejected(self):
        for bad in ("../x.py", "/etc/passwd", "a\\b.py", "a//b.py", "./a.py"):
            with self.assertRaises(Exception):
                model.validate_path(bad)

    def test_unsafe_map_evidence_path_rejected(self):
        bad_map = valid_map()
        bad_map["nodes"][0]["evidence"][0]["path"] = "../secret.py"
        with self.assertRaises(Exception):
            model.validate_map(bad_map)

    def test_facts_and_entry_point_paths_bounded(self):
        with self.assertRaises(Exception):
            model.validate_path("x" * 600)
        self.assertEqual(model.parse_entry_point("app.py · main()"), ("app.py", "main"))


class MapIntakeTests(unittest.TestCase):
    def test_empty_nodes_rejected(self):
        with self.assertRaises(Exception):
            model.validate_map({"nodes": [], "edges": []})

    def test_missing_node_id_rejected(self):
        bad = valid_map()
        del bad["nodes"][0]["id"]
        with self.assertRaises(Exception):
            model.validate_map(bad)

    def test_edge_unknown_reference_rejected(self):
        bad = valid_map()
        bad["edges"] = [{"from": "n1", "to": "ghost"}]
        with self.assertRaises(Exception):
            model.validate_map(bad)

    def test_missing_current_map_rejected(self):
        with self.assertRaises(Exception):
            engine.suggest_map(REPO, make_request(SHA40, current_map=None))


class CanonicalAndIdentityTests(unittest.TestCase):
    def test_canonical_buckets_and_request_trace(self):
        res = extension.handle(CTX, "POST", make_request(SHA40))
        for key in ("proposals", "unresolved", "no_proposal", "limits", "request", "status", "revision"):
            self.assertIn(key, res)
        self.assertEqual(res["request"]["base_revision"], SHA40)

    def test_determinism_same_input_same_output(self):
        request = make_request(SHA40, base_revision="c" * 40,
                               changed_paths=[{"path": "app.py", "status": "modified"}])
        first = extension.handle(CTX, "POST", request)
        second = extension.handle(CTX, "POST", request)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_mode_honesty_no_ai_candidate_without_model(self):
        request = make_request(SHA40, mode="ai")
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            res = extension.handle(CTX, "POST", request)
        self.assertNotEqual(res["status"], "ai_candidate")

    def test_proposal_id_stable_and_payload_sensitive(self):
        pid1 = model.proposal_id_for(SHA40, "NODE_ADD", "a.py", {"node_id": "x"})
        pid2 = model.proposal_id_for(SHA40, "NODE_ADD", "a.py", {"node_id": "x"})
        pid3 = model.proposal_id_for(SHA40, "NODE_ADD", "a.py", {"node_id": "y"})
        self.assertEqual(pid1, pid2)
        self.assertNotEqual(pid1, pid3)
        self.assertTrue(pid1.startswith(f"mp-{SHA40[:8]}-"))

    def test_node_id_collision_widening(self):
        existing = {"mapnode-" + hashlib.sha256(b"a.py").hexdigest()[:10]}
        widened = model.node_id_for_path("a.py", existing)
        self.assertNotIn(widened, existing)
        self.assertTrue(widened.startswith("mapnode-"))

    def test_make_proposal_rejects_position_and_empty_evidence(self):
        with self.assertRaises(ValueError):
            model.make_proposal(SHA40, "NODE_ADD", "a.py", {"position": {"x": 1}}, "r",
                                [{"kind": "git_diff", "revision": SHA40}], "medium", [])
        with self.assertRaises(ValueError):
            model.make_proposal(SHA40, "NODE_ADD", "a.py", {}, "r", [], "medium", [])

    def test_legacy_projection_from_admitted_node_add_only(self):
        proposal = model.make_proposal(
            SHA40, "NODE_ADD", "a.py",
            {"node_id": model.node_id_for_path("a.py", set()), "title": "t", "summary": "s"},
            "rationale",
            [model.make_evidence("git_diff", revision=SHA40, path="a.py", detail="d")],
            "medium", ["u"],
        )
        projected = engine._legacy_candidates([proposal])
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["evidencePaths"], ["a.py"])


class NoMapWriteTests(unittest.TestCase):
    def test_map_file_hash_unchanged(self):
        map_path = ROOT / "data" / "project-map.json"
        before = hashlib.sha256(map_path.read_bytes()).hexdigest()
        extension.handle(CTX, "POST", make_request(SHA40))
        after = hashlib.sha256(map_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class CoreCompareAdapterTests(unittest.TestCase):
    def test_core_changes_mapped_to_changed_paths(self):
        adapted = model.adapt_core_compare({
            "baseRevision": "c" * 40,
            "targetRevision": SHA40,
            "changes": [
                {"code": "A", "path": "new.py"},
                {"code": "M", "path": "app.py"},
                {"code": "D", "path": "old.py"},
                {"code": "R100", "oldPath": "a.py", "path": "b.py"},
            ],
        })
        request = model.validate_request(adapted)
        statuses = {c["path"]: c["status"] for c in request["changed_paths"]}
        self.assertEqual(statuses["new.py"], "added")
        self.assertEqual(statuses["app.py"], "modified")
        self.assertEqual(statuses["old.py"], "removed")
        self.assertEqual(statuses["b.py"], "renamed")
        renamed = request["changed_paths"][3]
        self.assertEqual(renamed["old_path"], "a.py")


if __name__ == "__main__":
    unittest.main()
