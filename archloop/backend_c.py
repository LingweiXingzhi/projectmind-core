"""Adapter to C's candidate module (extensions/map_proposal/candidates.py, PR #53).

C owns the candidate algorithms; A only converts their output into the
workbench's graph/operation shapes, keeps the `rule_based` marking and never
lets a candidate write itself into a draft (the user applies it explicitly).
The module is imported only when it actually answers; a missing or broken C
module is reported as unavailable instead of being faked.
"""
from __future__ import annotations

import importlib

from .contract import ContractError, ID_PATTERN, validate_graph

REF = "C PR #53 — 55ea6466583d98e0f466e5d4055922ef4aeecb12 (candidates.py)"


def _candidates_module():
    try:
        return importlib.import_module("extensions.map_proposal.candidates")
    except Exception as exc:
        raise ContractError("BACKEND_UNAVAILABLE",
                            f"C 候选模块不可用：{type(exc).__name__}: {exc}") from exc


def c_status() -> dict:
    try:
        module = _candidates_module()
    except ContractError as exc:
        return {"available": False, "kind": "unavailable", "ref": REF, "reason": str(exc)}
    functions = [name for name in ("generate_bootstrap_proposal", "generate_incremental_proposal",
                                   "generate_nl_correction_patch", "detect_process_deviations")
                 if callable(getattr(module, name, None))]
    return {"available": bool(functions), "kind": "extension:map_proposal", "ref": REF,
            "functions": functions,
            "labeled": "C 的规则候选模块（rule_based，只读；候选不直接写入草稿）"}


def _clean_id(value: str, fallback: str) -> str:
    """C's ids are its own; the workbench needs contract-legal stable ids."""
    if isinstance(value, str) and ID_PATTERN.fullmatch(value):
        return value
    slug = "".join(ch for ch in str(value or "") if ch.isascii() and (ch.isalnum() or ch in "_.-"))
    candidate = f"c_{slug[:40]}" if slug else fallback
    return candidate if ID_PATTERN.fullmatch(candidate) else fallback


def _evidence_from_c(items, fallback_node: str) -> list:
    out = []
    for item in items or []:
        kind = item.get("kind")
        detail = item.get("detail") or item.get("symbol") or item.get("id") or kind or "C 候选依据"
        if kind == "user_requirement":
            out.append({"path": str(detail), "reason": "C 规则候选：用户需求依据", "kind": "requirement"})
        elif kind in ("source_symbol", "file"):
            path = item.get("path") or ""
            symbol = item.get("symbol")
            if not path:
                out.append({"path": f"C 候选依据：{detail}", "reason": "C 规则候选缺少可核查路径",
                            "kind": "unknown"})
            else:
                out.append({"path": path,
                            "reason": f"C 规则候选：源码符号 {symbol}" if symbol else "C 规则候选：源码文件",
                            "kind": "code_fact"})
        else:
            out.append({"path": str(detail), "reason": "C 规则候选：未知依据", "kind": "unknown"})
    if not out:
        out.append({"path": f"C 候选：{fallback_node} 未提供依据", "reason": "C 输出没有证据项", "kind": "unknown"})
    return out


def candidate_to_graph(candidate: dict, *, context: str) -> tuple[dict, list]:
    """Convert C's graphCandidate/operations into an A-shaped candidate graph."""
    graph_candidate = candidate.get("graphCandidate") or {}
    nodes = []
    for index, node in enumerate(graph_candidate.get("nodes", []) or []):
        node_id = _clean_id(node.get("nodeId"), f"c_node_{index + 1}")
        # C's "planned" is a proposal, not a human confirmation: it must never
        # render as 设计已确认 before review (BATCH-1C C-02)
        planned = (candidate.get("mode") == "planning") or node.get("status") == "planned"
        nodes.append({
            "id": node_id,
            "title": node.get("title") or node_id,
            "summary": node.get("role") or "（C 候选未填写职责）",
            "status": "candidate",
            "provenance": "rule_based",
            "entryPoints": [item for item in (node.get("interfaces") or []) if isinstance(item, str)][:20],
            "interfaces": [],
            "evidence": _evidence_from_c(node.get("evidence"), node_id),
            "process": _steps_from_c(node.get("expectedProcesses"), node_id),
            "assumptions": list(node.get("assumptions", []) or []),
        })
    ids = {node["id"] for node in nodes}
    edges = []
    for relation in graph_candidate.get("relations", []) or []:
        source = _clean_id(relation.get("from") or relation.get("source"), "")
        target = _clean_id(relation.get("to") or relation.get("target"), "")
        if source in ids and target in ids:
            edges.append({"from": source, "to": target,
                          "type": relation.get("type") or "functional_collaboration",
                          "label": relation.get("label") or "C 候选关系"})
    graph = {"nodes": nodes, "edges": edges}
    warnings = list(candidate.get("warnings", []) or [])
    if not nodes:
        raise ContractError("BACKEND_UNAVAILABLE", "C 候选没有产生任何功能节点")
    validate_graph(graph)
    return graph, warnings


def _steps_from_c(processes, node_id: str) -> list:
    steps = []
    for index, step in enumerate(processes or []):
        if isinstance(step, str):
            step = {"stepId": f"s{index + 1}", "title": step}
        step_id = _clean_id(step.get("stepId") or step.get("id"), f"s{index + 1}")
        if any(existing["stepId"] == step_id for existing in steps):
            step_id = f"{step_id}_{index + 1}"
        steps.append({
            "stepId": step_id,
            "title": step.get("title") or step.get("name") or step_id,
            "detail": step.get("detail", ""),
            "inputs": [str(x) for x in (step.get("inputs", []) or [])],
            "outputs": [str(x) for x in (step.get("outputs", []) or [])],
            "branches": [str(x) for x in (step.get("branches", []) or [])],
            "next": [str(x) for x in (step.get("next", []) or [])],
        })
    return steps


def bootstrap_candidate(context: dict, record: dict) -> dict:
    """Run C's bootstrap for one workspace context (read-only)."""
    module = _candidates_module()
    request = {
        "mode": context,
        "workspaceId": record["workspaceId"],
        "codeRepoId": record["identity"].get("codeRepoId"),
        "codeRevision": record["identity"].get("codeRevision"),
        "goals": [{"title": goal, "description": goal, "id": f"req_{index + 1}"}
                  for index, goal in enumerate(_goal_lines(record))],
    }
    facts = record.get("lastContextPack") or {}
    request["facts"] = {"symbols": [
        {"path": item["path"], "name": symbol.get("name"), "kind": symbol.get("kind"),
         "qualified_name": symbol.get("qualified")}
        for item in facts.get("files", []) for symbol in item.get("symbols", [])[:10]]}
    try:
        candidate = module.generate_bootstrap_proposal(request)
    except Exception as exc:
        raise ContractError("BACKEND_UNAVAILABLE",
                            f"C 候选模块调用失败：{type(exc).__name__}: {exc}") from exc
    if candidate.get("status") != "ok":
        raise ContractError(
            "STALE_CONTEXT" if candidate.get("errorCode") == "STALE_CONTEXT" else "BACKEND_UNAVAILABLE",
            candidate.get("message") or "C 候选返回失败")
    graph, warnings = candidate_to_graph(candidate, context=context)
    return {"proposalId": candidate.get("proposalId"), "kind": "rule_based",
            "graph": graph, "warnings": warnings}


def _goal_lines(record: dict) -> list:
    lines = []
    for key in ("goals", "description", "constraints"):
        text = (record.get(key) or "").strip()
        if text:
            lines.extend([line.strip() for line in text.splitlines() if line.strip()])
    return lines[:20]


def nl_patch_candidate(base_graph: dict, node_id: str, instruction: str) -> dict:
    """C's rule-based correction patch -> A operations (labeled rule_based)."""
    module = _candidates_module()
    projected = {"mapRevision": base_graph.get("mapRevision"),
                 "nodes": [{"nodeId": node["id"], "role": node.get("summary", "")}
                           for node in base_graph.get("nodes", [])]}
    reply = module.generate_nl_correction_patch(projected, {"nodeId": node_id}, instruction)
    if reply.get("status") != "ok":
        raise ContractError("EVIDENCE_MISMATCH" if reply.get("errorCode") == "EVIDENCE_MISMATCH"
                            else "BACKEND_UNAVAILABLE",
                            reply.get("message") or "C 规则纠正返回失败")
    operations = []
    for operation in reply.get("operations", []) or []:
        if operation.get("op") == "update_node":
            changes = operation.get("changes", {}) or {}
            fields = {}
            if "role" in changes:
                fields["summary"] = changes["role"]
            elif "summary" in changes:
                fields["summary"] = changes["summary"]
            if fields:
                operations.append({"type": "update_node", "nodeId": operation.get("nodeId"),
                                   "fields": fields,
                                   "reason": operation.get("reason") or "C 规则纠正"})
    if not operations:
        raise ContractError("BACKEND_UNAVAILABLE", "C 规则纠正没有返回可应用的操作")
    return {"proposalId": reply.get("proposalId"), "kind": "rule_based",
            "operations": operations, "confidence": reply.get("confidence"),
            "warnings": list(reply.get("warnings", []) or [])}


def deviations_for(graph: dict, observed_traces: list) -> dict:
    """C's process-deviation detection on the current draft graph (read-only)."""
    module = _candidates_module()
    projected = {"nodes": [{"nodeId": node["id"],
                            "expectedProcesses": [step.get("stepId") for step in node.get("process", [])]}
                           for node in graph.get("nodes", [])]}
    reply = module.detect_process_deviations(projected, observed_traces or [])
    result = {"status": reply.get("status"), "verdict": reply.get("verdict"),
              "deviations": reply.get("deviations", []),
              "reason": reply.get("reason", ""),
              "labeled": "C 规则偏差检测：静态图与提供的追踪数据对照；无追踪证据时为 UNKNOWN"}
    for deviation in result["deviations"]:
        node_id = deviation.get("nodeId")
        title = next((node.get("title") for node in graph.get("nodes", []) if node["id"] == node_id), None)
        deviation["nodeTitle"] = title
        deviation["labeled"] = "规则候选：需要人来裁决，不代表已确认偏差"
    return result


def _incremental_ops_to_a(base_graph: dict, c_operations: list) -> tuple[list, list]:
    """Convert C's raw incremental patch into CONTRACT_V1 operations.

    C answers in its own patch vocabulary (`op`/`data`/`changes`); the workbench
    applies CONTRACT_V1 operations (`type`/`node`/`fields`/`nodeId`). Returning
    C's raw shape produced candidates that every apply path rejected with
    VALIDATION_FAILED (BATCH-2 C-INCREMENTAL-01).

    The returned operations are applicable **in the order they are emitted**,
    which is enforced here by simulating them on a working copy:
    - several changes to one node are merged into ONE update (a later update
      must not resurrect an earlier file's evidence — BATCH-3 C-INCREMENTAL-01);
    - a node still referenced by a relation is not removed (removing it would
      fail the graph contract); the change is reported as a warning instead;
    - derived ids that collide are made unique, and a collision that cannot be
      resolved becomes a warning, never a failing operation.
    Anything C proposed that has no applicable counterpart is reported as a
    warning instead of as a broken operation.
    """
    import copy as _copy
    from . import ops as ops_module

    base_graph = _copy.deepcopy(base_graph)
    nodes_by_id = {node["id"]: node for node in base_graph.get("nodes", []) or []}
    referenced = set()
    for edge in base_graph.get("edges", []) or []:
        referenced.add(edge.get("from"))
        referenced.add(edge.get("to"))
    operations: list = []
    warnings: list = []

    def emit(operation: dict, working: dict) -> bool:
        """Append only operations that really apply to the accumulated graph."""
        try:
            return_target = ops_module.apply_operation(working, operation)
        except ContractError as exc:
            warnings.append({"change": operation.get("type"),
                             "reason": f"候选操作在草稿上无法应用（{exc.code}）：{exc}"})
            return False
        working.clear()
        working.update(return_target)
        operations.append(operation)
        return True

    working: dict = {"nodes": base_graph.get("nodes", []), "edges": base_graph.get("edges", [])}
    # file path -> node ids whose evidence names it (the "modified" targets)
    evidence_paths = {}
    for node in base_graph.get("nodes", []) or []:
        for item in node.get("evidence", []) or []:
            if item.get("path"):
                evidence_paths.setdefault(item["path"], set()).add(node["id"])
    merged_updates: dict = {}          # node id -> {paths, reasons}
    planned_adds: list = []            # emitted before updates/removals
    planned_removes: list = []         # emitted last
    taken_ids = set(nodes_by_id)
    for operation in c_operations or []:
        kind = operation.get("op")
        if kind == "add_node":
            node_id = _clean_id(operation.get("nodeId"), "")
            data = operation.get("data") or {}
            if not node_id:
                warnings.append({"change": operation.get("nodeId"),
                                 "reason": "C 增量给出的节点 ID 不合法；未转成可应用操作"})
                continue
            unique_id = node_id
            suffix = 2
            while unique_id in taken_ids:
                unique_id = f"{node_id}_{suffix}"
                suffix += 1
                if suffix > 50:
                    unique_id = ""
                    break
            if not unique_id:
                warnings.append({"change": node_id,
                                 "reason": f"新增候选的节点 ID 无法唯一化（{node_id} 已占用）"})
                continue
            if unique_id != node_id:
                warnings.append({"change": node_id,
                                 "reason": f"节点 ID 已占用，新增候选改用 {unique_id}"})
            taken_ids.add(unique_id)
            planned_adds.append({
                "type": "add_node",
                "node": {
                    "id": unique_id,
                    "title": data.get("title") or unique_id,
                    "summary": data.get("role") or "（C 增量候选未填写职责）",
                    "status": "candidate",
                    "provenance": "rule_based",
                    "entryPoints": [], "interfaces": [], "assumptions": [], "process": [],
                    "evidence": _evidence_from_c(data.get("evidence"), unique_id),
                },
                "reason": "C 规则增量：新增代码文件对应的职责候选"})
        elif kind == "update_node":
            path = operation.get("file")
            matched = [node_id for node_id, node in nodes_by_id.items()
                       if node_id in evidence_paths.get(path, set())]
            if not matched:
                warnings.append({"change": path,
                                 "reason": "草稿中没有节点的证据引用该文件；只登记变化，不产生操作"})
                continue
            for node_id in matched:
                entry = merged_updates.setdefault(node_id, {"paths": [], "reason": ""})
                if path not in entry["paths"]:
                    entry["paths"].append(path)
                entry["reason"] = operation.get("reason") or entry["reason"]
        elif kind == "remove_node":
            node_id = _clean_id(operation.get("nodeId"), "")
            if node_id not in nodes_by_id:
                warnings.append({"change": operation.get("nodeId"),
                                 "reason": f"草稿中没有节点 {node_id}；删除候选跳过（不猜测新建）"})
                continue
            if node_id in referenced:
                warnings.append({"change": node_id,
                                 "reason": f"节点 {node_id} 仍被关系引用；删除候选跳过"
                                           "（请先处理关系，避免不可应用的破坏性操作）"})
                continue
            planned_removes.append({"type": "remove_node", "nodeId": node_id,
                                    "reason": operation.get("reason") or "源码文件已在目标提交中删除"})
        else:
            warnings.append({"change": kind,
                             "reason": "C 增量返回了适配层不认识的操作；未转成可应用操作"})
    # emission order is adds -> updates -> removes: every operation is checked
    # against the accumulated graph, so a statement C contradicted itself about
    # (modified AND deleted) still degrades to a warning instead of a failure
    # (BATCH-3 C-INCREMENTAL-01)
    for operation in planned_adds:
        emit(operation, working)
    # one merged evidence refresh per node: applying them keeps every earlier
    # file's downgrade
    for node_id, entry in merged_updates.items():
        node = nodes_by_id[node_id]
        paths = set(entry["paths"])
        refreshed = []
        changed = False
        for item in node.get("evidence", []) or []:
            if item.get("path") in paths and item.get("kind", "code_fact") == "code_fact":
                changed = True
                # the fixed revision this fact was checked against no longer
                # contains the file as reviewed: it must be re-checked before
                # it counts again
                refreshed.append({**item, "kind": "unknown",
                                  "reason": f"{item.get('reason', '')}"
                                            f"（源码文件在目标提交中已修改，需按新提交复核）"})
            else:
                refreshed.append(item)
        if not changed:
            warnings.append({"change": "/".join(sorted(paths)),
                             "reason": f"节点 {node_id} 的证据没有可刷新的代码事实"})
            continue
        emit({"type": "update_node", "nodeId": node_id, "fields": {"evidence": refreshed},
              "reason": entry["reason"] or f"源码文件 {'/'.join(sorted(paths))} 发生修改，需更新事实证据"},
             working)
    for operation in planned_removes:
        emit(operation, working)
    return operations, warnings


def incremental_candidate(base_graph: dict, base_code_revision: str, target_code_revision: str,
                          facts_diff: dict) -> dict:
    """C's incremental proposal -> CONTRACT_V1 operations for review (read-only)."""
    module = _candidates_module()
    graph_input = {"mapRevision": base_graph.get("mapRevision"),
                   "codeRevision": base_code_revision,
                   "nodes": [{"nodeId": node["id"]} for node in base_graph.get("nodes", [])]}
    reply = module.generate_incremental_proposal(graph_input, base_code_revision,
                                                 target_code_revision, facts_diff or {})
    if reply.get("status") != "ok":
        raise ContractError("STALE_CONTEXT" if reply.get("errorCode") == "STALE_CONTEXT"
                            else "BACKEND_UNAVAILABLE",
                            reply.get("message") or "C 增量提案返回失败")
    operations, conversion_warnings = _incremental_ops_to_a(base_graph, reply.get("operations", []))
    return {"proposalId": reply.get("proposalId"), "kind": "rule_based",
            "baseMapRevision": reply.get("baseMapRevision"),
            "targetCodeRevision": reply.get("targetCodeRevision"),
            "operations": operations,
            "warnings": list(reply.get("warnings", []) or []) + conversion_warnings,
            "labeled": "C 规则增量候选：按文件变化定位待复核对象，不代表认知已更新"}


__all__ = ["c_status", "bootstrap_candidate", "nl_patch_candidate", "deviations_for",
           "incremental_candidate", "candidate_to_graph", "REF"]