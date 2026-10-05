# -*- coding: utf-8 -*-
"""C MEDIUM regressions: C-04/C-05/C-06/C-07/C-08.

Oracles from the independent audit section 4 (MEDIUM table) and the repair
plan sections 16/16xx. Each test reproduces the audit's real attack shape.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, model  # noqa: E402
from extensions.map_proposal.facts_adapter import FactsMismatch  # noqa: E402
from tests.test_w3_relations import (  # noqa: E402
    A_CLASS,
    B_CLASS,
    B2_CLASS,
    build_repo,
    facts_for,
    make_request,
    node,
    two_node_map,
    with_installed_b,
)


def run_engine(base_files, target_files, map_data, changed, facts=None,
               base_entries=None):
    repo, base, target, tmp = build_repo(base_files, target_files)
    if facts is None:
        facts = facts_for(target, sorted(
            {p for p in base_files} | {p for p in target_files}))
    request = {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": changed,
        "code_facts": facts,
        "current_map": map_data,
        "prior_decisions": [],
    }
    if base_entries is None:
        return engine.suggest_map(repo, request)
    with with_installed_b(base_entries):
        return engine.suggest_map(repo, request)


class C04EmptyDeclarations(unittest.TestCase):
    def test_c04_empty_entries_never_support_node_add(self):
        # Real-B shape: an added empty __init__.py comes back with
        # entries=[] (a present record, empty list). The pre-fix code only
        # diverted on a MISSING record, so the empty file became a NODE_ADD
        # candidate with zero declaration evidence.
        repo_base = {"pkg/a.py": A_CLASS}
        repo_target = {"pkg/a.py": A_CLASS, "pkg/__init__.py": ""}
        repo, base, target, tmp = build_repo(repo_base, repo_target)
        self.addCleanup(tmp.cleanup)
        facts = {
            "revision": target,
            "files": [
                {"path": "pkg/a.py",
                 "entries": [{"name": "A", "kind": "class", "line": 1}]},
                {"path": "pkg/__init__.py", "entries": []},
            ],
            "skipped": [],
        }
        request = make_request(base, target, two_node_map(),
                               facts=facts)
        request["changed_paths"] = [
            {"path": "pkg/a.py", "status": "modified"},
            {"path": "pkg/__init__.py", "status": "added"},
        ]
        res = engine.suggest_map(repo, request)
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])
        self.assertTrue(any(u["subject"] == "pkg/__init__.py"
                            and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))


class C05ResponsibilityIdentity(unittest.TestCase):
    def test_c05_tail_name_match_does_not_fire_responsibility(self):
        # Audit repro: top-level main stays, Widget.main is removed, yet the
        # entryPoint main was declared gone via tail-name matching.
        base_code = ("def main():\n    return 1\n\n"
                     "class Widget:\n    def main(self):\n        return 2\n")
        target_code = "def main():\n    return 1\n\nclass Widget:\n    pass\n"
        repo, base, target, tmp = build_repo({"pkg/a.py": base_code},
                                             {"pkg/a.py": target_code})
        self.addCleanup(tmp.cleanup)
        target_facts = {
            "revision": target,
            "files": [{"path": "pkg/a.py", "entries": [
                {"name": "main", "kind": "function", "line": 1},
                {"name": "Widget", "kind": "class", "line": 4},
            ]}],
            "skipped": [],
        }
        base_entries = {"pkg/a.py": [
            {"name": "main", "kind": "function", "line": 1},
            {"name": "Widget", "kind": "class", "line": 4},
            {"name": "Widget.main", "kind": "method", "line": 5},
        ]}
        request = make_request(base, target,
                               two_node_map(), facts=target_facts)
        request["current_map"]["nodes"] = [
            node("na", ["pkg/a.py"], entry="pkg/a.py · main()")]
        request["current_map"]["edges"] = []
        with with_installed_b(base_entries):
            res = engine.suggest_map(repo, request)
        self.assertEqual(
            [p for p in res["proposals"] if p["kind"] == "RESPONSIBILITY_CHANGE"], [])
        self.assertTrue(any("same-responsibility" in n["reason"]
                            for n in res["no_proposal"]))

    def test_c05_full_identity_still_fires_responsibility(self):
        # The oracle must not be weakened: when the entryPoint symbol itself
        # (full dotted identity) is gone, RESPONSIBILITY_CHANGE still fires.
        base_code = "def main():\n    return 1\n\nclass Widget:\n    pass\n"
        target_code = "class Widget:\n    pass\n"
        repo, base, target, tmp = build_repo({"pkg/a.py": base_code},
                                             {"pkg/a.py": target_code})
        self.addCleanup(tmp.cleanup)
        target_facts = {
            "revision": target,
            "files": [{"path": "pkg/a.py", "entries": [
                {"name": "Widget", "kind": "class", "line": 1},
            ]}],
            "skipped": [],
        }
        base_entries = {"pkg/a.py": [
            {"name": "main", "kind": "function", "line": 1},
            {"name": "Widget", "kind": "class", "line": 3},
        ]}
        request = make_request(base, target, two_node_map(), facts=target_facts)
        request["current_map"]["nodes"] = [
            node("na", ["pkg/a.py"], entry="pkg/a.py · main()")]
        request["current_map"]["edges"] = []
        with with_installed_b(base_entries):
            res = engine.suggest_map(repo, request)
        self.assertEqual(len([p for p in res["proposals"]
                              if p["kind"] == "RESPONSIBILITY_CHANGE"]), 1)


class C06UnsupportedImportSemantics(unittest.TestCase):
    def test_c06_direct_import_module_is_visible(self):
        res = run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "from importlib import import_module\n"
                                    "import_module('pkg.b')\n",
             "pkg/b.py": B_CLASS},
            two_node_map(),
            changed=[{"path": "pkg/a.py", "status": "modified"}],
        )
        self.assertEqual([p for p in res["proposals"]
                          if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py"
                            and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))

    def test_c06_aliased_import_module_is_visible(self):
        res = run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "from importlib import import_module as im\n"
                                    "im('pkg.b')\n",
             "pkg/b.py": B_CLASS},
            two_node_map(),
            changed=[{"path": "pkg/a.py", "status": "modified"}],
        )
        self.assertEqual([p for p in res["proposals"]
                          if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py"
                            and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))

    def test_c06_src_layout_unresolved_internal_import_is_visible(self):
        # src-layout: the repo holds src/pkg/b.py, the source imports pkg.b.
        # The resolver cannot explain it; the pre-fix code dropped it
        # silently (no relation, no diagnostic).
        base_code = "class A:\n    pass\n"
        target_code = base_code + "import pkg.b\n"
        repo, base, target, tmp = build_repo(
            {"src/pkg/a.py": base_code, "src/pkg/b.py": B_CLASS},
            {"src/pkg/a.py": target_code, "src/pkg/b.py": B_CLASS})
        self.addCleanup(tmp.cleanup)
        facts = {
            "revision": target,
            "files": [
                {"path": "src/pkg/a.py",
                 "entries": [{"name": "A", "kind": "class", "line": 1}]},
                {"path": "src/pkg/b.py",
                 "entries": [{"name": "B", "kind": "class", "line": 1}]},
            ],
            "skipped": [],
        }
        request = make_request(base, target, two_node_map(), facts=facts)
        request["changed_paths"] = [{"path": "src/pkg/a.py", "status": "modified"}]
        request["current_map"] = {
            "note": "m",
            "nodes": [node("na", ["src/pkg/a.py"]), node("nb", ["src/pkg/b.py"])],
            "edges": [{"from": "na", "to": "nb"}],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual([p for p in res["proposals"]
                          if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any("import resolution incomplete" in l
                            and "pkg.b" in l for l in res["limits"]))
        self.assertTrue(any(u["subject"] == "src/pkg/a.py"
                            and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))


class C07DegradedComparison(unittest.TestCase):
    def test_c07_missing_base_comparison_is_visible_degradation(self):
        # The path belongs to a map node but no base comparison is available
        # (no installed B on this base, no supplied base entries): the
        # responsibility channel must surface UNKNOWN, not an ordinary
        # no_proposal.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": "def main():\n    return 1\n"},
            {"pkg/a.py": "def run():\n    return 2\n"})
        self.addCleanup(tmp.cleanup)
        facts = {
            "revision": target,
            "files": [{"path": "pkg/a.py",
                       "entries": [{"name": "run", "kind": "function", "line": 1}]}],
            "skipped": [],
        }
        request = make_request(base, target, two_node_map(), facts=facts)
        request["current_map"]["nodes"] = [
            node("na", ["pkg/a.py"], entry="pkg/a.py · main()")]
        request["current_map"]["edges"] = []
        res = engine.suggest_map(repo, request)
        self.assertTrue(any(u["subject"] == "pkg/a.py"
                            and u["reason"] == "HUMAN_REQUIRED"
                            and "声明比较不可用" in u["note"]
                            for u in res["unresolved"]))
        self.assertFalse(any("no declaration comparison available" == n.get("reason")
                             for n in res["no_proposal"]))


class C08PathValidation(unittest.TestCase):
    def test_c08_supplied_facts_traversal_path_rejected(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS}, {"pkg/a.py": A_CLASS + "# t\n"})
        self.addCleanup(tmp.cleanup)
        facts = facts_for(target, ["pkg/a.py"])
        facts["files"].append({"path": "../../secret.py",
                               "entries": [{"name": "S", "kind": "class", "line": 1}]})
        request = make_request(base, target, two_node_map(), facts=facts)
        with self.assertRaises(FactsMismatch):
            engine.suggest_map(repo, request)

    def test_c08_entry_point_traversal_path_rejected(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS}, {"pkg/a.py": A_CLASS + "# t\n"})
        self.addCleanup(tmp.cleanup)
        map_data = two_node_map()
        map_data["nodes"][0]["entryPoint"] = "../../secret.py · main()"
        request = make_request(base, target, map_data)
        with self.assertRaises(model.RequestError):
            engine.suggest_map(repo, request)

    def test_c08_valid_paths_still_accepted(self):
        # The validation must not over-reject: ordinary repo paths in facts
        # and entryPoints keep flowing.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": "def main():\n    return 1\n"},
            {"pkg/a.py": "def main():\n    return 2\n"})
        self.addCleanup(tmp.cleanup)
        facts = facts_for(target, ["pkg/a.py"])
        request = make_request(base, target, two_node_map(), facts=facts)
        request["current_map"]["nodes"] = [
            node("na", ["pkg/a.py"], entry="pkg/a.py · main()")]
        request["current_map"]["edges"] = []
        res = engine.suggest_map(repo, request)
        self.assertIn(res["status"], ("rule_candidate", "empty"))


if __name__ == "__main__":
    unittest.main()
