# -*- coding: utf-8 -*-
"""Role C: Architecture candidate generation, incremental proposals, and process deviations."""

import hashlib
import time
import uuid

# 机器错误码规范
ERR_STALE_CONTEXT = "STALE_CONTEXT"
ERR_EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
ERR_REVISION_CONFLICT = "REVISION_CONFLICT"
ERR_UNCONFIGURED = "UNCONFIGURED"


def _make_proposal_id(prefix: str, data: str) -> str:
    h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}"


def _semantic_content_digest(candidate: dict) -> str:
    """Identity of a candidate must bind its semantic content (D-C-02).

    Two planning candidates for the same workspace with a different number of
    nodes or different titles/roles are different candidates: they must not
    share one proposalId, or a later apply/review step can silently target the
    wrong content. This digest covers the graph candidate and, for planning,
    the requirement basis — never layout or run timing.
    """
    import json as _json
    material = {
        "mode": candidate.get("mode"),
        "codeRepoId": candidate.get("codeRepoId"),
        "codeRevision": candidate.get("codeRevision"),
        "graphCandidate": candidate.get("graphCandidate"),
    }
    canonical = _json.dumps(material, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def generate_bootstrap_proposal(context: dict) -> dict:
    """生成初版架构候选（Bootstrap）。

    支持 existing_project、planning 与 mixed 三种模式。
    """
    mode = context.get("mode", "existing_project")
    workspace_id = context.get("workspaceId", f"ws_{uuid.uuid4().hex[:8]}")

    if mode == "planning":
        # 无项目规划模式：codeRepoId 与 codeRevision 必须为 null
        goals = context.get("goals", [])

        nodes = []
        for idx, goal in enumerate(goals):
            node_id = f"plan_node_{idx + 1}"
            nodes.append({
                "nodeId": node_id,
                "title": goal.get("title", f"规划功能 {idx + 1}"),
                "role": goal.get("description", "待实现需求"),
                "status": "planned",
                "evidence": [
                    {
                        "kind": "user_requirement",
                        "id": goal.get("id", f"req_{idx + 1}"),
                        "detail": goal.get("detail", "由用户目标驱动")
                    }
                ],
                "interfaces": goal.get("interfaces", []),
                "expectedProcesses": goal.get("processes", [])
            })

        proposal = {
            "proposalId": "",
            "workspaceId": workspace_id,
            "mode": "planning",
            "kind": "rule_based",
            "status": "ok",
            "codeRepoId": None,
            "codeRevision": None,
            "verifiedCodeRevision": None,
            "graphCandidate": {
                "nodes": nodes,
                "relations": context.get("plannedRelations", [])
            },
            "warnings": []
        }
        # the id binds the semantic content of this candidate, not just the
        # workspace and node count (D-C-02): different goals → different id
        proposal["proposalId"] = "prop_boot_plan_" + _semantic_content_digest(proposal)
        return proposal

    # 已有项目或混合模式
    repo_id = context.get("codeRepoId")
    code_rev = context.get("codeRevision")
    if not repo_id or not code_rev:
        return {
            "status": "error",
            "errorCode": ERR_STALE_CONTEXT,
            "message": "existing_project 模式必须提供 codeRepoId 与 codeRevision"
        }

    facts = context.get("facts", {})
    symbols = facts.get("symbols", [])
    nodes = []

    # 按包路径/功能对符号做有界聚类
    clusters = {}
    for sym in symbols:
        path = sym.get("path", "root")
        top_pkg = path.split("/")[0] if "/" in path else "root"
        clusters.setdefault(top_pkg, []).append(sym)

    for pkg_name, sym_list in clusters.items():
        clean_name = pkg_name.replace(".", "_")
        node_id = f"node_{clean_name}"
        evidence_items = [
            {
                "kind": "source_symbol",
                "path": s.get("path"),
                "symbol": s.get("qualified_name") or s.get("name")
            }
            for s in sym_list[:5]  # 取前 5 项关键事实作为证据
        ]
        nodes.append({
            "nodeId": node_id,
            "title": f"模块: {pkg_name}",
            "role": f"管理 {pkg_name} 核心逻辑，包含 {len(sym_list)} 个已识别代码符号",
            "status": "implemented",
            "evidence": evidence_items,
            "interfaces": [s.get("name") for s in sym_list if s.get("kind") in ("function", "class")][:3],
            "expectedProcesses": []
        })

    proposal = {
        "proposalId": "",
        "workspaceId": workspace_id,
        "mode": mode,
        "kind": "rule_based",
        "status": "ok",
        "codeRepoId": repo_id,
        "codeRevision": code_rev,
        "graphCandidate": {
            "nodes": nodes,
            "relations": []
        },
        "warnings": []
    }
    # same rule as planning: the id binds the candidate content, so two
    # different clusterings of one revision cannot share an identity (D-C-02)
    proposal["proposalId"] = "prop_boot_code_" + _semantic_content_digest(proposal)
    return proposal


def generate_nl_correction_patch(base_graph: dict, selection: dict, prompt: str) -> dict:
    """根据自然语言纠错指令生成局部 Patch。

    严格保留未选中的节点与属性，绑定 baseMapRevision。
    """
    base_rev = base_graph.get("mapRevision", "rev_initial")
    nodes = base_graph.get("nodes", [])
    target_node_id = selection.get("nodeId")

    operations = []
    found = False
    for node in nodes:
        if node.get("nodeId") == target_node_id:
            found = True
            old_role = node.get("role", "")
            new_role = f"{old_role}; [纠正]: {prompt}".strip("; ")
            operations.append({
                "op": "update_node",
                "nodeId": target_node_id,
                "changes": {
                    "role": new_role
                },
                "reason": f"用户自然语言指令修正: {prompt}"
            })

    if not found:
        return {
            "status": "error",
            "errorCode": ERR_EVIDENCE_MISMATCH,
            "message": f"所选节点 {target_node_id} 在 baseMapRevision 中未找到"
        }

    return {
        "proposalId": _make_proposal_id("prop_nl", f"{base_rev}_{target_node_id}_{prompt}"),
        "kind": "rule_based",
        "status": "ok",
        "baseMapRevision": base_rev,
        "operations": operations,
        "confidence": 0.95,
        "warnings": []
    }


def generate_incremental_proposal(base_graph: dict, base_code_rev: str, target_code_rev: str, facts_diff: dict) -> dict:
    """增量更新提案：比对代码变更，输出标准化 Patch。

    严守 no_map_write 只读约束。
    """
    base_map_rev = base_graph.get("mapRevision")
    current_graph_rev = base_graph.get("codeRevision")
    if current_graph_rev and current_graph_rev != base_code_rev:
        return {
            "status": "error",
            "errorCode": ERR_STALE_CONTEXT,
            "message": f"图基线代码版本 {current_graph_rev} 与请求基线 {base_code_rev} 不一致"
        }

    operations = []
    # 1. 新增文件 -> add_node
    for added_file in facts_diff.get("added_files", []):
        clean_file = added_file.replace("/", "_").replace(".py", "")
        node_id = f"node_{clean_file}"
        operations.append({
            "op": "add_node",
            "nodeId": node_id,
            "data": {
                "title": f"新增模块 {added_file}",
                "role": "新增代码文件对应的功能职责",
                "status": "implemented",
                "evidence": [{"kind": "file", "path": added_file}]
            }
        })

    # 2. 修改文件 -> update_node
    for modified_file in facts_diff.get("modified_files", []):
        operations.append({
            "op": "update_node",
            "file": modified_file,
            "changes": {"evidence_refresh": True},
            "reason": f"源码文件 {modified_file} 发生修改，需更新事实证据"
        })

    # 3. 删除文件 -> remove_node
    for deleted_file in facts_diff.get("deleted_files", []):
        clean_del = deleted_file.replace("/", "_").replace(".py", "")
        node_id = f"node_{clean_del}"
        operations.append({
            "op": "remove_node",
            "nodeId": node_id,
            "reason": f"源码文件 {deleted_file} 已在目标代码提交中删除"
        })

    return {
        "proposalId": _make_proposal_id("prop_inc", f"{base_map_rev}_{base_code_rev}_{target_code_rev}"),
        "kind": "rule_based",
        "status": "ok",
        "baseMapRevision": base_map_rev,
        "targetCodeRevision": target_code_rev,
        "operations": operations,
        "confidence": 0.90,
        "warnings": []
    }


def detect_process_deviations(graph: dict, observed_traces: list) -> dict:
    """期望过程偏差检测。

    对照图上已确认的过程步骤与实际追踪证据。
    若无运行时追踪证据，如实返回 UNKNOWN，不将静态导入伪装成调用链。

    证据身份先于结论（D-C-01）：一条轨迹只有在其声明的 codeRepoId /
    codeRevision 与图一致、且确实覆盖了该节点声明的步骤时，才能支撑
    ALIGNED / DEVIATION_DETECTED；错仓、错 SHA、无关轨迹或缺少预期步骤
    的输入被记录为 rejected/inconclusive，整体结论保持 UNKNOWN，绝不误报
    ALIGNED。
    """
    if not observed_traces:
        return {
            "status": "ok",
            "verdict": "UNKNOWN",
            "deviations": [],
            "rejectedTraces": [],
            "coveredNodes": [],
            "reason": "缺少可验证的运行时执行追踪数据；静态导入关系不代表运行时执行调用链。"
        }

    expected_repo = graph.get("codeRepoId")
    expected_revision = graph.get("codeRevision")
    usable: list[tuple[int, dict]] = []
    rejected: list[dict] = []
    if expected_repo is None and expected_revision is None:
        # There is no repository/revision to check the observation against
        # (e.g. a planning/design process): the identity of the evidence can
        # not be verified, so no verdict beyond UNKNOWN may be reported
        # (FINAL-R2-C-01).
        return {
            "status": "ok",
            "verdict": "UNKNOWN",
            "deviations": [],
            "rejectedTraces": [{"traceIndex": index,
                                "reason": "声明过程没有可核对的仓库/版本身份，观察轨迹无法归属"}
                               for index in range(len(observed_traces))],
            "inconclusive": [],
            "coveredNodes": [],
            "reason": "图没有给出可核对的 codeRepoId/codeRevision；无身份的观察不能判定一致或偏差，"
                      "结论保持 UNKNOWN。",
            "warnings": [],
        }
    for index, trace in enumerate(observed_traces):
        if not isinstance(trace, dict) or not isinstance(trace.get("called_steps"), list) \
                or len(trace['called_steps']) > 200 or not all(isinstance(step, str) and len(step) <= 200
                                                              for step in trace['called_steps']):
            rejected.append({"traceIndex": index, "reason": "轨迹缺少 called_steps 列表，无法作为观察证据"})
            continue
        if expected_repo is not None and trace.get("codeRepoId") != expected_repo:
            rejected.append({"traceIndex": index, "reason": "轨迹声明的是另一个代码仓库身份（codeRepoId 不匹配或未声明）",
                             "traceRepoId": trace.get("codeRepoId"), "expectedRepoId": expected_repo})
            continue
        if expected_revision is not None and trace.get("codeRevision") != expected_revision:
            rejected.append({"traceIndex": index, "reason": "轨迹记录的是另一个代码版本（codeRevision 不匹配或未声明）",
                             "traceRevision": trace.get("codeRevision"), "expectedRevision": expected_revision})
            continue
        usable.append((index, trace))

    deviations = []
    covered_nodes: set[str] = set()
    inconclusive: list[dict] = []
    for node in graph.get("nodes", []):
        expected_steps = node.get("expectedProcesses", [])
        if len(expected_steps) < 2:
            continue
        for index, trace in usable:
            called_steps = trace.get("called_steps", [])
            target_id = node.get("nodeId")
            if not set(called_steps) & set(expected_steps):
                # the trace says nothing about this node's declared process:
                # it can neither confirm nor deny it
                inconclusive.append({"traceIndex": index, "nodeId": target_id,
                                     "reason": "轨迹未覆盖该节点声明的任何步骤，不足以判断一致性"})
                continue
            # A trace is conclusive only when it contains the *whole* declared
            # chain. A partial observation (e.g. only the last step ran) is not
            # evidence of alignment — it is either a bypass or insufficient
            # evidence, never ALIGNED (FINAL-C-01).
            missing = [step for step in expected_steps if step not in called_steps]
            if missing:
                # report the first declared step that never ran (and the step
                # that should have led into it, when that one did run)
                first_missing = next(index_ for index_, step in enumerate(expected_steps)
                                     if step not in called_steps)
                prior = expected_steps[first_missing - 1] if first_missing > 0 else None
                if prior is None and not any(step in called_steps for step in expected_steps):
                    inconclusive.append({"traceIndex": index, "nodeId": target_id,
                                         "reason": "轨迹只包含不在声明链上的步骤，无法定位偏差"})
                    continue
                deviations.append({
                    "deviationId": f"dev_{target_id}_{prior or 'start'}_{missing[0]}",
                    "nodeId": target_id,
                    # an executed step whose declared successor did not run is
                    # the classic bypass; a chain that never started at its
                    # first step is an incomplete chain
                    "type": "bypassed_step" if prior else "incomplete_chain",
                    "expectedStep": missing[0],
                    "priorStep": prior,
                    "missingSteps": missing,
                    "evidence": trace,
                    "recommendation": "可选择【修正认知】更新期望执行过程，或【修正实现】创建代码补丁任务。"
                })
                continue
            positions = [called_steps.index(step) for step in expected_steps]
            if positions != sorted(positions):
                reversed_pair = next(
                    (expected_steps[i], expected_steps[i + 1])
                    for i in range(len(expected_steps) - 1)
                    if called_steps.index(expected_steps[i]) > called_steps.index(expected_steps[i + 1]))
                deviations.append({
                    "deviationId": f"dev_{target_id}_{reversed_pair[0]}_{reversed_pair[1]}",
                    "nodeId": target_id,
                    "type": "out_of_order",
                    "expectedStep": reversed_pair[1],
                    "priorStep": reversed_pair[0],
                    "evidence": trace,
                    "recommendation": "可选择【修正认知】更新期望执行过程，或【修正实现】创建代码补丁任务。"
                })
                continue
            covered_nodes.add(target_id)

    if deviations:
        verdict = "DEVIATION_DETECTED"
        reason = ""
    elif covered_nodes:
        verdict = "ALIGNED"
        reason = "轨迹完整包含这些节点声明的步骤链且顺序一致；一致性仅在覆盖范围内成立。"
    else:
        verdict = "UNKNOWN"
        reason = ("没有一条轨迹覆盖图上声明的期望步骤，或轨迹来自其他仓库/版本；"
                  "证据不足时不报告 ALIGNED。")
    return {
        "status": "ok",
        "verdict": verdict,
        "deviations": deviations,
        "rejectedTraces": rejected,
        "inconclusive": inconclusive[:20],
        "coveredNodes": sorted(covered_nodes),
        "reason": reason,
        "warnings": [],
    }
