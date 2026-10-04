"""Deterministic proposal engine for C v0.1.

Same request in → byte-identical result out (no clocks, no randomness, sorted
iteration everywhere). Evidence kinds: git_diff / code_fact / map_node /
context_claim — every proposal cites at least one (revision, path)-locatable
fact. Inference never poses as FACT: rationale/uncertainty say so explicitly.
"""
from __future__ import annotations

import json

from extensions.map_proposal import ca_adapter, diff_model, facts_adapter
from extensions.map_proposal.model import (RequestError, make_evidence, make_proposal,
                                           parse_entry_point, validate_map, validate_request)

TOP_LEVEL_KINDS = {"class", "function", "async_function"}


def _fact_evidence(target, path, entries, detail=None):
    names = ", ".join(f"{e['name']}({e.get('kind')}@{e.get('line')})" for e in entries[:3])
    return make_evidence("code_fact", revision=target, path=path,
                         detail=detail or f"declarations: {names}")


def _map_node_evidence(node_id, detail):
    return make_evidence("map_node", detail=f"{node_id}: {detail}")


def _diff_evidence(target, path, detail):
    return make_evidence("git_diff", revision=target, path=path, detail=detail)


def _is_high_impact_claim(claim):
    """RULE-6: claims asserting revision/PR-status/contract-shape/implementation
    state cannot be independently verified by C v0.1 (no gh access, no PR
    verifier) — they never back a proposal, verified_fields or not. They are
    dropped to unresolved HUMAN_REQUIRED instead (C_V0_1_RESOLVED_SEMANTICS)."""
    key = claim.get("key") or ""
    if key.startswith(("implementation.", "contract.")):
        return True
    value = claim.get("value")
    if isinstance(value, dict):
        return any(field in {"status", "head", "revision", "merged", "pr", "state",
                             "shape", "delivered", "approval"} for field in value)
    text = ca_adapter.claim_value_text(claim).lower()
    return any(token in text for token in ("merged", "approved", "delivered", "released"))


def _context_evidence(claim):
    fields = None
    if isinstance(claim.get("value"), dict):
        fields = ca_adapter.verified_fields(claim)
    unverified = claim["freshness"] != "verified" or (
        isinstance(claim.get("value"), dict) and fields is None)
    entry = make_evidence("context_claim", detail=f"{claim['key']}@{claim['scope']}: "
                          f"{ca_adapter.claim_value_text(claim)[:200]}",
                          claim_id=claim["claim_id"], claim_scope=claim["scope"],
                          unverified=unverified)
    if isinstance(claim.get("value"), dict):
        entry["value_field_verification"] = {
            key: ("verified" if fields is not None and key in fields else "UNVERIFIED")
            for key in sorted(claim["value"])}
    return entry


def suggest(request, repo):
    limits, unresolved, no_proposal, proposals = [], [], [], []
    cleaned = validate_request(request)
    base, target = cleaned["base_revision"], cleaned["target_revision"]
    if base == target:
        return {"request": {"base_revision": base, "target_revision": target},
                "proposals": [], "unresolved": [], "no_proposal": [],
                "limits": ["same revision: no diff to analyze; map drift is not C's scope"],
                "metadata": {"mode": "DEGRADED_NO_CONTEXT", "facts_mode": "unknown",
                             "base_revision": base, "target_revision": target,
                             "map_version": None, "counts": {}}}
    current_map = validate_map(cleaned["current_map"])
    nodes = current_map["nodes"]
    node_by_path = {}
    for node in nodes:
        for path in node["evidence_paths"]:
            node_by_path.setdefault(path, []).append(node["id"])
    entry_lookup = {}
    for node in nodes:
        path, func = parse_entry_point(node["entry_point"])
        if path:
            entry_lookup[(node["id"], path)] = func

    facts, facts_limits = facts_adapter.load_code_facts(
        cleaned["code_facts"], repo, target,
        [c["path"] for c in cleaned["changed_paths"] if c["path"].endswith(".py")])
    limits.extend(facts_limits)
    files, skipped = facts["files"], facts["skipped"]
    facts_mode = "available" if facts["available"] else "unavailable"

    ca, ca_mode, ca_limits = ca_adapter.load_context(cleaned["context_pack"], target)
    limits.extend(ca_limits)

    changes = cleaned["changed_paths"]
    changed_paths = {c["path"] for c in changes} | \
                    {c["old_path"] for c in changes if c.get("old_path")}
    known_paths = set(files) | changed_paths | set(node_by_path)
    for node in nodes:
        known_paths.update(node["evidence_paths"])

    modified_paths = [c["path"] for c in changes
                      if c["status"] in ("modified", "renamed") and c["path"].endswith(".py")]
    base_facts = {"files": {}, "skipped": set(), "available": False}
    if facts["available"] and modified_paths:
        base_facts, base_limits = facts_adapter.load_code_facts(None, repo, base, modified_paths)
        limits.extend(base_limits)

    declaration_unchanged = set()
    for change in changes:
        path = change["path"]
        if path in skipped and path.endswith(".py"):
            unresolved.append({"subject": path, "reason": "NEEDS_HUMAN_REVIEW",
                               "kind": "UNKNOWN",
                               "evidence": [_diff_evidence(target, path,
                                                           "changed path is in B skipped (unparseable)")],
                               "note": "skipped files are never facts; no proposal from guesses"})
            continue
        if change["status"] == "renamed":
            _handle_renamed(change, base, target, node_by_path, files, proposals, no_proposal)
        elif change["status"] == "removed":
            continue
        elif change["status"] == "added":
            _handle_added(change, target, node_by_path, files, facts,
                          proposals, unresolved, no_proposal)
        else:
            _handle_modified(change, target, base, node_by_path, files, entry_lookup,
                             base_facts, proposals, unresolved, no_proposal,
                             declaration_unchanged)

    _handle_removals(changes, base, target, nodes, node_by_path, facts, proposals)
    relation_paths = [c["path"] for c in changes
                      if c["path"].endswith(".py") and c["path"] not in declaration_unchanged
                      and c["status"] in ("added", "modified", "renamed")]
    _handle_relations(repo, base, target, changes, relation_paths, node_by_path, known_paths,
                      limits, unresolved, proposals)
    proposals, limits = _apply_prior_decisions(proposals, cleaned["prior_decisions"], limits)
    proposals, limits, unresolved = _apply_context_claims(
        proposals, ca, ca_mode, changed_paths, {node["id"] for node in nodes},
        limits, unresolved, target)

    proposals.sort(key=lambda item: (item["subject"], item["kind"]))
    final = []
    for index, item in enumerate(proposals, 1):
        final.append(make_proposal(index, target, item["kind"], item["subject"],
                                   item["proposed_change"], item["rationale"],
                                   item["evidence"], item["confidence"], item["uncertainty"]))
    metadata = {"mode": ca_mode, "facts_mode": facts_mode, "base_revision": base,
                "target_revision": target, "map_version": None,
                "map_version_note": "current map has no version identity; results are pinned "
                                    "to target_revision only",
                "counts": {"proposals": len(final), "unresolved": len(unresolved),
                           "no_proposal": len(no_proposal)}}
    if ca_mode == ca_adapter.FULL:
        metadata["context_authority"] = {"schema_version": ca["schema_version"],
                                         "project_revision": ca["project_revision"],
                                         "registry_hash": ca["registry_hash"]}
    return {"request": {"base_revision": base, "target_revision": target},
            "proposals": final, "unresolved": unresolved, "no_proposal": no_proposal,
            "limits": limits, "metadata": metadata}


def _handle_renamed(change, base, target, node_by_path, files, proposals, no_proposal):
    old_path, path = change["old_path"], change["path"]
    owners = node_by_path.get(old_path, [])
    if owners and not node_by_path.get(path, []):
        entries = files.get(path) or []
        # M1: the old path only exists at base; the new path only at target.
        evidence = [_diff_evidence(base, old_path, f"renamed → {path} (old path absent at target)"),
                    _diff_evidence(target, path, "new path appears at target"),
                    _map_node_evidence(owners[0], "evidence path renamed")]
        if entries:
            evidence.append(_fact_evidence(target, path, entries))
        proposals.append({
            "kind": "IMPLEMENTATION_LINK_CHANGE", "subject": old_path, "node_ids": owners,
            "proposed_change": {"node_id": owners[0],
                                "evidence_path_update": {"from": old_path, "to": path}},
            "rationale": "节点证据路径在 target 中改名/移动;建议更新 evidence 引用 — 人工确认",
            "evidence": evidence,
            "confidence": "medium" if len(owners) == 1 else "low",
            "uncertainty": (["multiple candidate nodes claim the renamed path"]
                            if len(owners) > 1 else [])})
    else:
        no_proposal.append({"paths": [f"{old_path} → {path}"],
                            "reason": "rename outside declared map evidence domains"})


def _handle_added(change, target, node_by_path, files, facts,
                  proposals, unresolved, no_proposal):
    path = change["path"]
    if node_by_path.get(path):
        no_proposal.append({"paths": [path],
                            "reason": "path already declared in map evidence domain"})
        return
    if not path.endswith(".py"):
        no_proposal.append({"paths": [path], "reason": "non-python addition"})
        return
    lowered = path.lower()
    if ("/tests/" in lowered or lowered.startswith("tests/")
            or lowered.startswith("test_") or "/test_" in lowered):
        no_proposal.append({"paths": [path], "reason": "test-only addition"})
        return
    if any(token in lowered for token in ("generated", "/migrations/", "_pb2.py")):
        no_proposal.append({"paths": [path], "reason": "generated or mechanical file"})
        return
    if not facts["available"]:
        unresolved.append({"subject": path, "reason": "NEEDS_HUMAN_REVIEW", "kind": "UNKNOWN",
                           "evidence": [_diff_evidence(target, path, "added; code facts unavailable")],
                           "note": "no B facts: not fabricating code_fact evidence (F1' degraded)"})
        return
    entries = files.get(path)
    if entries is None:
        unresolved.append({"subject": path, "reason": "NEEDS_HUMAN_REVIEW", "kind": "UNKNOWN",
                           "evidence": [_diff_evidence(target, path, "added; no parseable declarations")],
                           "note": "no declaration facts; not fabricating code_fact evidence"})
        return
    classes = [e for e in entries if e.get("kind") == "class" and "." not in e.get("name", "")]
    if not classes:
        unresolved.append({"subject": path, "reason": "NEEDS_HUMAN_REVIEW", "kind": "UNKNOWN",
                           "evidence": [_diff_evidence(target, path, "added"),
                                        _fact_evidence(target, path, entries, "no top-level class")],
                           "note": "helper/function-only module: cannot infer an architecture node"})
        return
    primary = classes[0]
    node_id = "map-" + path.rsplit("/", 1)[-1].removesuffix(".py").replace("_", "-").lower()
    proposals.append({
        "kind": "NODE_ADD", "subject": path, "node_ids": None,
        "proposed_change": {"node_id": node_id,
                            "title": path.rsplit("/", 1)[-1].removesuffix(".py"),
                            "summary": f"新文件引入 {primary['name']} 等声明；职责候选，需人工确认",
                            "entryPoint": f"{path} · {primary['name']}"},
        "rationale": "新增文件 + B 声明事实(含 class),地图证据域无对应节点;职责为 INFERENCE,由人裁决",
        "evidence": [_diff_evidence(target, path, "added"),
                     _fact_evidence(target, path, entries),
                     _map_node_evidence("(map)", f"no node evidence covers {path}")],
        "confidence": "low",
        "uncertainty": ["responsibility inferred from file name and declarations — "
                        "human must confirm"]})


def _handle_modified(change, target, base, node_by_path, files, entry_lookup,
                     base_facts, proposals, unresolved, no_proposal,
                     declaration_unchanged):
    path = change["path"]
    if not path.endswith(".py"):
        no_proposal.append({"paths": [path], "reason": "non-python change"})
        return
    owners = node_by_path.get(path, [])
    target_entries = files.get(path)
    base_entries = base_facts["files"].get(path) if base_facts["available"] else None
    if base_entries is not None and target_entries is not None:
        if sorted(map(json.dumps, base_entries)) == sorted(map(json.dumps, target_entries)):
            declaration_unchanged.add(path)
            no_proposal.append({"paths": [path],
                                "reason": "no declaration-level change "
                                          "(comments/formatting/internal body)"})
            return
        if not owners:
            unresolved.append({"subject": path, "reason": "NEEDS_HUMAN_REVIEW", "kind": "UNKNOWN",
                               "evidence": [_diff_evidence(target, path, "modified"),
                                            _fact_evidence(target, path, target_entries)],
                               "note": "declaration change outside declared map domains"})
            return
        gone = sorted({e.get("name") for e in base_entries}
                      - {e.get("name") for e in target_entries})
        touched_responsibility = False
        for owner in owners:
            func = entry_lookup.get((owner, path))
            if func and any(g == func or g.rsplit(".", 1)[-1] == func for g in gone):
                touched_responsibility = True
                replacement = next((e for e in target_entries
                                    if e.get("kind") in TOP_LEVEL_KINDS), None)
                proposals.append({
                    "kind": "RESPONSIBILITY_CHANGE", "subject": owner, "node_ids": [owner],
                    "proposed_change": {"node_id": owner,
                                        "entryPoint": (f"{path} · {replacement['name']}"
                                                       if replacement else None),
                                        "summary": None},
                    "rationale": f"节点 {owner} 的 entryPoint 函数 {func} 在 target 中缺失;"
                                 "职责可能已改变 — 候选替换需人工确认",
                    "evidence": [_diff_evidence(target, path, f"entryPoint {func} missing at target"),
                                 _fact_evidence(target, path, target_entries,
                                                detail=f"gone: {', '.join(gone)[:200]}"),
                                 _map_node_evidence(owner, "node entryPoint points at changed file")],
                    "confidence": "low",
                    "uncertainty": ["entryPoint disappearance does not prove responsibility change",
                                    "±decorator line offset when comparing declaration lines"]})
        if not touched_responsibility:
            no_proposal.append({"paths": [path],
                                "reason": "same-responsibility internal change (entryPoint intact)"})
        return
    if owners:
        no_proposal.append({"paths": [path],
                            "reason": "changed inside map domain; no declaration comparison available"})
        return
    unresolved.append({"subject": path, "reason": "NEEDS_HUMAN_REVIEW", "kind": "UNKNOWN",
                       "evidence": [_diff_evidence(target, path, "modified outside map domains")],
                       "note": "no code facts to characterize the change"})


def _handle_removals(changes, base, target, nodes, node_by_path, facts, proposals):
    if not facts["available"]:
        return
    removed = {c["path"] for c in changes if c["status"] == "removed"}
    if not removed:
        return
    for node in nodes:
        evidence_paths = set(node["evidence_paths"])
        if evidence_paths and evidence_paths <= removed:
            # M1: cite the node's own paths; the old path exists at base, not target.
            own = sorted(evidence_paths)[0]
            proposals.append({
                "kind": "NODE_REMOVE_CANDIDATE", "subject": node["id"], "node_ids": [node["id"]],
                "proposed_change": {"node_id": node["id"]},
                "rationale": "节点的全部证据路径在 target 提交中已删除;地图可能过期 — 候选,不武断",
                "evidence": [_diff_evidence(base, own, "evidence path present at base"),
                             _diff_evidence(target, own,
                                            f"all evidence paths removed: {sorted(evidence_paths)}"),
                             _map_node_evidence(node["id"], "every evidence path absent at target")],
                "confidence": "low",
                "uncertainty": ["map may be stale rather than the node meaningless — human decides"]})


def _handle_relations(repo, base, target, changes, relation_paths, node_by_path, known_paths,
                      limits, unresolved, proposals):
    try:
        signals = diff_model.import_signals(repo, base, target, relation_paths)
    except diff_model.DiffSignalError as exc:
        limits.append(f"import signal extraction failed: {exc}")
        return
    # M2 churn guard: the same (file, module) gaining and losing an import in one
    # diff is reformatting, not a relation change.
    added_keys = {(s["path"], s["module"]) for s in signals["added"]}
    signals["removed"] = [s for s in signals["removed"]
                          if (s["path"], s["module"]) not in added_keys]
    signals["added"] = [s for s in signals["added"]
                        if (s["path"], s["module"]) not in
                        {(r["path"], r["module"]) for r in signals["removed"]}]
    emitted_pairs = set()
    for signal in signals["added"]:
        target_path = diff_model.resolve_module(signal["module"], known_paths)
        if target_path is None:
            continue
        source_owners = node_by_path.get(signal["path"], [])
        target_owners = node_by_path.get(target_path, [])
        if not source_owners or not target_owners or set(source_owners) == set(target_owners):
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
        proposals.append({
            "kind": "RELATION_ADD", "subject": f"{source_owners[0]}→{target_owners[0]}",
            "node_ids": None,
            "proposed_change": {"from": source_owners[0], "to": target_owners[0],
                                "label": f"import 依赖(候选):{signal['path']} → {target_path}"},
            "rationale": "跨模块新增 import 连接两个已有节点的证据域;方向与语义需人工确认",
            "evidence": [_diff_evidence(target, signal["path"], f"import added: {signal['line']}"),
                         _map_node_evidence(source_owners[0], f"covers {signal['path']}"),
                         _map_node_evidence(target_owners[0], f"covers {target_path}")],
            "confidence": confidence, "uncertainty": uncertainty})
    for signal in signals["removed"]:
        target_path = diff_model.resolve_module(signal["module"], known_paths)
        if target_path is None:
            continue
        source_owners = node_by_path.get(signal["path"], [])
        target_owners = node_by_path.get(target_path, [])
        if not source_owners or not target_owners or set(source_owners) == set(target_owners):
            continue
        pair = (tuple(sorted(source_owners)), tuple(sorted(target_owners)))
        if pair in emitted_pairs:
            continue
        # M3: "all imports between the two sides are gone" is verified on the
        # involved source file — the import must exist at base and be gone at
        # target; any added signal for the same pair already suppressed above.
        try:
            at_base = diff_model.static_import_count(repo, base, signal["path"], target_path)
            at_target = diff_model.static_import_count(repo, target, signal["path"], target_path)
        except diff_model.DiffSignalError as exc:
            limits.append(f"import recheck failed: {exc}")
            continue
        if at_base == 0 or at_target > 0:
            continue
        emitted_pairs.add(pair)
        proposals.append({
            "kind": "RELATION_REMOVE_CANDIDATE", "subject": f"{source_owners[0]}→{target_owners[0]}",
            "node_ids": None,
            "proposed_change": {"from": source_owners[0], "to": target_owners[0],
                                "label": f"import 移除(候选):{signal['path']} → {target_path}"},
            "rationale": f"该文件在 target 中已无指向此节点的 import(base {at_base} 条→target 0 条);"
                         "是否意味关系消失由人判断",
            "evidence": [_diff_evidence(base, signal["path"],
                                        f"import present at base: {at_base} → {target_path}"),
                         _diff_evidence(target, signal["path"], "import removed at target"),
                         _map_node_evidence(source_owners[0], f"covers {signal['path']}"),
                         _map_node_evidence(target_owners[0], f"covers {target_path}")],
            "confidence": "low", "uncertainty": []})
    for signal in signals["dynamic"]:
        unresolved.append({"subject": signal["path"], "reason": "NEEDS_HUMAN_REVIEW",
                           "kind": "UNKNOWN",
                           "evidence": [_diff_evidence(target, signal["path"],
                                                       f"dynamic import: {signal['line']}")],
                           "note": "dynamic/string-built import: too weak for RELATION_ADD"})


def _apply_prior_decisions(proposals, prior_decisions, limits):
    rejected = {(item.get("subject"), item.get("kind")) for item in prior_decisions
                if item.get("decision") == "REJECTED"}
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
        limits.append(f"suppressed by prior_decisions: {', '.join(sorted(suppressed))}")
    return kept, limits


def _apply_context_claims(proposals, ca, ca_mode, changed_paths, node_ids, limits,
                          unresolved, target):
    """RULE-6/7 enforcement (H1/H2 fixes):
    - high-impact claims (implementation./contract. or status/head/merged-style
      values) are NEVER attached — C v0.1 cannot independently verify them; they
      go to unresolved HUMAN_REQUIRED (a coherent forgery passes the validator,
      so the only safe posture is not to背书 what C cannot check);
    - claims whose value text mentions changed-away paths contradict the diff
      and are dropped the same way;
    - known conflicts related to this difference (mentioning changed paths or
      map node ids) land in unresolved HUMAN_REQUIRED and any proposal touching
      those paths/nodes is moved out of proposals until a human resolves.
    A surviving low-impact claim may only SUPPLEMENT a proposal that already
    stands on git/fact/map evidence."""
    if ca_mode == ca_adapter.DEGRADED:
        return proposals, limits, unresolved

    def drop_to_unresolved(claim, note):
        limits.append(f"context claim not used as evidence ({note}): "
                      f"{claim['key']}@{claim['scope']}")
        unresolved.append({"subject": f"claim:{claim['key']}", "reason": "HUMAN_REQUIRED",
                           "kind": "UNKNOWN",
                           "evidence": [make_evidence("context_claim",
                                                      detail=ca_adapter.claim_value_text(claim)[:300],
                                                      claim_id=claim["claim_id"],
                                                      claim_scope=claim["scope"], unverified=True)],
                           "note": note})

    conflict_keys = ca["conflict_keys"]
    for claim in ca["claims"]:
        if claim["key"] in conflict_keys:
            continue
        mentioned = sorted(path for path in changed_paths if path and path
                           in ca_adapter.claim_value_text(claim))
        if mentioned:
            drop_to_unresolved(claim, "pack contradicts independent git evidence "
                                      f"(mentions changed path {mentioned[0]}); human decides")
        elif _is_high_impact_claim(claim):
            drop_to_unresolved(claim, "high-impact assertion (revision/PR status/contract/"
                                      "implementation) — C v0.1 has no independent verifier "
                                      "for it and must not背书 it")
    if conflict_keys:
        limits.append(f"context claims excluded (known conflicts): {', '.join(sorted(conflict_keys))}")
        for row in ca.get("conflict_rows", []):
            row_text = " ".join(ca_adapter.claim_value_text(claim)
                                for claim in row.get("claims", []) if isinstance(claim, dict))
            mentioned_paths = sorted(path for path in changed_paths if path and path in row_text)
            mentioned_nodes = sorted(node_id for node_id in node_ids
                                     if node_id and node_id in row_text)
            if not mentioned_paths and not mentioned_nodes:
                continue
            unresolved.append({"subject": f"conflict:{row.get('key')}",
                               "reason": "HUMAN_REQUIRED", "kind": "UNKNOWN",
                               "evidence": [make_evidence("context_claim", detail=row_text[:300],
                                                          claim_id=None,
                                                          claim_scope=row.get("scope"),
                                                          unverified=True)],
                               "note": "known CA conflict related to this difference "
                                       "(paths: " + ", ".join(mentioned_paths) +
                                       "; nodes: " + ", ".join(mentioned_nodes) +
                                       "); C must not pick a side"})
            kept = []
            for proposal in proposals:
                touched_nodes = set(proposal.get("node_ids") or [])
                change = proposal.get("proposed_change") or {}
                if change.get("node_id"):
                    touched_nodes.add(change["node_id"])
                touches = proposal["subject"] in mentioned_paths \
                    or proposal["subject"] in mentioned_nodes \
                    or bool(touched_nodes & set(mentioned_nodes)) \
                    or any(path in row_text for path in [proposal["subject"]]
                           if path in changed_paths)
                if touches:
                    unresolved.append({"subject": proposal["subject"],
                                       "reason": "HUMAN_REQUIRED", "kind": "UNKNOWN",
                                       "evidence": proposal["evidence"][:1],
                                       "note": "proposal suppressed pending human resolution of "
                                               f"known conflict {row.get('key')}"})
                    limits.append(f"proposal moved to unresolved (related known conflict): "
                                  f"{proposal['kind']}:{proposal['subject']}")
                else:
                    kept.append(proposal)
            proposals[:] = kept
    if ca["claims"] and proposals:
        supplementable = [c for c in ca["claims"]
                          if c["key"] not in conflict_keys
                          and c["claim_id"] not in {u.get("claim_id") for u in unresolved}
                          and not _is_high_impact_claim(c)
                          and not any(path and path in ca_adapter.claim_value_text(c)
                                      for path in changed_paths)]
        if supplementable:
            proposals[0].setdefault("evidence", []).append(_context_evidence(supplementable[0]))
            limits.append(f"context claim attached as supplementary evidence: "
                          f"{supplementable[0]['key']}@{supplementable[0]['scope']}")
        else:
            limits.append("no low-impact verifiable context claim available; "
                          "no context_claim attached to proposals")
    return proposals, limits, unresolved
