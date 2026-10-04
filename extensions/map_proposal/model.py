"""C / Map Proposal v0.1 — deterministic, evidence-backed proposal engine.

Boundary (C_PRODUCT_BOUNDARY): C only proposes; it never writes the map, never
accepts its own proposals, never re-implements B, and never arbitrates conflicts.
"""
from __future__ import annotations

import re

SHA_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
MAX_CHANGES = 2000
MAX_PATH_LENGTH = 512
MAX_NODES = 2000
MAX_PRIOR_DECISIONS = 1000
STATUSES = ("added", "modified", "removed", "renamed")
EVIDENCE_KINDS = ("git_diff", "code_fact", "map_node", "context_claim")


class RequestError(ValueError):
    """Invalid SuggestMapRequest; safe to surface as 400."""


def _bounded_text(value, limit, label, required=False):
    if value is None:
        if required:
            raise RequestError(f"{label} 必填")
        return ""
    if not isinstance(value, str):
        raise RequestError(f"{label} 须为文本")
    if len(value) > limit:
        raise RequestError(f"{label} 最长 {limit} 字符")
    return value


def validate_path(path, label="path"):
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH:
        raise RequestError(f"{label} 须为非空短文本")
    if "\\" in path or (path[0] == "/" if path else False) or             (len(path) > 1 and path[1] == ":") or             any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise RequestError(f"{label} 须为仓库内相对路径")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise RequestError(f"{label} 不能含 .. 或空段")
    return path


def validate_request(request):
    if not isinstance(request, dict):
        raise RequestError("SuggestMapRequest 须为 JSON 对象")
    for key in ("base_revision", "target_revision"):
        value = request.get(key)
        if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
            raise RequestError(f"{key} 必须是完整的 40/64 位小写 Git SHA")
    changes = request.get("changed_paths")
    if not isinstance(changes, list):
        raise RequestError("changed_paths 须为列表")
    if len(changes) > MAX_CHANGES:
        raise RequestError(f"changed_paths 最多 {MAX_CHANGES} 项")
    if not changes and request.get("base_revision") != request.get("target_revision"):
        raise RequestError("changed_paths 须为非空列表")
    parsed = []
    for item in changes:
        if not isinstance(item, dict):
            raise RequestError("changed_paths 项须为对象")
        path = validate_path(item.get("path"), "changed path")
        status = item.get("status")
        if status not in STATUSES:
            raise RequestError("changed path status 须为 added|modified|removed|renamed")
        old_path = None
        if status == "renamed":
            old_path = validate_path(item.get("old_path"), "renamed old_path")
        parsed.append({"path": path, "status": status, "old_path": old_path})
    prior = request.get("prior_decisions") or []
    if not isinstance(prior, list) or len(prior) > MAX_PRIOR_DECISIONS:
        raise RequestError(f"prior_decisions 须为最多 {MAX_PRIOR_DECISIONS} 项的列表")
    for item in prior:
        if not isinstance(item, dict):
            raise RequestError("prior_decisions 项须为对象")
        _bounded_text(item.get("subject"), MAX_PATH_LENGTH, "prior subject", True)
        _bounded_text(item.get("kind"), 64, "prior kind", True)
        if item.get("decision") not in ("REJECTED", "ACCEPTED", "DEFERRED"):
            raise RequestError("prior decision 须为 REJECTED|ACCEPTED|DEFERRED")
    return {"base_revision": request["base_revision"],
            "target_revision": request["target_revision"],
            "changed_paths": parsed,
            "prior_decisions": prior,
            "code_facts": request.get("code_facts"),
            "current_map": request.get("current_map"),
            "context_pack": request.get("context_pack")}


def validate_map(current_map):
    if not isinstance(current_map, dict):
        raise RequestError("current_map 须为对象")
    nodes = current_map.get("nodes")
    edges = current_map.get("edges")
    if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
        raise RequestError("current_map 须含非空 nodes 与 edges 列表")
    if len(nodes) > MAX_NODES:
        raise RequestError(f"current_map 最多 {MAX_NODES} 个节点")
    parsed_nodes, ids = [], set()
    for node in nodes:
        if not isinstance(node, dict):
            raise RequestError("map node 须为对象")
        node_id = _bounded_text(node.get("id"), 200, "node id", True)
        if node_id in ids:
            raise RequestError(f"map 节点 id 重复: {node_id}")
        ids.add(node_id)
        evidence_paths = []
        evidence = node.get("evidence") or []
        if not isinstance(evidence, list):
            raise RequestError("node evidence 须为列表")
        for item in evidence:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise RequestError("node evidence 项须含 path")
            evidence_paths.append(item["path"])
        parsed_nodes.append({"id": node_id,
                             "title": _bounded_text(node.get("title"), 200, "node title", True),
                             "entry_point": _bounded_text(node.get("entryPoint"), 300, "entryPoint", True),
                             "evidence_paths": evidence_paths})
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") not in ids or edge.get("to") not in ids:
            raise RequestError("map edge 须引用已知节点")
    return {"nodes": parsed_nodes, "edges": edges, "has_version_identity": False}


def parse_entry_point(entry_point):
    """"path · func()" → (path, func);否则 (None, None)。"""
    if "·" in entry_point:
        path, _, func = entry_point.partition("·")
        return path.strip(), func.strip().split("(")[0].strip()
    head = entry_point.split()[0] if entry_point else ""
    if head.endswith(".py"):
        return head, None
    return None, None


def make_evidence(kind, revision=None, path=None, detail="", claim_id=None, claim_scope=None,
                  unverified=False):
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"unknown evidence kind {kind}")
    entry = {"kind": kind, "detail": str(detail)[:400]}
    if revision is not None:
        entry["revision"] = revision
    if path is not None:
        entry["path"] = path
    if kind == "context_claim":
        entry["claim_id"] = claim_id
        entry["claim_scope"] = claim_scope
        if unverified:
            entry["verification"] = "UNVERIFIED"
    return entry


def make_proposal(seq, target_revision, kind, subject, proposed_change, rationale,
                  evidence, confidence, uncertainty):
    return {"proposal_id": f"mp-{target_revision[:8]}-{seq:02d}",
            "kind": kind,
            "subject": subject,
            "proposed_change": proposed_change,
            "rationale": rationale[:600],
            "evidence": evidence,
            "confidence": confidence,
            "uncertainty": [str(item)[:300] for item in uncertainty],
            "status": "PROPOSED",
            "human_required": True}
