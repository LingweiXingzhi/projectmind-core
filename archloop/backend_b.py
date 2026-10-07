"""Single A<->B compatibility adapter: the A workbench drives B's real version service.

This module is the ONLY place where A-shape and B-shape data are converted.
Rules (CONTRACT_V1, A-registered):

* B (`extensions.architecture_workspace`, PR #51) owns drafts, CAS, human
  review and immutable Git-backed versions. A never re-implements them.
* A's page structure is a *projection*: the conversion preserves object
  identity, evidence, process branches, allowed failure paths, confirmation
  scope and provenance lineage. It must round-trip without losing data.
* Fields B's strict schema cannot carry per object (node provenance,
  assumptions, step detail, legacy import notes) travel in exactly ONE
  graph-level metadata evidence object per draft (observation kind,
  machine-marked reason). It is deliberately unreferenced by nodes so it never
  blocks code-review coverage, and it is restored verbatim on the way back.
* Edge type enum differs: A "expected_sequence" == B "expected_order".
* Node status differs: A candidate/confirmed_design/implemented
  == B unknown/planned/implemented.
* The A draft's CAS revision (string) stays A's; B's integer draftRevision is
  mirrored into the A record so both sides can detect conflicts.

Nothing here is a second version backend: every persistence/review/publish
call goes to `WorkspaceService` / `HumanReviewGateway` from B.
"""
from __future__ import annotations

import copy
import hashlib
import json

from .contract import ContractError

META_EVIDENCE_ID = "ev-a-projection-meta"
META_REASON_PREFIX = "A_projection_metadata:graph_meta"
ENTRY_DESCRIPTION = "公开入口（来自 A 工作台）"
CONTRACT_DESCRIPTION = "团队接口（来自 A 工作台）"

EDGE_TYPE_TO_B = {
    "static_reference": "static_reference",
    "functional_collaboration": "functional_collaboration",
    "expected_sequence": "expected_order",
}
EDGE_TYPE_TO_A = {value: key for key, value in EDGE_TYPE_TO_B.items()}

STATUS_TO_B = {"candidate": "unknown", "confirmed_design": "planned", "implemented": "implemented"}
STATUS_TO_A = {"unknown": "candidate", "planned": "confirmed_design", "implemented": "implemented"}

A_DRAFT_ORIGIN_TO_B = {
    "ai_candidate": "ai_generated",
    "edited_candidate": "ai_generated",
    "dev_sample": "rule_based",
    "legacy_import": "legacy",
    "human_input": "manual",
    "rule_based": "rule_based",
}
B_ORIGIN_TO_A = {
    "ai_generated": "ai_candidate",
    "rule_based": "rule_based",
    "legacy": "legacy_import",
    "restored": "edited_candidate",
    "manual": "human_input",
}

# B machine code -> A machine code. A's contract adds B's vocabulary where the
# meaning matches; nothing is translated through Chinese prose.
B_ERROR_TO_A = {
    "INVALID_INPUT": "VALIDATION_FAILED",
    "NOT_FOUND": "NOT_FOUND",
    "REVISION_CONFLICT": "REVISION_CONFLICT",
    "STALE_CONTEXT": "STALE_CONTEXT",
    "EVIDENCE_MISMATCH": "EVIDENCE_MISMATCH",
    "HUMAN_REVIEW_REQUIRED": "HUMAN_REVIEW_REQUIRED",
    "REVIEW_EXPIRED": "REVIEW_EXPIRED",
    "REVIEW_REPLAY": "REVIEW_REPLAY",
    "REQUEST_FORBIDDEN": "REQUEST_FORBIDDEN",
    "REFERENCE_CONFLICT": "REFERENCE_CONFLICT",
    "DIRTY_ARCHITECTURE_REPO": "DIRTY_ARCHITECTURE_REPO",
    "PUBLICATION_FAILED": "PUBLICATION_FAILED",
    "PUBLICATION_CONFLICT": "PUBLICATION_CONFLICT",
    "VERSION_CONFLICT": "VERSION_CONFLICT",
    "STORAGE_FAILED": "STORAGE_FAILED",
}


def _short_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _unique(candidate: str, taken: set) -> str:
    if candidate not in taken:
        taken.add(candidate)
        return candidate
    index = 2
    while f"{candidate}-{index}" in taken:
        index += 1
    chosen = f"{candidate}-{index}"
    taken.add(chosen)
    return chosen


def a_evidence_to_b_list(items, *, node_id: str, code_repo_id, code_revision, taken_ids: set) -> list:
    """Convert A node/step evidence entries into B evidence objects."""
    out = []
    for item in items or []:
        kind = item.get("kind", "code_fact")
        reason = item.get("reason", "") or "未填写依据"
        evidence_id = _unique(
            "ev-" + _short_hash(node_id, kind, str(item.get("path", "")), reason), taken_ids)
        if kind == "code_fact":
            if not code_repo_id or not code_revision:
                # a code fact with no repository binding cannot be verified:
                # it becomes an honest unknown instead of a fake fact
                record = {"id": evidence_id, "kind": "unknown",
                          "content": str(item.get("path", "")) or "（未关联仓库）",
                          "unknownReason": "无代码仓库绑定，代码事实无法核查",
                          "reason": reason}
            else:
                record = {"id": evidence_id, "kind": "code", "reason": reason,
                          "path": item.get("path", ""), "codeRepoId": code_repo_id,
                          "codeRevision": code_revision}
                if item.get("codeRevision") and item["codeRevision"] != code_revision:
                    record["unknownReason"] = "证据声明的代码版本与工作区当前版本不一致"
                for key in ("lineStart", "lineEnd"):
                    if isinstance(item.get(key), int):
                        record[key] = item[key]
        elif kind == "requirement":
            record = {"id": evidence_id, "kind": "user_goal",
                      "content": str(item.get("path", "")) or "（未填写需求内容）",
                      "reason": reason}
        else:  # unknown
            record = {"id": evidence_id, "kind": "unknown",
                      "content": str(item.get("path", "")) or "（未知项）",
                      "unknownReason": reason or "未核查", "reason": "未核查"}
        out.append(record)
    return out


def b_evidence_to_a(item: dict) -> dict:
    kind = item.get("kind")
    if kind == "code" and not item.get("unknownReason"):
        result = {"path": item.get("path", ""), "reason": item.get("reason", ""),
                  "kind": "code_fact", "evidenceId": item.get("id")}
        for key in ("lineStart", "lineEnd"):
            if key in item:
                result[key] = item[key]
        return result
    if kind in ("code",):
        return {"path": item.get("path", ""),
                "reason": f"{item.get('reason', '')}（{item.get('unknownReason', '')}）",
                "kind": "unknown", "evidenceId": item.get("id")}
    if kind in ("user_goal", "user_constraint"):
        reason = item.get("reason", "")
        if kind == "user_constraint":
            reason = f"[约束] {reason}"
        return {"path": item.get("content", ""), "reason": reason,
                "kind": "requirement", "evidenceId": item.get("id")}
    return {"path": item.get("content", ""), "reason": item.get("unknownReason", ""),
            "kind": "unknown", "evidenceId": item.get("id")}


def _interface_id(node_id: str, kind: str, name: str) -> str:
    return "iface-" + _short_hash(node_id, kind, name)


def a_to_b_graph(a_graph: dict, *, code_repo_id, code_revision) -> dict:
    """Project an A draft graph into B's strict `architecture_graph_v1`."""
    if not isinstance(a_graph, dict) or not isinstance(a_graph.get("nodes"), list):
        raise ContractError("VALIDATION_FAILED", "A 图缺少 nodes 列表")
    taken_evidence: set = set()
    taken_edges: set = set()
    step_ids_seen: set = set()
    b_evidence: list = []
    b_nodes: list = []
    b_edges: list = []
    b_processes: list = []
    meta = {"provenance": {}, "assumptions": {}, "stepDetails": {}, "importNotes": {}}
    layout = {}

    for node in a_graph["nodes"]:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ContractError("VALIDATION_FAILED", "A 节点缺少 id")
        evidence_ids = []
        for record in a_evidence_to_b_list(node.get("evidence", []), node_id=node_id,
                                           code_repo_id=code_repo_id,
                                           code_revision=code_revision,
                                           taken_ids=taken_evidence):
            b_evidence.append(record)
            evidence_ids.append(record["id"])
        interfaces = []
        for entry in node.get("entryPoints", []) or []:
            interfaces.append({"id": _interface_id(node_id, "code_entry", str(entry)),
                               "name": str(entry), "kind": "code_entry",
                               "description": ENTRY_DESCRIPTION, "evidenceIds": []})
        for contract in node.get("interfaces", []) or []:
            interfaces.append({"id": _interface_id(node_id, "team_contract", str(contract)),
                               "name": str(contract), "kind": "team_contract",
                               "description": CONTRACT_DESCRIPTION, "evidenceIds": []})
        for interface in node.get("interfaceDetails", []) or []:
            items = []
            for record in a_evidence_to_b_list(interface.get("evidence", []), node_id=node_id,
                                               code_repo_id=code_repo_id,
                                               code_revision=code_revision,
                                               taken_ids=taken_evidence):
                b_evidence.append(record)
                items.append(record["id"])
            kind = interface.get("kind", "team_contract")
            interfaces.append({"id": _interface_id(node_id, kind, str(interface.get("name", ""))),
                               "name": str(interface.get("name", "")), "kind": kind,
                               "description": str(interface.get("description", "") or "（未填写说明）"),
                               "evidenceIds": items})
        b_nodes.append({"id": node_id, "title": node.get("title") or node_id,
                        "responsibility": node.get("summary") or "（未填写职责）",
                        "implementationStatus": STATUS_TO_B.get(node.get("status"), "unknown"),
                        "interfaces": interfaces, "evidenceIds": evidence_ids})
        meta["provenance"][node_id] = node.get("provenance")
        if node.get("assumptions"):
            meta["assumptions"][node_id] = list(node["assumptions"])
        if node.get("importNote"):
            meta["importNotes"][node_id] = node["importNote"]
        if isinstance(node.get("position"), dict) and node["position"]:
            try:
                x, y = float(node["position"].get("x")), float(node["position"].get("y"))
                if x >= 0 and y >= 0:
                    layout[node_id] = {"x": x, "y": y}
            except (TypeError, ValueError):
                pass

        # one expected process per node; A step IDs stay stable inside it, and
        # next/branch targets are rewritten through the same id mapping so a
        # collision-renamed step is still referenced correctly.
        id_map = {}
        # pass 1: every step id of this node is known before any reference is
        # rewritten, so a forward reference is never dropped (BATCH-1 A-01)
        for step in node.get("process", []) or []:
            a_step_id = str(step.get("stepId", ""))
            b_step_id = a_step_id if a_step_id not in step_ids_seen else f"{a_step_id}--{node_id}"
            step_ids_seen.add(b_step_id)
            id_map[a_step_id] = b_step_id
        steps = []
        for step in node.get("process", []) or []:
            a_step_id = str(step.get("stepId", ""))
            b_step_id = id_map[a_step_id]
            if step.get("detail"):
                meta["stepDetails"][b_step_id] = step["detail"]
            step_evidence = []
            for record in a_evidence_to_b_list(step.get("evidence", []), node_id=node_id,
                                               code_repo_id=code_repo_id,
                                               code_revision=code_revision,
                                               taken_ids=taken_evidence):
                b_evidence.append(record)
                step_evidence.append(record["id"])
            steps.append({"id": b_step_id, "nodeId": node_id,
                          "title": step.get("title") or b_step_id,
                          "inputs": [str(x) for x in (step.get("inputs", []) or [])],
                          "outputs": [str(x) for x in (step.get("outputs", []) or [])],
                          "condition": str(step.get("condition", "") or ""),
                          "allowedFailures": [str(x) for x in (step.get("allowedFailures", []) or [])],
                          "nextStepIds": [id_map.get(str(x), str(x)) for x in (step.get("next", []) or [])],
                          "branches": [{"condition": str(branch), "nextStepId": None}
                                       for branch in (step.get("branches", []) or [])],
                          "evidenceIds": step_evidence})
        if steps:
            valid_ids = {step["id"] for step in steps}
            for step in steps:
                targets = [tid for tid in step["nextStepIds"] if tid in valid_ids]
                step["nextStepIds"] = targets
                fallback = targets[0] if targets else step["id"]
                for branch in step["branches"]:
                    branch["nextStepId"] = fallback
            b_processes.append({"id": "process-" + node_id,
                                "title": f"{node.get('title') or node_id} 的期望过程",
                                "kind": "expected", "steps": steps, "evidenceIds": []})

    for edge in a_graph.get("edges", []) or []:
        b_type = EDGE_TYPE_TO_B.get(edge.get("type"))
        if b_type is None:
            raise ContractError("VALIDATION_FAILED", f"关系类型不受支持: {edge.get('type')!r}")
        edge_id = _unique("edge-" + _short_hash(str(edge.get("from")), str(edge.get("to")),
                                               b_type, str(edge.get("label", ""))), taken_edges)
        b_edges.append({"id": edge_id, "from": edge.get("from"), "to": edge.get("to"),
                        "type": b_type, "label": edge.get("label") or "（未填写关系说明）",
                        "evidenceIds": []})

    if any(meta[key] for key in ("provenance", "assumptions", "stepDetails", "importNotes")):
        payload = json.dumps(meta, ensure_ascii=False, sort_keys=True)
        chunks = [payload[index:index + 15000]
                  for index in range(0, max(len(payload), 1), 15000)]
        for number, chunk in enumerate(chunks):
            # zero-padded ordinal so lexical order == payload order
            evidence_id = META_EVIDENCE_ID if number == 0 else f"{META_EVIDENCE_ID}-{number:05d}"
            b_evidence.append({"id": evidence_id, "kind": "observation", "content": chunk,
                               "unknownReason": META_REASON_PREFIX,
                               "reason": "A 工作台页面投影元数据；未参与核查"})
    graph = {"schemaVersion": "architecture_graph_v1", "nodes": b_nodes, "edges": b_edges,
             "evidence": b_evidence, "processes": b_processes}
    # B normalizes these collections by ID; emit them already sorted so a
    # re-projection of unchanged content produces byte-identical objects and
    # the operation diff stays minimal (no order-only churn).
    for key in ("nodes", "edges", "evidence", "processes"):
        graph[key].sort(key=lambda item: item["id"])
    for node in graph["nodes"]:
        node["interfaces"].sort(key=lambda item: item["id"])
    return {"graph": graph, "layout": layout}


def _meta_chunk_index(evidence_id: str) -> int:
    suffix = evidence_id[len(META_EVIDENCE_ID):].lstrip("-")
    if not suffix:
        return 0
    try:
        return int(suffix)
    except ValueError:
        return 0


def _meta_from_b_evidence(evidence: list) -> dict:
    chunks = []
    for item in evidence or []:
        if item.get("kind") == "observation" and \
                str(item.get("unknownReason", "")).startswith(META_REASON_PREFIX) and \
                (str(item.get("id", "")) == META_EVIDENCE_ID
                 or str(item.get("id", "")).startswith(META_EVIDENCE_ID + "-")):
            chunks.append((_meta_chunk_index(str(item.get("id"))), item.get("content", "")))
    if not chunks:
        return {}
    chunks.sort(key=lambda pair: pair[0])
    try:
        return json.loads("".join(chunk for _, chunk in chunks))
    except (json.JSONDecodeError, TypeError) as exc:
        # silently dropping the carrier would drop provenance/assumptions and
        # mislabel the graph: refuse instead (BATCH-1 A-04)
        raise ContractError("EVIDENCE_MISMATCH",
                            "A 投影元数据无法解析；拒绝在丢失来源谱系的情况下继续") from exc


def b_to_a_graph(b_graph: dict, packet: dict | None = None) -> dict:
    """Project a B graph back into A's page graph (lossless for A fields)."""
    meta = _meta_from_b_evidence(b_graph.get("evidence", []) or [])
    provenance = meta.get("provenance", {}) or {}
    assumptions = meta.get("assumptions", {}) or {}
    step_details = meta.get("stepDetails", {}) or {}
    import_notes = meta.get("importNotes", {}) or {}
    packet = packet or {}
    packet_origin = B_ORIGIN_TO_A.get(packet.get("origin"))
    evidence_by_id = {item["id"]: item for item in b_graph.get("evidence", []) or []
                      if not (item.get("kind") == "observation"
                              and str(item.get("unknownReason", "")).startswith(META_REASON_PREFIX))}

    processes_by_node: dict = {}
    for process in b_graph.get("processes", []) or []:
        for step in process.get("steps", []) or []:
            processes_by_node.setdefault(step["nodeId"], []).append(step)

    nodes = []
    for node in b_graph.get("nodes", []) or []:
        node_id = node["id"]
        evidence = [b_evidence_to_a(evidence_by_id[eid]) for eid in node.get("evidenceIds", [])
                    if eid in evidence_by_id]
        entry_points, interfaces, interface_details = [], [], []
        for interface in node.get("interfaces", []) or []:
            if interface.get("kind") == "code_entry" and \
                    interface.get("description", "") == ENTRY_DESCRIPTION:
                entry_points.append(interface["name"])
            elif interface.get("kind") == "team_contract" and \
                    interface.get("description", "") == CONTRACT_DESCRIPTION:
                interfaces.append(interface["name"])
            else:
                detail = {"name": interface.get("name"), "kind": interface.get("kind"),
                          "description": interface.get("description")}
                if interface.get("evidenceIds"):
                    detail["evidence"] = [b_evidence_to_a(evidence_by_id[eid])
                                          for eid in interface["evidenceIds"] if eid in evidence_by_id]
                interface_details.append(detail)
        node_steps = processes_by_node.get(node_id, [])
        reverse_ids = {}
        for step in node_steps:
            b_step_id = step.get("id", "")
            a_step_id = b_step_id
            if b_step_id.endswith("--" + node_id):
                a_step_id = b_step_id[: -len("--" + node_id)]
            reverse_ids[b_step_id] = a_step_id
        steps = []
        for step in node_steps:
            b_step_id = step.get("id", "")
            a_step_id = reverse_ids[b_step_id]
            next_steps = [reverse_ids.get(target, target) for target in (step.get("nextStepIds", []) or [])]
            branches = [branch.get("condition", "") for branch in step.get("branches", []) or []]
            # a branch target that is not already in next carries real data:
            # keep it instead of dropping it (BATCH-1 A-01)
            for branch in step.get("branches", []) or []:
                target = branch.get("nextStepId")
                mapped = reverse_ids.get(target, target)
                if isinstance(target, str) and target not in (b_step_id, next_steps and "") \
                        and mapped not in next_steps and target != b_step_id:
                    next_steps.append(mapped)
            entry = {
                "stepId": a_step_id,
                "title": step.get("title", ""),
                "detail": step_details.get(b_step_id, ""),
                "inputs": list(step.get("inputs", []) or []),
                "outputs": list(step.get("outputs", []) or []),
                "branches": branches,
                "next": next_steps,
            }
            if step.get("condition"):
                entry["condition"] = step["condition"]
            if step.get("allowedFailures"):
                entry["allowedFailures"] = list(step["allowedFailures"])
            if step.get("evidenceIds"):
                entry["evidence"] = [b_evidence_to_a(evidence_by_id[eid])
                                     for eid in step["evidenceIds"] if eid in evidence_by_id]
            steps.append(entry)
        node_out = {
            "id": node_id,
            "title": node.get("title", ""),
            "summary": node.get("responsibility", ""),
            "status": STATUS_TO_A.get(node.get("implementationStatus"), "candidate"),
            "provenance": provenance.get(node_id) or packet_origin or
                          ("code_fact" if any(item.get("kind") == "code_fact" for item in evidence)
                           else "human_input"),
            "entryPoints": entry_points,
            "interfaces": interfaces,
            "evidence": evidence,
            "process": steps,
            "assumptions": list(assumptions.get(node_id, []) or []),
        }
        if interface_details:
            node_out["interfaceDetails"] = interface_details
        if import_notes.get(node_id):
            node_out["importNote"] = import_notes[node_id]
        nodes.append(node_out)

    edges = []
    for edge in b_graph.get("edges", []) or []:
        a_type = EDGE_TYPE_TO_A.get(edge.get("type"))
        if a_type is None:
            raise ContractError("BACKEND_UNAVAILABLE", f"B 返回未知关系类型: {edge.get('type')!r}")
        edges.append({"from": edge.get("from"), "to": edge.get("to"),
                      "type": a_type, "label": edge.get("label", "")})
    return {"nodes": nodes, "edges": edges}


def diff_to_operations(old_b_graph: dict, new_b_graph: dict) -> list:
    """Compute B draft operations turning old_b_graph into new_b_graph.

    Objects are matched by ID; identities are stable across projections
    (node/step IDs are A's; evidence/edge/interface IDs are content hashes).
    Ordering respects B's per-operation checks: steps of a removed process are
    never touched, step operations run before/after their process exists.
    """
    operations = []

    def _update_or_replace(key, object_id, old_object, new_object, extra=None):
        """B's update cannot delete a key: a disappearing field is a
        remove+add pair so the new object is reproduced exactly (BATCH-1 A-03)."""
        extra = dict(extra or {})
        removed_fields = set(old_object) - set(new_object)
        if removed_fields:
            operations.append({"op": f"{key}.remove", "id": object_id, **extra})
            operations.append({"op": f"{key}.add", "value": copy.deepcopy(new_object), **extra})
            return
        changes = {field: copy.deepcopy(value) for field, value in new_object.items()
                   if old_object.get(field) != value and field != "id"}
        if changes:
            operations.append({"op": f"{key}.update", "id": object_id, "changes": changes, **extra})

    collections = (("nodes", "node"), ("edges", "edge"), ("evidence", "evidence"))
    for collection, key in collections:
        old = {item["id"]: item for item in old_b_graph.get(collection, []) or []}
        new = {item["id"]: item for item in new_b_graph.get(collection, []) or []}
        for object_id in sorted(set(old) - set(new)):
            operations.append({"op": f"{key}.remove", "id": object_id})
        for object_id in sorted(set(new)):
            if object_id not in old:
                operations.append({"op": f"{key}.add", "value": copy.deepcopy(new[object_id])})
            elif old[object_id] != new[object_id]:
                _update_or_replace(key, object_id, old[object_id], new[object_id])

    old_processes = {item["id"]: item for item in old_b_graph.get("processes", []) or []}
    new_processes = {item["id"]: item for item in new_b_graph.get("processes", []) or []}
    old_steps = {step["id"]: (process["id"], step)
                 for process in old_processes.values() for step in process["steps"]}
    new_steps = {step["id"]: (process["id"], step)
                 for process in new_processes.values() for step in process["steps"]}
    removed_processes = set(old_processes) - set(new_processes)

    added_processes = set(new_processes) - set(old_processes)
    # 1) steps that disappear from a process that SURVIVES
    for step_id in sorted(set(old_steps) - set(new_steps)):
        process_id = old_steps[step_id][0]
        if process_id not in removed_processes:
            operations.append({"op": "step.remove", "id": step_id, "processId": process_id})
    # 2) whole processes that disappear (their steps go with them)
    for process_id in sorted(removed_processes):
        operations.append({"op": "process.remove", "id": process_id})
    # 3) new processes carry their full steps in one add: emitting step.add for
    #    them as well duplicates ids and makes B reject the batch (BATCH-1 A-02)
    for process_id in sorted(added_processes):
        operations.append({"op": "process.add", "value": copy.deepcopy(new_processes[process_id])})
    # 4) surviving processes: metadata fields only; steps are handled by
    #    step.* operations so nothing is added twice
    for process_id in sorted(set(new_processes) & set(old_processes)):
        old_process, new_process = old_processes[process_id], new_processes[process_id]
        if {k: v for k, v in old_process.items() if k != "steps"} == \
                {k: v for k, v in new_process.items() if k != "steps"}:
            continue
        if set(old_process) - set(new_process):
            operations.append({"op": "process.remove", "id": process_id})
            operations.append({"op": "process.add", "value": copy.deepcopy(new_process)})
            continue
        changes = {field: copy.deepcopy(value) for field, value in new_process.items()
                   if field != "steps" and field != "id" and old_process.get(field) != value}
        if changes:
            operations.append({"op": "process.update", "id": process_id, "changes": changes})
    # 5) steps of surviving processes
    for step_id in sorted(set(new_steps)):
        process_id, step = new_steps[step_id]
        if process_id in added_processes:
            continue
        if step_id not in old_steps:
            operations.append({"op": "step.add", "processId": process_id,
                               "value": copy.deepcopy(step)})
        else:
            old_process, old_step = old_steps[step_id]
            if old_process != process_id:
                if old_process in removed_processes or old_process != process_id:
                    operations.append({"op": "step.remove", "id": step_id, "processId": old_process})
                    operations.append({"op": "step.add", "processId": process_id,
                                       "value": copy.deepcopy(step)})
            elif old_step != step:
                if set(old_step) - set(step):
                    operations.append({"op": "step.remove", "id": step_id, "processId": process_id})
                    operations.append({"op": "step.add", "processId": process_id,
                                       "value": copy.deepcopy(step)})
                else:
                    changes = {field: copy.deepcopy(value) for field, value in step.items()
                               if old_step.get(field) != value and field != "id"}
                    if changes:
                        operations.append({"op": "step.update", "processId": process_id,
                                           "id": step_id, "changes": changes})
    return operations


def coverage_for(record: dict, b_graph: dict, verify_code: bool = True) -> dict:
    """Default review coverage.

    verify_code=True: every verifiable code evidence + the nodes fully backed
    by it; nodes referencing unknown or non-code evidence stay uncovered so
    the review shows partial coverage instead of claiming more.
    verify_code=False (design/planning confirmation): the human reviewed the
    whole draft, so all objects are listed as covered.
    """
    if not verify_code:
        # partial (never "all"): every node/edge/process the human saw is listed,
        # but the machine-marked projection carrier is not human content and
        # stays unconfirmed; an all-coverage claim would have to list it as
        # confirmed, which would be false (BATCH-1 A-05).
        return {"scope": "partial",
                "nodes": sorted(item["id"] for item in b_graph.get("nodes", []) or []),
                "edges": sorted(item["id"] for item in b_graph.get("edges", []) or []),
                "processes": sorted(item["id"] for item in b_graph.get("processes", []) or []),
                # the machine-marked projection carrier is never human-reviewed
                # content: listing it as confirmed would be a false claim
                "evidence": sorted(item["id"] for item in b_graph.get("evidence", []) or []
                                   if not (item.get("kind") == "observation"
                                           and str(item.get("unknownReason", "")).startswith(
                                               META_REASON_PREFIX)))}
    code_revision = record.get("identity", {}).get("codeRevision")
    evidence = {item["id"]: item for item in b_graph.get("evidence", []) or []}
    covered_evidence = sorted(
        item["id"] for item in evidence.values()
        if item.get("kind") == "code" and item.get("codeRevision") == code_revision
        and not item.get("unknownReason"))
    covered_set = set(covered_evidence)
    covered_nodes = []
    for node in b_graph.get("nodes", []) or []:
        needed = set(node.get("evidenceIds", [])) | {
            eid for interface in node.get("interfaces", []) or []
            for eid in interface.get("evidenceIds", [])}
        if needed <= covered_set:
            covered_nodes.append(node["id"])
    return {"scope": "partial", "nodes": sorted(covered_nodes),
            "edges": sorted(edge["id"] for edge in b_graph.get("edges", []) or []),
            "processes": [], "evidence": covered_evidence}


class BackendB:
    """Owns the configured B service instance and the A<->B call surface."""

    KIND = "architecture_workspace_v1"
    REF = "B PR #51 — runtime b58fee7455bf8348f50e3863759e53bbd711dc6d (head bba8e84)"

    def __init__(self, data_root, *, code_repositories=(), architecture_repo=None,
                 architecture_branch=None, allowed_origin=None):
        self.data_root = str(data_root)
        self.architecture_repo = str(architecture_repo) if architecture_repo else None
        self.architecture_branch = architecture_branch
        self.allowed_origin = allowed_origin
        self.available = False
        self.reason = None
        self.service = None
        self.gateway = None
        self.code_repositories = {}
        try:
            from extensions.architecture_workspace import HumanReviewGateway, WorkspaceService
            self.service = WorkspaceService(
                self.data_root, code_repositories=list(code_repositories),
                architecture_repo=architecture_repo, architecture_branch=architecture_branch)
            self.code_repositories = dict(self.service.code_repositories)
            if allowed_origin:
                self.gateway = HumanReviewGateway(self.service, allowed_origin)
            self.available = True
        except Exception as exc:  # a broken config is reported, never hidden
            self.reason = f"{type(exc).__name__}: {exc}"

    # ---------- status ----------

    def status(self) -> dict:
        label = {
            "kind": self.KIND if self.available else "unavailable",
            "available": self.available,
            "ref": self.REF,
            "dataRoot": self.data_root,
            "architectureRepo": self.architecture_repo,
            "architectureBranch": self.architecture_branch,
            "codeRepoIds": sorted(self.code_repositories),
            "reviewGateway": bool(self.gateway),
            "reason": self.reason,
        }
        if self.available:
            try:
                # real read probe, not a bare registration
                with self.service.store.transaction() as db:
                    db.execute("SELECT COUNT(*) FROM documents").fetchone()
                label["probe"] = "ok"
            except Exception as exc:
                label["available"] = False
                label["kind"] = "unavailable"
                label["reason"] = f"probe failed: {type(exc).__name__}: {exc}"
        label["labeled"] = ("B 的真实版本服务已接入：草稿经人审确认后由该服务产生不可变认知版本"
                            if label["available"] else
                            f"B 版本服务不可用：{self.reason or '未配置数据根/架构仓库'}")
        return label

    def require(self):
        if not self.available or self.service is None:
            raise ContractError("BACKEND_UNAVAILABLE",
                                f"B 版本服务不可用：{self.reason or '未配置'}")
        return self.service

    def repo_id_for(self, path: str) -> str:
        """Registered-repo lookup by configured path; identity comes from B."""
        from pathlib import Path as _Path
        from repo_index.gitio import repository_root
        root = str(repository_root(_Path(path)))
        for repo_id, repo in self.code_repositories.items():
            if str(repo) == root:
                return repo_id
        raise ContractError("STALE_CONTEXT", f"代码仓库未在服务端登记: {root}")

    # ---------- error translation ----------

    def _wrap(self, func, *args, **kwargs):
        from extensions.architecture_workspace.errors import WorkspaceError
        try:
            return func(*args, **kwargs)
        except WorkspaceError as exc:
            code = B_ERROR_TO_A.get(exc.code, "BACKEND_UNAVAILABLE")
            raise ContractError(code, f"版本服务拒绝：{exc.detail}",
                                {"backendCode": exc.code}) from exc
        except ContractError:
            raise
        except Exception as exc:
            raise ContractError("BACKEND_UNAVAILABLE",
                                f"版本服务调用失败：{type(exc).__name__}: {exc}") from exc

    # ---------- workspace / draft ----------

    def ensure_workspace(self, record: dict) -> dict:
        service = self.require()
        identity = record["identity"]
        binding = record.get("backendB") or {}
        mode = record["context"]
        if binding.get("workspaceId"):
            return self._wrap(service.open_workspace, workspace_id=binding["workspaceId"],
                              code_revision=identity.get("codeRevision"))
        code_repo_id = None
        if mode != "planning":
            code_repo_id = self.repo_id_for(identity["repoPath"])
        return self._wrap(service.open_workspace, mode=mode, code_repo_id=code_repo_id,
                          code_revision=identity.get("codeRevision"),
                          map_id=identity.get("mapId") if record.get("mapIdProvided") else None)

    def sync_draft(self, record: dict, a_graph: dict, *, origin: str,
                   allow_rebase: bool = False) -> dict:
        """Create or update B's draft so it equals the A draft (via operations)."""
        payload_allows_rebase = allow_rebase
        service = self.require()
        identity = record["identity"]
        code_repo_id = None if record["context"] == "planning" else self.repo_id_for(identity["repoPath"])
        workspace = self.ensure_workspace(record)
        projection = a_to_b_graph(a_graph, code_repo_id=code_repo_id,
                                  code_revision=identity.get("codeRevision"))
        b_origin = A_DRAFT_ORIGIN_TO_B.get(origin, "manual")
        binding = dict(record.get("backendB") or {})
        binding.update({"workspaceId": workspace["workspaceId"], "mapId": workspace["mapId"]})

        draft = None
        if binding.get("draftId"):
            draft = self._wrap(service.get_draft, binding["draftId"])
            expected_b_revision = binding.get("bDraftRevision")
            if expected_b_revision is not None and draft["draftRevision"] != expected_b_revision \
                    and not payload_allows_rebase:
                # another writer changed the shared draft: syncing the stale A
                # graph would silently revert their work (BATCH-1 SYNC-01)
                raise ContractError("REVISION_CONFLICT",
                                    "版本服务中的草稿已被其他写入者修改；请先读取差异再决定",
                                    {"expected": expected_b_revision,
                                     "current": draft["draftRevision"]})
        created_fresh = False
        if draft is not None and draft.get("status") == "published":
            # the published draft is frozen; further edits need a new draft
            # based on the published map revision (B semantics, not A's).
            draft = self._wrap(service.create_draft, workspace["workspaceId"],
                               from_map_revision=draft.get("publishedMapRevision")
                               or workspace["mapRevision"],
                               base_map_revision=workspace["mapRevision"], origin="restored")
            created_fresh = True
        if draft is None:
            draft = self._wrap(service.create_draft, workspace["workspaceId"],
                               graph=projection["graph"],
                               base_map_revision=workspace["mapRevision"], origin=b_origin)
            created_fresh = True
            operations = ([{"op": "layout.set", "value": projection["layout"]}]
                          if projection["layout"] else [])
        else:
            operations = diff_to_operations(draft["graph"], projection["graph"])
            if projection["layout"]:
                operations.append({"op": "layout.set", "value": projection["layout"]})
        binding.update({"draftId": draft["draftId"], "proposalId": draft["proposalId"],
                        "bDraftRevision": draft["draftRevision"]})
        if not operations:
            return {"created": created_fresh, "draft": draft, "binding": binding, "noop": True}
        draft = self._wrap(service.apply_draft_operations, draft["draftId"],
                           operations=operations,
                           expected_draft_revision=draft["draftRevision"],
                           base_map_revision=workspace["mapRevision"],
                           proposal_id=binding["proposalId"])
        binding["bDraftRevision"] = draft["draftRevision"]
        return {"created": created_fresh, "draft": draft, "binding": binding,
                "operations": operations}

    def draft_state(self, record: dict) -> dict | None:
        binding = record.get("backendB") or {}
        if not binding.get("draftId"):
            return None
        return self._wrap(self.require().get_draft, binding["draftId"])

    def current_b_graph(self, record: dict) -> dict | None:
        draft = self.draft_state(record)
        return draft["graph"] if draft else None

    # ---------- review / publish ----------

    def create_session(self, actor: str, meta: dict) -> dict:
        if self.gateway is None:
            raise ContractError("BACKEND_UNAVAILABLE", "未配置人审 Gateway（需要 loopback origin）")
        return self._wrap(self.gateway.create_session, actor,
                          peer=meta["peer"], host=meta["host"], origin=meta["origin"])

    def assert_session_active(self, record: dict, meta: dict) -> None:
        """Refuse when the stored review session is gone/expired or the caller's
        real peer/host/origin no longer match it (publish/session boundary)."""
        if self.gateway is None:
            raise ContractError("BACKEND_UNAVAILABLE", "未配置人审 Gateway")
        session = (record.get("backendB") or {}).get("sessionSecret") or {}
        if not session:
            raise ContractError("REQUEST_FORBIDDEN", "没有有效的人审会话；请重新预览并确认")
        self._wrap(self.gateway._session, session_id=session.get("sessionId"),
                   csrf_token=session.get("csrfToken"), peer=meta["peer"],
                   host=meta["host"], origin=meta["origin"])

    def preview_review(self, record: dict, request: dict, meta: dict) -> dict:
        if self.gateway is None:
            raise ContractError("BACKEND_UNAVAILABLE", "未配置人审 Gateway")
        binding = record.get("backendB") or {}
        if not binding.get("draftId"):
            raise ContractError("VALIDATION_FAILED", "草稿尚未同步到版本服务；请先保存草稿")
        auth = {"session_id": request.get("sessionId"), "csrf_token": request.get("csrfToken"),
                "peer": meta["peer"], "host": meta["host"], "origin": meta["origin"]}
        draft = self._wrap(self.service.get_draft, binding["draftId"])
        default_verify = bool(draft["codeRepoId"])
        if request.get("verifyCode") is None:
            verify_code = default_verify
        else:
            verify_code = bool(request.get("verifyCode"))
        if verify_code and not draft["codeRepoId"]:
            raise ContractError("VALIDATION_FAILED",
                                "规划工作区没有代码，不能做代码核查；请以 verifyCode=false 确认设计")
        coverage = request.get("coverage") or coverage_for(record, draft["graph"], verify_code)
        limits = request.get("limits") or ["核查仅适用于列明覆盖；未列出的对象与证据未核查"]
        return self._wrap(
            self.gateway.preview_review, binding["draftId"], auth=auth,
            reason=request.get("reason") or "工作台人审预览",
            expected_draft_revision=draft["draftRevision"],
            expected_map_revision=draft["baseMapRevision"],
            proposal_id=draft["proposalId"],
            code_repo_id=draft["codeRepoId"], code_revision=draft["codeRevision"],
            coverage=coverage, limits=limits,
            verify_code=verify_code,
            rejected_candidates=request.get("rejectedCandidates") or [])

    def confirm_review(self, record: dict, request: dict, meta: dict) -> dict:
        if self.gateway is None:
            raise ContractError("BACKEND_UNAVAILABLE", "未配置人审 Gateway")
        binding = record.get("backendB") or {}
        decision = request.get("decision")
        if decision not in ("accept", "reject"):
            raise ContractError("VALIDATION_FAILED", "decision 必须是 accept/reject")
        auth = {"session_id": request.get("sessionId"), "csrf_token": request.get("csrfToken"),
                "peer": meta["peer"], "host": meta["host"], "origin": meta["origin"]}
        draft = self._wrap(self.service.get_draft, binding["draftId"])
        return self._wrap(
            self.gateway.confirm_review, binding["draftId"], auth=auth,
            confirmation_token=request.get("confirmationToken"),
            preview_digest=request.get("previewDigest"), decision=decision,
            expected_draft_revision=draft["draftRevision"],
            expected_map_revision=draft["baseMapRevision"],
            proposal_id=draft["proposalId"],
            code_repo_id=draft["codeRepoId"], code_revision=draft["codeRevision"])

    def publish(self, record: dict, request: dict, meta: dict) -> dict:
        service = self.require()
        binding = record.get("backendB") or {}
        if not binding.get("draftId"):
            raise ContractError("VALIDATION_FAILED", "草稿尚未同步到版本服务")
        draft = self._wrap(service.get_draft, binding["draftId"])
        return self._wrap(service.publish_reviewed_graph, binding["draftId"],
                          publication_token=request.get("publicationToken"),
                          expected_map_revision=draft["baseMapRevision"])

    # ---------- versions ----------

    def get_version(self, workspace_b_id: str, map_revision: str) -> dict:
        return self._wrap(self.require().get_version, workspace_b_id, map_revision)

    def export_version(self, workspace_b_id: str, map_revision: str) -> dict:
        return self._wrap(self.require().export_version, workspace_b_id, map_revision)

    def import_git_version(self, workspace_b_id: str, *, map_revision, map_source_revision,
                           expected_map_revision) -> dict:
        return self._wrap(self.require().import_git_version, workspace_b_id,
                          map_revision=map_revision, map_source_revision=map_source_revision,
                          expected_map_revision=expected_map_revision)

    def graph_snapshot(self, workspace_b_id: str) -> dict:
        return self._wrap(self.require().graph_snapshot, workspace_b_id)

    def associate_code(self, workspace_b_id: str, *, code_repo_id, code_revision,
                       expected_map_revision) -> dict:
        return self._wrap(self.require().associate_code, workspace_b_id,
                          code_repo_id=code_repo_id, code_revision=code_revision,
                          expected_map_revision=expected_map_revision)

    # ---------- adapter-registry compatibility ----------

    def call(self, action: str, payload: dict) -> dict:
        if action == "status":
            return self.status()
        raise ContractError(
            "BACKEND_UNAVAILABLE",
            f"B 版本服务不接受单步动作 {action!r}：人审与发布必须走 预览→确认→发布 的真实会话流程",
            {"action": action})


__all__ = ["BackendB", "a_to_b_graph", "b_to_a_graph", "diff_to_operations", "coverage_for",
           "EDGE_TYPE_TO_B", "EDGE_TYPE_TO_A", "STATUS_TO_B", "STATUS_TO_A",
           "A_DRAFT_ORIGIN_TO_B", "B_ORIGIN_TO_A", "META_EVIDENCE_ID", "META_REASON_PREFIX"]