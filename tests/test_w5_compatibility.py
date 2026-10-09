# -*- coding: utf-8 -*-
"""W5 convergence contract tests: compatibility envelope, mode honesty,
determinism, error and path boundaries, identity replay (A26-A29 subset,
X07/X09, F20 replay).
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, extension, model  # noqa: E402
from extensions.map_proposal.facts_adapter import FactsMismatch  # noqa: E402

REPO = Path(".").resolve()
SHA40 = "a" * 40
BASE = "c" * 40


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def request(**overrides):
    req = {
        "base_revision": BASE,
        "target_revision": SHA40,
        "changed_paths": [{"path": "services/auth.py", "status": "added"}],
        "code_facts": {"revision": SHA40,
                       "files": [{"path": "services/auth.py",
                                  "entries": [{"name": "AuthService", "kind": "class", "line": 1}]}],
                       "skipped": []},
        "current_map": {"note": "m", "nodes": [node("n1", ["app.py"])], "edges": []},
        "prior_decisions": [],
    }
    req.update(overrides)
    return req


def with_installed_b(entries_by_path):
    def collect(repo, revision, wanted):
        return {"revision": revision,
                "files": [{"path": p, "entries": e} for p, e in entries_by_path.items()],
                "skipped": []}

    fake = mock.Mock()
    fake.collect_code_facts = mock.Mock(side_effect=collect)
    return mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake})


class CompatibilityEnvelopeTests(unittest.TestCase):
    def test_legacy_candidates_equal_admitted_node_adds(self):
        with with_installed_b({}):
            res = engine.suggest_map(REPO, request())
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(res["candidates"]), len(node_adds))
        for candidate, proposal in zip(res["candidates"], node_adds):
            self.assertEqual(candidate["title"], proposal["proposed_change"]["title"])
            paths = {e["path"] for e in proposal["evidence"] if e.get("path")}
            self.assertTrue(set(candidate["evidencePaths"]) <= paths)

    def test_legacy_candidates_cannot_exceed_canonical(self):
        # RELATION-only output must project an empty legacy candidates list
        req = request(changed_paths=[{"path": "pkg/a.py", "status": "modified"}],
                      code_facts={"revision": SHA40,
                                  "files": [{"path": "pkg/a.py",
                                             "entries": [{"name": "A", "kind": "class", "line": 1}]}],
                                  "skipped": []},
                      current_map={"note": "m",
                                   "nodes": [node("na", ["pkg/a.py"]), node("nb", ["pkg/b.py"])],
                                   "edges": [{"from": "na", "to": "nb"}]})
        with with_installed_b({}):
            res = engine.suggest_map(REPO, req)
        self.assertEqual(res["candidates"], [])

    def test_revision_is_full_target_sha(self):
        with with_installed_b({}):
            res = engine.suggest_map(REPO, request())
        self.assertEqual(res["revision"], SHA40)
        self.assertEqual(res["request"]["target_revision"], SHA40)

    def test_x07_mode_honesty_with_placeholder_key(self):
        import os
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-placeholder"}):
            res = engine.suggest_map(REPO, request(mode="ai"))
        self.assertNotEqual(res["status"], "ai_candidate")
        self.assertEqual(res["status"], "rule_candidate")


class DeterminismAndIdentityTests(unittest.TestCase):
    def test_a26_repeat_is_byte_identical(self):
        with with_installed_b({}):
            first = engine.suggest_map(REPO, request())
            second = engine.suggest_map(REPO, request())
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_x09_same_basename_files_get_distinct_node_ids(self):
        first = model.node_id_for_path("svc/alpha/service.py", set())
        second = model.node_id_for_path("svc/beta/service.py", set())
        self.assertNotEqual(first, second)

    def test_node_id_respects_existing_map_ids(self):
        existing = {"mapnode-" + __import__("hashlib").sha256(b"app.py").hexdigest()[:10]}
        candidate = model.node_id_for_path("app.py", existing)
        self.assertNotIn(candidate, existing)


class ErrorBoundaryTests(unittest.TestCase):
    def test_malformed_facts_shape_controlled_rejection(self):
        with self.assertRaises(FactsMismatch):
            engine.suggest_map(REPO, request(code_facts={"revision": SHA40, "files": "nope"}))

    def test_malformed_map_shape_controlled_rejection(self):
        bad = {"note": "m", "nodes": [{"no_id": True}], "edges": []}
        with self.assertRaises(model.RequestError):
            engine.suggest_map(REPO, request(current_map=bad))

    def test_s28_rename_old_path_abuse_rejected(self):
        with self.assertRaises(model.RequestError):
            model.validate_request(request(changed_paths=[
                {"path": "b.py", "status": "renamed", "old_path": "../secret.py"}]))

    def test_installed_b_exception_shape_not_available(self):
        fake = mock.Mock()
        fake.collect_code_facts = mock.Mock(side_effect=RuntimeError("boom"))
        with mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake}):
            res = engine.suggest_map(REPO, request(code_facts=None))
        self.assertEqual(res["status"], "degraded")

    def test_no_position_anywhere_in_any_proposal(self):
        with with_installed_b({}):
            res = engine.suggest_map(REPO, request())
        for proposal in res["proposals"]:
            self.assertNotIn("position", proposal["proposed_change"])
            self.assertEqual(proposal["status"], "PROPOSED")
            self.assertTrue(proposal["human_required"])
            self.assertTrue(proposal["evidence"])


class F20ReplayTests(unittest.TestCase):
    def test_rejected_candidate_suppressed_and_limit_traced(self):
        req = request(prior_decisions=[{"subject": "services/auth.py", "kind": "NODE_ADD",
                                        "decision": "REJECTED"}])
        with with_installed_b({}):
            res = engine.suggest_map(REPO, req)
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])
        self.assertTrue(any("F20" in l and "services/auth.py" in l for l in res["limits"]))

    def test_accepted_deferred_do_not_suppress(self):
        req = request(prior_decisions=[{"subject": "services/auth.py", "kind": "NODE_ADD",
                                        "decision": "DEFERRED"}])
        with with_installed_b({}):
            res = engine.suggest_map(REPO, req)
        self.assertEqual(len([p for p in res["proposals"] if p["kind"] == "NODE_ADD"]), 1)


if __name__ == "__main__":
    unittest.main()
