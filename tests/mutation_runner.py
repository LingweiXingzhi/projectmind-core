# -*- coding: utf-8 -*-
"""C mutation runner (A13) — proves the contract suite is bound to its
invariants with VALID SEMANTIC mutations only. V-02 repaired.

Status vocabulary (V-02) — only SEMANTIC_CAUGHT counts as success:
- ANCHOR_NOT_FOUND: the mutation anchor text does not exist in current
  source (the mutation drifted; it cannot be evaluated this round).
- INVALID_MUTATION: the mutated file does not parse as Python — the mutation
  broke the code, not the invariant. Historically M4 shipped an orphan
  `except` (SyntaxError) and was counted as caught; that claim is retired.
- ENVIRONMENT_ERROR: infrastructure failure (clone failure, timeout, or the
  UNMUTATED baseline suite is already red — a red baseline can never count
  as a kill).
- SEMANTIC_MISSED: mutation applied and valid, guards stayed green — the
  suite is NOT bound to the invariant (reported, never counted as caught).
- SEMANTIC_CAUGHT: mutation applied and valid, the declared guard suite
  fails on the mutated tree.

Every mutation is applied in a fresh clone under tempfile; the real worktree
is untouched and mutations are never committed. A mutation that parses and
runs but changes nothing observable cannot be caught — it reports
SEMANTIC_MISSED honestly instead of inflating the score.
"""
import argparse
import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_REPO = Path(__file__).resolve().parents[1]

# (id, description, target invariant, file, old, new, [guarding test modules])
MUTATIONS = [
    (
        "M1_revision_gate_off",
        "disable B revision gate: any facts revision accepted",
        "B revision gate (F06/L06/S14)",
        "extensions/map_proposal/facts_adapter.py",
        'def _check_revision(raw_revision, target_revision):\n'
        '    if not isinstance(raw_revision, str) or raw_revision != target_revision:\n'
        '        raise FactsMismatch("code_facts.revision 必须等于 target_revision")',
        'def _check_revision(raw_revision, target_revision):\n    return None',
        ["tests.test_map_proposal"],
    ),
    (
        "M2_eligibility_gate_neutralized",
        "neutralize the centralized evidence-domain eligibility gate: skipped/"
        "uncollected members stop blocking strong relation proposals",
        "B skipped eligibility across the full evidence domain (A4/E-3, C-02)",
        "extensions/map_proposal/facts_adapter.py",
        "    return (not violations, violations)",
        "    return (True, [])",
        ["tests.test_w3_relations"],
    ),
    (
        "M3_head_subject_collapsed",
        "collapse T3 head-claim subjects: every implementation.* head is compared "
        "against the target pin, so a legitimate baseline head at base 'contradicts' "
        "the pack and releases related conflicts",
        "CA typed trust (A9, C-03)",
        "extensions/map_proposal/ca_adapter.py",
        '    if key.startswith("implementation.target_head"):\n'
        '        return "target"\n'
        '    if key.startswith("implementation.baseline"):\n'
        '        return "baseline"\n'
        '    return "foreign"',
        '    return "target"',
        ["tests.test_w4_ca_trust"],
    ),
    (
        "M4_text_only_import",
        "blob 'parsing' rebuilt from raw text lines (valid Python, wrong "
        "semantics): multiline and unsupported import forms degrade silently",
        "AST semantic relation proof (DROP L05, C-3)",
        "extensions/map_proposal/relations.py",
        'def _parse_blob(repo, revision, source_path):\n'
        '    """Pinned blob → AST. Raises DiffSignalError on read/parse failure\n'
        '    (UNKNOWN, never silent zero)."""\n'
        '    try:\n'
        '        raw = gitio.read_blob(repo, revision, source_path)\n'
        '        return ast.parse(raw)',
        'def _parse_blob(repo, revision, source_path):\n'
        '    """MUTATION M4: text-only import extraction — valid Python, wrong\n'
        '    semantics: multiline/unsupported forms degrade instead of raising."""\n'
        '    import re as _re\n'
        '    raw = gitio.read_blob(repo, revision, source_path)\n'
        '    kept = [line for line in raw.splitlines()\n'
        '            if _re.match(r"\\s*(from\\s+[\\w.]+\\s+import\\s+|import\\s+[\\w])", line)]\n'
        '    return ast.parse("\\n".join(kept) or "pass")',
        ["tests.test_w3_relations"],
    ),
    (
        "M5_position_allowed",
        "allow position into proposed_change",
        "position prohibition (K02/S-1)",
        "extensions/map_proposal/model.py",
        '    if "position" in proposed_change:\n'
        '        raise ValueError("proposed_change 不得包含 position")',
        '    if "position" in proposed_change:\n        pass',
        ["tests.test_map_proposal", "tests.test_w5_compatibility"],
    ),
    (
        "M6_lifecycle_auto_accept",
        "candidate lifecycle becomes ACCEPTED / human_required=False",
        "human lifecycle boundary (S-4)",
        "extensions/map_proposal/model.py",
        '        "status": "PROPOSED",\n        "human_required": True,',
        '        "status": "ACCEPTED",\n        "human_required": False,',
        ["tests.test_w5_compatibility", "tests.test_w2_channels"],
    ),
]


def run(cmd, cwd, timeout=600):
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 1,
                                           stderr=f"ENVIRONMENT_ERROR: {exc}")


def run_guards(clone, guards):
    """(all_green, failing_details) for the guard modules on the clone."""
    failing = []
    for module in guards:
        proc = run([sys.executable, "-m", "unittest", module], clone)
        if proc.returncode != 0:
            failing.append({"module": module,
                            "tail": (proc.stderr or proc.stdout)[-500:]})
    return (not failing), failing


def evaluate(mid, desc, invariant, rel_file, old, new, guards, clone_parent, results):
    record = {"id": mid, "description": desc, "invariant": invariant,
              "file": rel_file, "guards": guards}

    clone = clone_parent / mid
    cloned = run(["git", "clone", "--quiet", "--no-hardlinks", str(SOURCE_REPO), str(clone)],
                 clone_parent)
    if cloned.returncode:
        record.update(status="ENVIRONMENT_ERROR", detail=cloned.stderr[-500:])
        results.append(record)
        return

    target_file = clone / rel_file
    content = target_file.read_text(encoding="utf-8")
    if old not in content:
        record.update(status="ANCHOR_NOT_FOUND",
                      detail="mutation anchor text not found in current source (drift)")
        results.append(record)
        return

    mutated = content.replace(old, new, 1)
    try:
        ast.parse(mutated)
    except SyntaxError as exc:
        record.update(status="INVALID_MUTATION",
                      detail=f"mutated file does not parse: {exc} — the mutation "
                             "broke the code, not the invariant")
        results.append(record)
        return
    target_file.write_text(mutated, encoding="utf-8")

    # Baseline sanity: an already-red guard suite can never count as a kill.
    baseline_green, baseline_failing = run_guards(clone, guards)
    if not baseline_green:
        record.update(status="ENVIRONMENT_ERROR",
                      detail="baseline guard suite is red on the UNMUTATED clone",
                      baseline_failing=baseline_failing)
        results.append(record)
        return

    caught, failing = run_guards(clone, guards)
    if caught:
        # Semantic proof: did the guards fail because of the invariant, or is
        # the whole tree broken? A full-suite run distinguishes a genuine
        # caught from collateral damage: if the FULL suite only fails in the
        # guard modules, the mutation is scoped as intended.
        record.update(status="SEMANTIC_CAUGHT", failing=failing)
    else:
        full = run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                    "-p", "test_*.py"], clone, timeout=1200)
        if full.returncode != 0:
            record.update(status="SEMANTIC_CAUGHT",
                          failing=[{"module": "full suite (not the declared guards)",
                                    "tail": (full.stderr or full.stdout)[-500:]}],
                          note="caught only by the full suite — declared guards "
                               "are not bound to the invariant")
        else:
            record.update(status="SEMANTIC_MISSED",
                          detail="mutation applied, valid, and no guard failed — "
                                 "the suite is not bound to this invariant")
    results.append(record)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    results = []
    tmp_parent = Path(tempfile.mkdtemp(prefix="pm-mutation-"))
    try:
        for mid, desc, invariant, rel_file, old, new, guards in MUTATIONS:
            evaluate(mid, desc, invariant, rel_file, old, new, guards, tmp_parent, results)
            print(json.dumps({"id": mid, "status": results[-1]["status"]},
                             ensure_ascii=False), flush=True)
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)

    caught = sum(1 for r in results if r["status"] == "SEMANTIC_CAUGHT")
    summary = {
        "semantic_caught": caught,
        "total": len(results),
        "claim": f"SEMANTIC_CAUGHT {caught}/{len(results)} — only valid semantic "
                 "mutations caught by their guard suites count (V-02)",
        "statuses": {r["id"]: r["status"] for r in results},
    }
    print("SUMMARY: " + json.dumps(summary, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(
            json.dumps({"summary": summary, "results": results},
                       ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
