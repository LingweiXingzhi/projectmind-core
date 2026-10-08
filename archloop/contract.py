"""CONTRACT_V1: shared identity, provenance, error codes and graph schema rules.

Engineering contract for the architecture cognition loop (this round). It does
not override the repo's confirmed Project Model rules: AI proposes, humans
confirm; code facts are evidence, candidates are suggestions.
"""
from __future__ import annotations

import hashlib
import json
import re
from http import HTTPStatus

SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
# Same identifier rule as B's schema (extensions/architecture_workspace/schema.py)
# so one registered repository keeps one identity across both sides.
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,119}$")
STEP_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,119}$")

CONTEXTS = ("existing_project", "planning", "mixed")
EDGE_TYPES = ("static_reference", "functional_collaboration", "expected_sequence")
NODE_STATUS = ("candidate", "confirmed_design", "implemented")
PROVENANCE = ("code_fact", "ai_candidate", "human_input", "rule_based")
REVIEW_STATES = ("unconfirmed", "confirmed", "stale")

# Machine error codes (contract section: no branching on Chinese prose).
ERROR_CODES = {
    "BAD_REQUEST": HTTPStatus.BAD_REQUEST,
    "VALIDATION_FAILED": HTTPStatus.BAD_REQUEST,
    "NOT_FOUND": HTTPStatus.NOT_FOUND,
    "STALE_CONTEXT": HTTPStatus.CONFLICT,
    "REVISION_CONFLICT": HTTPStatus.CONFLICT,
    "EVIDENCE_MISMATCH": HTTPStatus.CONFLICT,
    "BACKEND_UNAVAILABLE": HTTPStatus.SERVICE_UNAVAILABLE,
    "DEV_SAMPLE_DISABLED": HTTPStatus.FORBIDDEN,
    "AI_NOT_CONFIGURED": HTTPStatus.SERVICE_UNAVAILABLE,
    "AI_GENERATION_FAILED": HTTPStatus.BAD_GATEWAY,
    "FORBIDDEN_ORIGIN": HTTPStatus.FORBIDDEN,
    "NOT_RUN_AWAITING_CONFIGURATION": HTTPStatus.SERVICE_UNAVAILABLE,
    # B version-service vocabulary (extensions/architecture_workspace/errors.py)
    # registered by A as part of CONTRACT_V1; HTTP mapping per B's proposal:
    # 403 review/session codes, 409 conflicts, 503 publication/storage.
    "HUMAN_REVIEW_REQUIRED": HTTPStatus.FORBIDDEN,
    "REVIEW_EXPIRED": HTTPStatus.FORBIDDEN,
    "REVIEW_REPLAY": HTTPStatus.FORBIDDEN,
    "REQUEST_FORBIDDEN": HTTPStatus.FORBIDDEN,
    "REFERENCE_CONFLICT": HTTPStatus.CONFLICT,
    "PUBLICATION_CONFLICT": HTTPStatus.CONFLICT,
    "VERSION_CONFLICT": HTTPStatus.CONFLICT,
    "DIRTY_ARCHITECTURE_REPO": HTTPStatus.CONFLICT,
    "PUBLICATION_FAILED": HTTPStatus.SERVICE_UNAVAILABLE,
    "STORAGE_FAILED": HTTPStatus.SERVICE_UNAVAILABLE,
    "CODE_REQUIRED": HTTPStatus.CONFLICT,
    "INVALID_TRANSITION": HTTPStatus.CONFLICT,
    "SCOPE_MISMATCH": HTTPStatus.CONFLICT,
    "VERIFICATION_REQUIRED": HTTPStatus.FORBIDDEN,
    "VERIFICATION_FAILED": HTTPStatus.CONFLICT,
    "SOURCE_REQUIRED": HTTPStatus.CONFLICT,
    "LOCAL_REFERENCE_REQUIRED": HTTPStatus.CONFLICT,
    "BRANCH_REQUIRED": HTTPStatus.CONFLICT,
    "FORBIDDEN": HTTPStatus.FORBIDDEN,
}


class ContractError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"Unknown contract error code: {code}")
        super().__init__(message)
        self.code = code
        self.status = ERROR_CODES[code]
        self.details = details or {}


def is_full_sha(value: object) -> bool:
    return isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_revision(graph: dict) -> str:
    """mapRevision: immutable identity over canonical semantic content.

    Layout-only fields (positions) are excluded so dragging a node never
    mints a new map revision; responsibilities, provenance, assumptions,
    relations, evidence and process do.
    """
    semantic = {
        "nodes": sorted(
            (
                {
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "summary": node.get("summary"),
                    "status": node.get("status"),
                    "provenance": node.get("provenance"),
                    "assumptions": node.get("assumptions", []),
                    "entryPoints": node.get("entryPoints", []),
                    "interfaces": node.get("interfaces", []),
                    "evidence": sorted(
                        (json.dumps(item, ensure_ascii=False, sort_keys=True)
                         for item in node.get("evidence", [])),
                    ),
                    "process": node.get("process", []),
                }
                for node in graph.get("nodes", [])
            ),
            key=lambda node: node["id"],
        ),
        "edges": sorted(
            (
                {"from": edge.get("from"), "to": edge.get("to"),
                 "type": edge.get("type"), "label": edge.get("label")}
                for edge in graph.get("edges", [])
            ),
            key=lambda edge: canonical_json(edge),
        ),
    }
    digest = hashlib.sha256(canonical_json(semantic).encode("utf-8")).hexdigest()
    return f"maprev-{digest[:40]}"


def validate_graph(graph: object) -> dict:
    """Validate the minimal architecture graph schema (CONTRACT_V1).

    Nodes carry responsibilities, optional entry points/interfaces, evidence,
    and an expected process (stable step IDs). Edges carry a contract type.
    Provenance/status fields are mandatory so facts, AI candidates and human
    confirmations never blur.
    """
    if not isinstance(graph, dict):
        raise ContractError("VALIDATION_FAILED", "图必须是 JSON 对象")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ContractError("VALIDATION_FAILED", "图需要 nodes 与 edges 列表")
    if not nodes:
        raise ContractError("VALIDATION_FAILED", "图至少需要一个功能节点")
    seen = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ContractError("VALIDATION_FAILED", "节点必须是对象")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not ID_PATTERN.fullmatch(node_id):
            raise ContractError("VALIDATION_FAILED", f"节点 ID 不合法: {node_id!r}")
        if node_id in seen:
            raise ContractError("VALIDATION_FAILED", f"节点 ID 重复: {node_id}")
        seen.add(node_id)
        for key in ("title", "summary"):
            if not isinstance(node.get(key), str) or not node[key].strip():
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 缺少 {key}")
        if node.get("status") not in NODE_STATUS:
            raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的 status 必须是 {NODE_STATUS}")
        if node.get("provenance") not in PROVENANCE:
            raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的 provenance 必须是 {PROVENANCE}")
        evidence = node.get("evidence", [])
        if not isinstance(evidence, list):
            raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的 evidence 必须是列表")
        for item in evidence:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的证据需要 path")
            kind = item.get("kind", "code_fact")
            if kind not in ("code_fact", "requirement", "unknown"):
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 证据 kind 不合法")
        for key in ("entryPoints", "interfaces"):
            value = node.get(key, [])
            if not isinstance(value, list) or any(not isinstance(entry, str) for entry in value):
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的 {key} 必须是字符串列表")
        process = node.get("process", [])
        if not isinstance(process, list):
            raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的 process 必须是列表")
        step_ids = set()
        for step in process:
            if not isinstance(step, dict):
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的过程步骤必须是对象")
            step_id = step.get("stepId")
            if not isinstance(step_id, str) or not STEP_ID_PATTERN.fullmatch(step_id):
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的过程步骤需要稳定 stepId")
            if step_id in step_ids:
                raise ContractError("VALIDATION_FAILED", f"节点 {node_id} 的 stepId 重复: {step_id}")
            step_ids.add(step_id)
            if not isinstance(step.get("title"), str) or not step["title"].strip():
                raise ContractError("VALIDATION_FAILED", f"步骤 {step_id} 缺少 title")
            for key in ("inputs", "outputs", "branches"):
                value = step.get(key, [])
                if not isinstance(value, list) or any(not isinstance(entry, str) for entry in value):
                    raise ContractError("VALIDATION_FAILED", f"步骤 {step_id} 的 {key} 必须是字符串列表")
            next_steps = step.get("next", [])
            if not isinstance(next_steps, list) or any(
                not isinstance(entry, str) or entry not in step_ids and not _forward_ref(step_ids, process, entry)
                for entry in next_steps
            ):
                raise ContractError("VALIDATION_FAILED", f"步骤 {step_id} 的 next 引用了未知步骤")
    for edge in edges:
        if not isinstance(edge, dict):
            raise ContractError("VALIDATION_FAILED", "关系必须是对象")
        if edge.get("from") not in seen or edge.get("to") not in seen:
            raise ContractError("VALIDATION_FAILED", "关系端点必须指向已知节点")
        if edge.get("type") not in EDGE_TYPES:
            raise ContractError("VALIDATION_FAILED", f"关系 type 必须是 {EDGE_TYPES}")
        if not isinstance(edge.get("label"), str) or not edge["label"].strip():
            raise ContractError("VALIDATION_FAILED", "关系需要 label")
    return graph


def _forward_ref(step_ids: set, process: list, entry: str) -> bool:
    # next may reference a later step in the same process list.
    return any(step.get("stepId") == entry for step in process)


def validate_workspace_identity(identity: dict, context: str) -> dict:
    """Enforce identity separation (contract section 8)."""
    if context not in CONTEXTS:
        raise ContractError("VALIDATION_FAILED", f"context 必须是 {CONTEXTS}")
    workspace_id = identity.get("workspaceId")
    if not isinstance(workspace_id, str) or not ID_PATTERN.fullmatch(workspace_id):
        raise ContractError("VALIDATION_FAILED", "workspaceId 不合法")
    planning = context == "planning"
    code_repo = identity.get("codeRepoId")
    if planning:
        if code_repo is not None or identity.get("codeRevision") is not None \
                or identity.get("verifiedCodeRevision") is not None:
            raise ContractError("VALIDATION_FAILED", "planning 上下文不允许 codeRepoId/codeRevision/verifiedCodeRevision")
    else:
        if not isinstance(code_repo, str) or not ID_PATTERN.fullmatch(code_repo):
            raise ContractError("VALIDATION_FAILED", "已有项目上下文需要稳定 codeRepoId")
        if identity.get("codeRevision") is not None and not is_full_sha(identity.get("codeRevision")):
            raise ContractError("VALIDATION_FAILED", "codeRevision 必须是完整 Git SHA 或 null")
    if identity.get("mapSourceRevision") is not None and not is_full_sha(identity.get("mapSourceRevision")):
        raise ContractError("VALIDATION_FAILED", "mapSourceRevision 必须是完整 Git SHA 或 null")
    return identity


def identity_view(identity: dict, map_revision: str | None, draft_revision: str | None) -> dict:
    return {
        "workspaceId": identity.get("workspaceId"),
        "codeRepoId": identity.get("codeRepoId"),
        "mapId": identity.get("mapId"),
        "codeRevision": identity.get("codeRevision"),
        "mapRevision": map_revision,
        "draftRevision": draft_revision,
        "mapSourceRevision": identity.get("mapSourceRevision"),
        "verifiedCodeRevision": identity.get("verifiedCodeRevision"),
    }
