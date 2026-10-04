# -*- coding: utf-8 -*-
"""W6 integration smoke: run the canonical pipeline against THIS repository's
real git history (TEAM's own projectmind-core), with the real demo map and
real compare output. Code facts are constructed test-side by a minimal AST
scan of the pinned blobs — this is fixture construction only; C itself never
parses declarations at runtime (that is B's job).

Oracle: the pipeline runs end-to-end on real data, respects every publication
invariant (PROPOSED / human_required / no position / no map write), is
deterministic, and degrades honestly when B is absent.
"""
import ast
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys = __import__("sys")
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine  # noqa: E402

REPO = ROOT


def git(*args):
    out = subprocess.run(["git", "-C", str(REPO), *args], check=True,
                         capture_output=True)
    return out.stdout


def rev_of(ref):
    return git("rev-parse", ref).decode().strip()


def name_status(base, target):
    raw = git("diff", "--name-status", "-M", base, target, "--").decode()
    changes = []
    for line in raw.splitlines():
        parts = line.split("\t")
        code = parts[0]
        if code.startswith(("R", "C")):
            changes.append({"path": parts[2], "status": "renamed", "old_path": parts[1]})
        elif code == "A":
            changes.append({"path": parts[1], "status": "added"})
        elif code == "M":
            changes.append({"path": parts[1], "status": "modified"})
        elif code == "D":
            changes.append({"path": parts[1], "status": "removed"})
    return changes


def blob(revision, path):
    try:
        return git("show", f"{revision}:{path}").decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        return None


def test_side_facts(target, paths):
    """Fixture-only: build B-shaped facts by scanning pinned blobs."""
    files = []
    skipped = []
    for path in sorted(paths):
        source = blob(target, path)
        if source is None or not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            skipped.append({"path": path, "reason": "syntax"})
            continue
        entries = []
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                entries.append({"name": node.name, "kind": kind, "line": node.lineno})
        files.append({"path": path, "entries": entries})
    return {"revision": target, "files": files, "skipped": skipped}


class RealDiffSmokeTests(unittest.TestCase):
    def setUp(self):
        self.base = rev_of("HEAD~5")
        self.target = rev_of("HEAD")
        self.changed = name_status(self.base, self.target)
        map_text = (REPO / "data" / "project-map.json").read_text(encoding="utf-8")
        self.map_before_hash = hashlib.sha256(map_text.encode("utf-8")).hexdigest()
        self.current_map = json.loads(map_text)

    def test_end_to_end_on_real_history(self):
        if not self.changed:
            self.skipTest("no changes in last 5 commits")
        facts = test_side_facts(self.target,
                                {c["path"] for c in self.changed} |
                                {c.get("old_path") for c in self.changed if c.get("old_path")})
        request = {
            "base_revision": self.base,
            "target_revision": self.target,
            "changed_paths": self.changed,
            "code_facts": facts,
            "current_map": self.current_map,
            "prior_decisions": [],
        }
        res = engine.suggest_map(REPO, request)
        # publication invariants
        for proposal in res["proposals"]:
            self.assertIn(proposal["kind"],
                          ("NODE_ADD", "RELATION_ADD", "RELATION_REMOVE_CANDIDATE",
                           "IMPLEMENTATION_LINK_CHANGE", "NODE_REMOVE_CANDIDATE",
                           "RESPONSIBILITY_CHANGE"))
            self.assertEqual(proposal["status"], "PROPOSED")
            self.assertTrue(proposal["human_required"])
            self.assertNotIn("position", proposal["proposed_change"])
            self.assertTrue(proposal["evidence"])
            self.assertTrue(proposal["proposal_id"].startswith(f"mp-{self.target[:8]}-"))
        # determinism on real data
        second = engine.suggest_map(REPO, request)
        self.assertEqual(json.dumps(res, sort_keys=True), json.dumps(second, sort_keys=True))
        # no map write
        map_text_after = (REPO / "data" / "project-map.json").read_text(encoding="utf-8")
        self.assertEqual(self.map_before_hash,
                         hashlib.sha256(map_text_after.encode("utf-8")).hexdigest())
        # honest degradation note when B is absent
        res_degraded = engine.suggest_map(REPO, {**request, "code_facts": None})
        self.assertEqual(res_degraded["status"], "degraded")
        self.assertEqual(res_degraded["proposals"], [])


if __name__ == "__main__":
    unittest.main()
