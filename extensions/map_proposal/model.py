# -*- coding: utf-8 -*-
"""C convergence primitives: pins, paths, map intake, stable identity, evidence.

Ported from LOCAL model.py @5058c54 (P02/P07) with R06 identity changes:
- proposal IDs are stable short hashes of (target, kind, subject, payload),
  not sequence numbers (DROP L09);
- node IDs hash the full repo-relative path with deterministic collision
  widening against the existing map ID set.
"""
from __future__ import annotations

import hashlib
import json
import re

SHA_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
MAX_CHANGES = 2000
MAX_PATH_LENGTH = 512
MAX_NODES = 2000
MAX_PRIOR_DECISIONS = 1000
STATUSES = ("added", "modified", "removed", "renamed")
EVIDENCE_KINDS = ("git_diff", "code_fact", "map_node", "context_claim")
PROPOSAL_KINDS = (
    "NODE_ADD",
    "RELATION_ADD",
    "RELATION_REMOVE_CANDIDATE",
    "IMPLEMENTATION_LINK_CHANGE",
    "NODE_REMOVE_CANDIDATE",
    "RESPONSIBILITY_CHANGE",
)


class RequestError(ValueError):
    """Invalid SuggestMapRequest; safe to surface as a controlled 400."""


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
    """Repository-relative safe path: no backslash, no drive, no absolute, no .. segments."""
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LENGTH:
        raise RequestError(f"{label} 须为非空短文本")
    if "\\" in path or path[0] == "/" or (len(path) > 1 and path[1] == ":") or any(
        ord(c) < 32 or ord(c) == 127 for c in path
    ):
        raise RequestError(f"{label} 须为仓库内相对路径")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise RequestError(f"{label} 不能含 .. 或空段")
    return path


def _pin(request, key):
    value = request.get(key)
    if value is None:
        raise RequestError(f"{key} 缺失：请求必须携带完整 pin，不得从 snapshot 补值")
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise RequestError(f"{key} 必须是完整的 40/64 位小写 Git SHA")
    return value


def validate_request(request):
    """Validate the canonical C request shape (C_INPUT_OUTPUT_CONTRACT_PROPOSAL)."""
    if not isinstance(request, dict):
        raise RequestError("SuggestMapRequest 须为 JSON 对象")
    base = _pin(request, "base_revision")
    target = _pin(request, "target_revision")
    changes = request.get("changed_paths")
    if not isinstance(changes, list):
        raise RequestError("changed_paths 须为列表")
    if len(changes) > MAX_CHANGES:
        raise RequestError(f"changed_paths 最多 {MAX_CHANGES} 项")
    if not changes and base != target:
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
    return {
        "base_revision": base,
        "target_revision": target,
        "changed_paths": parsed,
        "prior_decisions": prior,
        "code_facts": request.get("code_facts"),
        "current_map": request.get("current_map"),
        "context_pack": request.get("context_pack"),
        "context_pack_id": request.get("context_pack_id"),
    }


def adapt_core_compare(data):
    """Explicit adapter from Core compare shape
    ({baseRevision, targetRevision, changes:[{code, path, oldPath?}]}) to the
    canonical C request. C does not invent its own diff vocabulary (invariant 5).
    """
    if not isinstance(data, dict):
        raise RequestError("请求须为 JSON 对象")
    changes = data.get("changes")
    if changes is None:
        return data
    if not isinstance(changes, list):
        raise RequestError("changes 须为列表")
    mapped = []
    for item in changes:
        if not isinstance(item, dict):
            raise RequestError("changes 项须为对象")
        code = item.get("code")
        entry = {"path": item.get("path")}
        if isinstance(code, str) and code.startswith(("R", "C")):
            entry["status"] = "renamed"
            entry["old_path"] = item.get("oldPath")
        elif code == "A":
            entry["status"] = "added"
        elif code == "M":
            entry["status"] = "modified"
        elif code == "D":
            entry["status"] = "removed"
        else:
            entry["status"] = code
        mapped.append(entry)
    adapted = dict(data)
    if "base_revision" not in adapted and "baseRevision" in data:
        adapted["base_revision"] = data["baseRevision"]
    if "target_revision" not in adapted and "targetRevision" in data:
        adapted["target_revision"] = data["targetRevision"]
    adapted["changed_paths"] = mapped
    return adapted


def validate_map(current_map):
    """Intake the human map exactly as Core stores it: {note, nodes, edges}.

    Non-empty nodes is a Core property and is not relaxed for test doubles
    (invariant 6). Evidence paths are validated like every other path source
    (S28). The map carries no version identity (invariant 4).
    """
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
            evidence_paths.append(validate_path(item["path"], "map evidence path"))
        parsed_nodes.append(
            {
                "id": node_id,
                "title": _bounded_text(node.get("title"), 200, "node title"),
                "summary": _bounded_text(node.get("summary"), 2000, "node summary"),
                "entry_point": _bounded_text(node.get("entryPoint"), 300, "entryPoint"),
                "evidence_paths": evidence_paths,
            }
        )
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") not in ids or edge.get("to") not in ids:
            raise RequestError("map edge 须引用已知节点")
    return {"nodes": parsed_nodes, "edges": edges, "has_version_identity": False}


def parse_entry_point(entry_point):
    """"path · func()" → (path, func); otherwise (None, None)."""
    if "·" in entry_point:
        path, _, func = entry_point.partition("·")
        return path.strip(), func.strip().split("(")[0].strip()
    head = entry_point.split()[0] if entry_point else ""
    if head.endswith(".py"):
        return head, None
    return None, None


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def proposal_id_for(target_revision, kind, subject, proposed_change):
    """Stable ID: target + kind + normalized subject/payload short hash (R06)."""
    digest = hashlib.sha256(
        _canonical_json([target_revision, kind, subject, proposed_change]).encode("utf-8")
    ).hexdigest()[:12]
    return f"mp-{target_revision[:8]}-{digest}"


def node_id_for_path(path, existing_ids):
    """Deterministic node ID over the full repo-relative path, widened on
    collision with existing map IDs (F10/X09)."""
    for width in (10, 12, 16, 32, 64):
        candidate = "mapnode-" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:width]
        if candidate not in existing_ids:
            return candidate
    salt = 0
    while True:
        candidate = "mapnode-" + hashlib.sha256(
            f"{path}#{salt}".encode("utf-8")
        ).hexdigest()[:64]
        if candidate not in existing_ids:
            return candidate
        salt += 1


def make_evidence(kind, revision=None, path=None, detail="", claim_id=None, claim_scope=None,
                  unverified=False, name=None, line=None):
    """Evidence entry. code_fact carries structured path/name/line (R06, DROP T05)."""
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"unknown evidence kind {kind}")
    entry = {"kind": kind, "detail": str(detail)[:400]}
    if revision is not None:
        entry["revision"] = revision
    if path is not None:
        entry["path"] = path
    if name is not None:
        entry["name"] = name
    if line is not None:
        entry["line"] = line
    if kind == "context_claim":
        entry["claim_id"] = claim_id
        entry["claim_scope"] = claim_scope
        if unverified:
            entry["verification"] = "UNVERIFIED"
    return entry


def make_proposal(target_revision, kind, subject, proposed_change, rationale,
                  evidence, confidence, uncertainty):
    """Canonical proposal. K02 invariants enforced at construction time."""
    if kind not in PROPOSAL_KINDS:
        raise ValueError(f"unknown proposal kind {kind}")
    if not evidence:
        raise ValueError("proposal evidence 须非空")
    if not isinstance(proposed_change, dict):
        raise ValueError("proposed_change 须为对象")
    if "position" in proposed_change:
        raise ValueError("proposed_change 不得包含 position")
    return {
        "proposal_id": proposal_id_for(target_revision, kind, subject, proposed_change),
        "kind": kind,
        "subject": subject,
        "proposed_change": proposed_change,
        "rationale": str(rationale)[:600],
        "evidence": list(evidence),
        "confidence": confidence,
        "uncertainty": [str(item)[:300] for item in uncertainty],
        "status": "PROPOSED",
        "human_required": True,
    }
