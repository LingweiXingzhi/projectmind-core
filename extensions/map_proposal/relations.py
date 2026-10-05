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

Removal proof domain is BOTH endpoint map-node evidence domains (R03, C-01
fix): a relation removal candidate requires an existing map edge, at least
one import from the source node's evidence domain into ANY member of the
target node's evidence domain at base, and NO such import at target — the
proof is node-level, so a signal naming one target file never bounds the
proof domain (S03, X12 multi-source, C-01 multi-target residual).

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
from extensions.map_proposal.facts_adapter import domain_gate, path_eligibility
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


def _importlib_bindings(tree):
    """Local names bound to importlib.import_module by from-imports
    (C-06): `from importlib import import_module` and its aliased form
    previously produced NO dynamic signal at all — the direct call vanished
    silently. Only this module-scoped binding is tracked; cross-module
    rebinding stays an unexplained dynamic path (recorded as such)."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    bound.add(alias.asname or alias.name)
    return bound


def _scan_imports(tree):
    """(static module strings, dynamic import tags, plain-provenance strings)
    from one parsed module.

    ImportFrom contributes its package prefix AND each prefix-qualified alias
    so `from pkg import b` (b a submodule) and `from . import b` carry the
    submodule candidate; relative dots are preserved (adversarial 1a/1b/3).
    `plain` carries every string introduced OUTSIDE alias expansion (Import
    names and ImportFrom prefixes); a candidate that also has plain
    provenance must NOT be alias-downgraded, because the same string can
    arise from an explicit import in another statement (Codex round-2
    MEDIUM). Aliased and parenthesized/multiline forms are AST-native.
    Docstrings, comments and string literals never appear here.
    C-06: direct and aliased `import_module(...)` calls are dynamic signals,
    not silent absences."""
    static, dynamic, plain = set(), set(), set()
    importlib_names = _importlib_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.add(alias.name)
                plain.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0) + (node.module or "")
            if prefix:
                static.add(prefix)
                plain.add(prefix)
            for alias in node.names:
                if not prefix:
                    static.add(alias.name)
                    plain.add(alias.name)
                    continue
                candidate = prefix + alias.name if prefix.endswith(".") \
                    else f"{prefix}.{alias.name}"
                static.add(candidate)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and (func.id == "__import__" or func.id in importlib_names):
                dynamic.add(_dynamic_tag(
                    node, "__import__" if func.id == "__import__" else "importlib.import_module"))
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                dynamic.add(_dynamic_tag(node, "importlib.import_module"))
    return static, dynamic, plain


def _dynamic_tag(call_node, api):
    """Dynamic import tag includes the statically visible string target
    (Codex HIGH-2: only diffing API names made `__import__('pkg.b')` →
    `__import__('pkg.c')` a silent absence, violating C-3). Both the first
    positional and the `name=` keyword form are recognized; later positional
    args have different meanings per API and are never the module target
    (Codex round-3 LOW)."""
    candidates = list(call_node.args[:1])
    candidates.extend(kw.value for kw in call_node.keywords if kw.arg == "name")
    for arg in candidates:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
            return f"{api}:{arg.value}"
    return api


def imported_paths(repo, revision, source_path):
    """Dotted module strings actually imported by source_path@revision (AST).
    Raises DiffSignalError on read/parse failure."""
    static, _, _ = _scan_imports(_parse_blob(repo, revision, source_path))
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


def _repo_internal_unresolved(module, source_path, known_paths):
    """C-06: is an unresolvable module still repo-internal? A relative import
    that fails to resolve is repo-internal by construction; an absolute one
    is repo-internal when a known path ends with the module's path shape
    (src-layout: 'pkg.b' vs known 'src/pkg/b.py'). External/stdlib modules
    match nothing and stay out of architecture relations — recorded limit,
    never a fabricated relation."""
    if not module:
        return False
    if module.startswith("."):
        return True
    base = module.replace(".", "/")
    for candidate in (base + ".py", base + "/__init__.py"):
        suffix = "/" + candidate
        for known in known_paths:
            if known == candidate or known.endswith(suffix):
                return True
    return False


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
    target_static, target_dynamic, target_plain = _scan_imports(
        _parse_blob(repo, target, path))
    target_resolved = {}
    unresolved_internal = set()
    for module in sorted(target_static):
        resolved = resolve_module(module, path, known_paths)
        if resolved:
            target_resolved.setdefault(resolved, []).append(module)
        elif _repo_internal_unresolved(module, path, known_paths):
            # C-06: repo-internal imports the current resolver cannot explain
            # (src-layout, namespace packages) stay visible as UNKNOWN.
            unresolved_internal.add(module)
    added = {p: mods for p, mods in target_resolved.items() if p not in base_resolved}
    return {
        "path": path,
        "added": added,
        # Codex MEDIUM-4: a resolved target reached ONLY through from-import
        # alias expansion may actually be a package-__init__ attribute — the
        # proposal must carry that ambiguity, never medium confidence. A
        # candidate string with plain provenance (an Import name or an
        # ImportFrom prefix anywhere in the file) is NOT downgraded (Codex
        # round-2 MEDIUM: same string, different import forms).
        "added_from_derived": {
            p: all(m not in target_plain for m in mods)
            for p, mods in added.items()
        },
        "removed": {p: mods for p, mods in base_resolved.items() if p not in target_resolved},
        "dynamic": sorted(target_dynamic - base_dynamic),
        "unresolved_internal": sorted(unresolved_internal),
    }


def _gate_unresolved(unresolved, subject, target_revision, violations):
    """Visible HUMAN_REQUIRED for an evidence-domain eligibility violation
    (C-02): strong proposals never silently cancel on skipped/uncollected
    members — the gap surfaces for human decision instead."""
    details = []
    evidence = []
    for path, state, reason in violations[:6]:
        label = "B skipped" if state == "skipped" else "未被 B 收集"
        details.append(f"{path}（{label}" + (f": {reason}" if reason else "") + "）")
        evidence.append(
            {"kind": "code_fact_skipped" if state == "skipped" else "code_fact_missing",
             "revision": target_revision, "path": path})
    unresolved.append(
        {
            "subject": subject,
            "reason": "HUMAN_REQUIRED",
            "evidence": evidence,
            "note": "提案证据域成员的 B 事实资格不合格，不发布强候选（C-02 准入门）："
                    + "；".join(details),
        }
    )


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
    gated_pairs = set()
    proof_cache = {}
    for event in events:
        source_path = event["path"]
        for target_path in sorted(event["added"]):
            source_owners = indexes["node_by_path"].get(source_path, [])
            target_owners = indexes["node_by_path"].get(target_path, [])
            if not source_owners or not target_owners or set(source_owners) == set(target_owners):
                continue
            pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
            if pair in emitted_pairs or pair in gated_pairs:
                continue
            # C-02: centralized evidence-domain eligibility (A4/E-3) — a
            # strong node-level claim requires every member of BOTH endpoint
            # domains to be positively eligible in B facts (present, not
            # skipped, not merely uncollected). Violations surface as
            # HUMAN_REQUIRED, never as a silent cancel.
            gate_ok, gate_violations = domain_gate(
                _node_domain_paths(indexes, source_owners, source_path)
                + _node_domain_paths(indexes, target_owners, target_path), facts)
            if not gate_ok:
                gated_pairs.add(pair)
                _gate_unresolved(unresolved, f"{source_owners[0]}->{target_owners[0]}",
                                 target, gate_violations)
                continue
            emitted_pairs.add(pair)
            modules = "、".join(sorted(event["added"][target_path]))
            uncertainty = []
            multi_owner = len(source_owners) > 1 or len(target_owners) > 1
            if multi_owner:
                uncertainty.append("multiple candidate nodes on this import edge")
            if event["added_from_derived"].get(target_path):
                uncertainty.append(
                    "from-import 目标可能是包 __init__ 中的同名属性而非子模块，需人工确认")
                confidence = "low"
            else:
                confidence = "low" if multi_owner else "medium"
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
            if pair in emitted_pairs or pair in gated_pairs:
                continue
            # C-02: both endpoint domains must be B-eligible before the proof
            # reads them; a skipped member (e.g. over B's budget) or one B
            # never collected must not silently strengthen the proof.
            gate_ok, gate_violations = domain_gate(
                _node_domain_paths(indexes, source_owners, source_path)
                + _node_domain_paths(indexes, target_owners, target_path), facts)
            if not gate_ok:
                gated_pairs.add(pair)
                _gate_unresolved(unresolved, f"{source_owners[0]}->{target_owners[0]}",
                                 target, gate_violations)
                continue
            # C-01: the removal claim is node-level (source domain -> target
            # domain), so every target_path inside one target domain shares a
            # single verdict — compute the proof once per node pair.
            if pair in proof_cache:
                verdict, base_signals = proof_cache[pair]
            else:
                verdict, base_signals = _domain_import_gone(
                    repo, base, target, indexes, source_path, source_owners,
                    target_path, target_owners, known_paths, limits)
                proof_cache[pair] = (verdict, base_signals)
            if verdict != "gone":
                continue
            emitted_pairs.add(pair)
            evidence = [
                diff_evidence(target, source_path, "import removed at target"),
                map_node_evidence(source_owners[0], f"covers {source_path}"),
                map_node_evidence(target_owners[0], f"covers {target_path}"),
            ]
            for base_path, base_modules, base_target in base_signals[:4]:
                evidence.insert(0, diff_evidence(
                    base, base_path,
                    "import present at base (AST): "
                    + "、".join(base_modules) + " -> " + base_target))
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
                    "rationale": "源节点证据域内全部 .py 文件对目标节点证据域（全部成员）的"
                                 "静态 import 已消失（AST 证实）；是否意味架构关系消失由人判断",
                    "evidence": evidence,
                    "confidence": "low",
                    "uncertainty": [],
                }
            )

    for event in events:
        if event["unresolved_internal"]:
            # C-06: unexplained repo-internal imports surface as UNKNOWN —
            # the relation signal for this file is incomplete, never silently
            # absent.
            modules = "、".join(event["unresolved_internal"][:8])
            limits.append(f"import resolution incomplete in {event['path']} "
                          f"(src-layout/namespace/dynamic path): {modules}")
            unresolved.append(
                {
                    "subject": event["path"],
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [diff_evidence(target, event["path"],
                                               f"unresolved repo-internal imports: {modules}")],
                    "note": "存在无法用当前解释器解析的仓库内 import（src-layout／命名空间包等）；"
                            "关系信号不完整，进入 UNKNOWN（C-06）",
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


def _node_domain_paths(indexes, owners, signal_path):
    """Every .py evidence path of the given map nodes, plus the signal path
    itself (it stays in the proof domain even if map coverage drifts)."""
    domain = set()
    for owner in owners:
        for node in indexes["nodes"]:
            if node["id"] == owner:
                domain.update(p for p in node["evidence_paths"] if p.endswith(".py"))
    domain.add(signal_path)
    return sorted(domain)


def _domain_import_gone(repo, base, target, indexes, signal_path, source_owners,
                        target_path, target_owners, known_paths, limits):
    """C-01 removal proof over the FULL source node evidence domain AND the
    FULL target node evidence domain: the claim is the node-level relation
    source domain -> target domain, so 'gone' requires that at target NO file
    of the source domain imports ANY member of the target domain, while at
    base at least one such import existed (A6/R03). A single-file signal only
    triggers the proof; it never bounds the proof domain — the pre-C-01 proof
    checked only the one signal target file and wrongly released relations
    whose target domain kept other imported members (b.py gone, b2.py kept).
    Any read/parse failure -> ('unknown', []), never treated as zero
    (DROP L05).

    Returns (verdict, base_signals): verdict in {'gone', 'retained',
    'unknown', 'insufficient'}; base_signals lists
    (source_path, modules, target_path) importing the target domain at base,
    for proposal evidence."""
    source_domain = _node_domain_paths(indexes, source_owners, signal_path)
    target_domain = _node_domain_paths(indexes, target_owners, target_path)
    if not source_domain or not target_domain:
        return "insufficient", []

    target_domain_set = set(target_domain)
    had_import_at_base = False
    base_signals = []
    for path in source_domain:
        try:
            base_resolved = _resolved_imports(repo, base, path, known_paths)
            target_resolved = _resolved_imports(repo, target, path, known_paths)
        except gitio.DiffSignalError as exc:
            limits.append(f"import removal proof unavailable: {exc}")
            return "unknown", []
        if set(target_resolved) & target_domain_set:
            return "retained", []
        for target_file in sorted(set(base_resolved) & target_domain_set):
            base_signals.append(
                (path, sorted(base_resolved[target_file]), target_file))
            had_import_at_base = True
    if not had_import_at_base:
        return "insufficient", []
    return "gone", base_signals
