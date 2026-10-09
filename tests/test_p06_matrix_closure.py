# -*- coding: utf-8 -*-
"""P06 matrix closure: PARTIAL S-matrix variants (S08/S12/S17/S18/S27),
subdirectory rename, and the extension-seam error boundary (400/500,
malicious map text, no silent worktree fallback).

Oracles from C_CONVERGENCE_PLAN §8 and C_SELF_AUDIT remaining-PARTIAL list.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine, model  # noqa: E402


def git(cwd, *args):
    out = subprocess_run(["git", "-C", str(cwd), *args])
    return out.strip()


def subprocess_run(args):
    import subprocess
    out = subprocess.run(args, check=True, capture_output=True, text=True)
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
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD")
    return repo, base, target, tmp


def node(node_id, paths, entry=None):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": entry or f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def run_engine(repo, base, target, changed, map_data, facts_files, skipped=None):
    request = {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": changed,
        "code_facts": {"revision": target, "files": facts_files,
                       "skipped": skipped or []},
        "current_map": map_data,
        "prior_decisions": [],
    }
    return engine.suggest_map(repo, request)


def two_node_map(extra_na=()):
    return {
        "note": "m",
        "nodes": [node("na", ["pkg/a.py", *extra_na]), node("nb", ["pkg/b.py"])],
        "edges": [{"from": "na", "to": "nb"}],
    }


A = "class A:\n    pass\n"
B = "class B:\n    pass\n"
MAIN_FN = "def main():\n    return 1\n"
RUN_FN = "def run():\n    return 2\n"


class S08FormattingOnly(unittest.TestCase):
    def test_s08_line_and_quote_drift_only_zero_proposals(self):
        # Line-number and quote-style drift, declarations byte-identical:
        # zero proposals with an explicit no-cross-signal reason (A08).
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": 'x = "one"\n' + A, "pkg/b.py": B},
            {"pkg/a.py": "x = 'one'\n\n\n" + A, "pkg/b.py": B},
        )
        self.addCleanup(tmp.cleanup)
        res = run_engine(repo, base, target,
                         [{"path": "pkg/a.py", "status": "modified"}],
                         two_node_map(),
                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(n.get("reason") for n in res["no_proposal"]))


class S12TestNoise(unittest.TestCase):
    def test_s12_test_and_generated_noise_no_business_candidates(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A, "pkg/b.py": B, "tests/test_a.py": "def test_old():\n    pass\n"},
            {"pkg/a.py": A, "pkg/b.py": B,
             "tests/test_a.py": "def test_new():\n    pass\n",
             "docs/generated/schema.py": "GEN = 1\n"},
        )
        self.addCleanup(tmp.cleanup)
        res = run_engine(repo, base, target,
                         [{"path": "tests/test_a.py", "status": "modified"},
                          {"path": "docs/generated/schema.py", "status": "added"}],
                         two_node_map(),
                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]},
                          {"path": "tests/test_a.py", "entries": [{"name": "test_new", "kind": "function", "line": 1}]},
                          {"path": "docs/generated/schema.py", "entries": [{"name": "GEN", "kind": "function", "line": 1}]}])
        self.assertEqual(res["proposals"], [])


class S17MultiOwnerAmbiguity(unittest.TestCase):
    def test_s17_multi_owner_relation_ends_low_confidence_not_arbitrary(self):
        # A17 beyond rename: an endpoint path covered by TWO map nodes →
        # low-confidence candidate with the ambiguity uncertainty, never an
        # arbitrary single-owner pick.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A, "pkg/a2.py": A, "pkg/b.py": B, "pkg/b2.py": B},
            {"pkg/a.py": A + "from pkg.b import B\n", "pkg/a2.py": A,
             "pkg/b.py": B, "pkg/b2.py": B},
        )
        self.addCleanup(tmp.cleanup)
        map_data = {
            "note": "m",
            "nodes": [node("na", ["pkg/a.py"]),
                      node("na2", ["pkg/a.py", "pkg/a2.py"]),
                      node("nb", ["pkg/b.py"]),
                      node("nb2", ["pkg/b.py", "pkg/b2.py"])],
            "edges": [],
        }
        res = run_engine(repo, base, target,
                         [{"path": "pkg/a.py", "status": "modified"}],
                         map_data,
                         [{"path": p, "entries": [{"name": "X", "kind": "class", "line": 1}]}
                          for p in ("pkg/a.py", "pkg/a2.py", "pkg/b.py", "pkg/b2.py")])
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0]["confidence"], "low")
        self.assertTrue(any("multiple candidate nodes" in u
                            for u in adds[0]["uncertainty"]))


class S18MissingEvidence(unittest.TestCase):
    def test_s18_added_file_without_b_entries_unresolved_unknown(self):
        # Added file, but B returns no declaration entries: unresolved UNKNOWN,
        # zero strong candidates — "B 无条目 ≠ 架构上不存在" (A18/C-3).
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A, "pkg/b.py": B},
            {"pkg/a.py": A, "pkg/b.py": B, "pkg/ghost.py": "class G:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        res = run_engine(repo, base, target,
                         [{"path": "pkg/ghost.py", "status": "added"}],
                         two_node_map(),
                         # B facts deliberately omit pkg/ghost.py entries
                         [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
        self.assertEqual(res["proposals"], [])
        self.assertTrue(any(u["subject"] == "pkg/ghost.py" for u in res["unresolved"]))


class S04SubdirectoryRename(unittest.TestCase):
    def test_s04_subdirectory_move_link_change(self):
        repo, base, target, tmp = build_repo(
            {"pkg/sub/a.py": A, "pkg/b.py": B},
            {"pkg/sub2/a.py": A, "pkg/b.py": B},
        )
        self.addCleanup(tmp.cleanup)
        map_data = {
            "note": "m",
            "nodes": [node("na", ["pkg/sub/a.py"]), node("nb", ["pkg/b.py"])],
            "edges": [],
        }
        res = run_engine(repo, base, target,
                         [{"path": "pkg/sub2/a.py", "status": "renamed",
                           "old_path": "pkg/sub/a.py"}],
                         map_data,
                         [{"path": "pkg/sub2/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                          {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}])
        links = [p for p in res["proposals"] if p["kind"] == "IMPLEMENTATION_LINK_CHANGE"]
        self.assertEqual(len(links), 1)
        # R06 identity: link-change subjects carry the old repo path and the
        # affected map node id in proposed_change.
        self.assertEqual(links[0]["subject"], "pkg/sub/a.py")
        self.assertEqual(links[0]["proposed_change"]["node_id"], "na")
        self.assertEqual(
            [p for p in res["proposals"] if p["kind"] == "NODE_ADD"], [])


class S27MalformedWithContext(unittest.TestCase):
    def test_s27_malformed_map_evidence_inside_valid_context_rejected(self):
        # valid-context malformed_payload_map: a structurally invalid node
        # (evidence item without path) inside an otherwise valid request is a
        # controlled rejection (A27). Note: whether Core's map schema REQUIRES
        # title/summary/entryPoint per node is NOT defined by the contract —
        # recorded as HUMAN_DECISION_REQUIRED_MAP_NODE_FIELDS (P07), not
        # invented here.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A, "pkg/b.py": B},
            {"pkg/a.py": A + "# t\n", "pkg/b.py": B},
        )
        self.addCleanup(tmp.cleanup)
        map_data = two_node_map()
        map_data["nodes"].append(
            {"id": "bad", "title": "t", "summary": "s",
             "entryPoint": "pkg/a.py · f()", "position": {"x": 1, "y": 2},
             "evidence": [{"reason": "no path key"}]})
        with self.assertRaises(model.RequestError):
            run_engine(repo, base, target,
                       [{"path": "pkg/a.py", "status": "modified"}],
                       map_data,
                       [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}])


class ExtensionSeamBoundary(unittest.TestCase):
    """Handler-level error mapping and hostile map text (A27/A28 at the seam)."""

    def setUp(self):
        from extensions.map_proposal import extension
        self.extension = extension

    def _ctx(self, repo):
        class Ctx:
            pass
        ctx = Ctx()
        ctx.repo = str(repo)
        return ctx

    def _repo_with_commit(self):
        # target differs from base (comment line) so the second commit is real
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A}, {"pkg/a.py": A + "# touched\n"})
        self.addCleanup(tmp.cleanup)
        return repo, base, target

    def test_malicious_map_text_controlled_rejection_not_crash(self):
        repo, base, target = self._repo_with_commit()
        hostile = {
            "note": "x" * 10000,
            "nodes": [{"id": "../escape", "title": "t", "summary": "s",
                       "entryPoint": "../../etc/passwd · f()",
                       "position": {"x": 1, "y": 2},
                       "evidence": [{"path": "../../etc/passwd", "reason": "r"}]}],
            "edges": [],
        }
        data = {"base_revision": base, "target_revision": target,
                "changed_paths": [], "code_facts": None, "current_map": hostile}
        from extension_host import ExtensionError
        with self.assertRaises(ExtensionError) as caught:
            self.extension.handle(self._ctx(repo), "POST", data)
        self.assertEqual(caught.exception.status.value, 400)

    def test_missing_pin_is_400_not_head_fallback(self):
        repo, base, target = self._repo_with_commit()
        from extension_host import ExtensionError
        data = {"changed_paths": [], "code_facts": None,
                "current_map": {"note": "n", "nodes": [], "edges": []}}
        with self.assertRaises(ExtensionError) as caught:
            self.extension.handle(self._ctx(repo), "POST", data)
        self.assertEqual(caught.exception.status.value, 400)

    def test_get_method_allowed_post_only_others_rejected(self):
        repo, base, target = self._repo_with_commit()
        from extension_host import ExtensionError
        with self.assertRaises(ExtensionError) as caught:
            self.extension.handle(self._ctx(repo), "DELETE", {})
        self.assertEqual(caught.exception.status.value, 405)


class P07EntryPointDiagnostics(unittest.TestCase):
    def test_unparseable_entry_point_is_visible_degradation_not_silence(self):
        # R8/G-3: a map whose entryPoint strings do not match the contract
        # format used to kill the RESPONSIBILITY channel silently. The
        # channel's inactivity must now be visible in limits.
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": MAIN_FN, "pkg/b.py": B},
            {"pkg/a.py": RUN_FN, "pkg/b.py": B},
        )
        self.addCleanup(tmp.cleanup)
        map_data = {
            "note": "m",
            "nodes": [node("na", ["pkg/a.py"], entry="主入口"),
                      node("nb", ["pkg/b.py"])],
            "edges": [],
        }
        res = run_engine(repo, base, target,
                         [{"path": "pkg/a.py", "status": "modified"}],
                         map_data,
                         [{"path": "pkg/a.py", "entries": [{"name": "run", "kind": "function", "line": 1}]}],
                         )
        self.assertTrue(any("entryPoint 格式无法解析" in l and "na" in l
                            for l in res["limits"]))
        # A properly formatted entryPoint produces no diagnostic.
        map_data2 = {
            "note": "m",
            "nodes": [node("na", ["pkg/a.py"], entry="pkg/a.py · main()"),
                      node("nb", ["pkg/b.py"])],
            "edges": [],
        }
        res2 = run_engine(repo, base, target,
                          [{"path": "pkg/a.py", "status": "modified"}],
                          map_data2,
                          [{"path": "pkg/a.py", "entries": [{"name": "run", "kind": "function", "line": 1}]}],
                          )
        self.assertFalse(any("entryPoint 格式无法解析" in l for l in res2["limits"]))


if __name__ == "__main__":
    unittest.main()
