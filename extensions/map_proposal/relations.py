# -*- coding: utf-8 -*-
"""Independent import-relation channel (R03, W3).

Signal AND proof are the same artifact: a per-file AST diff of the pinned
base blob against the pinned target blob. The diff patch is not parsed at
all — a regex on patch text was only ever a candidate extractor (DROP L05)
and its line-based form silently missed relative imports, from-submodule
imports and multiline imports (adversarial cases 1a/1b/3/4, 2026-10-04).
Blob read/parse failure raises DiffSignalError → UNKNOWN/unresolved, never
"zero imports" (C-3). Declaration-channel verdicts never gate this channel
(F05): "declarations unchanged" does not mean "no import signal" (X01/X11).

Resolution is a heuristic (dotted path ∩ known repo paths); modules that
resolve outside the repo (stdlib/site-packages) are not architecture
relations. Known resolution limits (namespace packages, src-layout) mean an
unresolved repo-internal import can stay invisible — recorded limit, does
not fabricate a relation.

Removal proof domain is the whole map-node evidence domain (R03): a relation
removal candidate requires an existing map edge and ALL .py files of the
source node's evidence domain free of imports into the target domain at
target, with at least one such import at base (S03, X12 multi-source).

Known edge: a rewrite between from-import shapes can add/drop the bare
package-prefix candidate (e.g. `from . import b` → `from .b import B`), so
the package __init__ dependency can look removed although Python still
executes the parent package implicitly. Bounded: removal candidates need an
existing map edge plus the full domain proof, and stay low-confidence
human-review items.
"""
from __future__ import annotations

import ast
import posixpath

from extensions.map_proposal import gitio
from extensions.map_proposal.analysis import diff_evidence, map_node_evidence
from extensions.map_proposal.facts_adapter import path_eligibility
from extensions.map_proposal.model import make_evidence


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


def _parse_blob(repo, revision, source_path):
    """Pinned blob → AST. Raises DiffSignalError on read/parse failure
    (UNKNOWN, never silent zero)."""
    try:
        raw = gitio.read_blob(repo, revision, source_path)
        return ast.parse(raw)
    except (gitio.DiffSignalError, SyntaxError, ValueError) as exc:
        raise gitio.DiffSignalError(f"cannot verify imports of {source_path}@{revision[:8]}: "
                                    f"{type(exc).__name__}") from exc


def _scan_imports(tree):
    """(static module strings, dynamic import tags) from one parsed module.

    ImportFrom contributes its package prefix AND each prefix-qualified alias
    so `from pkg import b` (b a submodule) and `from . import b` carry the
    submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
    Aliased and parenthesized/multiline forms are AST-native. Docstrings,
    comments and string literals never appear here."""
    static, dynamic = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0) + (node.module or "")
            if prefix:
                static.add(prefix)
            for alias in node.names:
                if not prefix:
                    static.add(alias.name)
                elif prefix.endswith("."):
                    static.add(prefix + alias.name)
                else:
                    static.add(f"{prefix}.{alias.name}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "__import__":
                dynamic.add("__import__")
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                dynamic.add("importlib.import_module")
    return static, dynamic


def imported_paths(repo, revision, source_path):
    """Dotted module strings actually imported by source_path@revision (AST).
    Raises DiffSignalError on read/parse failure."""
    static, _ = _scan_imports(_parse_blob(repo, revision, source_path))
    return static


def _resolved_imports(repo, revision, source_path, known_paths):
    """resolved repo path → module strings that reach it. Modules resolving
    outside known repo paths are external dependencies, not relations."""
    resolved = {}
    for module in sorted(imported_paths(repo, revision, source_path)):
        target_path = resolve_module(module, source_path, known_paths)
        if target_path:
            resolved.setdefault(target_path, []).append(module)
    return resolved


def _file_relation_events(repo, base, target, change, known_paths):
    """AST-diff one changed .py file's import sets: pinned base blob vs
    pinned target blob. `renamed` compares old_path@base with path@target;
    `added` has an empty base set; `modified` compares path@base. Raises
    DiffSignalError when a needed blob cannot be read or parsed."""
    path = change["path"]
    status = change["status"]
    base_ref = change.get("old_path") if status == "renamed" else None
    if base_ref is None and status == "modified":
        base_ref = path
    if base_ref:
        base_resolved = _resolved_imports(repo, base, base_ref, known_paths)
        base_dynamic = _scan_imports(_parse_blob(repo, base, base_ref))[1]
    else:
        base_resolved, base_dynamic = {}, set()
    target_static, target_dynamic = _scan_imports(_parse_blob(repo, target, path))
    target_resolved = {}
    for module in sorted(target_static):
        resolved = resolve_module(module, path, known_paths)
        if resolved:
            target_resolved.setdefault(resolved, []).append(module)
    return {
        "path": path,
        "added": {p: mods for p, mods in target_resolved.items() if p not in base_resolved},
        "removed": {p: mods for p, mods in base_resolved.items() if p not in target_resolved},
        "dynamic": sorted(target_dynamic - base_dynamic),
    }


def handle_relations(repo, base, target, indexes, facts, known_paths, relation_changes,
                     proposals, unresolved, limits):
    events = []
    for change in sorted(relation_changes, key=lambda c: c["path"]):
        try:
            events.append(_file_relation_events(repo, base, target, change, known_paths))
        except gitio.DiffSignalError as exc:
            limits.append(f"import signal extraction unavailable: {exc}")
            unresolved.append(
                {
                    "subject": change["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, change["path"],
                                               "import signal unverified")],
                    "note": "import 信号无法用 AST 证实（读取/解析失败），进入 UNKNOWN",
                }
            )

    emitted_pairs = set()
    for event in events:
        source_path = event["path"]
        for target_path in sorted(event["added"]):
            if path_eligibility(target_path, facts) == "skipped":
                continue
            source_owners = indexes["node_by_path"].get(source_path, [])
            target_owners = indexes["node_by_path"].get(target_path, [])
            if not source_owners or not target_owners or set(source_owners) == set(target_owners):
                continue
            pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
            if pair in emitted_pairs:
                continue
            emitted_pairs.add(pair)
            modules = "、".join(sorted(event["added"][target_path]))
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
                        "label": f"import 依赖(候选): {source_path} -> {target_path}",
                    },
                    "rationale": "跨节点证据域新增实际 import（AST 证实）；方向与语义需人工确认",
                    "evidence": [
                        diff_evidence(target, source_path,
                                      f"import added (AST): {modules} -> {target_path}"),
                        diff_evidence(target, target_path, f"imported by {source_path}"),
                        map_node_evidence(source_owners[0], f"covers {source_path}"),
                        map_node_evidence(target_owners[0], f"covers {target_path}"),
                    ],
                    "confidence": confidence,
                    "uncertainty": uncertainty,
                }
            )

    for event in events:
        source_path = event["path"]
        for target_path in sorted(event["removed"]):
            if path_eligibility(target_path, facts) == "skipped":
                continue
            source_owners = indexes["node_by_path"].get(source_path, [])
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
            verdict = _domain_import_gone(repo, base, target, indexes, source_path,
                                          source_owners, target_path, known_paths, limits)
            if verdict != "gone":
                continue
            emitted_pairs.add(pair)
            modules = "、".join(sorted(event["removed"][target_path]))
            proposals.append(
                {
                    "kind": "RELATION_REMOVE_CANDIDATE",
                    "subject": f"{source_owners[0]}->{target_owners[0]}",
                    "node_ids": None,
                    "proposed_change": {
                        "from": source_owners[0],
                        "to": target_owners[0],
                        "label": f"import 移除(候选): {source_path} -> {target_path}",
                    },
                    "rationale": "源节点证据域内全部 .py 文件对目标域的静态 import 已消失（AST 证实）；"
                                 "是否意味架构关系消失由人判断",
                    "evidence": [
                        diff_evidence(base, source_path,
                                      f"import present at base (AST): {modules} -> {target_path}"),
                        diff_evidence(target, source_path, "import removed at target"),
                        map_node_evidence(source_owners[0], f"covers {source_path}"),
                        map_node_evidence(target_owners[0], f"covers {target_path}"),
                    ],
                    "confidence": "low",
                    "uncertainty": [],
                }
            )

    for event in events:
        for tag in event["dynamic"]:
            if path_eligibility(event["path"], facts) == "skipped":
                continue
            unresolved.append(
                {
                    "subject": event["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, event["path"],
                                               f"dynamic import: {tag}")],
                    "note": "动态/字符串构造 import：依赖信号不足，不足以建立关系候选",
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
    """Does any AST import of source_path@revision resolve to target_path?
    Relative candidates keep their leading dots so resolve_module anchors
    them to the source package."""
    imported = imported_paths(repo, revision, source_path)
    for candidate in imported:
        if resolve_module(candidate, source_path, known_paths) == target_path:
            return True
    return False
