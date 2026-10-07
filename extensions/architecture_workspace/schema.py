"""Engineering contract candidate; not a confirmed Project Model."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from functools import wraps
from pathlib import PurePosixPath

from .errors import require, WorkspaceError

SCHEMA = "architecture_graph_v1"
ID = re.compile(r"[a-zA-Z][a-zA-Z0-9_.-]{0,119}\Z")
SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
MAP_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")
VERIFICATION_LIMIT = "核查仅适用于列明覆盖；不证明运行时全流程"
PREVIEW_FIELDS = ("draftId", "draftRevision", "workspaceId", "mapId",
                  "expectedMapRevision", "codeRepoId", "codeRevision", "proposalId",
                  "actor", "reason", "beforeGraph", "afterGraph", "appliedOperations",
                  "rejectedCandidates", "reviewCoverage", "limits", "verifyCode", "origin")


def input_guard(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except WorkspaceError:
            raise
        except (TypeError, KeyError, IndexError, AttributeError) as exc:
            raise WorkspaceError("INVALID_INPUT", "输入类型或必需结构不符合合同") from exc
    return guarded


def canonical(value):
    try:
        data = json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
        require(len(data.encode("utf-8")) <= 2_000_000, detail="对象超过 2 MB 上限")
        return data
    except (TypeError, ValueError, UnicodeError):
        require(False, detail="只接受有限 JSON 值")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), detail="需要稳定、受限的 ID")
    return value


def text(value, empty=False):
    require(isinstance(value, str) and (empty or value.strip())
            and len(value) <= 20_000 and "\x00" not in value)
    return value


def strings(values):
    require(isinstance(values, list) and len(values) <= 2000)
    for item in values:
        text(item)


def fields(obj, required, optional=()):
    require(isinstance(obj, dict) and not (set(obj) - set(required) - set(optional))
            and set(required) <= set(obj), detail="字段缺失或存在未定义字段")


def path(value):
    require(isinstance(value, str) and 0 < len(value) <= 20_000,
            "EVIDENCE_MISMATCH")
    require("\\" not in value and ":" not in value
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and not value.startswith("/") and all(p not in ("", ".", "..")
                                                   for p in value.split("/"))
            and PurePosixPath(value).as_posix() == value,
            "EVIDENCE_MISMATCH", "证据必须是规范的仓库内相对路径")
    return value


def records(values):
    require(isinstance(values, list) and len(values) <= 2000)
    result = {}
    for obj in values:
        require(isinstance(obj, dict))
        key = identifier(obj.get("id"))
        require(key not in result, detail="同类对象 ID 重复")
        result[key] = obj
    return result


@input_guard
def validate_graph(graph, context):
    graph = copy.deepcopy(graph)
    fields(graph, ("schemaVersion", "nodes", "edges", "evidence", "processes"))
    require(graph["schemaVersion"] == SCHEMA)
    nodes, edges, evidence, processes = [records(graph[k]) for k in
                                        ("nodes", "edges", "evidence", "processes")]

    def refs(ids):
        strings(ids)
        require(len(set(ids)) == len(ids) and set(ids) <= set(evidence),
                "EVIDENCE_MISMATCH", "证据 ID 不存在或重复")

    for ev in evidence.values():
        common = ("id", "kind", "reason")
        kind = ev.get("kind")
        if kind == "code":
            fields(ev, common + ("path", "codeRepoId", "codeRevision"),
                   ("lineStart", "lineEnd", "unknownReason"))
            path(ev["path"])
            require(ev["codeRepoId"] == context["codeRepoId"] is not None,
                    "EVIDENCE_MISMATCH")
            require(isinstance(ev["codeRevision"], str) and SHA.fullmatch(ev["codeRevision"]),
                    "EVIDENCE_MISMATCH")
            if ev["codeRevision"] != context["codeRevision"]:
                text(ev.get("unknownReason"))
            if "lineStart" in ev or "lineEnd" in ev:
                a, b = ev.get("lineStart"), ev.get("lineEnd")
                require(type(a) is int and type(b) is int and 0 < a <= b,
                        "EVIDENCE_MISMATCH")
        elif kind in ("user_goal", "user_constraint"):
            fields(ev, common + ("content",))
            text(ev["content"])
        elif kind in ("unknown", "observation"):
            fields(ev, common + ("content", "unknownReason"))
            text(ev["content"]); text(ev["unknownReason"])
        else:
            require(False, "EVIDENCE_MISMATCH", "证据类型不受支持")
        text(ev["reason"])
    all_interfaces = set()
    for node in nodes.values():
        fields(node, ("id", "title", "responsibility", "implementationStatus",
                      "interfaces", "evidenceIds"))
        text(node["title"]); text(node["responsibility"])
        require(node["implementationStatus"] in ("unknown", "planned", "implemented"))
        if context["mode"] == "planning":
            require(node["implementationStatus"] != "implemented",
                    "EVIDENCE_MISMATCH", "规划确认不能表示实现已完成")
        refs(node["evidenceIds"])
        for interface in records(node["interfaces"]).values():
            fields(interface, ("id", "name", "kind", "description", "evidenceIds"))
            require(interface["id"] not in all_interfaces, detail="接口 ID 在图内重复")
            all_interfaces.add(interface["id"])
            text(interface["name"]); text(interface["description"])
            require(interface["kind"] in ("code_entry", "team_contract"))
            refs(interface["evidenceIds"])
    for edge in edges.values():
        fields(edge, ("id", "from", "to", "type", "label", "evidenceIds"))
        require(edge["from"] in nodes and edge["to"] in nodes, "REFERENCE_CONFLICT")
        require(edge["type"] in ("static_reference", "functional_collaboration", "expected_order"))
        text(edge["label"]); refs(edge["evidenceIds"])
    all_steps = set()
    for process in processes.values():
        fields(process, ("id", "title", "kind", "steps", "evidenceIds"))
        text(process["title"]); require(process["kind"] == "expected")
        refs(process["evidenceIds"])
        steps = records(process["steps"])
        for step in steps.values():
            fields(step, ("id", "nodeId", "title", "inputs", "outputs", "condition",
                          "branches", "nextStepIds", "allowedFailures", "evidenceIds"))
            require(step["id"] not in all_steps, detail="步骤 ID 在图内重复")
            all_steps.add(step["id"])
            require(step["nodeId"] in nodes, "REFERENCE_CONFLICT")
            text(step["title"]); text(step["condition"], empty=True)
            for k in ("inputs", "outputs", "allowedFailures", "nextStepIds"):
                strings(step[k])
            require(set(step["nextStepIds"]) <= set(steps), "REFERENCE_CONFLICT")
            require(isinstance(step["branches"], list))
            for branch in step["branches"]:
                fields(branch, ("condition", "nextStepId"))
                text(branch["condition"])
                require(branch["nextStepId"] in steps, "REFERENCE_CONFLICT")
            refs(step["evidenceIds"])
    for key in ("nodes", "edges", "evidence", "processes"):
        graph[key].sort(key=lambda o: o["id"])
    for node in graph["nodes"]:
        node["interfaces"].sort(key=lambda o: o["id"])
    canonical(graph)
    return graph


def semantic_version(packet):
    # Layout, local workspace IDs, Git source SHA, actor and wall-clock time
    # are outside semantic identity. Code binding and review coverage are in it.
    return digest({key: packet[key] for key in
                   ("schemaVersion", "mapId", "codeRepoId", "codeRevision",
                    "verifiedCodeRevision", "status", "graph", "reviewCoverage", "limits")})


@input_guard
def validate_packet(packet):
    fields(packet, ("schemaVersion", "mapId", "mapRevision", "codeRepoId",
                    "codeRevision", "verifiedCodeRevision", "status", "graph",
                    "reviewCoverage", "limits", "review", "origin", "confirmation"))
    identifier(packet["mapId"])
    context = {"mode": "planning" if packet["codeRepoId"] is None else "existing_project",
               "codeRepoId": packet["codeRepoId"], "codeRevision": packet["codeRevision"]}
    require(packet["schemaVersion"] == "architecture_version_v1")
    require(packet["status"] in ("confirmed_design", "confirmed_cognition"))
    require((packet["codeRepoId"] is None) == (packet["codeRevision"] is None))
    require((packet["status"] == "confirmed_design") == (packet["codeRepoId"] is None),
            "EVIDENCE_MISMATCH")
    if packet["codeRevision"] is not None:
        identifier(packet["codeRepoId"])
        require(isinstance(packet["codeRevision"], str) and SHA.fullmatch(packet["codeRevision"]))
    require(packet["verifiedCodeRevision"] in (None, packet["codeRevision"]),
            "EVIDENCE_MISMATCH")
    require(packet["graph"] == validate_graph(packet["graph"], context))
    validate_coverage(packet["reviewCoverage"], packet["graph"])
    strings(packet["limits"])
    review = packet["review"]
    fields(review, PREVIEW_FIELDS + ("reviewId", "decision", "reviewedAt", "previewDigest",
                                     "verifiedCodeRevision", "actorIdentity"))
    require(review["decision"] == "accept" and review["afterGraph"] == packet["graph"]
            and all(review[k] == packet[k] for k in
                    ("mapId", "codeRepoId", "codeRevision", "verifiedCodeRevision", "reviewCoverage", "origin"))
            and review["actorIdentity"] == "local_operator_declaration",
            "EVIDENCE_MISMATCH")
    require(review["previewDigest"] == digest({k: review[k] for k in PREVIEW_FIELDS}),
            "EVIDENCE_MISMATCH")
    require(packet["limits"] == review["limits"] + [VERIFICATION_LIMIT], "EVIDENCE_MISMATCH")
    require(packet["origin"] in ("manual", "ai_generated", "rule_based", "legacy", "restored"))
    require(packet["confirmation"] == confirmation_states(packet["graph"], packet["reviewCoverage"]),
            "EVIDENCE_MISMATCH")
    require(packet["mapRevision"] == semantic_version(packet), "VERSION_CONFLICT")
    return copy.deepcopy(packet)


def validate_coverage(coverage, graph):
    fields(coverage, ("scope", "nodes", "edges", "processes", "evidence"))
    require(coverage["scope"] in ("partial", "all"))
    for key in ("nodes", "edges", "processes", "evidence"):
        strings(coverage[key])
        known = {o["id"] for o in graph[key]}
        require(len(set(coverage[key])) == len(coverage[key]) and set(coverage[key]) <= known)
        if coverage["scope"] == "all":
            require(set(coverage[key]) == known, detail="全覆盖必须列出全部对象 ID")
    normalized = copy.deepcopy(coverage)
    for key in ("nodes", "edges", "processes", "evidence"):
        normalized[key].sort()
    return normalized


def confirmation_states(graph, coverage):
    return {key: {"confirmed": sorted(coverage[key]),
                  "unconfirmed": sorted({o["id"] for o in graph[key]} - set(coverage[key]))}
            for key in ("nodes", "edges", "processes", "evidence")}
