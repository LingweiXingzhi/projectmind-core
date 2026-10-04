# -*- coding: utf-8 -*-
"""C signal channels over the diff × map cross product (R01/R05, W2).

Channels are independent: the declaration channel's verdict on one file never
ends another channel's analysis of the same file (F05, DROP L03). Ported from
LOCAL engine.py @5058c54 with the convergence fixes:
- L09 dropped: fact evidence cites every top-level declaration structurally,
  no first-three truncation;
- L10 dropped: no first-class / first-symbol entry-point guessing — sole
  top-level class may be cited, otherwise entryPoint stays unset with
  uncertainty;
- L11 dropped: stale-map detection checks every node's evidence paths against
  the pinned target tree (and base tree for honest evidence), not just this
  round's removed set, and does not depend on B availability.
"""
from __future__ import annotations

from extensions.map_proposal import gitio
from extensions.map_proposal.model import (
    make_evidence,
    node_id_for_path,
    parse_entry_point,
)

TOP_LEVEL_KINDS = ("class", "function", "async_function")


def build_indexes(current_map):
    """P02 node/entry indexes over the validated map. Nodes whose entryPoint
    cannot be parsed are reported (not silently skipped) so the RESPONSIBILITY
    channel's inactivity is visible (R8/G-3)."""
    node_by_path = {}
    for node in current_map["nodes"]:
        for path in node["evidence_paths"]:
            node_by_path.setdefault(path, []).append(node["id"])
    entry_lookup = {}
    unparseable_entry_points = []
    for node in current_map["nodes"]:
        path, func = parse_entry_point(node["entry_point"])
        if path:
            entry_lookup[(node["id"], path)] = func
        else:
            unparseable_entry_points.append(node["id"])
    node_ids = {node["id"] for node in current_map["nodes"]}
    return {
        "nodes": current_map["nodes"],
        "node_by_path": node_by_path,
        "entry_lookup": entry_lookup,
        "node_ids": node_ids,
        "edge_set": {(edge["from"], edge["to"]) for edge in current_map["edges"]},
        "unparseable_entry_points": unparseable_entry_points,
    }


def diff_evidence(revision, path, detail):
    return make_evidence("git_diff", revision=revision, path=path, detail=detail)


def fact_evidence(target, path, entries, detail=None):
    """Structured code_fact evidence: every top-level declaration cited with
    name/kind/line; nested names aggregate into one detail entry (no key
    evidence truncation, R06)."""
    evidence = []
    top_level = [e for e in entries if "." not in e.get("name", "")]
    for entry in top_level:
        evidence.append(
            make_evidence(
                "code_fact",
                revision=target,
                path=path,
                name=entry.get("name"),
                line=entry.get("line"),
                detail=f"kind={entry.get('kind')}",
            )
        )
    nested = [e for e in entries if "." in e.get("name", "")]
    if nested:
        evidence.append(
            make_evidence(
                "code_fact",
                revision=target,
                path=path,
                detail=detail
                or f"{len(nested)} nested declarations: "
                + ", ".join(e.get("name", "") for e in nested[:8]),
            )
        )
    if not evidence:
        evidence.append(
            make_evidence("code_fact", revision=target, path=path,
                          detail=detail or "no declarations parsed")
        )
    return evidence


def map_node_evidence(node_id, detail):
    return make_evidence("map_node", detail=f"{node_id}: {detail}")


def handle_renamed(change, base, target, indexes, facts, proposals, no_proposal):
    """P03: rename/move → evidence-path update on the owning node (S04);
    never a NODE_ADD."""
    old_path, path = change["old_path"], change["path"]
    owners = indexes["node_by_path"].get(old_path, [])
    if owners and not indexes["node_by_path"].get(path, []):
        evidence = [
            diff_evidence(base, old_path, f"renamed -> {path} (old path absent at target)"),
            diff_evidence(target, path, "new path appears at target"),
            map_node_evidence(owners[0], "evidence path renamed"),
        ]
        entries = facts["files"].get(path) or []
        if entries:
            evidence.extend(fact_evidence(target, path, entries))
        proposals.append(
            {
                "kind": "IMPLEMENTATION_LINK_CHANGE",
                "subject": old_path,
                "node_ids": owners,
                "proposed_change": {
                    "node_id": owners[0],
                    "evidence_path_update": {"from": old_path, "to": path},
                },
                "rationale": "节点证据路径在 target 中改名/移动；建议更新 evidence 引用 — 人工确认",
                "evidence": evidence,
                "confidence": "medium" if len(owners) == 1 else "low",
                "uncertainty": (
                    ["multiple candidate nodes claim the renamed path"]
                    if len(owners) > 1
                    else []
                ),
            }
        )
    else:
        no_proposal.append(
            {
                "paths": [f"{old_path} -> {path}"],
                "reason": "rename outside declared map evidence domains",
            }
        )


def _is_test_noise(path):
    lowered = path.lower()
    return (
        "/tests/" in lowered
        or lowered.startswith("tests/")
        or lowered.startswith("test_")
        or "/test_" in lowered
    )


def _is_generated(path):
    lowered = path.lower()
    return any(token in lowered for token in ("generated", "/migrations/", "_pb2.py"))


def handle_added(change, target, indexes, facts, proposals, unresolved, no_proposal):
    """R01 NODE_ADD: new file + B declarations + no map coverage. Precision
    rules (S09/S10/S12): test/generated noise and already-covered paths never
    become nodes; responsibility is INFERENCE with explicit uncertainty."""
    path = change["path"]
    if indexes["node_by_path"].get(path):
        no_proposal.append({"paths": [path], "reason": "path already declared in map evidence domain"})
        return
    if not path.endswith(".py"):
        no_proposal.append({"paths": [path], "reason": "non-python addition"})
        return
    if _is_test_noise(path):
        no_proposal.append({"paths": [path], "reason": "test-only addition"})
        return
    if _is_generated(path):
        no_proposal.append({"paths": [path], "reason": "generated or mechanical file"})
        return
    if not facts["available"]:
        unresolved.append(
            {
                "subject": path,
                "reason": "HUMAN_REQUIRED",
                "evidence": [diff_evidence(target, path, "added; code facts unavailable")],
                "note": "B 不可用：不虚构 code_fact 证据（降级路径）",
            }
        )
        return
    entries = facts["files"].get(path)
    if entries is None:
        unresolved.append(
            {
                "subject": path,
                "reason": "HUMAN_REQUIRED",
                "evidence": [diff_evidence(target, path, "added; no parseable declarations")],
                "note": "无声明事实：不虚构 code_fact 证据；B 无条目不等于架构上不存在",
            }
        )
        return

    classes = [e for e in entries if e.get("kind") == "class" and "." not in e.get("name", "")]
    uncertainty = ["responsibility inferred from filename and declarations — human must confirm"]
    entry_point = None
    if len(classes) == 1:
        entry_point = f"{path} · {classes[0]['name']}"
    elif len(classes) > 1:
        uncertainty.append("multiple top-level classes; primary entry point not asserted")
    else:
        uncertainty.append("function-only module; architecture node decided by human, not by class threshold")
    proposed_change = {
        "node_id": node_id_for_path(path, indexes["node_ids"]),
        "title": path.rsplit("/", 1)[-1].removesuffix(".py"),
        "summary": f"新文件引入 {len(entries)} 个声明；职责候选，需人工确认",
    }
    if entry_point:
        proposed_change["entryPoint"] = entry_point
    proposals.append(
        {
            "kind": "NODE_ADD",
            "subject": path,
            "node_ids": None,
            "proposed_change": proposed_change,
            "rationale": "新增文件 + B 声明事实，地图证据域无对应节点；职责为 INFERENCE，由人裁决",
            "evidence": [
                diff_evidence(target, path, "added"),
                *fact_evidence(target, path, entries),
                map_node_evidence("(map)", f"no node evidence covers {path}"),
            ],
            "confidence": "low",
            "uncertainty": uncertainty,
        }
    )


def handle_modified(change, target, base, indexes, facts, base_facts, proposals,
                    unresolved, no_proposal):
    """R01 declaration channel for modified files. Verdicts:
    - declarations identical → no_proposal (comments/formatting/internal body);
      this verdict is channel-local and never silences the import channel;
    - entryPoint declaration gone → RESPONSIBILITY_CHANGE without picking an
      unsupported replacement symbol (S06, DROP L10);
    - declaration change outside map domains → unresolved."""
    path = change["path"]
    if not path.endswith(".py"):
        no_proposal.append({"paths": [path], "reason": "non-python change"})
        return
    owners = indexes["node_by_path"].get(path, [])
    target_entries = facts["files"].get(path)
    base_entries = base_facts["files"].get(path) if base_facts["available"] else None

    if base_entries is not None and target_entries is not None:
        if sorted(map(repr, base_entries)) == sorted(map(repr, target_entries)):
            no_proposal.append(
                {"paths": [path], "reason": "no declaration-level change (comments/formatting/internal body)"}
            )
            return
        if not owners:
            unresolved.append(
                {
                    "subject": path,
                    "reason": "HUMAN_REQUIRED",
                    "evidence": [
                        diff_evidence(target, path, "modified"),
                        *fact_evidence(target, path, target_entries),
                    ],
                    "note": "声明变化发生在地图证据域之外",
                }
            )
            return
        gone = sorted({e.get("name") for e in base_entries} - {e.get("name") for e in target_entries})
        touched_responsibility = False
        for owner in owners:
            func = indexes["entry_lookup"].get((owner, path))
            if func and any(g == func or g.rsplit(".", 1)[-1] == func for g in gone):
                touched_responsibility = True
                replacements = [e["name"] for e in target_entries
                                if e.get("kind") in TOP_LEVEL_KINDS and "." not in e.get("name", "")]
                uncertainty = [
                    "entryPoint disappearance does not prove responsibility change",
                    f"top-level declarations remaining at target: {replacements or 'none'}"
                    " — replacement symbol is chosen by human, not by C",
                ]
                proposals.append(
                    {
                        "kind": "RESPONSIBILITY_CHANGE",
                        "subject": owner,
                        "node_ids": [owner],
                        "proposed_change": {"node_id": owner, "entryPoint": None, "summary": None},
                        "rationale": f"节点 {owner} 的 entryPoint 函数 {func} 在 target 中缺失；"
                                     "职责可能已改变 — 需人工确认新入口",
                        "evidence": [
                            diff_evidence(target, path, f"entryPoint {func} missing at target"),
                            *fact_evidence(target, path, target_entries,
                                           detail=f"gone: {', '.join(gone)[:200]}"),
                            map_node_evidence(owner, "node entryPoint points at changed file"),
                        ],
                        "confidence": "low",
                        "uncertainty": uncertainty,
                    }
                )
        if not touched_responsibility:
            no_proposal.append({"paths": [path], "reason": "same-responsibility internal change (entryPoint intact)"})
        return

    if owners:
        no_proposal.append({"paths": [path], "reason": "changed inside map domain; no declaration comparison available"})
        return
    unresolved.append(
        {
            "subject": path,
            "reason": "HUMAN_REQUIRED",
            "evidence": [diff_evidence(target, path, "modified outside map domains")],
            "note": "无代码事实可刻画该变化",
        }
    )


def handle_stale_map(repo, base, target, changes, indexes, proposals, limits):
    """R05: a node is a removal candidate only when EVERY evidence path is
    provably absent from the pinned target tree — including deletions that
    predate base (S16). Read failures are UNKNOWN, never treated as absence.
    Independent of B availability (DROP L11)."""
    try:
        target_paths = gitio.ls_tree_names(repo, target)
        base_paths = gitio.ls_tree_names(repo, base)
    except gitio.DiffSignalError as exc:
        limits.append(f"stale-map existence check unavailable: {exc}")
        return
    removed_this_round = {c["path"] for c in changes if c["status"] == "removed"}
    for node in indexes["nodes"]:
        evidence_paths = node["evidence_paths"]
        if not evidence_paths:
            continue
        if any(path in target_paths for path in evidence_paths):
            continue
        own = sorted(evidence_paths)[0]
        known_at_base = own in base_paths
        evidence = [
            diff_evidence(target, own, f"all evidence paths absent at target: {sorted(evidence_paths)}"),
            map_node_evidence(node["id"], "every evidence path absent at target"),
        ]
        if known_at_base:
            evidence.insert(0, diff_evidence(base, own, "evidence path present at base"))
        else:
            uncertainty = [
                "path already absent at base; C does not fabricate earlier history",
                "map may be stale rather than the node meaningless — human decides",
            ]
        if known_at_base:
            uncertainty = ["map may be stale rather than the node meaningless — human decides"]
        if set(evidence_paths) <= removed_this_round:
            source_note = "removed in this diff"
        elif known_at_base:
            source_note = "deleted between base and target"
        else:
            source_note = "already absent at base (stale map entry)"
        proposals.append(
            {
                "kind": "NODE_REMOVE_CANDIDATE",
                "subject": node["id"],
                "node_ids": [node["id"]],
                "proposed_change": {"node_id": node["id"]},
                "rationale": f"节点的全部证据路径在 target 提交中不存在（{source_note}）；"
                             "地图可能过期 — 候选，不武断",
                "evidence": evidence,
                "confidence": "low",
                "uncertainty": uncertainty,
            }
        )


def apply_prior_decisions(proposals, prior_decisions, limits):
    """P06/F20: human-REJECTED candidates with the same subject/kind stay
    suppressed; the human decision itself is never changed by C."""
    rejected = {
        (item.get("subject"), item.get("kind"))
        for item in prior_decisions
        if item.get("decision") == "REJECTED"
    }
    kept, suppressed = [], []
    for proposal in proposals:
        subject = proposal.get("subject")
        for node_id in proposal.get("node_ids") or [subject]:
            if (node_id, proposal["kind"]) in rejected:
                suppressed.append(f"{proposal['kind']}:{node_id}")
                break
        else:
            kept.append(proposal)
    if suppressed:
        limits.append(f"suppressed by prior_decisions (F20): {', '.join(sorted(suppressed))}")
    return kept, limits
