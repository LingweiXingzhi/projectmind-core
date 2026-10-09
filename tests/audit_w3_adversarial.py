# -*- coding: utf-8 -*-
"""Adversarial probes for the W3 import-relation channel (audit task 9).
Cases were NOT designed with the implementation in view; results are recorded
as-is. Each case builds a real temp git repo and runs the convergence engine.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extensions.map_proposal import engine  # noqa: E402
from tests.test_w3_relations import build_repo, node  # noqa: E402

MAP2 = {
    "note": "m",
    "nodes": [
        node("na", ["pkg/a.py"]),
        node("nb", ["pkg/b.py"]),
    ],
    "edges": [{"from": "na", "to": "nb"}],
}
MAP_NOEDGE = {**MAP2, "edges": []}


def facts_for(target, paths):
    return {
        "revision": target,
        "files": [{"path": p, "entries": [{"name": "X", "kind": "class", "line": 1}]} for p in paths],
        "skipped": [],
    }


def run_case(name, base_files, target_files, map_data, extra_changed=None, skipped=None):
    repo, base, target, tmp = build_repo(base_files, target_files)
    try:
        changed = [{"path": "pkg/a.py", "status": "modified"}] + (extra_changed or [])
        request = {
            "base_revision": base,
            "target_revision": target,
            "changed_paths": changed,
            "code_facts": {**facts_for(target, ["pkg/a.py", "pkg/b.py"]),
                           "skipped": skipped or []},
            "current_map": map_data,
            "prior_decisions": [],
        }
        res = engine.suggest_map(repo, request)
        kinds = sorted({p["kind"] for p in res["proposals"]})
        unresolved = sorted({u["subject"] for u in res["unresolved"]})
        rel_limits = [l for l in res["limits"] if "import" in l or "churn" in l]
        print(json.dumps({"case": name, "kinds": kinds, "unresolved": unresolved,
                          "limits": rel_limits}, ensure_ascii=False))
    finally:
        tmp.cleanup()


B = "class B:\n    pass\n"
A = "class A:\n    pass\n"

print("== task 9: adversarial relation cases ==")
# 1 relative import: from . import b / from .b import B
run_case("1a relative from . import b",
         {"pkg/a.py": A, "pkg/b.py": B, "pkg/__init__.py": ""},
         {"pkg/a.py": A + "from . import b\n", "pkg/b.py": B, "pkg/__init__.py": ""},
         MAP2)
run_case("1b relative from .b import B",
         {"pkg/a.py": A, "pkg/b.py": B, "pkg/__init__.py": ""},
         {"pkg/a.py": A + "from .b import B\n", "pkg/b.py": B, "pkg/__init__.py": ""},
         MAP2)
# 2 aliased
run_case("2a import pkg.b as pb",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "import pkg.b as pb\n", "pkg/b.py": B},
         MAP2)
run_case("2b from pkg.b import B as BB",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "from pkg.b import B as BB\n", "pkg/b.py": B},
         MAP2)
# 3 from pkg import b (submodule via from)
run_case("3 from pkg import b",
         {"pkg/a.py": A, "pkg/b.py": B, "pkg/__init__.py": ""},
         {"pkg/a.py": A + "from pkg import b\n", "pkg/b.py": B, "pkg/__init__.py": ""},
         MAP2)
# 4 multiline parenthesized import
run_case("4 multiline import (pkg.b,)",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "import (\n    pkg.b,\n)\n", "pkg/b.py": B},
         MAP2)
# 5 target is package __init__
run_case("5 import pkg (target __init__)",
         {"pkg/a.py": A, "pkg/__init__.py": ""},
         {"pkg/a.py": A + "import pkg\n", "pkg/__init__.py": ""},
         {"note": "m", "nodes": [node("na", ["pkg/a.py"]), node("npkg", ["pkg/__init__.py"])],
          "edges": [{"from": "na", "to": "npkg"}]})
# 6 two sources same relation (a.py and a2.py both add import na->nb)
run_case("6 two sources same relation",
         {"pkg/a.py": A, "pkg/a2.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "from pkg.b import B\n", "pkg/a2.py": A + "from pkg.b import B\n",
          "pkg/b.py": B},
         {"note": "m",
          "nodes": [node("na", ["pkg/a.py", "pkg/a2.py"]), node("nb", ["pkg/b.py"])],
          "edges": [{"from": "na", "to": "nb"}]})
# 7 one removes, another remains (multi-source residual)
run_case("7 one removes another remains",
         {"pkg/a.py": A + "from pkg.b import B\n", "pkg/a2.py": A + "from pkg.b import B\n",
          "pkg/b.py": B},
         {"pkg/a.py": A, "pkg/a2.py": A + "from pkg.b import B\n", "pkg/b.py": B},
         {"note": "m",
          "nodes": [node("na", ["pkg/a.py", "pkg/a2.py"]), node("nb", ["pkg/b.py"])],
          "edges": [{"from": "na", "to": "nb"}]})
# 8 syntax error in target source
run_case("8 syntax error target",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "from pkg.b import B\n def broken(:\n", "pkg/b.py": B},
         MAP2)
# 9 dynamic import
run_case("9 dynamic import",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "import importlib\nimportlib.import_module('pkg.b')\n", "pkg/b.py": B},
         MAP2)
# 10 import text inside plain string literal
run_case("10 string literal import text",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + 'X = "import pkg.b"\n', "pkg/b.py": B},
         MAP2)
# 11 docstring
run_case("11 docstring import text",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": '"""\nimport pkg.b\n"""\n' + A, "pkg/b.py": B},
         MAP2)
# 12 comment
run_case("12 commented import",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a.py": A + "# import pkg.b\n", "pkg/b.py": B},
         MAP2)
# 13 renamed file + relation change (renamed source keeps/changes import)
run_case("13 renamed source + import add",
         {"pkg/a.py": A, "pkg/b.py": B},
         {"pkg/a2.py": A + "from pkg.b import B\n", "pkg/b.py": B},
         MAP2,
         extra_changed=[{"path": "pkg/a2.py", "status": "renamed", "old_path": "pkg/a.py"}])
# 14 skipped source + normal source simultaneously
run_case("14 skipped + normal source",
         {"pkg/a.py": A + "from pkg.b import B\n", "pkg/a2.py": A, "pkg/b.py": B},
         {"pkg/a.py": A, "pkg/a2.py": A + "from pkg.b import B\n", "pkg/b.py": B},
         {"note": "m",
          "nodes": [node("na", ["pkg/a.py", "pkg/a2.py"]), node("nb", ["pkg/b.py"])],
          "edges": [{"from": "na", "to": "nb"}]},
         skipped=[{"path": "pkg/a.py", "reason": "syntax"}])
