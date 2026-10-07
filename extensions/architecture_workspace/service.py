"""Single B service: drafts, CAS, human review, immutable Git-backed versions."""
from __future__ import annotations

import copy
import hashlib
import hmac
import secrets
import time
from pathlib import Path

from repo_index.gitio import repository_root
from .errors import WorkspaceError, require
from .git_publication import (GitPublisher, code_identity, full_revision,
                              read_git, verify_evidence)
from .schema import (SCHEMA, canonical, digest, fields, identifier, records,
                     semantic_version, strings, text, validate_coverage, validate_graph,
                     VERIFICATION_LIMIT, input_guard, confirmation_states)
from .storage import Store


def new_id(prefix):
    return prefix + "-" + secrets.token_hex(16)


def token_hash(token):
    require(isinstance(token, str) and 32 <= len(token) <= 200, "HUMAN_REVIEW_REQUIRED")
    return hashlib.sha256(token.encode()).hexdigest()


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


class WorkspaceService:
    def __init__(self, data_root, *, code_repositories=(), architecture_repo=None,
                 architecture_branch=None):
        root = Path(data_root).resolve()
        self.code_repositories = {}
        for path in code_repositories:
            repo = repository_root(Path(path))
            key = code_identity(repo)
            require(key not in self.code_repositories, detail="同一来源只能登记一个代码工作副本")
            require(not overlaps(root, repo), detail="数据根不能与代码仓库重叠")
            self.code_repositories[key] = repo
        self.publisher = None
        if architecture_repo is not None:
            arch = repository_root(Path(architecture_repo))
            require(not overlaps(root, arch), detail="数据根不能与架构仓库重叠")
            require(all(not overlaps(arch, repo) for repo in self.code_repositories.values()),
                    detail="架构发布仓库不能是代码仓库")
            self.publisher = GitPublisher(arch, architecture_branch)
        self.store = Store(data_root)

    def _repo(self, repo_id, revision):
        identifier(repo_id)
        require(repo_id in self.code_repositories, "STALE_CONTEXT",
                "代码仓库未由服务端登记")
        repo = self.code_repositories[repo_id]
        require(code_identity(repo) == repo_id, "STALE_CONTEXT", "代码来源身份已改变")
        full_revision(repo, revision)
        return repo

    def _context(self, mode, repo_id, revision):
        require(mode in ("existing_project", "planning", "mixed"))
        if mode == "planning":
            require(repo_id is None and revision is None, "STALE_CONTEXT")
        else:
            self._repo(repo_id, revision)
        return {"mode": mode, "codeRepoId": repo_id, "codeRevision": revision}

    def open_workspace(self, *, workspace_id=None, map_id=None, mode=None,
                       code_repo_id=None, code_revision=None):
        with self.store.transaction() as db:
            if workspace_id:
                ws = Store.get(db, "workspace", identifier(workspace_id))
                require(map_id in (None, ws["mapId"]) and mode in (None, ws["mode"])
                        and code_repo_id in (None, ws["codeRepoId"]), "STALE_CONTEXT")
                if ws["codeRepoId"]:
                    self._repo(ws["codeRepoId"], code_revision or ws["codeRevision"])
                if code_revision is not None and code_revision != ws["codeRevision"]:
                    require(not ws.get("pendingPublication"), "REVISION_CONFLICT",
                            "发布尚未收口，不能切换代码上下文")
                    repo = self._repo(ws["codeRepoId"], code_revision)
                    self._compatible(repo, ws["codeRevision"], code_revision)
                    ws["codeRevision"] = code_revision
                    Store.put(db, "workspace", workspace_id, ws)
                return copy.deepcopy(ws)
            context = self._context(mode, code_repo_id, code_revision)
            ws = {"workspaceId": new_id("workspace"), "mapId": identifier(map_id) if map_id
                  else new_id("map"), **context, "mapRevision": None, "designHistory": []}
            existing = db.execute("SELECT body FROM documents WHERE kind='workspace'").fetchall()
            import json
            require(all(json.loads(row[0])["mapId"] != ws["mapId"] for row in existing),
                    "STALE_CONTEXT", "地图身份已经属于另一工作区")
            Store.put(db, "workspace", ws["workspaceId"], ws)
            return copy.deepcopy(ws)

    def associate_code(self, workspace_id, *, code_repo_id, code_revision,
                       expected_map_revision):
        self._repo(code_repo_id, code_revision)
        with self.store.transaction() as db:
            ws = Store.get(db, "workspace", identifier(workspace_id))
            require(ws["mode"] == "planning", "STALE_CONTEXT")
            require(not ws.get("pendingPublication"), "REVISION_CONFLICT")
            require(ws["mapRevision"] == expected_map_revision, "REVISION_CONFLICT")
            if ws["mapRevision"]:
                ws["designHistory"].append(ws["mapRevision"])
            ws.update(mode="mixed", codeRepoId=code_repo_id, codeRevision=code_revision)
            Store.put(db, "workspace", workspace_id, ws)
            return copy.deepcopy(ws)

    @staticmethod
    def _compatible(repo, old, target):
        if old == target:
            return
        try:
            merge = read_git(repo, "merge-base", old, target).decode().strip()
        except WorkspaceError as exc:
            raise WorkspaceError("STALE_CONTEXT", "代码分支与当前基线不相容") from exc
        require(merge == old, "STALE_CONTEXT", "代码分支不是当前基线的后继")

    @staticmethod
    def _current(db, draft):
        ws = Store.get(db, "workspace", draft["workspaceId"])
        require(all(ws[key] == draft[key] for key in
                    ("mapId", "mode", "codeRepoId", "codeRevision")), "STALE_CONTEXT")
        return ws

    def _evidence(self, graph, context):
        if context["codeRepoId"] is None:
            return
        repo = self._repo(context["codeRepoId"], context["codeRevision"])
        for evidence in graph["evidence"]:
            if evidence["kind"] == "code" and not evidence.get("unknownReason"):
                verify_evidence(repo, evidence, context["codeRevision"])

    def create_draft(self, workspace_id, *, graph=None, base_map_revision=None,
                     origin="manual", proposal_id=None, from_map_revision=None, legacy=None):
        require(origin in ("manual", "ai_generated", "rule_based", "legacy", "restored"))
        proposal_id = identifier(proposal_id) if proposal_id else new_id("proposal")
        with self.store.transaction() as db:
            ws = Store.get(db, "workspace", identifier(workspace_id))
            require(ws["mapRevision"] == base_map_revision, "REVISION_CONFLICT")
            layout = {}
            require(sum(x is not None for x in (graph, legacy, from_map_revision)) == 1)
            if from_map_revision is not None:
                version = Store.get(db, "version", workspace_id + "/" + from_map_revision)
                graph = copy.deepcopy(version["version"]["graph"]); origin = "restored"
                for ev in graph["evidence"]:
                    if ev["kind"] == "code" and ev["codeRevision"] != ws["codeRevision"]:
                        ev["unknownReason"] = "历史证据尚未核查到当前目标提交"
            elif legacy is not None:
                require(ws["mode"] != "planning", "STALE_CONTEXT")
                graph, layout = self._legacy(legacy, ws); origin = "legacy"
            graph = validate_graph(graph, ws)
            self._evidence(graph, ws)
            draft = {"draftId": new_id("draft"), "workspaceId": workspace_id,
                     **{k: ws[k] for k in ("mapId", "mode", "codeRepoId", "codeRevision")},
                     "baseMapRevision": base_map_revision, "draftRevision": 1,
                     "origin": origin, "proposalId": proposal_id, "status": "unconfirmed",
                     "graph": graph, "layout": layout, "operations": []}
            Store.put(db, "draft", draft["draftId"], draft)
            return copy.deepcopy(draft)

    @staticmethod
    def _legacy(legacy, ws):
        fields(legacy, ("note", "nodes", "edges"))
        text(legacy["note"])
        nodes = records(legacy["nodes"])
        require(bool(nodes) and isinstance(legacy["edges"], list))
        graph = {"schemaVersion": SCHEMA, "nodes": [], "edges": [],
                 "evidence": [], "processes": []}
        layout = {}
        for node in nodes.values():
            fields(node, ("id", "title", "summary", "entryPoint", "position", "evidence"))
            fields(node["position"], ("x", "y"))
            import math
            require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0
                        for v in node["position"].values()))
            text(node["title"]); text(node["summary"]); text(node["entryPoint"])
            require(isinstance(node["evidence"], list))
            evidence_ids = []
            for item in node["evidence"]:
                fields(item, ("path", "reason"))
                eid = new_id("evidence"); evidence_ids.append(eid)
                graph["evidence"].append({"id": eid, "kind": "code", **item,
                                         "codeRepoId": ws["codeRepoId"],
                                         "codeRevision": ws["codeRevision"]})
            graph["nodes"].append({"id": node["id"], "title": node["title"],
                                  "responsibility": node["summary"],
                                  "implementationStatus": "unknown", "evidenceIds": evidence_ids,
                                  "interfaces": [{"id": new_id("interface"), "name": node["entryPoint"],
                                                  "kind": "code_entry",
                                                  "description": "旧人工图声明，待人核查",
                                                  "evidenceIds": evidence_ids}]})
            layout[node["id"]] = node["position"]
        for edge in legacy["edges"]:
            fields(edge, ("from", "to", "label"))
            graph["edges"].append({"id": new_id("edge"), **edge,
                                  "type": "functional_collaboration", "evidenceIds": []})
        return graph, layout

    def get_draft(self, draft_id):
        with self.store.transaction() as db:
            return Store.get(db, "draft", identifier(draft_id))

    def apply_draft_operations(self, draft_id, *, operations, expected_draft_revision,
                               base_map_revision, proposal_id):
        require(isinstance(operations, list) and 0 < len(operations) <= 128)
        with self.store.transaction() as db:
            draft = Store.get(db, "draft", identifier(draft_id))
            ws = self._current(db, draft)
            require(draft["status"] not in ("published", "publishing"), "VERSION_CONFLICT")
            require(type(expected_draft_revision) is int
                    and draft["draftRevision"] == expected_draft_revision
                    and draft["baseMapRevision"] == base_map_revision == ws["mapRevision"],
                    "REVISION_CONFLICT")
            require(proposal_id == draft["proposalId"], "STALE_CONTEXT")
            graph = copy.deepcopy(draft["graph"])
            for operation in copy.deepcopy(operations):
                fields(operation, ("op",), ("id", "value", "changes", "processId",
                                           "source", "operationId"))
                op = operation["op"]
                require(isinstance(op, str))
                if op == "layout.set":
                    fields(operation, ("op", "value"), ("source", "operationId"))
                    layout = operation["value"]
                    require(isinstance(layout, dict) and set(layout) <= {n["id"] for n in graph["nodes"]})
                    import math
                    for pos in layout.values():
                        fields(pos, ("x", "y"))
                        require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0
                                    for v in pos.values()))
                    draft["layout"] = layout
                else:
                    parts = op.split(".")
                    require(len(parts) == 2 and parts[0] in
                            ("node", "edge", "evidence", "process", "step")
                            and parts[1] in ("add", "update", "remove", "reorder"))
                    entity, action = parts
                    required = {"add": ("value",), "update": ("id", "changes"),
                                "remove": ("id",), "reorder": ("value",)}[action]
                    fields(operation, ("op",) + required +
                           (("processId",) if entity == "step" else ()),
                           ("source", "operationId"))
                    if entity == "step":
                        process = next((p for p in graph["processes"]
                                        if p["id"] == operation.get("processId")), None)
                        require(process is not None, "REFERENCE_CONFLICT")
                        collection = process["steps"]
                    else:
                        collection = graph[{"node": "nodes", "edge": "edges",
                                            "evidence": "evidence", "process": "processes"}[entity]]
                    if action == "reorder":
                        require(entity == "step" and isinstance(operation.get("value"), list))
                        order = operation["value"]; objects = records(collection)
                        strings(order)
                        require(len(order) == len(objects) and set(order) == set(objects))
                        collection[:] = [objects[key] for key in order]
                    elif action == "add":
                        require(isinstance(operation.get("value"), dict))
                        obj = copy.deepcopy(operation["value"])
                        if "id" not in obj:
                            obj["id"] = new_id(entity)
                        identifier(obj["id"])
                        require(obj["id"] not in records(collection), detail="对象 ID 已存在")
                        collection.append(obj); operation["value"] = obj
                    else:
                        identifier(operation.get("id"))
                        obj = next((o for o in collection if o["id"] == operation["id"]), None)
                        require(obj is not None, "REFERENCE_CONFLICT")
                        if action == "remove":
                            collection.remove(obj)
                            if entity == "node":
                                draft["layout"].pop(obj["id"], None)
                        else:
                            require(isinstance(operation.get("changes"), dict)
                                    and "id" not in operation["changes"], detail="修改不能替换稳定 ID")
                            obj.update(operation["changes"])
                operation["operationId"] = identifier(operation.get("operationId") or new_id("operation"))
                require(operation["operationId"] not in {o["operationId"] for o in draft["operations"]})
                operation["source"] = operation.get("source", "human")
                require(operation["source"] in ("human", "ai_generated", "rule_based"))
                draft["operations"].append(operation)
            draft["graph"] = validate_graph(graph, draft)
            self._evidence(draft["graph"], draft)
            draft["draftRevision"] += 1; draft["status"] = "unconfirmed"
            draft.pop("reviewId", None)
            Store.put(db, "draft", draft_id, draft)
            return copy.deepcopy(draft)

    def _preview(self, draft_id, *, actor, reason, expected_draft_revision,
                 expected_map_revision, proposal_id, code_repo_id, code_revision,
                 coverage, limits, verify_code, rejected_candidates, ttl=300):
        """Only the trusted HumanReviewGateway invokes this private boundary."""
        text(actor); text(reason); strings(limits)
        require(type(verify_code) is bool and type(ttl) is int and 0 < ttl <= 600)
        require(type(expected_draft_revision) is int)
        require(isinstance(rejected_candidates, list) and len(rejected_candidates) <= 128)
        for candidate in rejected_candidates:
            fields(candidate, ("proposalId", "candidateId", "reason"))
            identifier(candidate["proposalId"]); identifier(candidate["candidateId"])
            text(candidate["reason"])
        with self.store.transaction() as db:
            draft = Store.get(db, "draft", identifier(draft_id))
            ws = self._current(db, draft)
            require(draft["draftRevision"] == expected_draft_revision
                    and draft["baseMapRevision"] == expected_map_revision == ws["mapRevision"],
                    "REVISION_CONFLICT")
            require(draft["status"] not in ("published", "publishing"), "VERSION_CONFLICT")
            require(proposal_id == draft["proposalId"]
                    and code_repo_id == draft["codeRepoId"]
                    and code_revision == draft["codeRevision"], "STALE_CONTEXT")
            coverage = validate_coverage(coverage, draft["graph"])
            old = None if expected_map_revision is None else Store.get(
                db, "version", draft["workspaceId"] + "/" + expected_map_revision)["version"]["graph"]
            preview = {"draftId": draft_id, "draftRevision": draft["draftRevision"],
                       "workspaceId": draft["workspaceId"], "mapId": draft["mapId"],
                       "expectedMapRevision": expected_map_revision,
                       "codeRepoId": code_repo_id, "codeRevision": code_revision,
                       "proposalId": proposal_id, "actor": actor, "reason": reason,
                       "beforeGraph": old, "afterGraph": draft["graph"],
                       "appliedOperations": draft["operations"],
                       "rejectedCandidates": rejected_candidates,
                       "reviewCoverage": coverage, "limits": limits, "verifyCode": verify_code,
                       "origin": draft["origin"]}
            token = secrets.token_urlsafe(32)
            Store.put(db, "intent", token_hash(token), {"preview": preview,
                      "previewDigest": digest(preview), "expiresAt": time.time() + ttl,
                      "response": None})
            return {"preview": preview, "previewDigest": digest(preview),
                    "confirmationToken": token, "expiresInSeconds": ttl}

    def record_review(self, draft_id, *, confirmation_token, preview_digest, decision,
                      expected_draft_revision, expected_map_revision, proposal_id,
                      code_repo_id, code_revision):
        require(decision in ("accept", "reject"))
        require(type(expected_draft_revision) is int)
        with self.store.transaction() as db:
            intent = Store.get(db, "intent", token_hash(confirmation_token), optional=True)
            require(intent is not None, "HUMAN_REVIEW_REQUIRED")
            p = intent["preview"]
            request = {"draftId": draft_id, "draftRevision": expected_draft_revision,
                       "expectedMapRevision": expected_map_revision, "proposalId": proposal_id,
                       "codeRepoId": code_repo_id, "codeRevision": code_revision}
            require(all(p[key] == val for key, val in request.items()), "STALE_CONTEXT")
            require(hmac.compare_digest(str(preview_digest), intent["previewDigest"]),
                    "HUMAN_REVIEW_REQUIRED")
            if intent["response"]:
                require(intent["decision"] == decision, "REVIEW_REPLAY")
                return copy.deepcopy(intent["response"])
            require(time.time() < intent["expiresAt"], "REVIEW_EXPIRED")
            draft = Store.get(db, "draft", identifier(draft_id)); ws = self._current(db, draft)
            require(draft["status"] not in ("publishing", "published"), "VERSION_CONFLICT")
            require(draft["draftRevision"] == expected_draft_revision
                    and draft["baseMapRevision"] == expected_map_revision == ws["mapRevision"],
                    "REVISION_CONFLICT")
            require(draft["graph"] == p["afterGraph"] and draft["operations"] == p["appliedOperations"],
                    "HUMAN_REVIEW_REQUIRED")
            self._evidence(draft["graph"], draft)
            verified = None
            if decision == "accept" and p["verifyCode"]:
                require(draft["codeRepoId"] is not None, "EVIDENCE_MISMATCH")
                covered = {e["id"]: e for e in draft["graph"]["evidence"]
                           if e["id"] in p["reviewCoverage"]["evidence"]}
                require(any(e["kind"] == "code" for e in covered.values()),
                        "EVIDENCE_MISMATCH", "代码核查必须明确覆盖代码证据")
                require(all(e["kind"] not in ("unknown", "observation")
                            and not e.get("unknownReason") for e in covered.values()),
                        "EVIDENCE_MISMATCH", "未知证据不能成为代码核查依据")
                for node in draft["graph"]["nodes"]:
                    if node["id"] in p["reviewCoverage"]["nodes"]:
                        needed = set(node["evidenceIds"]) | {
                            eid for interface in node["interfaces"] for eid in interface["evidenceIds"]}
                        require(needed <= set(covered), "EVIDENCE_MISMATCH")
                for key in ("edges", "processes"):
                    for item in draft["graph"][key]:
                        if item["id"] in p["reviewCoverage"][key]:
                            needed = set(item["evidenceIds"])
                            if key == "processes":
                                needed |= {eid for step in item["steps"] for eid in step["evidenceIds"]}
                            require(needed <= set(covered), "EVIDENCE_MISMATCH")
                verified = draft["codeRevision"]
            review_id = new_id("review")
            publication = secrets.token_urlsafe(32) if decision == "accept" else None
            review = {**copy.deepcopy(p), "reviewId": review_id, "decision": decision,
                      "reviewedAt": time.time(), "previewDigest": preview_digest,
                      "verifiedCodeRevision": verified,
                      "actorIdentity": "local_operator_declaration"}
            Store.put(db, "review", review_id, review, immutable=True)
            Store.put(db, "permit", review_id, {"tokenHash": token_hash(publication)
                      if publication else None})
            draft.update(status="review_approved" if publication else "review_rejected",
                         reviewId=review_id)
            Store.put(db, "draft", draft_id, draft)
            response = {"reviewId": review_id, "decision": decision,
                        "publicationToken": publication, "verifiedCodeRevision": verified}
            intent.update(response=response, decision=decision)
            Store.put(db, "intent", token_hash(confirmation_token), intent)
            return response

    def publish_reviewed_graph(self, draft_id, *, publication_token, expected_map_revision):
        require(self.publisher is not None, "PUBLICATION_FAILED", "未配置独立架构 Git 工作副本")
        with self.store.transaction() as db:
            draft = Store.get(db, "draft", identifier(draft_id))
            require(draft.get("reviewId") is not None, "HUMAN_REVIEW_REQUIRED")
            permit = Store.get(db, "permit", draft["reviewId"])
            require(permit["tokenHash"] is not None and hmac.compare_digest(
                    token_hash(publication_token), permit["tokenHash"]), "HUMAN_REVIEW_REQUIRED")
            if draft["status"] == "published":
                require(expected_map_revision == draft["baseMapRevision"], "STALE_CONTEXT")
                return Store.get(db, "version", draft["workspaceId"] + "/" + draft["publishedMapRevision"])
            ws = self._current(db, draft)
            require(ws["mapRevision"] == draft["baseMapRevision"] == expected_map_revision,
                    "REVISION_CONFLICT")
            review = Store.get(db, "review", draft["reviewId"])
            require(ws.get("pendingPublication") in (None, draft_id), "REVISION_CONFLICT")
            require(draft["status"] in ("review_approved", "publishing") and review["decision"] == "accept"
                    and draft["draftRevision"] == review["draftRevision"]
                    and draft["graph"] == review["afterGraph"], "HUMAN_REVIEW_REQUIRED")
            self._evidence(draft["graph"], draft)
            require(bool(draft["graph"]["nodes"]), detail="正式版本至少包含一个功能节点")
            packet = {"schemaVersion": "architecture_version_v1", "mapId": draft["mapId"],
                      "codeRepoId": draft["codeRepoId"], "codeRevision": draft["codeRevision"],
                      "verifiedCodeRevision": review["verifiedCodeRevision"],
                      "status": "confirmed_design" if draft["mode"] == "planning" else "confirmed_cognition",
                      "graph": draft["graph"], "reviewCoverage": review["reviewCoverage"],
                      "limits": review["limits"] + [VERIFICATION_LIMIT],
                      "origin": draft["origin"],
                      "confirmation": confirmation_states(draft["graph"], review["reviewCoverage"]),
                      "review": review}
            packet["mapRevision"] = semantic_version(packet)
            existing = Store.get(db, "version", draft["workspaceId"] + "/" + packet["mapRevision"],
                                 optional=True)
            if existing:
                # Same semantic version is reused; original review stays immutable.
                draft.update(status="published", publishedMapRevision=packet["mapRevision"])
                ws["mapRevision"] = packet["mapRevision"]
                Store.put(db, "draft", draft_id, draft); Store.put(db, "workspace", ws["workspaceId"], ws)
                return existing
            journal = Store.get(db, "journal", draft_id, optional=True)
            if journal is None:
                journal = {"status": "prepared", **self.publisher.prepare(packet)}
                Store.put(db, "journal", draft_id, journal)
                draft["status"] = "publishing"
                ws["pendingPublication"] = draft_id
                Store.put(db, "draft", draft_id, draft)
                Store.put(db, "workspace", ws["workspaceId"], ws)
            else:
                require(journal["packet"] == packet, "PUBLICATION_CONFLICT")
        source = self.publisher.publish(journal)
        return self._finalize(draft_id, journal, source)

    def _finalize(self, draft_id, journal, source):
        with self.store.transaction() as db:
            draft = Store.get(db, "draft", draft_id)
            if draft["status"] == "published":
                return Store.get(db, "version", draft["workspaceId"] + "/" + draft["publishedMapRevision"])
            ws = self._current(db, draft)
            require(ws["mapRevision"] == draft["baseMapRevision"], "REVISION_CONFLICT")
            packet = journal["packet"]
            require(draft["status"] == "publishing"
                    and ws.get("pendingPublication") == draft_id
                    and draft.get("reviewId") == packet["review"]["reviewId"]
                    and draft["draftRevision"] == packet["review"]["draftRevision"]
                    and draft["graph"] == packet["graph"], "PUBLICATION_CONFLICT")
            envelope = {"version": packet, "provenance": {"mapSourceRevision": source,
                        "sourceKind": "git_commit"}}
            Store.put(db, "version", draft["workspaceId"] + "/" + packet["mapRevision"],
                      envelope, immutable=True)
            ws["mapRevision"] = packet["mapRevision"]
            ws.pop("pendingPublication", None)
            draft.update(status="published", publishedMapRevision=packet["mapRevision"])
            Store.put(db, "workspace", ws["workspaceId"], ws)
            Store.put(db, "draft", draft_id, draft)
            journal.update(status="committed", mapSourceRevision=source)
            Store.put(db, "journal", draft_id, journal)
            return copy.deepcopy(envelope)

    def get_version(self, workspace_id, map_revision):
        with self.store.transaction() as db:
            identifier(workspace_id)
            return Store.get(db, "version", workspace_id + "/" + str(map_revision))

    def export_version(self, workspace_id, map_revision):
        # Exact same immutable envelope for C/D; never add current HEAD.
        return copy.deepcopy(self.get_version(workspace_id, map_revision))

    def import_git_version(self, workspace_id, *, map_revision, map_source_revision,
                           expected_map_revision):
        """Second client reads actual immutable Git bytes, never trusts a UI label."""
        require(self.publisher is not None, "PUBLICATION_FAILED")
        with self.store.transaction() as db:
            ws = Store.get(db, "workspace", identifier(workspace_id))
            require(not ws.get("pendingPublication")
                    and ws["mapRevision"] == expected_map_revision, "REVISION_CONFLICT")
            envelope = GitPublisher.read_version(self.publisher.repo, ws["mapId"],
                                                  map_revision, map_source_revision)
            packet = envelope["version"]
            require(packet["codeRepoId"] == ws["codeRepoId"]
                    and packet["codeRevision"] == ws["codeRevision"], "STALE_CONTEXT")
            key = workspace_id + "/" + map_revision
            existing = Store.get(db, "version", key, optional=True)
            if existing:
                # The reader adds verification notes outside the packet. Reuse
                # the original immutable envelope only for the same Git source.
                require(existing["version"] == packet and all(
                    existing["provenance"][k] == envelope["provenance"][k]
                    for k in ("mapSourceRevision", "sourceKind")), "VERSION_CONFLICT")
                envelope = existing
            else:
                Store.put(db, "version", key, envelope, immutable=True)
            ws["mapRevision"] = map_revision
            Store.put(db, "workspace", workspace_id, ws)
            return envelope

    def graph_snapshot(self, workspace_id):
        with self.store.transaction() as db:
            ws = Store.get(db, "workspace", identifier(workspace_id))
            version = None if ws["mapRevision"] is None else Store.get(
                db, "version", workspace_id + "/" + ws["mapRevision"])
        pending = []
        pending_evidence, pending_processes = [], []
        if ws["codeRepoId"] is not None:
            self._repo(ws["codeRepoId"], ws["codeRevision"])
        if version:
            packet = version["version"]
            if packet["codeRepoId"] != ws["codeRepoId"]:
                pending = [n["id"] for n in packet["graph"]["nodes"]]
            elif packet["codeRevision"] != ws["codeRevision"]:
                if packet["codeRevision"] is not None:
                    repo = self._repo(ws["codeRepoId"], ws["codeRevision"])
                    self._compatible(repo, packet["codeRevision"], ws["codeRevision"])
                    changed = set(read_git(repo, "diff", "--name-only", "--no-renames",
                                           packet["codeRevision"], ws["codeRevision"]).decode().splitlines())
                    affected = {e["id"] for e in packet["graph"]["evidence"]
                                if e["kind"] == "code" and e["path"] in changed}
                    pending_evidence = sorted(affected)
                    pending = [n["id"] for n in packet["graph"]["nodes"]
                               if set(n["evidenceIds"]) & affected
                               or any(set(i["evidenceIds"]) & affected for i in n["interfaces"])]
                    for edge in packet["graph"]["edges"]:
                        if set(edge["evidenceIds"]) & affected:
                            pending.extend([edge["from"], edge["to"]])
                    for process in packet["graph"]["processes"]:
                        whole_process = bool(set(process["evidenceIds"]) & affected)
                        affected_steps = [step for step in process["steps"]
                                          if whole_process or set(step["evidenceIds"]) & affected]
                        if affected_steps:
                            pending_processes.append(process["id"])
                            pending.extend(step["nodeId"] for step in affected_steps)
                else:
                    pending = [n["id"] for n in packet["graph"]["nodes"]]
            applicability = ("design_only" if ws["mode"] == "planning" else
                             "not_checked" if ws["codeRevision"] != packet["verifiedCodeRevision"]
                             else "reviewed_coverage_only")
        else:
            applicability = "unconfirmed"
        return {"workspace": ws, "versionEnvelope": version, "pendingNodeIds": sorted(set(pending)),
                "pendingEvidenceIds": pending_evidence, "pendingProcessIds": pending_processes,
                "applicability": applicability,
                "limits": ["未标记节点也可能受影响；静态引用不是运行时执行链"]}


# Reject malformed JSON-shaped values at the public service boundary.
for _method in ("open_workspace", "associate_code", "create_draft", "get_draft",
                "apply_draft_operations", "record_review", "publish_reviewed_graph",
                "get_version", "export_version", "import_git_version", "graph_snapshot"):
    setattr(WorkspaceService, _method, input_guard(getattr(WorkspaceService, _method)))
