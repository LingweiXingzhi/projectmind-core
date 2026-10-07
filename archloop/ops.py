"""Draft operations and graph diff (CONTRACT_V1 op schema).

Operations are the single currency for direct edits, AI correction previews
and (later) C proposals / B draft persistence:
  add_node / update_node / remove_node
  add_edge / update_edge / remove_edge
  update_process  (full expected-process replacement for one node; step IDs
                   are preserved by callers, validation keeps them stable)

Every operation is validated against the graph contract before applying, and
applying is CAS-guarded by the caller via expectedDraftRevision (service.py).
"""
from __future__ import annotations

import copy

from .contract import ContractError, ID_PATTERN, EDGE_TYPES, NODE_STATUS, PROVENANCE, semantic_revision, validate_graph

OP_TYPES = ("add_node", "update_node", "remove_node", "add_edge", "update_edge", "remove_edge", "update_process")


def _ensure(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ContractError(code, message)


def apply_operation(graph: dict, op: dict) -> dict:
    """Return a NEW graph with the operation applied; input graph untouched."""
    _ensure(isinstance(op, dict) and op.get("type") in OP_TYPES, "VALIDATION_FAILED",
            f"操作 type 必须是 {OP_TYPES}")
    kind = op["type"]
    next_graph = copy.deepcopy(graph)
    nodes = next_graph["nodes"]
    edges = next_graph["edges"]
    index_by_id = {node["id"]: i for i, node in enumerate(nodes)}

    if kind == "add_node":
        node = op.get("node")
        _ensure(isinstance(node, dict), "VALIDATION_FAILED", "add_node 需要 node")
        _ensure(isinstance(node.get("id"), str) and ID_PATTERN.fullmatch(node.get("id", "")),
                "VALIDATION_FAILED", "新节点 ID 不合法")
        _ensure(node["id"] not in index_by_id, "VALIDATION_FAILED", f"节点已存在: {node['id']}")
        node.setdefault("provenance", "human_input")
        node.setdefault("status", "candidate")
        nodes.append(node)
    elif kind == "update_node":
        node_id = op.get("nodeId")
        _ensure(node_id in index_by_id, "NOT_FOUND", f"节点不存在: {node_id}")
        fields = op.get("fields")
        _ensure(isinstance(fields, dict) and fields, "VALIDATION_FAILED", "update_node 需要 fields")
        allowed = {"title", "summary", "status", "entryPoints", "interfaces", "evidence"}
        _ensure(set(fields) <= allowed, "VALIDATION_FAILED", f"可更新字段: {sorted(allowed)}")
        if "status" in fields:
            _ensure(fields["status"] in NODE_STATUS, "VALIDATION_FAILED", "status 不合法")
        nodes[index_by_id[node_id]] = {**nodes[index_by_id[node_id]], **fields}
    elif kind == "remove_node":
        node_id = op.get("nodeId")
        _ensure(node_id in index_by_id, "NOT_FOUND", f"节点不存在: {node_id}")
        _ensure(op.get("force") is True or not [e for e in edges if e["from"] == node_id or e["to"] == node_id],
                "VALIDATION_FAILED",
                "节点仍被关系引用；先删除关系或传 force（界面会先展示影响）")
        nodes = [node for node in nodes if node["id"] != node_id]
        edges = [edge for edge in edges if edge["from"] != node_id and edge["to"] != node_id]
        next_graph["nodes"], next_graph["edges"] = nodes, edges
    elif kind == "add_edge":
        edge = op.get("edge")
        _ensure(isinstance(edge, dict), "VALIDATION_FAILED", "add_edge 需要 edge")
        _ensure(edge.get("type") in EDGE_TYPES, "VALIDATION_FAILED", f"关系 type 必须是 {EDGE_TYPES}")
        _ensure(edge.get("from") in index_by_id and edge.get("to") in index_by_id,
                "NOT_FOUND", "关系端点必须指向已知节点")
        edges.append(edge)
    elif kind == "update_edge":
        match = op.get("match")
        _ensure(isinstance(match, dict), "VALIDATION_FAILED", "update_edge 需要 match{from,to,type}")
        found = None
        for i, edge in enumerate(edges):
            if edge["from"] == match.get("from") and edge["to"] == match.get("to") and edge["type"] == match.get("type"):
                found = i
                break
        _ensure(found is not None, "NOT_FOUND", "未找到匹配的关系")
        fields = op.get("fields")
        _ensure(isinstance(fields, dict) and fields, "VALIDATION_FAILED", "update_edge 需要 fields")
        _ensure(set(fields) <= {"type", "label"}, "VALIDATION_FAILED", "关系可更新字段: type/label")
        if "type" in fields:
            _ensure(fields["type"] in EDGE_TYPES, "VALIDATION_FAILED", f"关系 type 必须是 {EDGE_TYPES}")
        edges[found] = {**edges[found], **fields}
    elif kind == "remove_edge":
        match = op.get("match")
        _ensure(isinstance(match, dict), "VALIDATION_FAILED", "remove_edge 需要 match{from,to,type}")
        kept = [edge for edge in edges
                if not (edge["from"] == match.get("from") and edge["to"] == match.get("to")
                        and edge["type"] == match.get("type"))]
        _ensure(len(kept) < len(edges), "NOT_FOUND", "未找到匹配的关系")
        next_graph["edges"] = kept
    elif kind == "update_process":
        node_id = op.get("nodeId")
        _ensure(node_id in index_by_id, "NOT_FOUND", f"节点不存在: {node_id}")
        process = op.get("process")
        _ensure(isinstance(process, list), "VALIDATION_FAILED", "update_process 需要 process 列表")
        nodes[index_by_id[node_id]] = {**nodes[index_by_id[node_id]], "process": process}

    validate_graph(next_graph)
    next_graph["mapRevision"] = semantic_revision(next_graph)
    return next_graph


def node_impact(graph: dict, node_id: str) -> dict:
    """References that would break if node_id were removed (UI impact view)."""
    edges = [edge for edge in graph.get("edges", []) if edge["from"] == node_id or edge["to"] == node_id]
    process_refs = []
    for node in graph.get("nodes", []):
        for step in node.get("process", []):
            if node_id in [entry.split(":", 1)[-1] for entry in step.get("outputs", []) if isinstance(entry, str)]:
                process_refs.append({"nodeId": node["id"], "stepId": step.get("stepId")})
    return {"nodeId": node_id, "edges": edges, "processReferences": process_refs}


def diff_graphs(base: dict, target: dict) -> dict:
    """Structural diff used by previews and the review page."""
    base_nodes = {node["id"]: node for node in base.get("nodes", [])}
    target_nodes = {node["id"]: node for node in target.get("nodes", [])}
    changed_nodes = []
    for node_id in sorted(set(base_nodes) | set(target_nodes)):
        old, new = base_nodes.get(node_id), target_nodes.get(node_id)
        if old == new:
            continue
        if old is None:
            changed_nodes.append({"id": node_id, "change": "added", "title": new.get("title")})
        elif new is None:
            changed_nodes.append({"id": node_id, "change": "removed", "title": old.get("title")})
        else:
            fields = [key for key in ("title", "summary", "status", "entryPoints", "interfaces", "evidence", "process")
                      if old.get(key) != new.get(key)]
            changed_nodes.append({"id": node_id, "change": "updated", "title": new.get("title"), "fields": fields})
    base_edges = {(e["from"], e["to"], e["type"], e["label"]) for e in base.get("edges", [])}
    target_edges = {(e["from"], e["to"], e["type"], e["label"]) for e in target.get("edges", [])}
    changed_edges = {
        "added": [{"from": e[0], "to": e[1], "type": e[2], "label": e[3]} for e in sorted(target_edges - base_edges)],
        "removed": [{"from": e[0], "to": e[1], "type": e[2], "label": e[3]} for e in sorted(base_edges - target_edges)],
    }
    return {"nodes": changed_nodes, "edges": changed_edges,
            "baseMapRevision": base.get("mapRevision"), "targetMapRevision": target.get("mapRevision")}


def provenance_label(provenance: str) -> str:
    labels = {"code_fact": "代码事实", "ai_candidate": "AI 候选", "human_input": "人工输入",
              "rule_based": "规则候选"}
    return labels.get(provenance, provenance)


__all__ = ["OP_TYPES", "apply_operation", "diff_graphs", "node_impact", "provenance_label"]
