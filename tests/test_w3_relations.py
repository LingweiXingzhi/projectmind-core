# -*- coding: utf-8 -*-
"""W3 convergence contract tests: the independent import-relation channel.

Oracles: S02 (real RELATION_ADD incl. X01 unchanged-declarations), S03
(relation removal + multi-source remaining import), S11 (docstring import
text is never a relation), X02 (dynamic import → UNKNOWN unresolved), X13
(churn), F04 (skipped source never feeds relations). Blobs are read from a
real temporary git repository so AST proofs run against actual pinned content.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine  # noqa: E402


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def rev_of(cwd):
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def write_tree(repo, files):
    for path, content in files.items():
        target = repo / path
        if content is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build_repo(base_files, target_files):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(repo, "init")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    write_tree(repo, base_files)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = rev_of(repo)
    write_tree(repo, target_files)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = rev_of(repo)
    return repo, base, target, tmp


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def two_node_map(edges=(("na", "nb"),), extra_na_paths=()):
    na_paths = ["pkg/a.py", *extra_na_paths]
    return {
        "note": "m",
        "nodes": [node("na", na_paths), node("nb", ["pkg/b.py"])],
        "edges": [{"from": f, "to": t} for f, t in edges],
    }


def facts_for(target, paths):
    return {
        "revision": target,
        "files": [{"path": p, "entries": [{"name": "X", "kind": "class", "line": 1}]} for p in paths],
        "skipped": [],
    }


def make_request(base, target, map_data, facts=None, skipped=None):
    facts = facts or facts_for(target, ["pkg/a.py", "pkg/b.py"])
    if skipped:
        facts = dict(facts)
        facts["skipped"] = list(skipped)
    return {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
        "code_facts": facts,
        "current_map": map_data,
        "prior_decisions": [],
    }


def with_installed_b(entries_by_path):
    """Mock installed B: base-revision declaration facts for the comparison."""
    from unittest import mock

    def collect(repo, revision, wanted):
        return {
            "revision": revision,
            "files": [{"path": p, "entries": e} for p, e in entries_by_path.items()],
            "skipped": [],
        }

    fake = mock.Mock()
    fake.collect_code_facts = mock.Mock(side_effect=collect)
    return mock.patch.dict(sys.modules, {"extensions.code_facts.facts": fake})


A_CLASS = "class A:\n    pass\n"
B_CLASS = "class B:\n    pass\n"


class RelationChannelTests(unittest.TestCase):
    def run_engine(self, base_files, target_files, map_data, facts=None, skipped=None,
                   base_entries=None):
        repo, base, target, tmp = build_repo(base_files, target_files)
        self.addCleanup(tmp.cleanup)
        request = make_request(base, target, map_data, facts=facts, skipped=skipped)
        if base_entries is None:
            return engine.suggest_map(repo, request)
        with with_installed_b(base_entries):
            return engine.suggest_map(repo, request)

    def test_s02_x01_real_import_add_with_unchanged_declarations(self):
        # supplied target facts declare X; the installed-B mock returns the
        # same declarations at base so the declaration channel sees no change
        same = [{"name": "X", "kind": "class", "line": 1}]
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
            base_entries={"pkg/a.py": same, "pkg/b.py": same},
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0]["proposed_change"]["from"], "na")
        self.assertEqual(adds[0]["proposed_change"]["to"], "nb")
        self.assertEqual(adds[0]["confidence"], "medium")
        # declaration channel independently found no declaration change, yet
        # the import channel still fired (F05 independence)
        self.assertTrue(any("no declaration-level change" in n["reason"]
                            for n in res["no_proposal"]))
        self.assertEqual(len(res["proposals"]), 1)

    def test_s11_x03_docstring_import_text_never_a_relation(self):
        docstring = '"""Usage:\nimport pkg.b\n"""\n'
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": docstring + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertEqual(res["proposals"], [])

    def test_s03_x11_last_import_removed_gives_removal_candidate(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        removals = [p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"]
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0]["proposed_change"]["from"], "na")
        self.assertEqual(removals[0]["proposed_change"]["to"], "nb")

    def test_s03_multi_source_remaining_import_no_removal(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS,
             "pkg/a2.py": "from pkg.b import B\n", "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS,
             "pkg/a2.py": "from pkg.b import B\n", "pkg/b.py": B_CLASS},
            two_node_map(extra_na_paths=["pkg/a2.py"]),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"], [])

    def test_removal_requires_existing_map_edge(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(edges=()),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"], [])

    def test_x13_import_rewrite_churn_no_relation(self):
        # F06 contract: "同一规范化目标的写法变换不产生关系变化". The AST
        # channel diffs RESOLVED import-target sets, so `import os` →
        # `from os import path` (no repo-internal relation change) yields no
        # signal at all — stronger than the old signal-then-suppress churn
        # guard, whose "churn" limit diagnostic no longer exists.
        res = self.run_engine(
            {"pkg/a.py": "import os\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from os import path\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual(res["proposals"], [])
        self.assertEqual([l for l in res["limits"] if "import" in l], [])

    def test_x02_dynamic_import_unknown_unresolved(self):
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "import importlib\n\n" + A_CLASS +
             "\nimportlib.import_module('pkg.b')\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))

    def test_parse_failure_is_unknown_not_zero(self):
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\ndef broken(:\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual([p for p in res["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any("import 信号无法用 AST 证实" in u["note"] or "AST" in u["note"]
                            for u in res["unresolved"]))

    def test_f04_x21_skipped_source_never_feeds_relations(self):
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(),
            skipped=[{"path": "pkg/a.py", "reason": "syntax"}],
        )
        self.assertEqual(
            [p for p in res["proposals"]
             if p["kind"] in ("RELATION_ADD", "RELATION_REMOVE_CANDIDATE")], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" for u in res["unresolved"]))

    def test_adversarial_1a_relative_from_dot_import_submodule(self):
        # Adversarial 1a (silent miss at 78c2751): `from . import b` must
        # resolve .b against the source package and yield RELATION_ADD.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
            {"pkg/a.py": A_CLASS + "from . import b\n", "pkg/b.py": B_CLASS,
             "pkg/__init__.py": ""},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_adversarial_1b_relative_from_dot_module_import(self):
        # Adversarial 1b (silent miss at 78c2751): `from .b import B`.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
            {"pkg/a.py": A_CLASS + "from .b import B\n", "pkg/b.py": B_CLASS,
             "pkg/__init__.py": ""},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_adversarial_3_from_package_import_submodule(self):
        # Adversarial 3 (silent miss at 78c2751): `from pkg import b` where
        # b is the submodule pkg/b.py — alias expansion must propose pkg.b.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS, "pkg/__init__.py": ""},
            {"pkg/a.py": A_CLASS + "from pkg import b\n", "pkg/b.py": B_CLASS,
             "pkg/__init__.py": ""},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_multiline_parenthesized_from_import(self):
        # Adversarial 4 (silent miss at 78c2751), valid form: parenthesized
        # multiline from-imports are AST-native, no line-based extractor.
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "from pkg.b import (\n    B,\n)\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_invalid_multiline_import_is_unknown_not_silent(self):
        # Adversarial 4 original form was a SyntaxError (`import (\n...`):
        # unsupported/invalid syntax must surface as UNKNOWN (unresolved +
        # limits), never as silent no-change (C-3).
        res = self.run_engine(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "import (\n    pkg.b,\n)\n", "pkg/b.py": B_CLASS},
            two_node_map(),
        )
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))
        self.assertTrue(any("import signal extraction unavailable" in l
                            for l in res["limits"]))

    def test_s03_domain_proof_is_ast_not_text(self):
        # Mutation M4 (DROP L05 regression) showed no test bound the domain
        # removal proof to AST: a remaining source file whose only "import"
        # is docstring text must NOT retain the relation, so the removal
        # candidate for the source that truly dropped the import still fires.
        res = self.run_engine(
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS,
             "pkg/a2.py": '"""from pkg.b import B"""\n' + A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS,
             "pkg/a2.py": '"""from pkg.b import B"""\n' + A_CLASS, "pkg/b.py": B_CLASS},
            two_node_map(extra_na_paths=["pkg/a2.py"]),
        )
        removals = [p for p in res["proposals"] if p["kind"] == "RELATION_REMOVE_CANDIDATE"]
        self.assertEqual(len(removals), 1)
        self.assertEqual((removals[0]["proposed_change"]["from"],
                          removals[0]["proposed_change"]["to"]), ("na", "nb"))

    def test_relation_add_determinism(self):
        base_files = {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS}
        target_files = {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS}
        repo, base, target, tmp = build_repo(base_files, target_files)
        self.addCleanup(tmp.cleanup)
        request = make_request(base, target, two_node_map())
        first = engine.suggest_map(repo, request)
        second = engine.suggest_map(repo, request)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
