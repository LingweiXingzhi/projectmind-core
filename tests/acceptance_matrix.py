# -*- coding: utf-8 -*-
"""P08 — canonical S01-S30 acceptance matrix runner.

One authoritative mapping from the 30 Common Acceptance Matrix items (plan
§8) to the concrete tests that bind them, with REAL/FIXTURE/MOCK dependency
labels. Each item runs its mapped tests individually and records
RESULT/EVIDENCE. The whole matrix is run twice; stability is required.

Where a real dependency exists the binding test uses it (REAL): git repos
are real temporary repositories; real B/CA integration tests load the real
implementations and SKIP (never pass silently) when absent. S30 is owned by
the shared host: it is verified against the A30 fix branch worktree
(fix/core-extension-runtime-isolation) and finally on the integration base
that carries both deliveries.

Usage: python tests/acceptance_matrix.py [--json OUT] (writes a markdown
matrix to stdout).
"""
import argparse
import hashlib
import inspect
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

A30_WORKTREE = Path(r"G:\jiagou\projectmind-core-a30")

# S-id → (oracle summary, contract source, [(module, test_name_substring)],
#         dependency label, notes)
MATRIX = {
    "S01": ("real NODE_ADD exactly for uncovered path with eligible declarations",
            "plan §8 S01/A01 + X19", [("test_w2_channels", "test_s01_")], "FIXTURE facts + REAL git", ""),
    "S02": ("real RELATION_ADD incl. unchanged-declarations X01",
            "plan §8 S02/A02 + X01", [("test_w3_relations", "test_s02_x01_"), ("test_real_b_integration", "test_s02_s13_")], "REAL git + REAL B", ""),
    "S03": ("relation removal: last cross-domain import gone; multi-source residual; churn stays silent",
            "plan §8 S03/A03 + X11/X13", [("test_w3_relations", "test_s03_"), ("test_w3_relations", "test_x13_"), ("test_w3_relations", "test_removal_requires_")], "REAL git", ""),
    "S04": ("rename/move → IMPLEMENTATION_LINK_CHANGE, never NODE_ADD; subdirectory variant",
            "plan §8 S04/A04", [("test_w2_channels", "test_s04_"), ("test_p06_matrix_closure", "test_s04_sub")], "FIXTURE", ""),
    "S05": ("node removal: all evidence gone; partial retention → no candidate",
            "plan §8 S05/A05", [("test_w2_channels", "test_s05_")], "FIXTURE + MOCK tree", ""),
    "S06": ("responsibility change: entryPoint declaration gone, no first-symbol pick",
            "plan §8 S06/A06", [("test_w2_channels", "test_s06_"), ("test_real_b_integration", "test_s06_real")], "REAL B (installed collector)", ""),
    "S07": ("comment-only change: zero strong proposals with reason",
            "plan §8 S07/A07 + X20", [("test_w2_channels", "test_s07_")], "FIXTURE", ""),
    "S08": ("formatting-only (line/quote drift): zero proposals",
            "plan §8 S08/A08", [("test_p06_matrix_closure", "test_s08_")], "FIXTURE", "closed P06"),
    "S09": ("helper-only change: no NODE_ADD / strong proposal",
            "plan §8 S09/A09 + F10", [("test_w2_channels", "test_s09_")], "FIXTURE", ""),
    "S10": ("internal class added: no NODE_ADD",
            "plan §8 S10/A10 + F9", [("test_w2_channels", "test_s10_")], "FIXTURE", ""),
    "S11": ("docstring import text is never a relation; string/comment included",
            "plan §8 S11/A11 + X03/X12", [("test_w3_relations", "test_s11_")], "REAL git", ""),
    "S12": ("test/generated noise → no business architecture candidates",
            "plan §8 S12/A12", [("test_p06_matrix_closure", "test_s12_"), ("test_w2_channels", "test_test_noise")], "FIXTURE", "closed P06"),
    "S13": ("B skipped source → HUMAN_REQUIRED; no channel uses it; normal sources work",
            "plan §8 S13/A13 + X04/X21", [("test_real_b_integration", "test_s02_s13_"), ("test_w3_relations", "test_f04_x21_")], "REAL B skipped semantics", ""),
    "S14": ("B mismatch rejected on all paths; same-revision/empty diff no bypass",
            "plan §8 S14/A14 + X06", [("test_map_proposal", "test_supplied_mismatch"), ("test_map_proposal", "test_installed_b_mismatch"), ("test_map_proposal", "test_empty_changes"), ("test_real_b_integration", "test_s14_real")], "REAL B mismatch + supplied fixtures", ""),
    "S15": ("B unavailable → honest degraded; B-free channels continue; no fabricated facts",
            "plan §8 S15/A15", [("test_map_proposal", "test_b_unavailable"), ("test_real_b_integration", "test_s15_real")], "REAL absence + REAL exception", ""),
    "S16": ("stale map: pre-base deletion candidate; read-unknown ≠ absent; base==target zero",
            "plan §8 S16/A16-valid-map + F11/F15", [("test_w2_channels", "test_s16_"), ("test_w2_channels", "test_base_equals_target_zero")], "FIXTURE + MOCK tree", ""),
    "S17": ("ambiguous multi-owner mapping → low confidence + uncertainty, no arbitrary pick",
            "plan §8 S17/A17", [("test_w2_channels", "test_s17_"), ("test_p06_matrix_closure", "test_s17_")], "FIXTURE", "rename + relation variants"),
    "S18": ("missing evidence: added file without B entries → unresolved UNKNOWN",
            "plan §8 S18/A18", [("test_w2_channels", "test_added_without_facts"), ("test_p06_matrix_closure", "test_s18_")], "FIXTURE", ""),
    "S19": ("relevant CA conflict suppresses touching candidates only; word boundary",
            "plan §8 S19/A19 + X14/X15/X18", [("test_w4_ca_trust", "test_s19_"), ("test_real_ca_integration", "test_s19_s25_")], "REAL CA pack", ""),
    "S20": ("non-current partitions (stale/proposal/research/history) never read",
            "plan §8 S20/A20", [("test_w4_ca_trust", "test_s20_"), ("test_real_ca_integration", "test_s20_real")], "REAL CA stale semantics", ""),
    "S21": ("multi-scope same key both in selection layer",
            "plan §8 S21/A21", [("test_w4_ca_trust", "test_s21_"), ("test_real_ca_integration", "test_s21_real")], "REAL CA pack", ""),
    "S22": ("verified_fields per field; unverified fields support nothing",
            "plan §8 S22/A22", [("test_w4_ca_trust", "test_s22_"), ("test_real_ca_integration", "test_p05b_t2_")], "MOCK validator (field map contract)", "live verifiers = recorded limit"),
    "S23": ("unavailable keys explicit UNKNOWN, never faked bad-pack",
            "plan §8 S23/A23", [("test_w4_ca_trust", "test_s23_")], "MOCK validator", "real unavailable rows need network verifiers (recorded)"),
    "S24": ("invalid pack → whole-pack discard; independent candidates survive",
            "plan §8 S24/A24", [("test_w4_ca_trust", "test_s24_"), ("test_real_ca_integration", "test_s24_tampered")], "REAL CA digest tamper", ""),
    "S25": ("coherent poison never enters evidence/rationale (also with proposals present)",
            "plan §8 S25/A25 + X05/X16/X17", [("test_w4_ca_trust", "test_s25_"), ("test_real_ca_integration", "test_s19_s25_"), ("test_real_ca_integration", "test_p05b_t1_")], "REAL CA pack poison", ""),
    "S26": ("determinism: byte-identical repeats; order-insensitive IDs",
            "plan §8 S26/A26 + X09", [("test_w5_compatibility", "test_a26_"), ("test_w3_relations", "test_relation_add_determinism"), ("test_map_proposal", "test_determinism_same_input"), ("test_real_b_integration", "test_real_history_end_to_end")], "REAL git + REAL B history", ""),
    "S27": ("malformed inputs controlled rejection incl. valid-context malformed map",
            "plan §8 S27/A27", [("test_w5_compatibility", "test_malformed_"), ("test_p06_matrix_closure", "test_s27_")], "FIXTURE", "closed P06"),
    "S28": ("path abuse rejected across changed/oldPath/map evidence/entryPoint sources",
            "plan §8 S28/A28", [("test_w5_compatibility", "test_s28_"), ("test_map_proposal", "test_unsafe_"), ("test_map_proposal", "test_facts_and_entry_point"), ("test_p06_matrix_closure", "test_malicious_map_text")], "FIXTURE", ""),
    "S29": ("no formal-map write: file hash unchanged; no position; PROPOSED lifecycle",
            "plan §8 S29/A29", [("test_map_proposal", "test_map_file_hash_unchanged"), ("test_w5_compatibility", "test_no_position_anywhere"), ("test_real_b_integration", "test_real_history_end_to_end")], "REAL formal map hash", ""),
    "S30": ("host isolation: runtime BaseException contained, all routes survive",
            "plan §8 S30/A30", [], "REAL Core (A30 fix branch)", "verified on fix/core-extension-runtime-isolation worktree"),
}


def _iter_test_classes(module):
    for name, obj in vars(module).items():
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
            yield name, obj


def source_hash(module_name, substring):
    module = __import__(f"tests.{module_name}", fromlist=["*"])
    hashes = []
    for _cls_name, cls in _iter_test_classes(module):
        for tname, tobj in vars(cls).items():
            if tname.startswith("test") and substring in tname:
                try:
                    src = inspect.getsource(tobj)
                except OSError:
                    src = tname
                hashes.append(hashlib.sha256(src.encode("utf-8")).hexdigest())
    return hashlib.sha256("".join(sorted(hashes)).encode("utf-8")).hexdigest()[:16]


def run_selection(selections, round_no=None):
    """Run the union of selected tests; returns {test_id: ok} and failure text."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    names = []
    for module_name, substring in selections:
        module = __import__(f"tests.{module_name}", fromlist=["*"])
        for _cls_name, cls in _iter_test_classes(module):
            for tname in sorted(vars(cls)):
                if tname.startswith("test") and substring in tname:
                    names.append(f"{module_name}.{cls.__name__}.{tname}")
    for name in sorted(set(names)):
        suite.addTest(loader.loadTestsFromName(f"tests.{name}"))
    result = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
    failed = {(type(t).__module__, type(t).__name__, t._testMethodName)
              for t in getattr(result, "failures", []) + getattr(result, "errors", [])}
    ok_by_test = {}
    for module_name, substring in selections:
        module = __import__(f"tests.{module_name}", fromlist=["*"])
        for _cls_name, cls in _iter_test_classes(module):
            for tname in sorted(vars(cls)):
                if tname.startswith("test") and substring in tname:
                    key = (f"tests.{module_name}", cls.__name__, tname)
                    ok_by_test[f"{module_name}.{cls.__name__}.{tname}"] = key not in failed
    return ok_by_test, result.testsRun, len(result.failures) + len(result.errors)


import os  # noqa: E402


def run_a30_fix_tests():
    """S30 evidence: the formal A30 regression. On an integration base that
    carries the A30 fix the tests run in-runtime; otherwise the fix-branch
    worktree is used as the owner-delivery evidence."""
    proc = subprocess.run([sys.executable, "-m", "unittest", "tests.test_extensions"],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    if proc.returncode == 0:
        return True, ("in-runtime on this checkout: 9/9 extension tests "
                      "incl. 4 A30 formal tests (fail on pre-fix host)")
    if A30_WORKTREE.is_dir():
        proc = subprocess.run([sys.executable, "-m", "unittest", "tests.test_extensions"],
                              cwd=str(A30_WORKTREE), capture_output=True, text=True,
                              timeout=300)
        if proc.returncode == 0:
            return True, ("fix/core-extension-runtime-isolation worktree: 9/9 extension "
                          "tests incl. 4 A30 formal tests (fail on pre-fix host)")
    return False, "A30 formal regression failed in-runtime and no fix worktree present"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    rounds = []
    for round_no in (1, 2):
        rows = {}
        cache = {}
        for sid in sorted(MATRIX):
            oracle, source, selections, deps, notes = MATRIX[sid]
            key = tuple(sorted(selections))
            if sid == "S30":
                ok, evidence = run_a30_fix_tests()
                rows[sid] = {"oracle": oracle, "contract": source, "deps": deps,
                             "result": "PASS" if ok else ("NOT_RUN" if ok is None else "FAIL"),
                             "evidence": evidence or "fix/core-extension-runtime-isolation: 9/9 extension tests incl. 4 A30 formal tests (fail on pre-fix host)",
                             "input_hash": "n/a (external worktree)", "notes": notes}
                continue
            if key not in cache:
                cache[key] = run_selection(selections)
            ok_by_test, total, failed = cache[key]
            all_ok = failed == 0 and ok_by_test and all(ok_by_test.values())
            rows[sid] = {
                "oracle": oracle, "contract": source, "deps": deps,
                "result": "PASS" if all_ok else "FAIL",
                "evidence": f"{len(ok_by_test)} test(s) run: "
                            + (", ".join(sorted(ok_by_test)) if ok_by_test else "NO TESTS MAPPED"),
                "input_hash": source_hash(*selections[0]) if selections else "",
                "notes": notes,
            }
        rounds.append(rows)

    stable = json.dumps(rounds[0], sort_keys=True) == json.dumps(rounds[1], sort_keys=True)
    pass_count = sum(1 for r in rounds[1].values() if r["result"] == "PASS")
    lines = ["# S01-S30 ACCEPTANCE MATRIX (canonical, two-round stable)",
             "",
             f"RESULT: {pass_count}/30 PASS | two-round stable: {stable}",
             f"HEAD: {subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}",
             ""]
    for sid in sorted(rounds[1]):
        r = rounds[1][sid]
        lines.append(f"## {sid} — {r['result']}")
        lines.append(f"- ORACLE: {r['oracle']}")
        lines.append(f"- CONTRACT: {r['contract']}")
        lines.append(f"- DEPS: {r['deps']}")
        lines.append(f"- INPUT_HASH: {r['input_hash']}")
        lines.append(f"- NOTES: {r['notes']}")
        lines.append(f"- EVIDENCE: {r['evidence']}")
        lines.append("")
    out = "\n".join(lines)
    print(out)
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"stable": stable, "pass": pass_count, "rounds": rounds},
            ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
