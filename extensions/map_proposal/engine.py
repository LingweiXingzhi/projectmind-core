# -*- coding: utf-8 -*-
"""C convergence engine — single canonical pipeline (R01/R06/R07 skeleton).

Pipeline (invariant order):
  request/path/pin validation → Core compare adaptation → B gate → map intake
  → independent signal channels (declaration / import / map / existence) →
  unified admission (skipped, evidence, conflicts, CA trust) → four-bucket
  canonical result → legacy compatibility projection.

W1 status: gates, canonical result, identity and projection are live; signal
channels are wired but empty until W2/W3 land. No map write ever happens here.
"""
from __future__ import annotations

from extensions.map_proposal import analysis, facts_adapter, model, relations, gitio


def suggest_map(repo, data) -> dict:
    request = model.validate_request(model.adapt_core_compare(data))
    if request["current_map"] is None:
        raise model.RequestError("current_map 缺失：C 需要当前人工地图原文，不得从 snapshot 偷补")
    current_map = model.validate_map(request["current_map"])

    target = request["target_revision"]
    base = request["base_revision"]

    # Installed-B collection focuses on paths that can exist at target.
    wanted = [
        c["path"]
        for c in request["changed_paths"]
        if c["status"] in ("added", "modified", "renamed")
    ]
    facts, limits = facts_adapter.load_code_facts(request["code_facts"], repo, target, wanted)

    changed_paths = set()
    for change in request["changed_paths"]:
        changed_paths.add(change["path"])
        if change["old_path"]:
            changed_paths.add(change["old_path"])

    proposals = []
    unresolved = facts_adapter.skipped_unresolved(changed_paths & facts["skipped"], target)
    no_proposal = []
    limits = _dedupe(limits)

    indexes = analysis.build_indexes(current_map)

    # Signal channels run independently (R01); a declaration-channel verdict on
    # one file never ends another channel's analysis of the same file (F05).
    # A changed path B skipped never feeds any strong candidate channel (F04);
    # its HUMAN_REQUIRED unresolved entry is already emitted above.
    # base==target: gates above already ran; every channel stays silent and the
    # zero-proposal same-revision branch below applies (invariant 13).
    modified_py_paths = [
        c["path"]
        for c in request["changed_paths"]
        if c["status"] == "modified" and c["path"].endswith(".py")
        and c["path"] not in facts["skipped"]
    ]
    base_facts = {"files": {}, "skipped": set(), "available": False}
    if base != target and modified_py_paths:
        base_facts, base_limits = facts_adapter.load_code_facts(None, repo, base, modified_py_paths)
        limits.extend(base_limits)

    if base != target:
        for change in request["changed_paths"]:
            path = change["path"]
            old_path = change.get("old_path")
            if path in facts["skipped"] or (old_path and old_path in facts["skipped"]):
                continue
            if change["status"] == "renamed":
                analysis.handle_renamed(change, base, target, indexes, facts, proposals, no_proposal)
            elif change["status"] == "added":
                analysis.handle_added(change, target, indexes, facts, proposals, unresolved, no_proposal)
            elif change["status"] == "modified":
                analysis.handle_modified(
                    change, target, base, indexes, facts, base_facts, proposals, unresolved, no_proposal
                )
            # removed paths are handled by the stale-map existence channel below.

        # R03: independent import-relation channel — runs regardless of
        # declaration-channel verdicts (F05); skipped sources never feed it.
        relation_paths = [
            c["path"]
            for c in request["changed_paths"]
            if c["path"].endswith(".py")
            and c["path"] not in facts["skipped"]
            and c["status"] in ("added", "modified", "renamed")
        ]
        known_paths = set(facts["files"]) | changed_paths | set(indexes["node_by_path"])
        relations.handle_relations(repo, base, target, indexes, facts, known_paths,
                                   relation_paths, proposals, unresolved, limits)

        # R05: stale-map target existence, independent of B availability.
        analysis.handle_stale_map(repo, base, target, request["changed_paths"], indexes,
                                  proposals, limits)
        limits = _dedupe(limits)

        # F20: human REJECTED subject/kind pairs stay suppressed.
        proposals, limits = analysis.apply_prior_decisions(
            proposals, request["prior_decisions"], limits
        )

        # Single publication exit (invariant 2): every candidate goes through the
        # canonical proposal constructor with its invariants.
        proposals = [
            model.make_proposal(
                target,
                item["kind"],
                item["subject"],
                item["proposed_change"],
                item["rationale"],
                item["evidence"],
                item["confidence"],
                item["uncertainty"],
            )
            for item in proposals
        ]

    if base == target:
        # Invariant 13: gates above already ran; zero proposals, and map drift
        # is explicitly out of scope for a same-revision diff judgment.
        no_proposal.append(
            {
                "reason": "same_revision",
                "note": "base==target：已完成输入与事实一致性校验，零提案；地图漂移不属于本次差异判断",
            }
        )
    elif not proposals and facts["available"]:
        no_proposal.append(
            {
                "reason": "no_cross_channel_signals",
                "note": "changed_paths 与地图/代码事实无交叉信号",
            }
        )

    return _canonical_result(
        base=base,
        target=target,
        facts=facts,
        current_map=current_map,
        proposals=proposals,
        unresolved=unresolved,
        no_proposal=no_proposal,
        limits=limits,
    )


def _dedupe(values):
    seen = {}
    for item in values:
        seen.setdefault(str(item), None)
    return list(seen)


def _canonical_result(base, target, facts, current_map, proposals, unresolved,
                      no_proposal, limits):
    proposals = sorted(proposals, key=lambda p: (p["kind"], p["subject"], p["proposal_id"]))
    unresolved = sorted(unresolved, key=lambda u: str(u.get("subject", "")))
    no_proposal = sorted(no_proposal, key=lambda n: str(n.get("reason", "")))

    # Honest status (R07): only rule generation exists; a request without a
    # real model run must never be labelled ai_candidate. Degraded is explicit
    # when the B dependency is unavailable.
    if not facts["available"]:
        status = "degraded"
    elif proposals:
        status = "rule_candidate"
    else:
        status = "empty"

    note_bits = []
    if not facts["available"]:
        note_bits.append("代码事实不可用，已降级运行")
    note_bits.append(f"规则生成 {len(proposals)} 个候选")
    note = "；".join(note_bits)

    return {
        "status": status,
        "revision": target,
        "candidates": _legacy_candidates(proposals),
        "note": note,
        "request": {
            "base_revision": base,
            "target_revision": target,
            "facts_source": facts["source"],
            "map_has_version_identity": current_map["has_version_identity"],
        },
        "proposals": proposals,
        "unresolved": unresolved,
        "no_proposal": no_proposal,
        "limits": limits,
    }


def _legacy_candidates(proposals):
    """K03: the old candidates field is a projection of already-admitted
    canonical NODE_ADD proposals — it never carries extra or un-gated items."""
    out = []
    for proposal in proposals:
        if proposal["kind"] != "NODE_ADD":
            continue
        change = proposal["proposed_change"]
        out.append(
            {
                "title": change.get("title", proposal["subject"]),
                "summary": change.get("summary", proposal["rationale"]),
                "evidencePaths": sorted(
                    {e["path"] for e in proposal["evidence"] if e.get("path")}
                ),
                "unknowns": list(proposal["uncertainty"]),
            }
        )
    return out
