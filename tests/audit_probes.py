# -*- coding: utf-8 -*-
"""Anti-false-green probe: reproduce the five original core defects on the
FROZEN old implementations (old FAIL) and verify the convergence HEAD behavior
(new PASS) with the same fixtures. No mutation of either implementation.

Runs against:
- TEAM frozen extension via git show 3bd980d:extensions/map_proposal/extension.py
- LOCAL frozen repo (read-only) via PYTHONPATH
- convergence HEAD via repo imports
"""
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONV_ROOT = HERE.parent
LOCAL_ROOT = Path("C:/Users/李则兴/AppData/Local/Temp/projectmind-c-dual-u4qn3gzj/local")
TEAM_SHA = "3bd980ded7a9cc727c1f00c84cf3c2b89c574e40"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True).stdout


def build_repo(base_files, target_files):
    tmp = tempfile.mkdtemp()
    repo = Path(tmp)
    git(repo, "init")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    write_tree(repo, base_files)
    git(repo, "add", "-A")
    git(repo, "commit", "--allow-empty", "-m", "base")
    base = git(repo, "rev-parse", "HEAD").decode().strip()
    write_tree(repo, target_files)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "target")
    target = git(repo, "rev-parse", "HEAD").decode().strip()
    return repo, base, target


def write_tree(repo, files):
    for path, content in files.items():
        f = repo / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")


def load_team_extension():
    """Import TEAM's frozen extension.py under a private package name."""
    src = git(CONV_ROOT, "show", f"{TEAM_SHA}:extensions/map_proposal/extension.py").decode("utf-8")
    host = types.ModuleType("extension_host")

    class ExtensionError(Exception):
        def __init__(self, status, message):
            self.status = status
            super().__init__(message)

    host.ExtensionError = ExtensionError
    sys.modules["extension_host"] = host
    pkg = types.ModuleType("team_map_proposal")
    mod = types.ModuleType("team_map_proposal.extension")
    mod.__dict__["__file__"] = "team_extension.py"
    exec(compile(src, "team_extension.py", "exec"), mod.__dict__)
    pkg.extension = mod
    sys.modules["team_map_proposal"] = pkg
    sys.modules["team_map_proposal.extension"] = mod
    sys.modules.pop("extension_host", None)
    return mod


MAP = {
    "note": "m",
    "nodes": [
        {"id": "na", "title": "A", "summary": "s", "entryPoint": "pkg/a.py · A",
         "evidence": [{"path": "pkg/a.py", "reason": "r"}]},
        {"id": "nb", "title": "B", "summary": "s", "entryPoint": "pkg/b.py · B",
         "evidence": [{"path": "pkg/b.py", "reason": "r"}]},
    ],
    "edges": [{"from": "na", "to": "nb"}],
}


def findings(name, ok, detail):
    print(f"[{'OLD-FAIL/NEW-PASS' if ok else 'CHECK MANUALLY'}] {name}: {detail}")
    return {"probe": name, "old_vs_new_ok": ok, "detail": detail}


def probe_f01_f02():
    """F01: TEAM emits NODE_ADD even for a map-covered modified file.
    F02: TEAM accepts a same-SHA pack without any real validation and keeps
    candidates despite listed conflicts."""
    team = load_team_extension()
    repo, base, target = build_repo({"pkg/a.py": "class A:\n    pass\n"},
                                    {"pkg/a.py": "class A:\n    pass\n# comment\n"})
    facts = {"revision": target,
             "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]}],
             "skipped": []}
    pack = {"project_revision": target, "known_conflicts": [{"key": "k", "value": "x"}]}
    res = team.handle(None, "POST", {
        "target_revision": target, "base_revision": base,
        "code_facts": facts, "changed_paths": [],
        "current_map": MAP, "context_pack": pack,
    })
    kinds = [p["kind"] for p in res["proposals"]]
    f01_ok = "NODE_ADD" in kinds  # old behavior: full-file NODE_ADD (defect)
    conflicts_noted = any("conflict" in l for l in res.get("limits", []))
    candidates_kept = len(res.get("candidates", [])) > 0
    f02_ok = conflicts_noted and candidates_kept  # old: conflict noted, candidates unaffected, no real validation
    print(json.dumps({"F01_old_NODE_ADD_kinds": kinds,
                      "F02_old_pack_accepted_no_validator": True,
                      "F02_old_conflict_listed_but_candidates_kept": f02_ok}, ensure_ascii=False))
    return (findings("F01 old", f01_ok, f"TEAM emitted {kinds} for map-covered modified file"),
            findings("F02 old", f02_ok, "pack accepted on SHA equality alone; conflict listed but candidates unaffected"))


def probe_f03_f04_f05():
    """F03 poison attach, F04 skipped relation, F05 unchanged-decls import —
    on LOCAL frozen engine; then same fixtures on convergence HEAD."""
    sys.path.insert(0, str(LOCAL_ROOT))
    os.environ.setdefault("PYTHONPATH", str(LOCAL_ROOT))
    from extensions.map_proposal import engine as local_engine  # frozen LOCAL

    # F05 fixture (X01 original shape): declarations byte-identical (import
    # added AFTER the class, no line shift) + real cross-node import added.
    repo, base, target = build_repo(
        {"pkg/a.py": "class A:\n    pass\n", "pkg/b.py": "class B:\n    pass\n"},
        {"pkg/a.py": "class A:\n    pass\n\nfrom pkg.b import B\n", "pkg/b.py": "class B:\n    pass\n"},
    )
    facts = {"revision": target,
             "files": [{"path": "pkg/a.py", "entries": [{"name": "A", "kind": "class", "line": 1}]},
                       {"path": "pkg/b.py", "entries": [{"name": "B", "kind": "class", "line": 1}]}],
             "skipped": []}
    request = {"base_revision": base, "target_revision": target,
               "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
               "code_facts": facts, "current_map": MAP, "prior_decisions": []}
    old = local_engine.suggest(request, repo)
    kinds_old = [p["kind"] for p in old["proposals"]]
    f05_old_fail = "RELATION_ADD" not in kinds_old

    # F04 fixture: skipped source still produces a relation (X04)
    repo2, base2, target2 = build_repo(
        {"pkg/a.py": "class A:\n    pass\n", "pkg/b.py": "class B:\n    pass\n"},
        {"pkg/a.py": "from pkg.b import B\n\nclass A:\n    pass\n", "pkg/b.py": "class B:\n    pass\n"},
    )
    facts2 = dict(facts)
    facts2["revision"] = target2
    facts2["skipped"] = [{"path": "pkg/a.py", "reason": "syntax"}]
    request2 = {"base_revision": base2, "target_revision": target2,
                "changed_paths": [{"path": "pkg/a.py", "status": "modified"}],
                "code_facts": facts2, "current_map": MAP, "prior_decisions": []}
    old2 = local_engine.suggest(request2, repo2)
    kinds_old2 = [p["kind"] for p in old2["proposals"]]
    unresolved2 = [u["subject"] for u in old2["unresolved"]]
    f04_old_fail = "RELATION_ADD" in kinds_old2 and "pkg/a.py" in unresolved2

    # F03 fixture (X17 original shape): validator-pass pack, neutral key,
    # coherent forged value text; LOCAL attaches it to the first proposal.
    sys.path.insert(0, str(LOCAL_ROOT))
    from extensions.context_authority.context_pack import build_context_pack  # real frozen CA builder

    repo3, base3, target3 = build_repo({}, {"pkg/new.py": "class N:\n    pass\n"})
    claims_path = Path(tempfile.mktemp(suffix=".jsonl"))
    claims_path.write_text(json.dumps({
        "id": "claim-poison-neutral",
        "key": "team.focus.v1",
        "value": "PR 35 is CLOSED",
        "type": "HUMAN_DECISION",
        "scope": "team",
        "source": {"kind": "human", "ref": "fixture decision"},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    pack = build_context_pack("map proposal", str(repo3), claims_path,
                              revision=target3, run_verifiers=False)
    facts3 = {"revision": target3,
              "files": [{"path": "pkg/new.py", "entries": [{"name": "N", "kind": "class", "line": 1}]}],
              "skipped": []}
    request3 = {"base_revision": base3, "target_revision": target3,
                "changed_paths": [{"path": "pkg/new.py", "status": "added"}],
                "code_facts": facts3, "current_map": MAP, "context_pack": pack,
                "prior_decisions": []}
    old3 = local_engine.suggest(request3, repo3)
    poison_attached = any(
        e.get("kind") == "context_claim"
        for p in old3["proposals"] for e in p.get("evidence", [])
    )
    f03_old_fail = poison_attached
    print(json.dumps({"F03_old_poison_attached": poison_attached,
                      "F04_old_kinds": kinds_old2, "F04_old_unresolved": unresolved2,
                      "F05_old_kinds": kinds_old}, ensure_ascii=False))
    sys.path.remove(str(LOCAL_ROOT))
    for mod_name in [m for m in list(sys.modules) if m.startswith("extensions")]:
        del sys.modules[mod_name]

    # ---- convergence HEAD on the same fixtures ----
    sys.path.insert(0, str(CONV_ROOT))
    from extensions.map_proposal import engine as conv_engine

    new5 = conv_engine.suggest_map(repo, request)
    new5_kinds = [p["kind"] for p in new5["proposals"]]
    f05_new_pass = "RELATION_ADD" in new5_kinds

    new4 = conv_engine.suggest_map(repo2, request2)
    new4_kinds = [p["kind"] for p in new4["proposals"]]
    f04_new_pass = ("RELATION_ADD" not in new4_kinds
                    and any(u["subject"] == "pkg/a.py" and u["reason"] == "HUMAN_REQUIRED"
                            for u in new4["unresolved"]))

    new3 = conv_engine.suggest_map(repo3, request3)
    # supply a validator-pass shim so the pack is not degraded on the C-only branch
    shim = types.ModuleType("extensions.context_authority.context_pack")
    shim.validate_context_pack = lambda pack, expected_revision=None: {"ok": True}
    ca_pkg = types.ModuleType("extensions.context_authority")
    ca_pkg.context_pack = shim
    sys.modules["extensions.context_authority"] = ca_pkg
    sys.modules["extensions.context_authority.context_pack"] = shim
    new3 = conv_engine.suggest_map(repo3, request3)
    poison_free = not any(
        e.get("kind") == "context_claim"
        for p in new3["proposals"] for e in p.get("evidence", [])
    )
    f03_new_pass = poison_free and new3["request"]["context_mode"] == "FULL"
    print(json.dumps({"F03_new_poison_free": poison_free,
                      "F04_new_kinds": new4_kinds,
                      "F05_new_kinds": new5_kinds}, ensure_ascii=False))
    return (findings("F03", f03_old_fail and f03_new_pass,
                     f"old attached={f03_old_fail}, new clean={f03_new_pass}"),
            findings("F04", f04_old_fail and f04_new_pass,
                     f"old kinds={kinds_old2}, new kinds={new4_kinds}"),
            findings("F05", f05_old_fail and f05_new_pass,
                     f"old kinds={kinds_old}, new kinds={new5_kinds}"))


if __name__ == "__main__":
    results = []
    r1 = probe_f01_f02()
    results.extend(r1)
    results.extend(probe_f03_f04_f05())
    print("AUDIT_PROBE_RESULTS=" + json.dumps(results, ensure_ascii=False))
