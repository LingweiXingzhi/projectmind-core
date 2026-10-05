# -*- coding: utf-8 -*-
"""P08 — canonical S01-S30 acceptance matrix runner (V-01 repaired).

One authoritative mapping from the 30 Common Acceptance Matrix items (plan
§8) to the concrete tests that bind them, with REAL/FIXTURE/MOCK dependency
labels. Each item runs its mapped tests individually and records an EXPLICIT
result category. The whole matrix is run twice; stability is required.

V-01 repair (HIGH): the runner can no longer manufacture false PASS.
- SkipTest is SKIP, never PASS (result.skipped is checked).
- A mapping that matches zero tests is NOT_RUN, never PASS.
- A module that fails to import/load is INVALID_TEST, never PASS.
- S30 runs the actual A30 runtime-isolation tests, bound by name
  (test_a30_*); it never infers A30 PASS from unrelated host tests, test
  counts or hardcoded evidence text. Zero discovered A30 tests -> NOT_RUN.
- INPUT_HASH covers the mapped test code of ALL selections plus the C
  implementation sources the tests exercise — not one function's source.
- Evidence reports the real counts and test names that ran.

Result categories (A14/A17): PASS, FAIL, SKIP, NOT_RUN, INVALID_TEST,
ENVIRONMENT_LIMIT, ERROR. Only PASS counts toward the ready gate; SKIP,
NOT_RUN and ENVIRONMENT_LIMIT never count as PASS.

Usage: python tests/acceptance_matrix.py [--json OUT] (writes a markdown
matrix to stdout).
"""
import argparse
import hashlib
import inspect
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

A30_WORKTREE = Path(r"G:\jiagou\projectmind-core-a30")
A30_TEST_PREFIX = "test_a30_"

RESULT_CATEGORIES = (
    "PASS", "FAIL", "SKIP", "NOT_RUN", "INVALID_TEST", "ENVIRONMENT_LIMIT", "ERROR",
)

# S-id → (oracle summary, contract source, [(module, test_name_substring)],
#         dependency label, notes)
MATRIX = {
    "S01": ("real NODE_ADD exactly for uncovered path with eligible declarations",
            "plan §8 S01/A01 + X19", [("test_w2_channels", "test_s01_")], "FIXTURE facts + REAL git", ""),
    "S02": ("real RELATION_ADD incl. unchanged-declarations X01",
            "plan §8 S02/A02 + X01", [("test_w3_relations", "test_s02_x01_"), ("test_real_b_integration", "test_s02_s13_")], "REAL git + REAL B", ""),
    "S03": ("relation removal: last cross-domain import gone; multi-source residual; churn stays silent",
            "plan §8 S03/A03 + X11/X13", [("test_w3_relations", "test_s03_"), ("test_w3_relations", "test_x13_"), ("test_w3_relations", "test_c01_"), ("test_w3_relations", "test_removal_requires_")], "REAL git", "C-01: multi-target residual proof bound"),
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
            "plan §8 S13/A13 + X04/X21", [("test_real_b_integration", "test_s02_s13_"), ("test_w3_relations", "test_f04_x21_"), ("test_w3_relations", "test_c02_")], "REAL B skipped semantics", "C-02: full evidence-domain eligibility gate bound"),
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
            "plan §8 S19/A19 + X14/X15/X18", [("test_w4_ca_trust", "test_s19_"), ("test_w4_ca_trust", "test_c03_"), ("test_real_ca_integration", "test_s19_s25_")], "REAL CA pack", "C-03: subject-aware T3 bound"),
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
            "plan §8 S30/A30", [], "REAL Core A30 runtime tests (bound by name)", "runs the actual test_a30_* behavior tests in-runtime when present, else in the A30 fix worktree (owner delivery); zero discovered A30 tests → NOT_RUN"),
}


def _iter_test_classes(module):
    for name, obj in vars(module).items():
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
            yield name, obj


def _match_specs(selections, import_root):
    """(module_name, class_name, test_name) specs, import errors, and the
    selections that matched ZERO tests. Import failures and empty selections
    are collected, never silently dropped — a passing selection must not mask
    a broken sibling (V-01 review MEDIUM)."""
    specs, import_errors, empty = [], [], []
    for module_name, substring in selections:
        try:
            module = __import__(f"{import_root}.{module_name}", fromlist=["*"])
        except Exception as exc:  # noqa: BLE001 — a broken mapping is evidence
            import_errors.append(f"{import_root}.{module_name}: {type(exc).__name__}: {exc}")
            continue
        found = 0
        for cls_name, cls in _iter_test_classes(module):
            for tname in sorted(vars(cls)):
                if tname.startswith("test") and substring in tname:
                    specs.append((module_name, cls_name, tname))
                    found += 1
        if not found:
            empty.append(f"{module_name}:{substring!r}")
    return specs, import_errors, empty


def run_selection(selections, import_root="tests"):
    """Run the union of selected tests with honest classification (V-01).

    Returns {"result", "evidence", "passed", "failed", "skipped", "total"}.
    - module import failure            -> INVALID_TEST (mapping/dependency broken)
    - zero matched tests               -> NOT_RUN (absence of evidence)
    - any assertion failure or error   -> FAIL
    - any SkipTest (and none failed)   -> SKIP (an explicit non-pass)
    - otherwise                        -> PASS
    """
    specs, import_errors, empty_selections = _match_specs(selections, import_root)
    if import_errors:
        return {
            "result": "INVALID_TEST",
            "evidence": "mapping/dependency broken: " + "; ".join(import_errors),
            "passed": 0, "failed": 0, "skipped": 0, "total": 0,
        }
    if empty_selections:
        # V-01 review: a zero-match selection next to passing ones used to be
        # masked into an overall PASS; absence of evidence is NOT_RUN.
        return {
            "result": "NOT_RUN",
            "evidence": "NO TESTS MAPPED for selection(s): "
                        + ", ".join(empty_selections),
            "passed": 0, "failed": 0, "skipped": 0, "total": 0,
        }
    if not specs:
        return {
            "result": "NOT_RUN",
            "evidence": "NO TESTS MAPPED by the selection substrings "
                        + repr([s[1] for s in selections]),
            "passed": 0, "failed": 0, "skipped": 0, "total": 0,
        }

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    load_errors = []
    for module_name, cls_name, tname in sorted(set(specs)):
        name = f"{import_root}.{module_name}.{cls_name}.{tname}"
        try:
            suite.addTest(loader.loadTestsFromName(name))
        except Exception as exc:  # noqa: BLE001 — unloadable test is not a pass
            load_errors.append(f"{name}: {type(exc).__name__}: {exc}")
    if load_errors:
        return {
            "result": "INVALID_TEST",
            "evidence": "tests failed to load: " + "; ".join(load_errors[:5]),
            "passed": 0, "failed": 0, "skipped": 0, "total": len(specs),
        }

    buffer = io.StringIO()
    result = unittest.TextTestRunner(verbosity=0, stream=buffer).run(suite)
    failures = [(type(t).__module__, t._testMethodName)
                for t, _ in getattr(result, "failures", [])]
    errors = [(type(t).__module__, t._testMethodName)
              for t, _ in getattr(result, "errors", [])]
    skipped = [t._testMethodName for t, _ in getattr(result, "skipped", [])]
    total = result.testsRun
    passed = total - len(failures) - len(errors) - len(skipped)

    if failures or errors:
        outcome = "FAIL"
        bad = [f"{m}.{n}" for m, n in (failures + errors)[:6]]
        evidence = (f"{passed} passed, {len(skipped)} skipped, "
                    f"{len(failures) + len(errors)} not-passed of {total} mapped; "
                    "not-passed: " + ", ".join(bad))
    elif skipped:
        outcome = "SKIP"
        evidence = (f"{passed} passed, {len(skipped)} SKIPPED of {total} mapped; "
                    "skipped: " + ", ".join(skipped[:6])
                    + " — skip is never PASS (V-01)")
    else:
        outcome = "PASS"
        evidence = f"{passed} passed, 0 skipped, 0 failed of {total} mapped"
    return {
        "result": outcome,
        "evidence": evidence,
        "passed": passed, "failed": len(failures) + len(errors),
        "skipped": len(skipped), "total": total,
    }


def _a30_test_names(root):
    """The actual A30-named runtime tests in root's tests.test_extensions."""
    script = (
        "import json, sys, unittest\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import tests.test_extensions as m\n"
        "out = set()\n"
        "for k, v in vars(m).items():\n"
        "    if isinstance(v, type) and issubclass(v, unittest.TestCase):\n"
        "        for tn in vars(v):\n"
        "            if tn.startswith('test_a30_'):\n"
        "                out.add(k + '.' + tn)\n"
        "print(json.dumps(sorted(out)))\n"
    )
    proc = subprocess.run([sys.executable, "-c", script, str(root)],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def _run_named_tests(root, qualified_names):
    """(outcomes, ran_count) — one subprocess PER named test, classified from
    the run's final summary line. V-01 review: a skipped test exits 0, and
    the A30 tests interleave HTTP-server logs between '...' and the verdict,
    so neither the return code nor same-line verbose parsing is trustworthy.
    Per-test isolation plus summary-line classification is immune to both."""
    outcomes = {}
    for name in qualified_names:
        proc = subprocess.run([sys.executable, "-m", "unittest", "-v",
                               f"tests.test_extensions.{name}"],
                              cwd=str(root), capture_output=True, text=True,
                              timeout=300)
        output = " ".join([proc.stdout or "", proc.stderr or ""])
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        summary = lines[-1] if lines else ""
        if proc.returncode != 0:
            outcomes[name] = "FAIL" if "FAILED" in summary else "ERROR"
        elif "skipped=" in summary:
            outcomes[name] = "skipped"
        elif summary.startswith("OK"):
            outcomes[name] = "ok"
        else:
            outcomes[name] = "UNKNOWN"
    return outcomes, len(qualified_names)


def run_a30_fix_tests():
    """S30 evidence: the REAL A30 runtime-isolation behavior tests, bound by
    name (V-01: no inference from unrelated host tests, counts, or hardcoded
    evidence text). Runs the discovered test_a30_* tests in-runtime when this
    checkout carries them; otherwise in the A30 fix worktree (owner delivery,
    labeled as external evidence).

    V-01 review fixes: a skipped A30 test exits 0 but classifies SKIP, never
    PASS; an enumeration failure is INVALID_TEST instead of a silent NOT_RUN;
    the evidence carries the parsed per-test outcomes; and INPUT_HASH pins
    the actual A30 test source plus the bound test names."""
    candidates = [("this checkout (in-runtime)", ROOT)]
    if A30_WORKTREE.is_dir():
        candidates.append((f"A30 fix worktree {A30_WORKTREE.name} (external owner delivery)",
                           A30_WORKTREE))
    invalid_roots = []
    for location, root in candidates:
        names = _a30_test_names(root)
        if names is None:
            invalid_roots.append(location)
            continue
        if not names:
            continue
        outcomes, ran = _run_named_tests(root, names)
        digest = hashlib.sha256()
        digest.update((root / "tests" / "test_extensions.py").read_bytes())
        digest.update(json.dumps(names).encode("utf-8"))
        row_hash = digest.hexdigest()[:16]
        header = (f"{len(names)} A30 runtime test(s) run in {location}: "
                  + ", ".join(f"{name}={outcomes.get(name, 'MISSING')}" for name in names))
        if ran != len(names) or any(name not in outcomes for name in names) \
                or any(outcome == "UNKNOWN" for outcome in outcomes.values()):
            return {"result": "INVALID_TEST", "input_hash": row_hash,
                    "evidence": header + "; could not account for the outcome of "
                    "every named A30 test"}
        if any(outcome in ("FAIL", "ERROR") for outcome in outcomes.values()):
            return {"result": "FAIL", "input_hash": row_hash, "evidence": header}
        if any(outcome == "skipped" for outcome in outcomes.values()):
            skipped_names = [name for name, outcome in outcomes.items()
                             if outcome == "skipped"]
            return {"result": "SKIP", "input_hash": row_hash,
                    "evidence": header + "; skipped: " + ", ".join(skipped_names)
                    + " — a skipped A30 behavior test is never PASS (V-01)"}
        return {"result": "PASS", "input_hash": row_hash, "evidence": header}
    if invalid_roots:
        return {"result": "INVALID_TEST", "input_hash": "n/a",
                "evidence": "A30 test enumeration failed in: "
                + "; ".join(invalid_roots)}
    return {
        "result": "NOT_RUN", "input_hash": "n/a",
        "evidence": "no test_a30_* runtime-isolation tests discovered in this "
                    "checkout or the A30 fix worktree — S30 cannot pass without "
                    "running the actual A30 behavior tests (V-01)",
    }


def input_hash(selections):
    """V-01 INPUT_HASH: pins the mapped TEST code across ALL selections plus
    every C implementation source the tests exercise. The pre-fix hash
    covered only the first selection's test-function sources, so evidence
    survived unrelated test and implementation changes."""
    parts = []
    for module_name, substring in selections:
        # The selection identity itself is hashed, so a zero-match selection
        # still changes the hash (V-01 review: bindings are part of the input).
        parts.append(f"selection:{module_name}:{substring}")
        specs, _, _ = _match_specs([(module_name, substring)], "tests")
        for module, cls_name, tname in specs:
            cls = getattr(__import__(f"tests.{module}", fromlist=["*"]), cls_name)
            try:
                src = inspect.getsource(getattr(cls, tname))
            except OSError:
                src = tname
            parts.append(f"{module}.{cls_name}.{tname}:{src}")
    impl_dir = ROOT / "extensions" / "map_proposal"
    for path in sorted(impl_dir.glob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    return hashlib.sha256("\x1e".join(parts).encode("utf-8")).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    rounds = []
    for _round_no in (1, 2):
        rows = {}
        cache = {}
        for sid in sorted(MATRIX):
            oracle, source, selections, deps, notes = MATRIX[sid]
            if sid == "S30":
                outcome = run_a30_fix_tests()
                rows[sid] = {
                    "oracle": oracle, "contract": source, "deps": deps,
                    "result": outcome["result"], "evidence": outcome["evidence"],
                    "input_hash": outcome["input_hash"],
                    "notes": notes,
                }
                continue
            key = tuple(sorted(selections))
            if key not in cache:
                cache[key] = run_selection(selections)
            sel = cache[key]
            rows[sid] = {
                "oracle": oracle, "contract": source, "deps": deps,
                "result": sel["result"], "evidence": sel["evidence"],
                "input_hash": input_hash(selections) if selections else "",
                "notes": notes,
            }
        rounds.append(rows)

    stable = json.dumps(rounds[0], sort_keys=True) == json.dumps(rounds[1], sort_keys=True)
    final = rounds[1]
    pass_count = sum(1 for r in final.values() if r["result"] == "PASS")
    breakdown = {}
    for r in final.values():
        breakdown[r["result"]] = breakdown.get(r["result"], 0) + 1
    breakdown_text = " ".join(f"{k}={v}" for k, v in sorted(breakdown.items()))
    lines = ["# S01-S30 ACCEPTANCE MATRIX (canonical, two-round stable, V-01 honest)",
             "",
             f"RESULT: {pass_count}/30 PASS | categories: {breakdown_text} | two-round stable: {stable}",
             f"HEAD: {subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}",
             ""]
    for sid in sorted(final):
        r = final[sid]
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
            {"stable": stable, "pass": pass_count, "breakdown": breakdown,
             "rounds": rounds},
            ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
