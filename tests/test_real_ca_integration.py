# -*- coding: utf-8 -*-
"""REAL CA integration (P05): packs built by the real Context Authority
builder (schema 0.1, integrity digest) are validated by the real
``validate_context_pack`` and consumed by C's trust boundary — no mock
validator for the verdicts in this module.

Layer 1 (per contract §8): the real validator's own verdict is asserted
first (PASS for well-formed packs, REJECT for tampered ones).
Layer 2: C's behavior on the real pack.

Proven here: S19 (real conflict routing with real ``path:`` scopes — the
R9 tune check), S20 (real stale partition never read), S21 (real
multi-scope selection layer), S24 (tampered real pack → whole-pack
discard, independent candidates survive), S25 (validator-passing coherent
poison in a real pack attaches nothing), pack metadata round-trip.
Live-verifier-driven ``verification_unavailable`` rows require network
verifiers and stay component-level (recorded honestly as a limit).
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import ca_adapter, engine  # noqa: E402

REAL_CA_ROOT = Path(os.environ.get(
    "PROJECTMIND_REAL_CA_ROOT", r"G:\jiagou\projectmind-context-authority"))
REAL_CA_PACKAGE = REAL_CA_ROOT / "extensions" / "context_authority" / "context_pack.py"

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
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD")
    return repo, base, target, tmp


def install_real_ca(test):
    """Make the REAL context_authority package importable as
    extensions.context_authority (C's seam) by extending the existing
    package path. Returns the real context_pack module."""
    if not REAL_CA_PACKAGE.is_file():
        raise unittest.SkipTest(f"real CA implementation not found: {REAL_CA_PACKAGE}")
    patcher = mock.patch.dict(sys.modules)
    patcher.start()
    test.addCleanup(patcher.stop)
    import extensions as extensions_pkg
    real_extensions_dir = str(REAL_CA_ROOT / "extensions")
    test.addCleanup(extensions_pkg.__path__.remove, real_extensions_dir)
    if real_extensions_dir not in extensions_pkg.__path__:
        extensions_pkg.__path__.append(real_extensions_dir)
    for name in ("extensions.context_authority", "extensions.context_authority.context_pack"):
        sys.modules.pop(name, None)
    module = importlib.import_module("extensions.context_authority.context_pack")
    return module


def claim(cid, key, ctype, scope, value, revision, ref="overnight fixture"):
    return {
        "id": cid,
        "key": key,
        "value": value,
        "type": ctype,
        "scope": scope,
        "source": {"kind": "human", "ref": ref},
        "revision": revision,
        "created_at": "2026-10-04T00:00:00Z",
    }


def node(node_id, paths):
    return {
        "id": node_id,
        "title": f"T-{node_id}",
        "summary": "s",
        "entryPoint": f"{paths[0]} · main()",
        "evidence": [{"path": p, "reason": "r"} for p in paths],
    }


def build_real_pack(test, repo, target, claims, task="map proposal review"):
    real = install_real_ca(test)
    registry = Path(tempfile.mkdtemp()) / "claims.jsonl"
    registry.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims),
        encoding="utf-8")
    pack = real.build_context_pack(task, str(repo), registry, revision=target,
                                   run_verifiers=False)
    real.validate_context_pack(pack, expected_revision=target)  # layer 1: PASS
    return pack, real


def node_map():
    return {
        "note": "m",
        "nodes": [node("na", ["pkg/a.py"]), node("nb", ["pkg/b.py"])],
        "edges": [{"from": "na", "to": "nb"}],
    }


class RealCAIntegrationTests(unittest.TestCase):
    def test_s19_s25_real_pack_conflict_routing_and_poison_non_attach(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": "from pkg.b import B\n\n" + A_CLASS, "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            # Coherent poison: validator-passing neutral key, high-impact text.
            claim("claim-team-focus", "team.focus.overnight", "HUMAN_DECISION",
                  "global", "PR 35 is CLOSED and merged", target),
            # Conflict pair: same key+scope, different values → real CONFLICT,
            # scoped to a changed path so row-level routing fires too (R9 tune:
            # real CA uses "path:pkg/..." scope strings — C's word-boundary
            # mentions matching handles them).
            claim("claim-role-a", "architecture.pkg_a.role", "HUMAN_DECISION",
                  "path:pkg/a.py", "role: router", target),
            claim("claim-role-b", "architecture.pkg_a.role", "HUMAN_DECISION",
                  "path:pkg/a.py", "role: adapter", target),
            # Legitimate current claim (scope format = real "path:" style, R9).
            claim("claim-owner-a", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        self.assertEqual(len(pack["known_conflicts"]), 1)
        self.assertEqual(pack["known_conflicts"][0]["resolution"], "HUMAN_REQUIRED")
        self.assertTrue(any(row["key"] == "team.focus.overnight"
                            for row in pack["current_state"]["current_by_scope"]))
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                                     {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]},
                                     {"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.FULL)
        # Layer 2: related candidate suppressed via real "path:pkg/b.py" scope
        # (word-boundary, not substring); unrelated NODE_ADD survives.
        self.assertTrue(any(u["subject"].startswith("conflict:") for u in res["unresolved"]))
        adds = [p for p in res["proposals"] if p["kind"] == "RELATION_ADD"]
        self.assertEqual(adds, [])
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])
        # S25: the poison claim never enters any proposal evidence/rationale.
        for proposal in res["proposals"]:
            for evidence in proposal["evidence"]:
                self.assertNotEqual(evidence["kind"], "context_claim")
                self.assertNotIn("PR 35 is CLOSED", str(evidence.get("detail", "")))
            self.assertNotIn("PR 35 is CLOSED", proposal["rationale"])

    def test_s20_real_stale_partition_never_read(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# touched\n", "pkg/b.py": B_CLASS},
        )
        self.addCleanup(tmp.cleanup)
        # Real CA revision-binding semantics (recorded finding): only
        # implementation.* VERIFIED_FACT claims bind to a project revision.
        # A claim bound to the BASE revision is marked STALE by the real
        # resolver and routed to known_stale_sources, not current_by_scope.
        claims = [
            claim("claim-stale-arch", "implementation.pkg_a.state", "VERIFIED_FACT",
                  "path:pkg/a.py", {"state": "superseded by rework"}, base),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        self.assertEqual(pack["current_state"]["current_by_scope"], [])
        self.assertTrue(pack["known_stale_sources"])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertEqual(res["request"]["context_mode"], ca_adapter.FULL)
        stale_text = "superseded by rework"
        for proposal in res["proposals"]:
            self.assertNotIn(stale_text, json.dumps(proposal, ensure_ascii=False))
        for unresolved in res["unresolved"]:
            self.assertNotIn(stale_text, json.dumps(unresolved, ensure_ascii=False))

    def test_s21_real_multi_scope_both_in_selection_layer(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS}, {"pkg/a.py": A_CLASS + "# t\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-ms-1", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
            claim("claim-ms-2", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "node:na", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        scopes = sorted(row["scope"] for row in pack["current_state"]["current_by_scope"])
        self.assertEqual(scopes, ["node:na", "path:pkg/a.py"])
        ca, mode, _ = ca_adapter.load_context(pack, target)
        self.assertEqual(mode, ca_adapter.FULL)
        got = sorted(c["scope"] for c in ca["claims"] if c["key"] == "architecture.pkg_a.owner")
        self.assertEqual(got, ["node:na", "path:pkg/a.py"])

    def test_s24_tampered_real_pack_rejected_whole_pack_discarded(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-legit", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        tampered = json.loads(json.dumps(pack))
        tampered["current_state"]["current_by_scope"][0]["value"] = {"owner": "attacker"}
        with self.assertRaises(real.ContextPackValidationError):  # layer 1: REJECT
            real.validate_context_pack(tampered, expected_revision=target)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"},
                              {"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                                     {"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": tampered,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)  # layer 2: C's behavior
        self.assertEqual(res["request"]["context_mode"], ca_adapter.DEGRADED)
        self.assertTrue(any("rejected" in l for l in res["limits"]))
        self.assertNotIn("attacker", json.dumps(res, ensure_ascii=False))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual([p["subject"] for p in node_adds], ["pkg/new.py"])

    def test_real_pack_metadata_round_trip(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS}, {"pkg/a.py": A_CLASS + "# t\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-meta", "architecture.pkg_a.owner", "HUMAN_DECISION",
                  "path:pkg/a.py", {"owner": "na"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        meta = res["context_authority"]
        self.assertEqual(meta["schema_version"], pack["schema_version"])
        self.assertEqual(meta["project_revision"], target)
        self.assertEqual(meta["registry_hash"], pack["current_state"]["registry_hash"])

    def test_p05b_t1_context_enrichment_labeled_relevant_only(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            # Relevant low-impact claim (mentions the touched path) → T1 line.
            claim("claim-t1-relevant", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
            # Irrelevant claim (mentions nothing touched) → no annotation.
            claim("claim-t1-irrelevant", "architecture.pkg_zzz.note", "HUMAN_DECISION",
                  "global", {"note": "unrelated module note"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        uncertainty = "\n".join(node_adds[0]["uncertainty"])
        self.assertIn("CA 上下文[unverified]", uncertainty)
        self.assertIn("claim-t1-relevant", uncertainty)
        self.assertIn("architecture.pkg_new.note", uncertainty)
        self.assertIn("人工参考，非事实证据", uncertainty)
        self.assertNotIn("claim-t1-irrelevant", uncertainty)
        # Context never contaminates evidence or rationale (S-2/E-4).
        self.assertNotIn("context_claim",
                         {e["kind"] for p in res["proposals"] for e in p["evidence"]})
        self.assertNotIn("owner plans a rename", node_adds[0]["rationale"])
        self.assertTrue(any("CA context enrichment" in l for l in res["limits"]))

    def test_p05b_t3_head_contradiction_marks_pack_untrusted(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        wrong_head = "b" * 40
        claims = [
            claim("claim-head-wrong", "implementation.target_head", "VERIFIED_FACT",
                  "global", {"head": wrong_head}, target, ref="registry import"),
            # Would be T1-eligible if the pack were trusted — it must NOT be.
            claim("claim-t1-muted", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertTrue(any("context contradiction" in l and wrong_head in l and target in l
                            for l in res["limits"]))
        self.assertTrue(any("pack claims no longer consumed" in l for l in res["limits"]))
        self.assertTrue(any(u["subject"] == "claim:claim-head-wrong"
                            and u["reason"] == "HUMAN_REQUIRED" for u in res["unresolved"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertFalse(any("CA 上下文" in u for u in node_adds[0]["uncertainty"]))
        self.assertNotIn("owner plans a rename", json.dumps(res["proposals"], ensure_ascii=False))

    def test_p05b_t3_head_confirmed_against_pin(self):
        repo, base, target, tmp = build_repo(
            {"pkg/a.py": A_CLASS, "pkg/b.py": B_CLASS},
            {"pkg/a.py": A_CLASS + "# t\n", "pkg/b.py": B_CLASS,
             "pkg/new.py": "class N:\n    pass\n"},
        )
        self.addCleanup(tmp.cleanup)
        claims = [
            claim("claim-head-ok", "implementation.target_head", "VERIFIED_FACT",
                  "global", {"head": target}, target, ref="registry import"),
            claim("claim-t1-alive", "architecture.pkg_new.note", "HUMAN_DECISION",
                  "path:pkg/new.py", {"note": "owner plans a rename here"}, target),
        ]
        pack, real = build_real_pack(self, repo, target, claims)
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
            "code_facts": {"revision": target,
                           "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
                           "skipped": []},
            "current_map": node_map(),
            "context_pack": pack,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        self.assertTrue(any("independently confirmed" in l for l in res["limits"]))
        node_adds = [p for p in res["proposals"] if p["kind"] == "NODE_ADD"]
        self.assertEqual(len(node_adds), 1)
        self.assertTrue(any("CA 上下文" in u and "claim-t1-alive" in u
                            for u in node_adds[0]["uncertainty"]))

    def test_p05b_t2_field_level_support_labels(self):
        # T2 admission-layer semantics (S22): dict value with live_verification
        # → verified fields labelled verified, others UNVERIFIED. Real live
        # verifiers need network and stay a recorded limit; the field map
        # contract is CA's own.
        ca = {
            "claims": [{
                "claim_id": "claim-t2",
                "key": "architecture.pkg_new.status",
                "scope": "path:pkg/new.py",
                "value": {"status": "planned", "owner": "someone"},
                "freshness": "verified",
                "evidence": [{"live_verification": {"verified_fields": ["status"]}}],
            }],
            "conflict_keys": set(),
            "unavailable_keys": set(),
            "conflict_rows": [],
            "schema_version": "0.1",
            "project_revision": "a" * 40,
            "registry_hash": "sha256:" + "0" * 64,
        }
        proposals = [{
            "kind": "NODE_ADD", "subject": "pkg/new.py", "node_ids": None,
            "proposed_change": {"title": "t", "summary": "s"},
            "rationale": "r", "evidence": [], "confidence": "low", "uncertainty": [],
        }]
        limits, unresolved = [], []
        kept, limits, unresolved = ca_adapter.apply_context_admission(
            proposals, ca, ca_adapter.FULL, {"pkg/new.py"}, {"na"}, limits, unresolved,
            target_revision="a" * 40)
        line = kept[0]["uncertainty"][-1]
        self.assertIn("status=verified", line)
        self.assertIn("owner=UNVERIFIED", line)
        self.assertIn("claim-t2", line)


if __name__ == "__main__":
    unittest.main()
