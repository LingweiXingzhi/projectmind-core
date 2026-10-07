"""Pure candidate-contract checks; these functions never apply or approve a graph.

The V2 contract remains an engineering candidate. A must retain the original
proposal whose digest is displayed; a digest verifies consistency, not identity
or permission. Full references are checked by the existing atomic draft writer.
"""
from __future__ import annotations

import copy
import math

from .errors import require, WorkspaceError
from .schema import (SHA, MAP_REV, canonical, digest, fields, identifier,
                     input_guard, path, strings, text, validate_graph)

API_VERSION = "b-surfaces-v2-candidate"
CONTEXT_FIELDS = ("workspaceId", "mapId", "mode", "codeRepoId", "codeRevision",
                  "baseMapRevision", "draftId", "draftRevision")
GENERATED_SOURCES = ("ai_generated", "rule_based")
MAX_OPERATIONS = 128


def _copy(value):
    # Before deepcopy, reject non-JSON, unbounded and non-finite inputs. Deeply
    # nested JSON also receives the same controlled boundary error.
    try:
        canonical(value)
        return copy.deepcopy(value)
    except RecursionError as exc:
        raise WorkspaceError("INVALID_INPUT", "输入嵌套超过安全限制") from exc


def _ids(values):
    strings(values)
    for value in values:
        identifier(value)
    require(len(set(values)) == len(values), detail="稳定 ID 不得重复")


def _coordinate(value):
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@input_guard
def validate_context(context):
    """Validate exactly the eight context fields and return an isolated copy."""
    context = _copy(context)
    fields(context, CONTEXT_FIELDS)
    identifier(context["workspaceId"]); identifier(context["mapId"])
    require(context["mode"] in ("planning", "existing_project", "mixed"))
    if context["mode"] == "planning":
        require(context["codeRepoId"] is None and context["codeRevision"] is None,
                "STALE_CONTEXT", "规划上下文不能绑定代码仓库或提交")
    else:
        identifier(context["codeRepoId"])
        require(isinstance(context["codeRevision"], str)
                and SHA.fullmatch(context["codeRevision"]),
                detail="代码版本必须是完整 Git SHA")
    base = context["baseMapRevision"]
    require(base is None or (isinstance(base, str) and MAP_REV.fullmatch(base)))
    if context["draftId"] is None:
        require(context["draftRevision"] is None, detail="无草稿时修订号必须为空")
    else:
        identifier(context["draftId"])
        require(type(context["draftRevision"]) is int and context["draftRevision"] > 0)
    return context


_ENTITY_FIELDS = {
    "node": ("title", "responsibility", "implementationStatus", "interfaces", "evidenceIds"),
    "edge": ("from", "to", "type", "label", "evidenceIds"),
    "evidence": ("kind", "reason", "path", "codeRepoId", "codeRevision", "lineStart",
                 "lineEnd", "unknownReason", "content"),
    "process": ("title", "kind", "steps", "evidenceIds"),
    "step": ("nodeId", "title", "inputs", "outputs", "condition", "branches",
             "nextStepIds", "allowedFailures", "evidenceIds"),
}


def _value(entity, value, context, *, partial=False):
    """Check individual field shapes without checking against a mutable graph."""
    required = () if partial else ("id",)
    optional = _ENTITY_FIELDS[entity]
    if not partial and entity != "evidence":
        required += _ENTITY_FIELDS[entity]
        optional = ()
    fields(value, required, optional)
    if partial:
        require(bool(value), detail="修改字段不能为空")
    else:
        identifier(value["id"])
    for key, item in value.items():
        if key in ("id", "nodeId", "from", "to", "codeRepoId"):
            identifier(item)
        elif key in ("title", "responsibility", "label", "reason", "unknownReason", "content"):
            text(item)
        elif key == "condition":
            text(item, empty=True)
        elif key in ("inputs", "outputs", "allowedFailures"):
            strings(item)
        elif key in ("evidenceIds", "nextStepIds"):
            _ids(item)
        elif key == "implementationStatus":
            require(item in ("unknown", "planned", "implemented"))
            if context["mode"] == "planning":
                require(item != "implemented", "EVIDENCE_MISMATCH")
        elif key == "interfaces":
            require(isinstance(item, list) and len(item) <= 2000)
            seen = set()
            for interface in item:
                fields(interface, ("id", "name", "kind", "description", "evidenceIds"))
                interface_id = identifier(interface["id"])
                require(interface_id not in seen); seen.add(interface_id)
                text(interface["name"]); text(interface["description"])
                require(interface["kind"] in ("code_entry", "team_contract"))
                _ids(interface["evidenceIds"])
        elif key == "type":
            require(item in ("static_reference", "functional_collaboration", "expected_order"))
        elif key == "kind":
            require(item in (("expected",) if entity == "process" else
                            ("code", "user_goal", "user_constraint", "unknown", "observation")))
        elif key == "path":
            path(item)
        elif key == "codeRevision":
            require(isinstance(item, str) and SHA.fullmatch(item), "EVIDENCE_MISMATCH")
        elif key in ("lineStart", "lineEnd"):
            require(type(item) is int and item > 0, "EVIDENCE_MISMATCH")
        elif key == "steps":
            require(isinstance(item, list) and len(item) <= 2000)
            seen = set()
            for step in item:
                _value("step", step, context)
                require(step["id"] not in seen); seen.add(step["id"])
        elif key == "branches":
            require(isinstance(item, list) and len(item) <= 2000)
            for branch in item:
                fields(branch, ("condition", "nextStepId"))
                text(branch["condition"]); identifier(branch["nextStepId"])
    if entity == "evidence" and not partial:
        kind = value.get("kind")
        common = ("id", "kind", "reason")
        if kind == "code":
            fields(value, common + ("path", "codeRepoId", "codeRevision"),
                   ("lineStart", "lineEnd", "unknownReason"))
            require(value["codeRepoId"] == context["codeRepoId"] is not None,
                    "EVIDENCE_MISMATCH")
            if value["codeRevision"] != context["codeRevision"]:
                text(value.get("unknownReason"))
        elif kind in ("user_goal", "user_constraint"):
            fields(value, common + ("content",))
        elif kind in ("unknown", "observation"):
            fields(value, common + ("content", "unknownReason"))
        else:
            require(False, "EVIDENCE_MISMATCH")
    if entity == "evidence" and "lineStart" in value and "lineEnd" in value:
        require(value["lineStart"] <= value["lineEnd"], "EVIDENCE_MISMATCH")
    if entity == "evidence" and not partial:
        require(("lineStart" in value) == ("lineEnd" in value), "EVIDENCE_MISMATCH")


def _operation(operation, context, *, source):
    require(isinstance(operation, dict))
    identifier(operation.get("operationId"))
    require(operation.get("source") == source, detail="操作来源必须与候选或人工选择一致")
    op = operation.get("op")
    require(isinstance(op, str))
    common = ("op", "operationId", "source")
    if op == "layout.set":
        fields(operation, common + ("value",))
        require(isinstance(operation["value"], dict) and len(operation["value"]) <= 2000)
        for key, pos in operation["value"].items():
            identifier(key); fields(pos, ("x", "y"))
            require(all(_coordinate(v) for v in pos.values()))
        return
    parts = op.split(".")
    require(len(parts) == 2 and parts[0] in _ENTITY_FIELDS
            and parts[1] in ("add", "update", "remove", "reorder"))
    entity, action = parts
    required = {"add": ("value",), "update": ("id", "changes"),
                "remove": ("id",), "reorder": ("value",)}[action]
    fields(operation, common + required + (("processId",) if entity == "step" else ()))
    if entity == "step":
        identifier(operation["processId"])
    if action == "reorder":
        require(entity == "step")
        _ids(operation["value"])
    elif action == "add":
        _value(entity, operation["value"], context)
    elif action == "update":
        identifier(operation["id"])
        _value(entity, operation["changes"], context, partial=True)
    else:
        identifier(operation["id"])


@input_guard
def validate_proposal(proposal, context):
    """Validate a fixed C proposal against a server-resolved current context."""
    context = validate_context(context)
    proposal = _copy(proposal)
    fields(proposal, ("apiVersion", "proposalId", "kind", "basis", "generation",
                      "candidates", "unknowns", "proposalDigest"))
    require(proposal["apiVersion"] == API_VERSION)
    identifier(proposal["proposalId"])
    require(proposal["kind"] in ("patch", "bootstrap"))
    require(validate_context(proposal["basis"]) == context, "STALE_CONTEXT")
    if proposal["kind"] == "bootstrap":
        require(context["draftId"] is None, "STALE_CONTEXT",
                "初图候选用于准备新草稿，不能绑定已有草稿")
    generation = proposal["generation"]
    fields(generation, ("source", "runId", "fixtureOnly"))
    require(generation["source"] in GENERATED_SOURCES)
    identifier(generation["runId"])
    require(type(generation["fixtureOnly"]) is bool)
    strings(proposal["unknowns"])
    claimed = proposal["proposalDigest"]
    require(isinstance(claimed, str) and MAP_REV.fullmatch(claimed), "EVIDENCE_MISMATCH")
    require(claimed == digest({key: value for key, value in proposal.items()
                              if key != "proposalDigest"}), "EVIDENCE_MISMATCH",
            "候选内容与展示摘要不一致")
    candidates = proposal["candidates"]
    require(isinstance(candidates, list) and 0 < len(candidates) <= MAX_OPERATIONS)
    candidate_ids, operation_ids = set(), set()
    for candidate in candidates:
        body = "graph" if proposal["kind"] == "bootstrap" else "operations"
        fields(candidate, ("candidateId", body))
        candidate_id = identifier(candidate["candidateId"])
        require(candidate_id not in candidate_ids, detail="候选 ID 重复")
        candidate_ids.add(candidate_id)
        if body == "graph":
            # Do not rewrite a hashed candidate to normalize its graph. The
            # draft creator will store validate_graph's normalized graph later.
            validate_graph(candidate["graph"], context)
        else:
            require(context["draftId"] is not None, "STALE_CONTEXT", "局部候选需要已有草稿")
            operations = candidate["operations"]
            require(isinstance(operations, list) and 0 < len(operations) <= MAX_OPERATIONS)
            for operation in operations:
                _operation(operation, context, source=generation["source"])
                op_id = operation["operationId"]
                require(op_id not in operation_ids, detail="操作 ID 在候选包内重复")
                operation_ids.add(op_id)
                require(len(operation_ids) <= MAX_OPERATIONS, detail="候选操作超过单次保存上限")
    return proposal


@input_guard
def compile_selection(proposal, context, selection, operations):
    """Bind every patch decision to the exact supplied operations, without writes.

    Supplied cross-candidate order is preserved because later operations may
    depend on earlier additions. Each candidate's own relative operation order
    remains fixed. Manual edits outside a C candidate use a separate save.
    """
    proposal = validate_proposal(proposal, context)
    require(proposal["kind"] == "patch", detail="初图通过 prepareDraft 选择，不能作为局部保存")
    selection = _copy(selection); operations = _copy(operations)
    require(isinstance(selection, list) and len(selection) <= MAX_OPERATIONS)
    require(isinstance(operations, list) and len(operations) <= MAX_OPERATIONS)
    actual = {}
    for operation in operations:
        require(isinstance(operation, dict))
        key = identifier(operation.get("operationId"))
        require(key not in actual, detail="实际操作 ID 重复")
        actual[key] = operation
    candidates = {c["candidateId"]: c for c in proposal["candidates"]}
    decided, expected, rejected = set(), set(), []
    for choice in selection:
        fields(choice, ("candidateId", "decision", "operationIds"), ("reason",))
        key = identifier(choice["candidateId"])
        require(key in candidates and key not in decided, detail="候选选择缺失、未知或重复")
        decided.add(key)
        decision = choice["decision"]
        require(decision in ("accept", "modify", "reject"))
        _ids(choice["operationIds"])
        if "reason" in choice:
            text(choice["reason"])
        originals = {o["operationId"]: o for o in candidates[key]["operations"]}
        if decision == "reject":
            require(not choice["operationIds"], detail="拒绝候选不能应用操作")
            text(choice.get("reason"))
            rejected.append({"proposalId": proposal["proposalId"], "candidateId": key,
                             "reason": choice["reason"]})
            continue
        require(set(choice["operationIds"]) == set(originals), detail="选择必须覆盖候选的完整操作组")
        require([op_id for op_id in actual if op_id in originals] == list(originals),
                detail="候选操作组内的顺序必须与原候选一致")
        expected.update(originals)
        for op_id, original in originals.items():
            require(op_id in actual, detail="已选择的操作未出现在实际应用列表")
            applied = actual[op_id]
            if decision == "accept":
                require(canonical(applied) == canonical(original),
                        detail="接受操作必须与原候选全文相同")
            else:
                _operation(applied, context, source="human")
                require(all(applied.get(k) == original.get(k) for k in
                            ("operationId", "op", "id", "processId")),
                        detail="人工修改不能替换操作种类或稳定目标")
                if original["op"].endswith(".add"):
                    require(applied["value"]["id"] == original["value"]["id"],
                            detail="人工修改新增对象不能替换稳定 ID")
    require(decided == set(candidates), detail="每个候选必须有且只有一个决定")
    require(set(actual) == expected, detail="实际操作必须等于已选择操作，不能夹带拒绝项或额外编辑")
    return {"operations": operations, "rejectedCandidates": rejected, "selection": selection}
