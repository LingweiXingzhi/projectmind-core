# -*- coding: utf-8 -*-
"""REAL B integration (P04): the actual code_facts collector from the
validated B+D integration line runs inside C's pipeline — no mocks for the
final verdict.

The collector is loaded from the real implementation file and registered as
``extensions.code_facts.facts`` in sys.modules (C's installed-B seam). This
is the real B code executing, not a stub. Tests skip with an explicit reason
only when the real implementation is absent from this machine; skips are
recorded in the acceptance matrix, never counted as PASS.

Oracles: S06 (real base declaration delta → RESPONSIBILITY_CHANGE), S13
(real syntax-bad source → real skipped semantics), S14 (real revision
mismatch / same-revision cannot bypass), S15 (real unavailable / collector
exception → honest degradation), real-history end-to-end (Git compare →
real B facts → C).

Ownership check: C's map_proposal modules use ast ONLY in relations.py
(import analysis is C's own inference domain); declaration parsing remains
B's product alone (plan §5 P05 boundary).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, facts_adapter, model  # noqa: E402

REAL_B_ROOT = Path(os.environ.get(
    "PROJECTMIND_REAL_B_ROOT", str(ROOT)))
REAL_B_FACTS = REAL_B_ROOT / "extensions" / "code_facts" / "facts.py"

A_CLASS = "class A:\n    pass\n"
B_CLASS = "class B:\n    pass\n"


def git(cwd, *args):
    out = subprocess.run(["git", "-C", str(cwd), *args], check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


def build_repo(base_files, target_files):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(repo, "init")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    for path, content in base_files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    for path, content in target_files.items():
        if content is None:
            (repo / path).unlink()
            continue
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD")
    return repo, base, target, tmp


def install_real_b(test):
    """Register the REAL collector as C's installed-B seam. Returns the
    loaded module. Skips only when the real implementation is absent."""
    if not REAL_B_FACTS.is_file():
        raise unittest.SkipTest(f"real B implementation not found: {REAL_B_FACTS}")
    patcher = mock.patch.dict(sys.modules)
    patcher.start()
    test.addCleanup(patcher.stop)
    spec = importlib.util.spec_from_file_location("projectmind_real_b_facts", REAL_B_FACTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = types.ModuleType("extensions.code_facts")
    package.__path__ = []
    package.facts = module
    sys.modules["extensions.code_facts"] = package
    sys.modules["extensions.code_facts.facts"] = module
    return module


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def two_node_map(entry=None):
    return {
        "note": "m",
        "nodes": [node("na", ["pkg/a.py"], entry=entry), node("nb", ["pkg/b.py"])],
        "edges": [{"from": "na", "to": "nb"}],
    }


class RealBIntegrationTests(unittest.TestCase):
    def test_s02_s13_real_collector_supplied_pipeline(self):
        real = install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS,
             "pkg/bad.py": "def broken(:\n"},
        )
        self.addCleanup(tmp.cleanup)
        # Real collector against a real pinned revision: bad.py comes back in
        # skipped with the collector's own reason — REAL skipped semantics.
        facts = real.collect_code_facts(repo, target, ["pkg/a.py", "pkg/b.py", "pkg/bad.py"])
        self.assertEqual(facts["revision"], target)
        self.assertEqual({f["path"] for f in facts["files"]}, {"pkg/a.py", "pkg/b.py"})
        self.assertEqual([s["path"] for s in facts["skipped"]], ["pkg/bad.py"])
        self.assertTrue(facts["skipped"][0]["reason"])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/bad.py", "status": "added"}],
            "code_facts": facts,
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual((adds[0]["proposed_change"]["from"],
                          adds[0]["proposed_change"]["to"]), ("na", "nb"))
        # REAL skipped source: HUMAN_REQUIRED, no strong candidate depends on it.
        self.assertTrue(any(u["subject"] == "pkg/bad.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in res["unresolved"]))
        self.assertEqual(
            [p for p in res["proposals"] if p["subject"] == "pkg/bad.py"], [])

    def test_s06_real_base_delta_gives_responsibility_change(self):
        install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": "def main():\n    return 1\n", "pkg/b.py": B_CLASS},
            {"pkg/a.py": "def run():\n    return 2\n", "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        # code_facts absent → C collects target AND base through the REAL
        # installed collector; the declaration delta (main gone) is real.
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "current_map": two_node_map(entry="pkg/a.py · main()"),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["facts_source"], "installed")
        resp = [p for p in res["proposals"] if p["kind"] == "RESPONSIBILITY_CHANGE"]
        self.assertEqual(len(resp), 1)
        self.assertEqual(resp[0]["subject"], "na")
        self.assertEqual(resp[0]["status"], "PROPOSED")
        self.assertTrue(resp[0]["human_required"])
        evidence_text = json.dumps(resp[0]["evidence"], ensure_ascii=False)
        self.assertIn("main", evidence_text)
        self.assertIn(target[:8], evidence_text)

    def test_s14_real_revision_mismatch_rejected_same_revision_safe(self):
        real = install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# touched\n", "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        stale = real.collect_code_facts(repo, base, ["pkg/a.py", "pkg/b.py"])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "code_facts": stale,
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        with self.assertRaises(facts_adapter.FactsMismatch):
            engine.suggest_map(repo, request)
        # Same revision: gates run, then zero proposals (invariant 13).
        same = real.collect_code_facts(repo, target, ["pkg/a.py", "pkg/b.py"])
        request_same = {
            "base_revision": target,
            "target_revision": target,
            "changed_paths": [],
            "code_facts": same,
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request_same)
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(n["reason"] == "same_revision" for n in res["no_proposal"]))

    def test_real_wanted_paths_removed_path_strictness(self):
        real = install_real_b(self)
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/gone.py": B_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS, "pkg/gone.py": None, "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        # Real B is strict: a wanted path absent from the pinned tree rejects
        # the whole call (CodeFactsError) — documented interface behavior.
        with self.assertRaises(real.CodeFactsError):
            real.collect_code_facts(repo, target, ["pkg/a.py", "pkg/gone.py"])
        # C never hands removed paths to the collector: engine's wanted list
        # only contains added/modified/renamed paths, so the pipeline runs.
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/gone.py", "status": "removed"}],
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["facts_source"], "installed")

    def test_s15_real_collector_unavailable_and_exception(self):
        # Unavailable: with the installed real module hidden, C degrades
        # honestly and the B-free channels (rename link) still fire. On the
        # BCD integration base the real extension IS installed, so absence
        # is simulated explicitly (module set to None -> ImportError).
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": None, "pkg/a2.py": A_CLASS, "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a2.py", "status": "renamed",
                               "old_path": "pkg/a.py"}],
            "current_map": two_node_map(),
            "prior_decisions": [],
        }
        with mock.patch.dict(sys.modules, {"extensions.code_facts.facts": None,
                                           "extensions.code_facts": None}):
            res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["facts_source"], "none")
        self.assertEqual(res["status"], "degraded")
        links = [p for p in res["proposals"] if p["kind"] == "IMPLEMENTATION_LINK_CHANGE"]
        self.assertEqual(len(links), 1)
        # Collector exception: real B loaded, but the target is not a repo →
        # CodeFactsError → degraded with limits, never fabricated facts.
        install_real_b(self)
        with mock.patch.dict(sys.modules):
            bogus = Path(tempfile.mkdtemp())  # not a git repository
            request_bad = {
                "base_revision": base,
                "target_revision": "a" * 40,
                "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
                "current_map": two_node_map(),
                "prior_decisions": [],
            }
            res_bad = engine.suggest_map(bogus, request_bad)
            self.assertEqual(res_bad["request"]["facts_source"], "none")
            self.assertEqual(res_bad["proposals"], [])
            self.assertTrue(any("degraded" in str(l).lower() or "unavailable" in str(l).lower()
                                or "降级" in str(l) for l in res_bad["limits"]))

    def test_real_history_end_to_end_deterministic_no_map_write(self):
        install_real_b(self)
        repo = ROOT
        target = git(repo, "rev-parse", "HEAD")
        depth = min(5, int(git(repo, "rev-list", "--first-parent", "--count", "HEAD")) - 1)
        if depth < 1:
            self.skipTest("no parent commit available; upstream history is not verified")
        base = git(repo, "rev-parse", f"HEAD~{depth}")
        raw = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-status", "-M", base, target],
            check=True, capture_output=True, text=True).stdout
        changed = []
        for line in raw.splitlines():
            parts = line.split("\t")
            if parts[0].startswith("R"):
                changed.append({"path": parts[2], "status": "renamed",
                                "old_path": parts[1]})
            elif parts[0] == "A":
                changed.append({"path": parts[1], "status": "added"})
            elif parts[0] == "M":
                changed.append({"path": parts[1], "status": "modified"})
            elif parts[0] == "D":
                changed.append({"path": parts[1], "status": "removed"})
        self.assertTrue(changed)
        real_map = {
            "note": "overnight real-history smoke",
            "nodes": [node("na", ["extensions/map_proposal/model.py"]),
                      node("ne", ["extensions/map_proposal/engine.py"])],
            "edges": [{"from": "na", "to": "ne"}],
        }
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": changed,
            "current_map": real_map,
            "prior_decisions": [],
        }
        # Hash the FORMAL map file (Codex false-green fix: hashing
        # implementation files did not verify formal-map preservation).
        map_files = [ROOT / "data" / "project-map.json"]
        before = {p: p.read_bytes() for p in map_files}
        first = engine.suggest_map(repo, request)
        second = engine.suggest_map(repo, request)
        after = {p: p.read_bytes() for p in map_files}
        self.assertEqual(before, after)  # no map write (S29)
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))  # deterministic
        for proposal in first["proposals"]:
            self.assertIn(proposal["kind"], model.PROPOSAL_KINDS)
            self.assertEqual(proposal["status"], "PROPOSED")
            self.assertTrue(proposal["human_required"])
            self.assertNotIn("position", proposal["proposed_change"])
            self.assertTrue(proposal["evidence"])
            self.assertNotIn("position", json.dumps(proposal))


if __name__ == "__main__":
    unittest.main()
