# -*- coding: utf-8 -*-
"""Independent import-relation channel (R03, W3).

Signal source is the pinned diff; the *proof* is always an AST walk of the
pinned blobs (DROP L05: a regex on patch text is only a candidate-signal
extractor — docstring/comment import text never becomes a relation, a parse
failure never counts as "zero imports"). Declaration-channel verdicts never
gate this channel (F05): "declarations unchanged" does not mean "no import
signal" (X01/X11).

Removal proof domain is the whole map-node evidence domain (R03): a relation
removal candidate requires an existing map edge and ALL .py files of the
source node's evidence domain free of imports into the target domain at
target, with at least one such import at base (S03, X12 multi-source).
"""
from __future__ import annotations

import ast
import posixpath
import re

from extensions.map_proposal import gitio
from extensions.map_proposal.analysis import diff_evidence, map_node_evidence
from extensions.map_proposal.facts_adapter import path_eligibility
from extensions.map_proposal.model import make_evidence

_ADDED_STATIC = re.compile(r"^\+\s*(?:from\s+([\w.]+)\s+import\s+(.+)|import\s+([\w.,\s]+))")
_ADDED_DYNAMIC = re.compile(r"^\+\s*.*(?:importlib\.import_module|__import__)\s*\(")
_REMOVED_STATIC = re.compile(r"^-\s*(?:from\s+([\w.]+)\s+import\s+(.+)|import\s+([\w.,\s]+))")


def _modules(module, names):
    """Candidate module strings referenced by one import statement."""
    if module is not None:
        return [module]
    return [n.strip().split(" as ")[0].strip() for n in names.split(",") if n.strip()]


def import_signals(repo, base_revision, target_revision, changed_py_paths):
    """Candidate import events from the pinned patch (regex = candidates only)."""
    signals = {"added": [], "removed": [], "dynamic": []}
    if not changed_py_paths:
        return signals
    raw = gitio.diff_patches(repo, base_revision, target_revision, changed_py_paths)
    path = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("--- ") or path is None:
            continue
        added = _ADDED_STATIC.match(line)
        if added:
            module, from_names = added.group(1), added.group(2)
            plain_names = added.group(3) if module is None else None
            for module_name in _modules(module, from_names or plain_names or ""):
                signals["added"].append({"path": path, "module": module_name,
                                         "line": line.lstrip("+- ").strip()[:200]})
            continue
        if _ADDED_DYNAMIC.match(line):
            signals["dynamic"].append({"path": path, "line": line.lstrip("+- ").strip()[:200]})
            continue
        removed = _REMOVED_STATIC.match(line)
        if removed:
            module, from_names = removed.group(1), removed.group(2)
            plain_names = removed.group(3) if module is None else None
            for module_name in _modules(module, from_names or plain_names or ""):
                signals["removed"].append({"path": path, "module": module_name,
                                           "line": line.lstrip("+- ").strip()[:200]})
    return signals


def resolve_module(module, source_path, known_paths):
    """Module string → repo-relative path among known_paths. Absolute forms
    resolve directly; relative import targets resolve against the source
    file's package directory."""
    if not module:
        return None
    if module.startswith("."):
        depth = len(module) - len(module.lstrip("."))
        rest = module.lstrip(".").replace(".", "/")
        base_dir = posixpath.dirname(source_path)
        for _ in range(depth - 1):
            base_dir = posixpath.dirname(base_dir)
        base = posixpath.join(base_dir, rest) if rest else base_dir
    else:
        base = module.replace(".", "/")
    for candidate in (base + ".py", posixpath.join(base, "__init__.py")):
        if candidate in known_paths:
            return candidate
    return None


def imported_paths(repo, revision, source_path):
    """All import targets (resolved among repo paths is the caller's job) —
    returns the set of dotted module strings actually imported, via AST.
    Raises DiffSignalError on read/parse failure (never "zero")."""
    try:
        raw = gitio.read_blob(repo, revision, source_path)
        tree = ast.parse(raw)
    except (gitio.DiffSignalError, SyntaxError, ValueError) as exc:
        raise gitio.DiffSignalError(f"cannot verify imports of {source_path}@{revision[:8]}: "
                                    f"{type(exc).__name__}") from exc
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0) + (node.module or "")
            modules.add(prefix)
            if node.module:
                for alias in node.names:
                    modules.add(f"{node.module}.{alias.name}")
    return modules


def imports_target(repo, revision, source_path, module, target_path, known_paths):
    """True when source_path@revision actually (AST) imports a module that
    resolves to target_path. Raises DiffSignalError when the blob cannot be
    read or parsed."""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        if candidate.lstrip(".") != module.lstrip("."):
            continue
        if resolve_module(candidate.lstrip("."), source_path, known_paths) == target_path:
            return True
    return False


def handle_relations(repo, base, target, indexes, facts, known_paths, relation_paths,
                     proposals, unresolved, limits):
    try:
        signals = import_signals(repo, base, target, relation_paths)
    except gitio.DiffSignalError as exc:
        limits.append(f"import signal extraction failed: {exc}")
        return

    # Churn guard: the same (file, module) gaining and losing an import in one
    # diff is reformatting, not a relation change (X13).
    added_keys = {(s["path"], s["module"]) for s in signals["added"]}
    removed_keys = {(s["path"], s["module"]) for s in signals["removed"]}
    churn = added_keys & removed_keys
    if churn:
        limits.append("import churn suppressed (same module added and removed): "
                      + ", ".join(sorted(f"{p}:{m}" for p, m in churn)))
    signals["added"] = [s for s in signals["added"] if (s["path"], s["module"]) not in churn]
    signals["removed"] = [s for s in signals["removed"] if (s["path"], s["module"]) not in churn]

    for signal in signals["dynamic"]:
        if path_eligibility(signal["path"], facts) != "skipped":
            unresolved.append(
                {
                    "subject": signal["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, signal["path"],
                                               f"dynamic import: {signal['line']}")],
                    "note": "动态/字符串构造 import：依赖信号不足，不足以建立关系候选",
                }
            )

    emitted_pairs = set()
    for signal in signals["added"]:
        target_path = resolve_module(signal["module"], signal["path"], known_paths)
        if target_path is None:
            continue
        if path_eligibility(signal["path"], facts) == "skipped" or \
                path_eligibility(target_path, facts) == "skipped":
            continue
        source_owners = indexes["node_by_path"].get(signal["path"], [])
        target_owners = indexes["node_by_path"].get(target_path, [])
        if not source_owners or not target_owners or set(source_owners) == set(target_owners):
            continue
        # AST proof on the pinned target blob (docstring text never passes).
        try:
            if not imports_target(repo, target, signal["path"], signal["module"],
                                  target_path, known_paths):
                continue
        except gitio.DiffSignalError as exc:
            limits.append(f"import verification unavailable: {exc}")
            unresolved.append(
                {
                    "subject": signal["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, signal["path"], "import signal unverified")],
                    "note": "import 信号无法用 AST 证实（读取/解析失败），进入 UNKNOWN",
                }
            )
            continue
        pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
        if pair in emitted_pairs:
            continue
        emitted_pairs.add(pair)
        uncertainty, confidence = [], "low"
        if len(source_owners) > 1 or len(target_owners) > 1:
            uncertainty.append("multiple candidate nodes on this import edge")
        else:
            confidence = "medium"
        proposals.append(
            {
                "kind": "RELATION_ADD",
                "subject": f"{source_owners[0]}->{target_owners[0]}",
                "node_ids": None,
                "proposed_change": {
                    "from": source_owners[0],
                    "to": target_owners[0],
                    "label": f"import 依赖(候选): {signal['path']} -> {target_path}",
                },
                "rationale": "跨节点证据域新增实际 import（AST 证实）；方向与语义需人工确认",
                "evidence": [
                    diff_evidence(target, signal["path"], f"import added: {signal['line']}"),
                    diff_evidence(target, target_path, f"imported by {signal['path']}"),
                    map_node_evidence(source_owners[0], f"covers {signal['path']}"),
                    map_node_evidence(target_owners[0], f"covers {target_path}"),
                ],
                "confidence": confidence,
                "uncertainty": uncertainty,
            }
        )

    for signal in signals["removed"]:
        target_path = resolve_module(signal["module"], signal["path"], known_paths)
        if target_path is None:
            continue
        if path_eligibility(signal["path"], facts) == "skipped" or \
                path_eligibility(target_path, facts) == "skipped":
            continue
        source_owners = indexes["node_by_path"].get(signal["path"], [])
        target_owners = indexes["node_by_path"].get(target_path, [])
        if not source_owners or not target_owners or set(source_owners) == set(target_owners):
            continue
        # Removal needs an existing map edge between the two domains (R03).
        edge_exists = any(
            (source_owner, target_owner) in indexes["edge_set"]
            for source_owner in source_owners
            for target_owner in target_owners
        )
        if not edge_exists:
            continue
        pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
        if pair in emitted_pairs:
            continue
        verdict = _domain_import_gone(repo, base, target, indexes, signal["path"],
                                      source_owners, target_path, known_paths, limits)
        if verdict != "gone":
            continue
        emitted_pairs.add(pair)
        proposals.append(
            {
                "kind": "RELATION_REMOVE_CANDIDATE",
                "subject": f"{source_owners[0]}->{target_owners[0]}",
                "node_ids": None,
                "proposed_change": {
                    "from": source_owners[0],
                    "to": target_owners[0],
                    "label": f"import 移除(候选): {signal['path']} -> {target_path}",
                },
                "rationale": "源节点证据域内全部 .py 文件对目标域的静态 import 已消失（AST 证实）；"
                             "是否意味架构关系消失由人判断",
                "evidence": [
                    diff_evidence(base, signal["path"], f"import present at base: {signal['line']}"),
                    diff_evidence(target, signal["path"], "import removed at target"),
                    map_node_evidence(source_owners[0], f"covers {signal['path']}"),
                    map_node_evidence(target_owners[0], f"covers {target_path}"),
                ],
                "confidence": "low",
                "uncertainty": [],
            }
        )


def _domain_import_gone(repo, base, target, indexes, signal_path, source_owners,
                        target_path, known_paths, limits):
    """Removal proof over the FULL source node evidence domain: every .py
    file's imports into target_path must exist at base (somewhere in the
    domain) and be gone at target everywhere. Any read/parse failure →
    'unknown' (never treated as zero, DROP L05)."""
    domain_paths = []
    for owner in source_owners:
        for node in indexes["nodes"]:
            if node["id"] == owner:
                domain_paths.extend(p for p in node["evidence_paths"] if p.endswith(".py"))
    domain_paths = sorted(set(domain_paths))
    if signal_path not in domain_paths:
        domain_paths.append(signal_path)
    if not domain_paths:
        return "insufficient"

    had_import_at_base = False
    for path in domain_paths:
        try:
            at_base = _imports_target_loose(repo, base, path, target_path, known_paths)
            at_target = _imports_target_loose(repo, target, path, target_path, known_paths)
        except gitio.DiffSignalError as exc:
            limits.append(f"import removal proof unavailable: {exc}")
            return "unknown"
        if at_base:
            had_import_at_base = True
        if at_target:
            return "retained"
    return "gone" if had_import_at_base else "insufficient"


def _imports_target_loose(repo, revision, source_path, target_path, known_paths):
    """Does any AST import of source_path@revision resolve to target_path?"""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        absolute = candidate.lstrip(".")
        if resolve_module(absolute, source_path, known_paths) == target_path:
            return True
    return False
