"""C / Map Proposal v0.1 — acceptance (F1–F20 + C-A21..A30), adversarial,
determinism, security and coexistence tests.

Fixtures build tiny git repos and tiny CA registries; no reliance on
projectmind-core's own history. Same input → byte-identical output everywhere.
"""
import base64
import json
import subprocess
import sys
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extension_host import ExtensionContext, ExtensionError, ExtensionHost  # noqa: E402
import app as core_app  # noqa: E402
from extensions.map_proposal.engine import suggest  # noqa: E402
from extensions.map_proposal.facts_adapter import FactsMismatch  # noqa: E402
from extensions.map_proposal.model import RequestError  # noqa: E402


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"git {args}: {result.stderr.strip()}")
    return result.stdout.strip()


_REPO_SEQ = {"n": 0}


def make_repo(base, files1, files2=None, renames=(), removals=()):
    _REPO_SEQ["n"] += 1
    repo = base / f"fixture-{_REPO_SEQ['n']}"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    for path, content in files1.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "base")
    c1 = git(repo, "rev-parse", "HEAD")
    if files2 is None:
        files2 = {}
    for old, new in renames:
        (repo / new).parent.mkdir(parents=True, exist_ok=True)
        git(repo, "mv", old, new)
    for path in removals:
        git(repo, "rm", "-q", path)
    for path, content in files2.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain").strip():
        git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "target")
        c2 = git(repo, "rev-parse", "HEAD")
    else:
        c2 = c1
    return repo, c1, c2


def make_map(nodes, edges=()):
    return {"note": "fixture map",
            "nodes": [{"id": node_id, "title": title, "summary": "s",
                       "entryPoint": entry, "position": {"x": 0, "y": 0},
                       "evidence": [{"path": path, "reason": "fixture"} for path in paths]}
                      for node_id, title, entry, paths in nodes],
            "edges": [{"from": f, "to": t, "label": label} for f, t, label in edges]}


def request(repo, c1, c2, changed, map_data, **extra):
    data = {"base_revision": c1, "target_revision": c2,
            "changed_paths": changed, "current_map": map_data}
    data.update(extra)
    return data


def registry_claims(lines):
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for line in lines:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    handle.close()
    return Path(handle.name)


def build_pack(repo, target, claims_path, task="map proposal"):
    from extensions.context_authority.context_pack import build_context_pack
    return build_context_pack(task, str(repo), claims_path, revision=target, run_verifiers=False)


def reseal(pack):
    from extensions.context_authority.context_pack import context_pack_digest
    pack.pop("integrity", None)
    pack["integrity"] = {"algorithm": "sha256", "digest": context_pack_digest(pack),
                         "guarantee": "structural_consistency_only"}
    return pack


HUMAN = {"kind": "human", "ref": "fixture decision"}


class SuggestTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def kinds(self, result):
        return [p["kind"] for p in result["proposals"]]


class AcceptanceTests(SuggestTestBase):
    def test_F1_new_module_with_class(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    def run(self):\n        pass\n"})
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(self.kinds(result), ["NODE_ADD"])
        proposal = result["proposals"][0]
        kinds_seen = {e["kind"] for e in proposal["evidence"]}
        self.assertIn("git_diff", kinds_seen)
        self.assertIn("code_fact", kinds_seen)
        self.assertEqual(proposal["status"], "PROPOSED")
        self.assertTrue(proposal["human_required"])
        self.assertNotIn("position", proposal["proposed_change"])

    def test_F2_added_cross_import(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    pass\n", "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "import b_mod\n\n\nclass Alpha:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertIn("RELATION_ADD", self.kinds(result))
        relation = next(p for p in result["proposals"] if p["kind"] == "RELATION_ADD")
        self.assertEqual(relation["proposed_change"]["from"], "node-a")
        self.assertEqual(relation["proposed_change"]["to"], "node-b")

    def test_F3_removed_import(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "import b_mod\n\n\nclass Alpha:\n    pass\n",
                                  "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "class Alpha:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertIn("RELATION_REMOVE_CANDIDATE", self.kinds(result))

    def test_F4_rename_updates_link_not_node_add(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {}, renames=[("a.py", "renamed_a.py")])
        result = suggest(request(repo, c1, c2,
                                 [{"path": "renamed_a.py", "status": "renamed",
                                   "old_path": "a.py"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(self.kinds(result), ["IMPLEMENTATION_LINK_CHANGE"])

    def test_F5_move_to_subdir(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {}, renames=[("a.py", "sub/a.py")])
        result = suggest(request(repo, c1, c2,
                                 [{"path": "sub/a.py", "status": "renamed", "old_path": "a.py"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(self.kinds(result), ["IMPLEMENTATION_LINK_CHANGE"])

    def test_F6_F7_F8_body_comment_format_only(self):
        for content in ("class Alpha:  # comment changed\n    pass\n",
                        "class Alpha:\n    pass        \n",
                        "class Alpha:\n    pass\n    # brand new comment\n"):
            repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                     {"a.py": content})
            result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                     make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
            self.assertEqual(result["proposals"], [])
            self.assertTrue(any(n["reason"].startswith("no declaration-level change")
                                for n in result["no_proposal"]), result["no_proposal"])

    def test_F9_new_class_same_responsibility(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"a.py": "class Alpha:\n    pass\n\n\nclass Internal:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual([p for p in result["proposals"] if p["kind"] == "NODE_ADD"], [])
        self.assertTrue(any("same-responsibility" in n["reason"] for n in result["no_proposal"]))

    def test_F10_helper_function_added(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"a.py": "def helper():\n    pass\n\n\nclass Alpha:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])

    def test_F11_stale_node_all_evidence_removed(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"old_mod.py": "class Old:\n    pass\n",
                                  "a.py": "class Alpha:\n    pass\n"},
                                 removals=["old_mod.py"])
        result = suggest(request(repo, c1, c2, [{"path": "old_mod.py", "status": "removed"}],
                                 make_map([("node-old", "Old", "old_mod.py · Old", ["old_mod.py"]),
                                           ("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertIn("NODE_REMOVE_CANDIDATE", self.kinds(result))
        proposal = next(p for p in result["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE")
        self.assertTrue(proposal["human_required"])

    def test_F13_skipped_changed_file(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"broken_new.py": "def broken(:\n"})
        result = suggest(request(repo, c1, c2, [{"path": "broken_new.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any(u["subject"] == "broken_new.py"
                            and u["reason"] == "NEEDS_HUMAN_REVIEW"
                            for u in result["unresolved"]))

    def test_F14_no_evidence_empty_module(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"empty_new.py": ""})
        result = suggest(request(repo, c1, c2, [{"path": "empty_new.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any(u["subject"] == "empty_new.py" for u in result["unresolved"]))

    def test_F15_same_revision(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        result = suggest(request(repo, c1, c1, [], make_map([("n", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any("same revision" in item for item in result["limits"]))

    def test_F16_entrypoint_renamed(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    def render(self):\n        pass\n"},
                                 {"a.py": "class Alpha:\n    def render_v2(self):\n        pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · render", ["a.py"])])), repo)
        self.assertIn("RESPONSIBILITY_CHANGE", self.kinds(result))
        proposal = next(p for p in result["proposals"] if p["kind"] == "RESPONSIBILITY_CHANGE")
        self.assertTrue(any(e["kind"] == "code_fact" for e in proposal["evidence"]))

    def test_F17_multiple_candidate_nodes(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {}, renames=[("a.py", "moved.py")])
        result = suggest(request(repo, c1, c2,
                                 [{"path": "moved.py", "status": "renamed", "old_path": "a.py"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "a.py · Alpha", ["a.py"])])), repo)
        proposal = result["proposals"][0]
        self.assertEqual(proposal["confidence"], "low")
        self.assertTrue(any("multiple candidate nodes" in u for u in proposal["uncertainty"]))

    def test_F18_unrelated_docs_change(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    pass\n", "docs.md": "hello\n"},
                                 {"docs.md": "hello world\n"})
        result = suggest(request(repo, c1, c2, [{"path": "docs.md", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])
        self.assertEqual(result["unresolved"], [])

    def test_F19_dynamic_import_weak_signal(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    pass\n", "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "mod = importlib.import_module('b_mod')\n\n\nclass Alpha:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertNotIn("RELATION_ADD", self.kinds(result))
        self.assertTrue(any(u["reason"] == "NEEDS_HUMAN_REVIEW" for u in result["unresolved"]))

    def test_F20_prior_rejection_suppresses(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        changed = [{"path": "pkg_new/feature.py", "status": "added"}]
        map_data = make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])
        first = suggest(request(repo, c1, c2, changed, map_data), repo)
        self.assertEqual(self.kinds(first), ["NODE_ADD"])
        second = suggest(request(repo, c1, c2, changed, map_data,
                                 prior_decisions=[{"subject": "pkg_new/feature.py",
                                                   "kind": "NODE_ADD", "decision": "REJECTED"}]), repo)
        self.assertEqual(second["proposals"], [])
        self.assertTrue(any("suppressed by prior_decisions" in item for item in second["limits"]))


class ContextAuthorityTests(SuggestTestBase):
    def multi_scope_claims(self):
        return [{"id": "claim-focus-team", "key": "team.focus.v1",
                 "value": {"focus": "integration"}, "type": "HUMAN_DECISION",
                 "scope": "team", "source": HUMAN},
                {"id": "claim-focus-core", "key": "team.focus.v1",
                 "value": {"focus": "snapshot"}, "type": "HUMAN_DECISION",
                 "scope": "core", "source": HUMAN}]

    def test_C_A21_multi_scope_both_visible(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        pack = build_pack(repo, c2, registry_claims(self.multi_scope_claims()))
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertEqual(result["metadata"]["mode"], "FULL")
        claims = [e for p in result["proposals"] for e in p["evidence"] if e["kind"] == "context_claim"]
        self.assertTrue(claims, "supplementary context claim expected")
        self.assertIn("claim_id", claims[0])

    def test_C_A22_high_impact_claims_never_attached(self):
        """H1 fix: implementation.*/contract.* claims assert facts C v0.1 cannot
        independently verify (no gh/PR verifier) — they are dropped to
        unresolved HUMAN_REQUIRED even when the pack marks them verified."""
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        claims = [{"id": "claim-cf-status", "key": "implementation.code_facts",
                   "value": {"status": "DELIVERED", "pr": 31, "head": c2[:40],
                             "delivered_shape": "legacy"},
                   "type": "VERIFIED_FACT", "scope": "main",
                   "source": {"kind": "repo", "ref": "extensions/code_facts/README.md",
                              "revision": c2}}]
        pack = build_pack(repo, c2, registry_claims(claims))
        row = next(r for r in pack["current_state"]["current_by_scope"]
                   if r["key"] == "implementation.code_facts")
        projected = pack["current_state"]["current"].get("implementation.code_facts") or {}
        verified_copy = next((r for r in pack.get("verified_facts", [])
                              if r.get("key") == "implementation.code_facts"), {})
        for ref in row["evidence"] + projected.get("evidence", []) + verified_copy.get("evidence", []):
            ref["live_verification"] = {"source": {"kind": "human", "ref": "fixture verifier"}, "verified_at": "2026-10-04T00:00:00Z", "freshness": "verified",
                                        "verified_fields": ["status", "pr", "head"]}
        row["freshness"] = "verified"
        if projected:
            projected["freshness"] = "verified"
        if verified_copy:
            verified_copy["freshness"] = "verified"
        reseal(pack)
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertEqual([e for p in result["proposals"] for e in p["evidence"]
                          if e["kind"] == "context_claim"], [])
        self.assertTrue(any(u["reason"] == "HUMAN_REQUIRED"
                            and u["subject"] == "claim:implementation.code_facts"
                            for u in result["unresolved"]))

    def test_C_A23_verifier_unavailable_row_excluded(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        claims = [{"id": "claim-cf-status", "key": "implementation.code_facts",
                   "value": {"status": "DELIVERED"}, "type": "VERIFIED_FACT",
                   "scope": "main",
                   "source": {"kind": "repo", "ref": "extensions/code_facts/README.md",
                              "revision": c2}}]
        pack = build_pack(repo, c2, registry_claims(claims))
        row = next(r for r in pack["current_state"]["current_by_scope"]
                   if r["key"] == "implementation.code_facts")
        pack["current_state"]["current_by_scope"].remove(row)
        pack["current_state"]["current"].pop("implementation.code_facts", None)
        pack["current_state"]["counts"]["current"] -= 1
        pack["verification_unavailable"].append(row)
        counts = pack["current_state"]["counts"]
        counts["verification_unavailable"] = counts.get("verification_unavailable", 0) + 1
        reseal(pack)
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertFalse([e for p in result["proposals"] for e in p["evidence"]
                          if e["kind"] == "context_claim"])

    def test_C_A24_coherent_poison_contradicts_diff(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"old_mod.py": "class Old:\n    pass\n",
                                  "a.py": "class Alpha:\n    pass\n"},
                                 removals=["old_mod.py"])
        claims = [{"id": "claim-poison", "key": "contract.old_module_shape",
                   "value": {"status": "current", "paths": ["old_mod.py"],
                              "note": "module is a current delivery"},
                   "type": "CONTRACT", "scope": "main",
                   "source": {"kind": "repo", "ref": "docs/fixture.md", "revision": c2}}]
        pack = build_pack(repo, c2, registry_claims(claims))
        result = suggest(request(repo, c1, c2, [{"path": "old_mod.py", "status": "removed"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        poisoned = [e for p in result["proposals"] for e in p["evidence"]
                    if e.get("claim_id") == "claim-poison"]
        self.assertEqual(poisoned, [])
        self.assertTrue(any(u["reason"] == "HUMAN_REQUIRED" for u in result["unresolved"]))
        self.assertTrue(any("not used as evidence" in item for item in result["limits"]))

    def test_C_A25_invalid_pack_degrades(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        pack = build_pack(repo, c2, registry_claims(self.multi_scope_claims()))
        del pack["evidence"]
        reseal(pack)
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertEqual(result["metadata"]["mode"], "DEGRADED_NO_CONTEXT")
        self.assertEqual(self.kinds(result), ["NODE_ADD"])
        self.assertFalse([e for p in result["proposals"] for e in p["evidence"]
                          if e["kind"] == "context_claim"])
        self.assertTrue(any("rejected" in item for item in result["limits"]))

    def test_C_A29_related_conflict_human_required(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"old_mod.py": "class Old:\n    pass\n",
                                  "a.py": "class Alpha:\n    pass\n"},
                                 removals=["old_mod.py"])
        claims = [{"id": "claim-conflict-a", "key": "team.focus.v1",
                   "value": {"focus": "keep old_mod.py"}, "type": "HUMAN_DECISION",
                   "scope": "team", "source": HUMAN},
                  {"id": "claim-conflict-b", "key": "team.focus.v1",
                   "value": {"focus": "old_mod.py must go"}, "type": "HUMAN_DECISION",
                   "scope": "team", "source": HUMAN}]
        pack = build_pack(repo, c2, registry_claims(claims))
        result = suggest(request(repo, c1, c2, [{"path": "old_mod.py", "status": "removed"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertTrue(any(u["reason"] == "HUMAN_REQUIRED" and "conflict:" in u["subject"]
                            for u in result["unresolved"]))
        self.assertFalse([e for p in result["proposals"] for e in p["evidence"]
                          if e.get("claim_id") in ("claim-conflict-a", "claim-conflict-b")])

    def test_C_A26_facts_revision_mismatch_rejected(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"a.py": "class Alpha:\n    pass  # changed\n"})
        with self.assertRaises(FactsMismatch):
            suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                            make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                            code_facts={"revision": c1, "files": [], "skipped": []}), repo)

    def test_C_A27_b_skipped_path_unresolved(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"broken_new.py": "def broken(:\n"})
        result = suggest(request(repo, c1, c2, [{"path": "broken_new.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any(u["subject"] == "broken_new.py"
                            and u["reason"] == "NEEDS_HUMAN_REVIEW"
                            for u in result["unresolved"]))

    def test_C_A28_contract_drift_tolerated(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 code_facts={"revision": c2, "files": 42, "skipped": None}), repo)
        self.assertEqual(result["metadata"]["facts_mode"], "unavailable")
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any(u["reason"] == "NEEDS_HUMAN_REVIEW" for u in result["unresolved"]))

    def test_C_A30_map_version_unknown(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertIsNone(result["metadata"]["map_version"])
        self.assertIn("map_version_note", result["metadata"])


class DegradedAndSecurityTests(SuggestTestBase):
    def test_no_facts_degraded_F1_prime(self):
        import builtins
        from unittest import mock
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("extensions.code_facts"):
                raise ImportError("B extension unavailable (simulated)")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=blocked):
            result = suggest(request(repo, c1, c2,
                                     [{"path": "pkg_new/feature.py", "status": "added"}],
                                     make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        self.assertEqual(result["metadata"]["facts_mode"], "unavailable")
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any(u["reason"] == "NEEDS_HUMAN_REVIEW" for u in result["unresolved"]))
        self.assertFalse([e for u in result["unresolved"] for e in u["evidence"]
                          if e["kind"] == "code_fact"])

    def test_traversal_path_rejected(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        with self.assertRaises(RequestError):
            suggest(request(repo, c1, c2, [{"path": "../secrets.py", "status": "added"}],
                            make_map([("n", "A", "a.py · Alpha", ["a.py"])])), repo)
        with self.assertRaises(RequestError):
            suggest(request(repo, c1, c2, [{"path": "C:/Windows/win.ini", "status": "added"}],
                            make_map([("n", "A", "a.py · Alpha", ["a.py"])])), repo)

    def test_too_many_changes_rejected(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        with self.assertRaises(RequestError):
            suggest(request(repo, c1, c2, [{"path": f"m{i}.py", "status": "added"}
                                           for i in range(2001)],
                            make_map([("n", "A", "a.py · Alpha", ["a.py"])])), repo)

    def test_invalid_revision_rejected(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        with self.assertRaises(RequestError):
            suggest(request(repo, c1, "HEAD", [{"path": "a.py", "status": "modified"}],
                            make_map([("n", "A", "a.py · Alpha", ["a.py"])])), repo)

    def test_malicious_map_text_stays_data(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-<script>alert(1)</script>", "A",
                                            "a.py · Alpha", ["a.py"])])), repo)
        json.dumps(result, ensure_ascii=False)  # hostile map text never breaks the output
        self.assertEqual(result["proposals"][0]["status"], "PROPOSED")
        self.assertTrue(all(p["human_required"] for p in result["proposals"]))


class DeterminismTests(SuggestTestBase):
    def test_same_request_byte_identical(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    pass\n", "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "import b_mod\n\n\nclass Alpha:\n    pass\n",
                                  "pkg_new/feature.py": "class Feature:\n    pass\n"})
        data = request(repo, c1, c2,
                       [{"path": "a.py", "status": "modified"},
                        {"path": "pkg_new/feature.py", "status": "added"}],
                       make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                 ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])]))
        first = json.dumps(suggest(data, repo), ensure_ascii=False, sort_keys=True)
        second = json.dumps(suggest(data, repo), ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)

    def test_proposal_ids_stable(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        data = request(repo, c1, c2, [{"path": "pkg_new/feature.py", "status": "added"}],
                       make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]))
        one = suggest(data, repo)["proposals"][0]["proposal_id"]
        two = suggest(data, repo)["proposals"][0]["proposal_id"]
        self.assertEqual(one, two)
        self.assertTrue(one.startswith(f"mp-{c2[:8]}-"))


class ExtensionIntegrationTests(SuggestTestBase):
    def host(self, repo):
        return ExtensionHost(ROOT / "extensions", ExtensionContext(
            repo=repo, map_path=ROOT / "data" / "project-map.json",
            snapshot=lambda: core_app.build_snapshot(repo, ROOT / "data" / "project-map.json"),
            compare=lambda b, t: core_app.compare_commits(repo, ROOT / "data" / "project-map.json", b, t)))

    def test_all_seven_extensions_coexist(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        host = self.host(repo)
        self.assertIn("map_proposal", host.loaded)
        self.assertEqual(host.unavailable, {})
        self.assertTrue({"code_facts", "context_authority", "continuity", "handoff",
                         "worklog"} <= set(host.loaded))

    def test_get_status_and_schema(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        host = self.host(repo)
        status = host.run("map_proposal", "GET", {})
        self.assertEqual(status["id"], "map_proposal")
        self.assertIn("invariants", host.run("map_proposal", "POST", {"action": "schema"}))

    def test_post_suggest_end_to_end_with_in_process_b(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        host = self.host(repo)
        result = host.run("map_proposal", "POST", {
            "action": "suggest",
            "request": {"base_revision": c1, "target_revision": c2,
                        "changed_paths": [{"path": "pkg_new/feature.py", "status": "added"}],
                        "current_map": make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])}})
        self.assertEqual([p["kind"] for p in result["proposals"]], ["NODE_ADD"])

    def test_invalid_request_returns_400(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"})
        host = self.host(repo)
        with self.assertRaises(ExtensionError) as ctx:
            host.run("map_proposal", "POST",
                     {"action": "suggest",
                      "request": {"base_revision": "nope", "target_revision": c2,
                                  "changed_paths": [], "current_map": {"nodes": [], "edges": []}}})
        self.assertEqual(int(ctx.exception.status), HTTPStatus.BAD_REQUEST)


class CodexRound1FixTests(SuggestTestBase):
    """Regressions for the findings raised by the Codex C audit (H1/H2/M1-M4)."""

    def test_H1_validator_passing_forgery_never_attached(self):
        """Codex probe: a coherent implementation.* forgery (status=MERGED, bogus
        head) with verified_fields passes the real CA validator — C must still
        refuse to attach it and must route it to HUMAN_REQUIRED."""
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        claims = [{"id": "claim-poison", "key": "implementation.code_facts",
                   "value": {"status": "MERGED", "head": "a" * 40}, "type": "VERIFIED_FACT",
                   "scope": "main",
                   "source": {"kind": "repo", "ref": "extensions/code_facts/README.md",
                              "revision": c2}}]
        pack = build_pack(repo, c2, registry_claims(claims))
        row = next(r for r in pack["current_state"]["current_by_scope"]
                   if r["key"] == "implementation.code_facts")
        projected = pack["current_state"]["current"].get("implementation.code_facts") or {}
        verified_copy = next((r for r in pack.get("verified_facts", [])
                              if r.get("key") == "implementation.code_facts"), {})
        for ref in row["evidence"] + projected.get("evidence", []) + verified_copy.get("evidence", []):
            ref["live_verification"] = {"source": {"kind": "human", "ref": "fixture verifier"},
                                        "verified_at": "2026-10-04T00:00:00Z",
                                        "freshness": "verified",
                                        "verified_fields": ["status", "head"]}
        row["freshness"] = "verified"
        if projected:
            projected["freshness"] = "verified"
        if verified_copy:
            verified_copy["freshness"] = "verified"
        reseal(pack)
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertFalse([e for p in result["proposals"] for e in p["evidence"]
                          if e["kind"] == "context_claim"])
        self.assertTrue(any(u["reason"] == "HUMAN_REQUIRED"
                            and u["subject"] == "claim:implementation.code_facts"
                            for u in result["unresolved"]))

    def test_F6_real_function_body_refactor(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    def render(self):\n        return 1\n"},
                                 {"a.py": "class Alpha:\n    def render(self):\n        value = 1\n        return value\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · render", ["a.py"])])), repo)
        self.assertEqual(result["proposals"], [])
        self.assertTrue(any(n["reason"].startswith("no declaration-level change")
                            for n in result["no_proposal"]))

    def test_M2_docstring_only_import_no_relation(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    pass\n", "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": 'class Alpha:\n    """see: import b_mod\n    """\n    pass\n'})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertNotIn("RELATION_ADD", self.kinds(result))

    def test_M3_import_churn_not_a_removal(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "import b_mod\n\n\nclass Alpha:\n    pass\n",
                                  "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "from b_mod import Beta\n\n\nclass Alpha:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertNotIn("RELATION_REMOVE_CANDIDATE", self.kinds(result))
        self.assertNotIn("RELATION_ADD", self.kinds(result))

    def test_M1_renamed_evidence_binds_base_revision(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {}, renames=[("a.py", "renamed_a.py")])
        result = suggest(request(repo, c1, c2,
                                 [{"path": "renamed_a.py", "status": "renamed",
                                   "old_path": "a.py"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])])), repo)
        diff_evidence = [e for p in result["proposals"] for e in p["evidence"]
                         if e["kind"] == "git_diff"]
        old_refs = [e for e in diff_evidence if e.get("path") == "a.py"]
        self.assertTrue(old_refs and old_refs[0]["revision"] == c1,
                        "old-path evidence must bind the base revision")

    def test_M1_removal_evidence_cites_node_path(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"old_mod.py": "class Old:\n    pass\n",
                                  "a-unrelated.py": "x = 1\n"},
                                 removals=["old_mod.py"])
        result = suggest(request(repo, c1, c2, [{"path": "old_mod.py", "status": "removed"}],
                                 make_map([("node-old", "Old", "old_mod.py · Old", ["old_mod.py"])])), repo)
        proposal = next(p for p in result["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE")
        diff_paths = {e.get("path") for e in proposal["evidence"] if e["kind"] == "git_diff"}
        self.assertIn("old_mod.py", diff_paths)

    def test_M4_partial_b_entry_tolerated(self):
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 code_facts={"revision": c2, "skipped": [],
                                             "files": [{"path": "pkg_new/feature.py",
                                                        "entries": [{"name": "Feature"}]}]}), repo)
        self.assertEqual(result["metadata"]["facts_mode"], "available")


    def test_H1_wraparound_claim_shapes_also_dropped(self):
        """Codex follow-up probes: high-impact assertions hidden in value text
        (MERGED token, SHA-like head) under innocuous keys must be dropped."""
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        claims = [
            {"id": "claim-note", "key": "architecture.note.v1",
             "value": {"summary": "MERGED", "commit": "a" * 40},
             "type": "HUMAN_DECISION", "scope": "team", "source": HUMAN},
            {"id": "claim-head", "key": "architecture.head.v1",
             "value": "a" * 40, "type": "HUMAN_DECISION", "scope": "team",
             "source": HUMAN},
            {"id": "claim-shape", "key": "contract.legacy_shape.v1",
             "value": {"shape": "legacy"}, "type": "CONTRACT", "scope": "main",
             "source": {"kind": "repo", "ref": "docs/x.md", "revision": c2}},
        ]
        pack = build_pack(repo, c2, registry_claims(claims))
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertFalse([e for p in result["proposals"] for e in p["evidence"]
                          if e["kind"] == "context_claim"])
        dropped = {u["subject"] for u in result["unresolved"]}
        self.assertTrue({"claim:architecture.note.v1", "claim:architecture.head.v1",
                         "claim:contract.legacy_shape.v1"} <= dropped)

    def test_H2_conflict_suppresses_relation_candidate(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "class Alpha:\n    pass\n",
                                  "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "import b_mod\n\n\nclass Alpha:\n    pass\n"})
        claims = [{"id": "claim-conflict-a", "key": "team.focus.v1",
                   "value": {"focus": "node-a owns the relation"}, "type": "HUMAN_DECISION",
                   "scope": "team", "source": HUMAN},
                  {"id": "claim-conflict-b", "key": "team.focus.v1",
                   "value": {"focus": "node-b owns the relation"}, "type": "HUMAN_DECISION",
                   "scope": "team", "source": HUMAN}]
        pack = build_pack(repo, c2, registry_claims(claims))
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])]),
                                 context_pack=pack), repo)
        self.assertEqual([p for p in result["proposals"] if p["kind"] == "RELATION_ADD"], [])
        self.assertTrue(any(u["reason"] == "HUMAN_REQUIRED"
                            and u["note"].startswith("proposal suppressed")
                            for u in result["unresolved"]))

    def test_H2_node_api_not_matched_as_node_a(self):
        """H2: substring guard — a conflict mentioning node-api must not suppress
        proposals that only touch node-a."""
        repo, c1, c2 = make_repo(self.base, {"a.py": "class Alpha:\n    pass\n"},
                                 {"pkg_new/feature.py": "class Feature:\n    pass\n"})
        claims = [{"id": "claim-conflict-a", "key": "team.focus.v1",
                   "value": {"focus": "node-api scope unresolved"}, "type": "HUMAN_DECISION",
                   "scope": "team", "source": HUMAN},
                  {"id": "claim-conflict-b", "key": "team.focus.v1",
                   "value": {"focus": "node-api alternative"}, "type": "HUMAN_DECISION",
                   "scope": "team", "source": HUMAN}]
        pack = build_pack(repo, c2, registry_claims(claims))
        result = suggest(request(repo, c1, c2,
                                 [{"path": "pkg_new/feature.py", "status": "added"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"])]),
                                 context_pack=pack), repo)
        self.assertEqual(self.kinds(result), ["NODE_ADD"])
        self.assertFalse([u for u in result["unresolved"]
                          if u["note"].startswith("proposal suppressed")])

    def test_M3_docstring_removal_not_a_relation(self):
        """Codex probe: base has `import b_mod` inside a docstring (not a real
        import) and the target removes the docstring AND changes declarations —
        line-regex counting saw it; AST counting must not."""
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": '"""\nimport b_mod\n"""\n\n\nclass Alpha:\n    pass\n',
                                  "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "class AlphaRenamed:\n    pass\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · Alpha", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertNotIn("RELATION_REMOVE_CANDIDATE", self.kinds(result))

    def test_M5_churn_with_declaration_change(self):
        """Codex probe: import churn in a file whose declarations ALSO changed —
        the churn filter (not the early exclusion) must suppress both signals."""
        repo, c1, c2 = make_repo(self.base,
                                 {"a.py": "import b_mod\n\n\nclass Alpha:\n    def render(self):\n        return 1\n",
                                  "b_mod.py": "class Beta:\n    pass\n"},
                                 {"a.py": "from b_mod import Beta\n\n\nclass Alpha:\n    def render(self):\n        value = 1\n        return value\n    def size(self):\n        return 2\n"})
        result = suggest(request(repo, c1, c2, [{"path": "a.py", "status": "modified"}],
                                 make_map([("node-a", "A", "a.py · render", ["a.py"]),
                                           ("node-b", "B", "b_mod.py · Beta", ["b_mod.py"])])), repo)
        self.assertNotIn("RELATION_ADD", self.kinds(result))
        self.assertNotIn("RELATION_REMOVE_CANDIDATE", self.kinds(result))

    def test_M5_removal_evidence_revisions(self):
        repo, c1, c2 = make_repo(self.base,
                                 {"own.py": "class Own:\n    pass\n",
                                  "aaa.py": "x = 1\n",
                                  "a.py": "class Alpha:\n    pass\n"},
                                 removals=["own.py", "aaa.py"])
        result = suggest(request(repo, c1, c2,
                                 [{"path": "own.py", "status": "removed"},
                                  {"path": "aaa.py", "status": "removed"}],
                                 make_map([("node-old", "Old", "own.py · Old", ["own.py"])])), repo)
        proposal = next(p for p in result["proposals"] if p["kind"] == "NODE_REMOVE_CANDIDATE")
        diff_refs = [(e["path"], e["revision"]) for e in proposal["evidence"]
                     if e["kind"] == "git_diff"]
        self.assertIn(("own.py", c1), diff_refs)
        self.assertIn(("own.py", c2), diff_refs)
        self.assertFalse([ref for ref in diff_refs if ref[0] == "aaa.py"])


if __name__ == "__main__":
    unittest.main()
