"""Context Authority — canonical context layer for all agents.

Its job is NOT to think for agents. Its job is to hand every agent the same
traceable factual baseline before thinking starts.

API (follows docs/standards/EXTENSION_INTERFACE.md):
  GET  ?action=state      -> CURRENT_STATE (derived view)
  GET  ?action=claims     -> the raw registry (provenance)
  GET  ?action=conflicts  -> unresolved conflicts only
  POST {"action": "resolve_state"}                    -> CURRENT_STATE
  POST {"action": "context", "task": "...",           -> Context Pack
        "revision": optional, "verify": optional bool}
POST ≤65,536 bytes per the shared extension contract. Strict key validation.
The resolver is deterministic: no LLM, no timestamps-wins, no silent fallback.
"""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from extension_host import ExtensionError

from extensions.context_authority.context_pack import build_context_pack
from extensions.context_authority.registry import RegistryProblems, load_registry
from extensions.context_authority.resolver import resolve
from extensions.context_authority.verifiers import build_default_verifiers

EXTENSION = {
    "title": "Context Authority",
    "description": "给所有 Agent 同一套可追溯的事实底座（CURRENT_STATE / Context Pack）",
}

REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "claims.jsonl"
GET_ACTIONS = ("state", "claims", "conflicts")
POST_ACTIONS = ("resolve_state", "context")


def _resolve_state(context) -> dict:
    problems = RegistryProblems()
    claims = load_registry(REGISTRY_PATH, problems)
    verifiers = build_default_verifiers(str(context.repo))
    return resolve(claims, verifiers=verifiers, problems=problems)


def handle(context, method: str, data: dict) -> dict:
    if method not in ("GET", "POST"):
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, "只支持 GET 或 POST")
    if method == "GET":
        action = (data or {}).get("action", "state")
        if action not in GET_ACTIONS:
            raise ExtensionError(HTTPStatus.BAD_REQUEST,
                                 f"GET action 须为 {GET_ACTIONS} 之一")
        state = _resolve_state(context)
        if action == "claims":
            claims = load_registry(REGISTRY_PATH)
            return {"claims": claims, "registry_hash": state["registry_hash"]}
        if action == "conflicts":
            return {"conflicts": state["conflicts"],
                    "resolution": "HUMAN_REQUIRED" if state["conflicts"] else None,
                    "counts": state["counts"]}
        return state

    if not isinstance(data, dict):
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "请求体必须是 JSON 对象")
    unknown = set(data) - {"action", "task", "revision", "verify"}
    if unknown:
        raise ExtensionError(HTTPStatus.BAD_REQUEST,
                             f"输入仅接受 action/task/revision/verify，收到 {sorted(unknown)}")
    action = data.get("action")
    if action not in POST_ACTIONS:
        raise ExtensionError(HTTPStatus.BAD_REQUEST,
                             f"POST action 须为 {POST_ACTIONS} 之一")
    if action == "resolve_state":
        return _resolve_state(context)
    task = data.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "action=context 需要 task 字符串")
    revision = data.get("revision")
    if revision is not None and not (isinstance(revision, str) and revision):
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "revision 须为非空字符串")
    verify = data.get("verify", True)
    if not isinstance(verify, bool):
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "verify 须为布尔值")
    try:
        return build_context_pack(task, str(context.repo), REGISTRY_PATH,
                                  revision=revision, run_verifiers=verify)
    except ValueError as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
