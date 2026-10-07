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

        return {
            "proposalId": _make_proposal_id("prop_boot_plan", workspace_id + str(len(nodes))),
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

    return {
        "proposalId": _make_proposal_id("prop_boot_code", f"{repo_id}_{code_rev}"),
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
    """
    if not observed_traces:
        return {
            "status": "ok",
            "verdict": "UNKNOWN",
            "deviations": [],
            "reason": "缺少可验证的运行时执行追踪数据；静态导入关系不代表运行时执行调用链。"
        }

    deviations = []
    for node in graph.get("nodes", []):
        expected_steps = node.get("expectedProcesses", [])
        if len(expected_steps) < 2:
            continue

        for trace in observed_traces:
            called_steps = trace.get("called_steps", [])
            for idx in range(len(expected_steps) - 1):
                cur_step = expected_steps[idx]
                next_step = expected_steps[idx + 1]
                if cur_step in called_steps and next_step not in called_steps:
                    target_id = node.get("nodeId")
                    deviations.append({
                        "deviationId": f"dev_{target_id}_{cur_step}_{next_step}",
                        "nodeId": target_id,
                        "type": "bypassed_step",
                        "expectedStep": next_step,
                        "priorStep": cur_step,
                        "evidence": trace,
                        "recommendation": "可选择【修正认知】更新期望执行过程，或【修正实现】创建代码补丁任务。"
                    })

    return {
        "status": "ok",
        "verdict": "DEVIATION_DETECTED" if deviations else "ALIGNED",
        "deviations": deviations,
        "warnings": []
    }
