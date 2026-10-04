"""ExtensionHost adapter for C / Map Proposal.

GET  → capability/status page data.
POST {action: "suggest", request: SuggestMapRequest} → SuggestMapResult.
POST {action: "schema"} → the frozen request/response contract description.

C never writes the map, never accepts proposals, and never arbitrates conflicts.
"""
from http import HTTPStatus

from extension_host import ExtensionError
from extensions.map_proposal.engine import suggest
from extensions.map_proposal.facts_adapter import FactsMismatch
from extensions.map_proposal.model import RequestError

EXTENSION = {"title": "地图建议", "description": "对比代码变化与人工地图，产出带证据的修改建议，供人复核。"}

SCHEMA_DOC = {
    "request": {
        "base_revision": "40/64-hex SHA（比较基准）",
        "target_revision": "40/64-hex SHA（被评估提交）",
        "changed_paths": [{"path": "...", "status": "added|modified|removed|renamed",
                           "old_path": "(renamed 必填)"}],
        "code_facts": "B 输出（可选；revision 必须等于 target_revision）",
        "current_map": {"nodes": "[{id,title,summary,entryPoint,position?,evidence[]}]",
                        "edges": "[{from,to,label}]"},
        "context_pack": "CA pack（可选；validate 失败→整包拒绝并降级）",
        "prior_decisions": [{"subject": "...", "kind": "...", "decision": "REJECTED|ACCEPTED|DEFERRED"}],
    },
    "result": {"proposals": [], "unresolved": [], "no_proposal": [], "limits": [], "metadata": {}},
    "kinds": ["NODE_ADD", "RELATION_ADD", "RELATION_REMOVE_CANDIDATE",
              "IMPLEMENTATION_LINK_CHANGE", "NODE_REMOVE_CANDIDATE", "RESPONSIBILITY_CHANGE"],
    "invariants": ["status 恒为 PROPOSED", "human_required 恒为 true",
                   "evidence 至少 1 条且可定位 (revision, path)",
                   "proposed_change 不含 position", "同输入同输出"],
}


def handle(context, method, data):
    if method == "GET":
        return {"id": "map_proposal", "capability": "map proposal (v0.1, deterministic)",
                "inputs": ["git diff (changed_paths)", "B code facts",
                           "current project map", "context authority pack (optional)"],
                "modes": ["FULL", "DEGRADED_NO_CONTEXT"],
                "schema": SCHEMA_DOC,
                "note": "C 只产出 PROPOSED；接受与否由人决定。"}
    if method != "POST":
        raise ExtensionError(HTTPStatus.METHOD_NOT_ALLOWED, "请使用 GET 或 POST")
    if not isinstance(data, dict):
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "请求须为 JSON 对象")
    action = data.get("action", "suggest")
    if action == "schema":
        return SCHEMA_DOC
    if action != "suggest":
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "不支持的 C 操作")
    request = data.get("request")
    if request is None:
        request = {key: value for key, value in data.items() if key != "action"}
    try:
        return suggest(request, context.repo)
    except (RequestError, FactsMismatch) as exc:
        raise ExtensionError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
