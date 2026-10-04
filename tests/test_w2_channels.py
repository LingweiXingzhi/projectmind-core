# -*- coding: utf-8 -*-
"""W2 convergence contract tests: diff × map channels.

Oracles: S01 (NODE_ADD precision), S04 (rename link), S05/S16 (stale map
existence), S06 (responsibility, no first-symbol pick), S09/S10 (helper and
internal class do not create nodes), F20 (prior REJECTED suppression), plus
F04 cross-channel skipped suppression and base==target silence (invariant 13).
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, gitio  # noqa: E402

REPO = Path(".").resolve()
SHA40 = "a" * 40
BASE = "c" * 40


def map_node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or (f"{paths[0]} · main()" if paths else "x.py · main()"),
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def valid_map(nodes):
    return {"note": "m", "nodes": nodes, "edges": []}


def entries(*triples):
    return [{"name": n, "kind": k, "line": l} for n, k, l in triples]


def make_request(base, target, changed, facts_files, map_nodes, skipped=None, prior=None):
    return {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": changed,
        "code_facts": {"revision": target, "files": facts_files, "skipped": skipped or []},
        "current_map": valid_map(map_nodes),
        "prior_decisions": prior or [],
    }


def with_base_facts(files_by_path):
    """Mock installed B for the base-revision declaration comparison."""
    fake = mock.Mock()
    fake.collect_code_facts = mock.Mock(
        return_value={
            "revision": BASE,
            "files": [{"path": p, "entries": e} for p, e in files_by_path.items()],
            "skipped": [],
        }
    )
    return mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake})


def patch_trees(target_paths, base_paths):
    def ls_tree(repo, revision):
        return set(target_paths) if revision == SHA40 else set(base_paths)

    return mock.patch.object(gitio, "ls_tree_names", side_effect=ls_tree)


class NodeAddTests(unittest.TestCase):
    def test_s01_new_module_exact_node_with_structured_evidence(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "services/auth.py", "status": "added"}],
            [{"path": "services/auth.py",
              "entries": entries(("AuthService", "class", 1), ("helper", "function", 10),
                                 ("Auth.inner", "class", 20))}],
            [map_node("n1", ["app.py"])],
        )
        res = engine.suggest_map(REPO, request)
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        proposal = node_adds[0]
        self.assertEqual(proposal["subject"], "services/auth.py")
        self.assertEqual(proposal["status"], "PROPOSED")
        self.assertTrue(proposal["human_required"])
        self.assertNotIn("position", proposal["proposed_change"])
        self.assertEqual(proposal["proposed_change"]["entryPoint"], "services/auth.py · AuthService")
        self.assertTrue(proposal["proposed_change"]["node_id"].startswith("mapnode-"))
        facts_ev = [e for e in proposal["evidence"] if e["kind"] == "code_fact"]
        names = {e.get("name") for e in facts_ev if e.get("name")}
        self.assertEqual(names, {"AuthService", "helper"})
        for ev in facts_ev:
            self.assertEqual(ev["revision"], SHA40)
            self.assertEqual(ev["path"], "services/auth.py")

    def test_s01_function_only_module_still_low_confidence_node(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "tools/render.py", "status": "added"}],
            [{"path": "tools/render.py", "entries": entries(("draw", "function", 3))}],
            [map_node("n1", ["app.py"])],
        )
        res = engine.suggest_map(REPO, request)
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertEqual(node_adds[0]["confidence"], "low")
        self.assertNotIn("entryPoint", node_adds[0]["proposed_change"])
        self.assertTrue(any("function-only" in u for u in node_adds[0]["uncertainty"]))

    def test_map_covered_added_path_not_a_node(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "app.py", "status": "added"}],
            [{"path": "app.py", "entries": entries(("App", "class", 1))}],
            [map_node("n1", ["app.py"])],
        )
        res = engine.suggest_map(REPO, request)
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])
        self.assertTrue(any("already declared" in n["reason"] for n in res["no_proposal"]))

    def test_test_noise_and_generated_not_nodes(self):
        for path, reason in (("tests/test_x.py", "test-only addition"),
                             ("gen/x_pb2.py", "generated or mechanical file")):
            request = make_request(
                BASE, SHA40, [{"path": path, "status": "added"}],
                [{"path": path, "entries": entries(("A", "class", 1))}],
                [map_node("n1", ["app.py"])],
            )
            res = engine.suggest_map(REPO, request)
            self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [],
                             path)
            self.assertTrue(any(n["reason"] == reason for n in res["no_proposal"]), path)

    def test_added_without_facts_entries_is_unresolved(self):
        request = make_request(
            BASE, SHA40, [{"path": "new.py", "status": "added"}],
            [], [map_node("n1", ["app.py"])],
        )
        res = engine.suggest_map(REPO, request)
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "new.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))


class ModifiedChannelTests(unittest.TestCase):
    def base(self, base_entries, target_entries, entry="app.py · main()"):
        request = make_request(
            BASE, SHA40, [{"path": "app.py", "status": "modified"}],
            [{"path": "app.py", "entries": target_entries}],
            [map_node("n1", ["app.py"], entry=entry)],
        )
        with with_base_facts({"app.py": base_entries}):
            return engine.suggest_map(REPO, request)

    def test_s09_helper_only_no_node_no_strong_proposal(self):
        res = self.base(entries(("main", "function", 1)),
                        entries(("main", "function", 1), ("helper", "function", 9)))
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any("same-responsibility internal change" in n["reason"]
                            for n in res["no_proposal"]))

    def test_s10_added_class_does_not_become_node(self):
        res = self.base(entries(("main", "function", 1)),
                        entries(("main", "function", 1), ("Inner", "class", 12)))
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])
        self.assertEqual(res["proposals"], [])

    def test_s07_comment_only_zero_strong_proposal(self):
        res = self.base(entries(("main", "function", 1)), entries(("main", "function", 1)))
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any("no declaration-level change" in n["reason"]
                            for n in res["no_proposal"]))

    def test_s06_entrypoint_gone_responsibility_no_first_symbol_pick(self):
        res = self.base(entries(("main", "function", 1)),
                        entries(("run", "function", 1), ("other", "function", 5)))
        responsibilities = [p for p in res["proposals"] if p["kind"] == "RESPONSIBILITY_CHANGE"]
        self.assertEqual(len(responsibilities), 1)
        proposal = responsibilities[0]
        self.assertEqual(proposal["subject"], "n1")
        self.assertIsNone(proposal["proposed_change"]["entryPoint"])
        self.assertTrue(any("run" in u for u in proposal["uncertainty"]))
        self.assertTrue(any("chosen by human" in u for u in proposal["uncertainty"]))

    def test_declaration_change_outside_map_domains_unresolved(self):
        request = make_request(
            BASE, SHA40, [{"path": "app.py", "status": "modified"}],
            [{"path": "app.py", "entries": entries(("run", "function", 1))}],
            [map_node("n1", ["other.py"])],
        )
        with with_base_facts({"app.py": entries(("main", "function", 1))}):
            res = engine.suggest_map(REPO, request)
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "app.py" for u in res["unresolved"]))


class RenameTests(unittest.TestCase):
    def test_s04_rename_updates_link_not_node(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "b.py", "status": "renamed", "old_path": "a.py"}],
            [{"path": "b.py", "entries": entries(("Svc", "class", 1))}],
            [map_node("n1", ["a.py"])],
        )
        res = engine.suggest_map(REPO, request)
        self.assertEqual(len(res["proposals"]), 1)
        proposal = res["proposals"][0]
        self.assertEqual(proposal["kind"], "IMPLEMENTATION_LINK_CHANGE")
        self.assertEqual(proposal["proposed_change"]["node_id"], "n1")
        self.assertEqual(proposal["proposed_change"]["evidence_path_update"],
                         {"from": "a.py", "to": "b.py"})
        revs = {(e["revision"], e["path"]) for e in proposal["evidence"] if e["kind"] == "git_diff"}
        self.assertIn((BASE, "a.py"), revs)
        self.assertIn((SHA40, "b.py"), revs)

    def test_s17_multiple_owners_ambiguity_flagged(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "b.py", "status": "renamed", "old_path": "a.py"}],
            [{"path": "b.py", "entries": entries(("Svc", "class", 1))}],
            [map_node("n1", ["a.py"]), map_node("n2", ["a.py"])],
        )
        res = engine.suggest_map(REPO, request)
        self.assertEqual(res["proposals"][0]["confidence"], "low")
        self.assertTrue(any("multiple candidate nodes" in u
                            for u in res["proposals"][0]["uncertainty"]))


class StaleMapTests(unittest.TestCase):
    def stale_request(self, evidence_paths):
        return make_request(
            BASE, SHA40, [{"path": "app.py", "status": "modified"}],
            [{"path": "app.py", "entries": entries(("main", "function", 1))}],
            [map_node("n1", evidence_paths)],
        )

    def run_stale(self, request, target_paths, base_paths):
        with with_base_facts({}):
            with patch_trees(target_paths, base_paths):
                return engine.suggest_map(REPO, request)

    def test_s16_fully_gone_at_target_removal_candidate(self):
        res = self.run_stale(self.stale_request(["gone.py"]), ["app.py"], ["app.py", "gone.py"])
        removals = [p for p in res["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE"]
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0]["subject"], "n1")
        self.assertEqual(removals[0]["confidence"], "low")

    def test_s16_deleted_before_base_flagged_honestly(self):
        res = self.run_stale(self.stale_request(["gone.py"]), ["app.py"], ["app.py"])
        removals = [p for p in res["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE"]
        self.assertEqual(len(removals), 1)
        self.assertTrue(any("already absent at base" in u
                            for u in removals[0]["uncertainty"]))

    def test_s05_partial_evidence_retained_no_removal(self):
        res = self.run_stale(self.stale_request(["gone.py", "app.py"]), ["app.py"], ["app.py", "gone.py"])
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE"], [])

    def test_read_failure_is_unknown_not_absence(self):
        request = self.stale_request(["gone.py"])
        with mock.patch.object(gitio, "ls_tree_names",
                               side_effect=gitio.DiffSignalError("boom")):
            res = engine.suggest_map(REPO, request)
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE"], [])
        self.assertTrue(any("stale-map existence check unavailable" in l for l in res["limits"]))

    def test_base_equals_target_zero_proposal_even_with_stale_map(self):
        request = make_request(
            SHA40, SHA40, [], [], [map_node("n1", ["gone.py"])]
        )
        with patch_trees(["app.py"], ["app.py"]):
            res = engine.suggest_map(REPO, request)
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(n["reason"] == "same_revision" for n in res["no_proposal"]))


class SkippedAndPriorTests(unittest.TestCase):
    def test_f04_skipped_source_never_feeds_strong_candidates(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "broken.py", "status": "modified"},
             {"path": "app.py", "status": "modified"}],
            [{"path": "app.py", "entries": entries(("main", "function", 1))}],
            [map_node("n1", ["app.py"])],
            skipped=[{"path": "broken.py", "reason": "syntax"}],
        )
        with with_base_facts({"app.py": entries(("main", "function", 1))}):
            res = engine.suggest_map(REPO, request)
        self.assertTrue(any(u["subject"] == "broken.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))
        for proposal in res["proposals"]:
            subjects = {proposal["subject"]}
            subjects.update(e.get("path", "") for e in proposal["evidence"])
            self.assertNotIn("broken.py", subjects)
        # normal source still analyzed by its own channel
        self.assertTrue(any("no declaration-level change" in n["reason"]
                            for n in res["no_proposal"]))

    def test_f20_prior_rejected_suppression(self):
        request = make_request(
            BASE, SHA40, [{"path": "gone.py", "status": "modified"}],
            [{"path": "gone.py", "entries": entries(("main", "function", 1))}],
            [map_node("n1", ["gone.py"]), map_node("n2", ["app.py"])],
            prior=[{"subject": "n1", "kind": "NODE_REMOVE_CANDIDATE", "decision": "REJECTED"}],
        )
        with with_base_facts({}):
            with patch_trees(["app.py"], ["app.py"]):
                res = engine.suggest_map(REPO, request)
        self.assertEqual([p for p in res["proposals"] if p["subject"] == "n1"], [])
        self.assertTrue(any("F20" in l and "n1" in l for l in res["limits"]))

    def test_determinism_full_request(self):
        request = make_request(
            BASE, SHA40,
            [{"path": "services/auth.py", "status": "added"}],
            [{"path": "services/auth.py", "entries": entries(("A", "class", 1))}],
            [map_node("n1", ["app.py"])],
        )
        with with_base_facts({}):
            with patch_trees(["app.py", "services/auth.py"], ["app.py"]):
                first = engine.suggest_map(REPO, request)
                second = engine.suggest_map(REPO, request)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
