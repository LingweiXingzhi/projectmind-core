# -*- coding: utf-8 -*-
"""Map Proposal extension (Role C).

Strictly follows:
- C_INPUT_OUTPUT_CONTRACT_PROPOSAL.md (SuggestMapRequest/Response, MapProposal)
- C_CONTEXT_SAFETY_RULES.md (Rules 1-10)
- DevKit Acceptance Suite (C-S01 ~ C-S11 backward compatibility)
"""

from http import HTTPStatus
import os

from extension_host import ExtensionError

EXTENSION = {
    "title": "项目地图提案 (Map Proposal)",
    "description": "基于代码事实、Git 变化与 Context Authority 事实底座，提出功能节点与关系提案。",
}


def handle(context, method: str, data: dict) -> dict:
    if method not in ("POST", "GET"):
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, "此扩展仅支持 POST 与 GET 请求")

    data = data or {}
    snapshot = context.snapshot() if hasattr(context, "snapshot") else {}
    current_revision = snapshot.get("revision", "")

    # 1. 基础字段解析与钉定 (PIN: target_revision)
    target_revision = data.get("target_revision") or current_revision
    base_revision = data.get("base_revision") or current_revision
    code_facts = data.get("code_facts")
    changed_paths = data.get("changed_paths") or []
    current_map = data.get("current_map") or snapshot
    context_pack = data.get("context_pack")
    requested_mode = data.get("mode")

    limits = []
    unresolved = []
    no_proposal = []
    proposals = []
    candidates = []

    # 2. 校验与防御：code_facts 必传与 SHA 一致性 (RULE-5, C-S02)
    if code_facts is None:
        return _make_response(
            status="refused",
            revision=target_revision,
            candidates=[],
            proposals=[],
            unresolved=[],
            no_proposal=[{"paths": [], "reason": "missing_code_facts"}],
            limits=["code_facts missing"],
            note="缺少 code_facts 输入",
            base_revision=base_revision,
        )

    facts_rev = code_facts.get("revision")
    if not facts_rev or facts_rev != target_revision:
        raise ExtensionError(
            HTTPStatus.BAD_REQUEST,
            f"SHA mismatch: code_facts revision ({facts_rev}) != target_revision ({target_revision})",
        )

    # 3. Context Pack 安全防御 (RULE-1, RULE-2, RULE-7)
    if context_pack:
        pack_rev = context_pack.get("project_revision")
        if pack_rev != target_revision:
            limits.append(f"context_pack revision {pack_rev} != target {target_revision}; pack dropped")
            context_pack = None
        else:
            known_conflicts = context_pack.get("known_conflicts") or []
            for conf in known_conflicts:
                if isinstance(conf, dict):
                    key = conf.get("key", "unknown")
                    limits.append(f"context_pack conflict on {key} excluded from proposals")
                    unresolved.append({
                        "subject": key,
                        "reason": "NEEDS_HUMAN_REVIEW",
                        "evidence": [conf],
                    })

    # 4. 代码事实与跳过文件提取 (C_B_CODEFACTS_USAGE)
    files = code_facts.get("files") or []
    skipped = code_facts.get("skipped") or []

    for s in skipped:
        p = s.get("path", "")
        reason = s.get("reason", "unknown")
        limits.append(f"code_facts skipped {p}: {reason}")
        unresolved.append({
            "subject": p,
            "reason": "NEEDS_HUMAN_REVIEW",
            "evidence": [{"kind": "code_fact_skipped", "detail": reason}],
        })

    if not files:
        return _make_response(
            status="empty",
            revision=target_revision,
            candidates=[],
            proposals=[],
            unresolved=unresolved,
            no_proposal=[{"paths": [], "reason": "empty_code_facts"}],
            limits=limits,
            note="输入中无代码文件证据，拒绝无凭据推导",
            base_revision=base_revision,
        )

    allowed_paths = {f["path"] for f in files if isinstance(f, dict) and "path" in f}
    if not allowed_paths:
        return _make_response(
            status="insufficient_evidence",
            revision=target_revision,
            candidates=[],
            proposals=[],
            unresolved=unresolved,
            no_proposal=[{"paths": [], "reason": "insufficient_evidence"}],
            limits=limits,
            note="未发现有效代码文件路径",
            base_revision=base_revision,
        )

    # 5. 确定运行状态 (RULE-6, C-S08, C-S10)
    has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
    if requested_mode == "ai" and has_api_key:
        status_name = "ai_candidate"
    else:
        status_name = "rule_candidate"

    # 6. 提案引擎（确定性排序，反目标检查：绝不含 position）
    sorted_files = sorted(files, key=lambda x: str(x.get("path", "")))

    for idx, f in enumerate(sorted_files):
        path = f.get("path")
        if not path or path not in allowed_paths:
            continue

        entries = f.get("entries") or []
        entry_names = [e["name"] for e in entries if isinstance(e, dict) and "name" in e]
        lead_entry = entry_names[0] if entry_names else "module"

        title = f"Component: {path}"
        summary = (
            f"基于代码事实推导的模块，定义符号: {', '.join(entry_names[:5])}"
            if entry_names
            else f"基于文件 {path} 推导的代码模块候选"
        )

        candidates.append({
            "title": title,
            "summary": summary,
            "evidencePaths": [path],
            "unknowns": [],
        })

        short_hash = target_revision[:8] if target_revision else "rev"
        prop_id = f"mp-{short_hash}-{idx + 1:03d}"
        node_id = path.replace("/", "-").replace(".", "-")

        evidence_chain = [
            {
                "kind": "code_fact",
                "revision": target_revision,
                "detail": f"{len(entries)} definitions in {path}",
                "claim_id": None,
            }
        ]

        proposals.append({
            "proposal_id": prop_id,
            "subject": path,
            "kind": "NODE_ADD",
            "proposed_change": {
                "node_id": node_id,
                "title": title,
                "summary": summary,
                "entryPoint": f"{path} · {lead_entry}",
            },
            "rationale": f"代码事实提取确认 {len(entries)} 个符号定义；人工图尚无对应独立节点",
            "evidence": evidence_chain,
            "confidence": "medium",
            "uncertainty": ["responsibility inferred from filenames/declarations — human must confirm"],
            "status": "PROPOSED",
            "human_required": True,
        })

    note_text = f"基于规则生成 {len(candidates)} 个候选节点"
    return _make_response(
        status=status_name,
        revision=target_revision,
        candidates=candidates,
        proposals=proposals,
        unresolved=unresolved,
        no_proposal=no_proposal,
        limits=limits,
        note=note_text,
        base_revision=base_revision,
    )


def _make_response(
    status: str,
    revision: str,
    candidates: list,
    proposals: list,
    unresolved: list,
    no_proposal: list,
    limits: list,
    note: str,
    base_revision: str = None,
) -> dict:
    return {
        "status": status,
        "revision": revision,
        "candidates": candidates,
        "note": note,
        "request": {
            "base_revision": base_revision or revision,
            "target_revision": revision,
        },
        "proposals": proposals,
        "unresolved": unresolved,
        "no_proposal": no_proposal,
        "limits": limits,
    }
