"""Workbench service facade (A role) — one place the HTTP layer talks to.

Machine-readable failures via ContractError; every response carries backend
labels so 演示数据 can never pass as production data. Publishing (human
review) and fix-task handoff go through the adapter and refuse both the
missing-backend case (BACKEND_UNAVAILABLE) and any dev-sample origin.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from . import backend_c
from . import context_pack as context_pack_module
from . import fix_tasks as fix_tasks_module
from . import correction as correction_module
from . import generate as generate_module
from . import ops as ops_module
from .adapters import AdapterRegistry, DEV_SAMPLE_MODE, call_backend, reject_sample_review
from .backend_b import b_to_a_graph
from .contract import (ContractError, ID_PATTERN, identity_view, is_full_sha,
                       semantic_revision, validate_workspace_identity)
from .store import DraftStore, workspace_lock


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_repo_id(repo_path: str, remote: str | None) -> str:
    """Stable repository identity: the registered source URL, never the local
    absolute directory (two clones of one source keep one identity). Only a
    repository with no remote at all falls back to its local path."""
    if remote:
        locator = remote.rstrip("/")
    else:
        from pathlib import Path as _Path
        locator = "local:" + str(_Path(repo_path).resolve())
    # identical rule to B's code_identity (extensions/architecture_workspace/
    # git_publication.py) so one source keeps one identity on both sides
    return "repo-" + hashlib.sha256(locator.encode("utf-8")).hexdigest()


class WorkbenchService:
    def __init__(self, data_root, adapter: AdapterRegistry | None = None) -> None:
        self.store = DraftStore(data_root)
        self.adapter = adapter or AdapterRegistry()
        # Git access is injected by app.py so this module reuses the host's
        # hardened git runner (env stripping, no prompts) instead of copying
        # repository rules; code facts always come from explicit revisions.
        self.git = None
        # Optional real B version service (single adapter layer: backend_b.py).
        # Bound by app.py from server-side configuration only.
        self.backend_b = None

    # ---------- injected git access ----------

    def bind_git(self, git_callable) -> None:
        self.git = git_callable

    def _require_git(self):
        if self.git is None:
            raise ContractError("BACKEND_UNAVAILABLE", "本实例未绑定 Git 访问")
        return self.git

    def _code_repo_identity(self, root: str, remote: str | None) -> str:
        """One identity for one registered source: when B's version service is
        bound, use its registered repo id (origin-URL based); otherwise a
        path-independent fallback. Two clones of one source never diverge
        because of their local directories."""
        backend_b = getattr(self, "backend_b", None)
        if backend_b is not None and backend_b.available:
            try:
                return backend_b.repo_id_for(root)
            except ContractError:
                pass
        return stable_repo_id(root, remote)

    def probe_repo(self, repo_path: str) -> dict:
        git = self._require_git()
        from pathlib import Path as _Path
        repo = _Path(repo_path)
        root = git(repo, "rev-parse", "--show-toplevel").decode("utf-8", errors="replace").strip()
        head = git(repo, "rev-parse", "HEAD").decode().strip()
        try:
            remote = git(repo, "remote", "get-url", "origin").decode("utf-8", errors="replace").strip()
        except Exception:
            remote = None
        raw = git(repo, "ls-tree", "-r", "-z", "--name-only", head)
        tracked = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
        return {"root": root, "head": head, "remote": remote, "trackedFiles": tracked}

    def diff_repo(self, repo_path: str, base: str, target: str) -> list[dict]:
        git = self._require_git()
        from pathlib import Path as _Path
        raw = git(_Path(repo_path), "diff", "--name-status", "-z", "-M", base, target, "--")
        parts = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
        changes = []
        index = 0
        while index < len(parts):
            code = parts[index]
            index += 1
            if code.startswith(("R", "C")):
                old_path, path = parts[index:index + 2]
                index += 2
                changes.append({"code": code, "oldPath": old_path, "path": path})
            else:
                changes.append({"code": code, "path": parts[index]})
                index += 1
        return changes

    # ---------- workspace lifecycle ----------

    def create_workspace(self, request: dict) -> dict:
        context = request.get("context")
        title = (request.get("title") or "").strip()
        if not title:
            raise ContractError("VALIDATION_FAILED", "请为工作区命名")
        identity = {
            "workspaceId": None,
            "codeRepoId": None,
            "mapId": None,
            "codeRevision": None,
            "mapSourceRevision": None,
            "verifiedCodeRevision": None,
        }
        repo_path = request.get("repoPath")
        if context in ("existing_project", "mixed"):
            if not isinstance(repo_path, str) or not repo_path.strip():
                raise ContractError("VALIDATION_FAILED", "已有项目需要仓库路径")
            probe = self.probe_repo(repo_path.strip())
            identity["codeRepoId"] = self._code_repo_identity(probe["root"], probe.get("remote"))
            identity["codeRevision"] = probe["head"]
            identity["repoPath"] = probe["root"]
            if context == "existing_project":
                identity["mapId"] = f"map-{identity['codeRepoId'][5:]}"
        provided_map_id = request.get("mapId")
        if provided_map_id is not None:
            # second copy / same-version handover: the caller names the durable
            # graph identity that was registered elsewhere (never inferred)
            if not isinstance(provided_map_id, str) or not ID_PATTERN.fullmatch(provided_map_id):
                raise ContractError("VALIDATION_FAILED", "mapId 不合法")
            identity["mapId"] = provided_map_id
        workspace_id = f"ws_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}"
        identity["workspaceId"] = workspace_id
        validate_workspace_identity(identity, context)
        record = {
            "workspaceId": workspace_id,
            "title": title,
            "context": context,
            "identity": identity,
            "mapIdProvided": provided_map_id is not None,
            "description": request.get("description", ""),
            "goals": request.get("goals", ""),
            "constraints": request.get("constraints", ""),
            "createdAt": _utcnow(),
            "updatedAt": _utcnow(),
            "draft": None,
        }
        self.store.create_workspace(record)
        return self._envelope(record, mode=request.get("mode", "production"))

    def open_workspace(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        return self._envelope(record)

    def list_workspaces(self) -> dict:
        return {"workspaces": self.store.list_workspaces(), "backend": self._backend_label()}

    def _backend_label(self) -> dict:
        backend_b = getattr(self, "backend_b", None)
        if backend_b is not None and backend_b.available:
            status = backend_b.status()
            return {
                "kind": backend_b.KIND if status.get("available") else "unavailable",
                "labeled": status.get("labeled"),
                "origin": backend_b.KIND if status.get("available") else "unavailable",
                "versionService": bool(status.get("available")),
                "ref": backend_b.REF,
                "reviewGateway": bool(status.get("reviewGateway")),
                "reason": status.get("reason"),
            }
        persistence = self.adapter._backends.get("persistence")
        delegating = bool(persistence and callable(persistence.get("call")))
        # Draft storage and the version service are distinct capabilities:
        # drafts stay in A's labeled local store until B's service actually
        # takes them over; a bare registration without a callable is not an
        # integration (FINAL-1 finding 8).
        return {
            "kind": "dev_sample_draft_store" if not delegating else "extension:persistence",
            "labeled": ("草稿保存在本实例数据目录，等待 B 版本服务接入；不产生正式认知版本"
                        if not delegating else
                        "版本服务已委托注册后端；草稿暂存本实例，正式版本以后端发布结果为准"),
            "origin": "dev_sample" if not delegating else "extension:persistence",
            "versionService": delegating,
        }

    def _envelope(self, record: dict, mode: str = "production") -> dict:
        draft = record.get("draft")
        draft_revision = draft.get("draftRevision") if draft else None
        map_revision = draft.get("graph", {}).get("mapRevision") if draft else None
        # mapSourceRevision / verifiedCodeRevision are facts about the
        # PUBLISHED graph; they apply to the identity only while the current
        # draft IS that published revision. Once the draft moves on, the
        # identity view nulls them and lastPublish carries the facts
        # (FINAL-3 finding F5).
        identity = dict(record["identity"])
        last_publish = record.get("lastPublish")
        # A's draft hash (maprev-...) and B's immutable version id (sha256:...)
        # are different formats: the published pair is recorded together and
        # compared field by field (BATCH-1 C-01).
        published_here = bool(last_publish) and draft is not None \
            and draft.get("publishedMapRevision") == last_publish.get("mapRevision") \
            and map_revision == last_publish.get("aMapRevision")
        if not published_here:
            identity["mapSourceRevision"] = None
            identity["verifiedCodeRevision"] = None
        else:
            # the immutable version id (sha256:...) is what the team shares;
            # show it while the draft is exactly that published version
            map_revision = last_publish.get("mapRevision")
        return {
            "workspace": {key: record.get(key) for key in
                          ("workspaceId", "title", "context", "description", "goals", "constraints",
                           "createdAt", "updatedAt")},
            "identity": identity_view(identity, map_revision, draft_revision),
            "draft": draft,
            "lastPublish": last_publish,
            "backend": self._backend_label(),
            "generation": generate_module.generate_status(),
            "mode": mode,
        }

    # ---------- generation ----------

    def tracked_at(self, repo_path: str, sha: str) -> set[str]:
        """Files present at one specific full SHA — never the worktree, never
        a fresher HEAD (FINAL-1 finding 3: evidence must be checked against
        the revision it claims to describe)."""
        git = self._require_git()
        from pathlib import Path as _Path
        raw = git(_Path(repo_path), "ls-tree", "-r", "-z", "--name-only", sha)
        return {part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part}

    def _evidence_guard(self, graph: dict, record: dict, basis_sha: str | None,
                        tracked: set[str] | None = None) -> dict:
        """Enforce evidence honesty before a graph may enter a draft.

        Every draft write path (generation, direct ops, legacy import) goes
        through here (FINAL-1 finding 2). The check runs against the exact
        revision the graph claims to describe (basis_sha), never a fresher
        HEAD. existing_project/mixed: code_fact paths missing from that
        revision downgrade to kind=unknown with a recorded downgrade.
        planning: code_fact evidence is rejected outright — there is no
        repository to check against.
        """
        context = record["context"]
        if context == "planning":
            for node in graph.get("nodes", []):
                for item in node.get("evidence", []):
                    # missing kind means code_fact by contract: normalize
                    # before the check so it cannot slip through (FINAL-1 #2)
                    if item.get("kind", "code_fact") == "code_fact":
                        raise ContractError("VALIDATION_FAILED",
                                            f"规划工作区不允许代码事实证据（节点 {node.get('id')}）；请改为需求依据")
            return graph
        if tracked is None:
            if not basis_sha:
                raise ContractError("VALIDATION_FAILED", "缺少证据核查基准 SHA")
            tracked = self.tracked_at(record["identity"]["repoPath"], basis_sha)
        downgraded = []
        for node in graph.get("nodes", []):
            for item in node.get("evidence", []):
                if item.get("kind", "code_fact") == "code_fact" and item.get("path") not in tracked:
                    item["kind"] = "unknown"
                    item["reason"] = f"{item.get('reason', '')}（该路径未在提交 {basis_sha[:12]} 中核实，降级为未知）"
                    downgraded.append({"nodeId": node.get("id"), "path": item.get("path")})
        if downgraded:
            graph = dict(graph)
            graph["evidenceDowngrades"] = downgraded
        return graph

    def generate(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            identity = record["identity"]
            mode = request.get("mode", "production")
            repo_facts = {}
            source_revision = identity.get("codeRevision")
            context_pack = None
            if identity.get("repoPath"):
                probe = self.probe_repo(identity["repoPath"])
                source_revision = probe["head"]
                # a real generation input: the fixed commit's bounded source
                # excerpts, symbols, imports and docs, with recorded coverage
                # (file names alone are not "having read the project").
                context_pack = context_pack_module.build_context_pack(
                    identity["repoPath"], source_revision)
                repo_facts = {
                    "codeRepoId": identity.get("codeRepoId"),
                    "codeRevision": source_revision,
                    "trackedFiles": probe.get("trackedFiles", [])[:400],
                    "contextPack": context_pack,
                }
                record["lastContextPack"] = {
                    "codeRevision": source_revision,
                    "coverage": context_pack["coverage"],
                    "entryPoints": context_pack["entryPoints"][:40],
                    "files": [{"path": item["path"], "symbols": item.get("symbols", [])[:40]}
                              for item in context_pack["files"]],
                    "at": _utcnow(),
                }
            if mode == "rule_based":
                # explicit rule-based route (C's engine), never labeled as AI
                candidate = backend_c.bootstrap_candidate(record["context"], record)
                graph = self._evidence_guard(candidate["graph"], record, source_revision)
                graph["mapRevision"] = semantic_revision(graph)
                candidate_id = f"cand_{secrets.token_hex(5)}"
                record["lastCandidate"] = {
                    "candidateId": candidate_id, "graph": graph, "origin": "rule_based",
                    "status": "rule_based", "sourceCodeRevision": source_revision,
                    "unknowns": candidate.get("warnings", []), "openQuestions": [],
                    "labeled": "规则候选（C 规则引擎，非 AI 生成）", "storedAt": _utcnow(),
                    "proposalId": candidate.get("proposalId")}
                record["updatedAt"] = _utcnow()
                self.store.save_workspace_record(record)
                self.store.append_history(workspace_id, {
                    "type": "generation", "origin": "rule_based", "at": _utcnow(),
                    "candidateId": candidate_id, "sourceCodeRevision": source_revision,
                    "proposalId": candidate.get("proposalId")})
                return {"status": "rule_based", "origin": "rule_based", "graph": graph,
                        "candidateId": candidate_id, "sourceCodeRevision": source_revision,
                        "warnings": candidate.get("warnings", []),
                        "contextCoverage": (context_pack or {}).get("coverage"),
                        "labeled": "C 规则引擎候选：不冒充 AI 生成，需人工修改与确认"}
            if mode == DEV_SAMPLE_MODE:
                sample = request.get("sampleGraph")
                if not isinstance(sample, dict):
                    raise ContractError("DEV_SAMPLE_DISABLED", "演示模式需要明确提供样例图；不会用样例顶替真实 AI 生成")
                result = generate_module.sample_candidate(sample, record["context"])
            else:
                result = generate_module.generate_candidate({
                    "context": record["context"],
                    "description": record.get("description", ""),
                    "goals": record.get("goals", ""),
                    "constraints": record.get("constraints", ""),
                }, repo_facts=repo_facts)
            if result.get("status") in ("ai_generated", "dev_sample"):
                # The candidate is stored server-side with its origin and the
                # exact code revision it was generated from; applying later can
                # only pick this stored candidate (no origin laundering).
                tracked = self.tracked_at(identity["repoPath"], source_revision) \
                    if identity.get("repoPath") and source_revision else None
                graph = self._evidence_guard(result["graph"], record, source_revision, tracked)
                graph["mapRevision"] = semantic_revision(graph)  # evidence downgrades change semantics
                candidate_id = f"cand_{secrets.token_hex(5)}"
                record["lastCandidate"] = {
                    "candidateId": candidate_id,
                    "graph": graph,
                    "origin": result["origin"],
                    "status": result["status"],
                    "sourceCodeRevision": source_revision,
                    "unknowns": result.get("unknowns", []),
                    "openQuestions": result.get("openQuestions", []),
                    "labeled": result.get("labeled"),
                    "storedAt": _utcnow(),
                }
                record["generation"] = {"status": result["status"], "at": _utcnow(),
                                        "mapRevision": graph["mapRevision"],
                                        "candidateId": candidate_id}
                record["updatedAt"] = _utcnow()
                self.store.save_workspace_record(record)
                self.store.append_history(workspace_id, {"type": "generation", "origin": result["origin"],
                                                         "at": _utcnow(),
                                                         "candidateId": candidate_id,
                                                         "sourceCodeRevision": source_revision})
                result = dict(result)
                result["graph"] = graph
                result["candidateId"] = candidate_id
                result["sourceCodeRevision"] = source_revision
            return result

    def apply_candidate(self, workspace_id: str, request: dict) -> dict:
        """User accepted a stored candidate: it becomes the working draft.

        Only the server-stored candidate can be applied (origin is not
        client-chosen), any existing draft is CAS-guarded, and the candidate's
        generation basis must match the workspace's bound revision.
        """
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            candidate = record.get("lastCandidate")
            if not candidate:
                raise ContractError("VALIDATION_FAILED", "没有已存储的候选；请先生成")
            candidate_id = request.get("candidateId")
            if candidate_id != candidate["candidateId"]:
                raise ContractError("STALE_CONTEXT", "候选已过期或不存在；请重新生成",
                                    {"expected": candidate["candidateId"]})
            if record["identity"].get("codeRevision") is not None \
                    and candidate.get("sourceCodeRevision") \
                    and record["identity"]["codeRevision"] != candidate["sourceCodeRevision"]:
                raise ContractError("STALE_CONTEXT",
                                    "候选的生成依据与工作区绑定提交不一致；请先复核并回挂",
                                    {"candidateBasis": candidate["sourceCodeRevision"],
                                     "boundRevision": record["identity"]["codeRevision"]})
            existing_draft = record.get("draft")
            if existing_draft is not None:
                expected = request.get("expectedDraftRevision")
                if not isinstance(expected, str) or expected != existing_draft["draftRevision"]:
                    raise ContractError("REVISION_CONFLICT", "已有草稿被修改过；请先查看差异再决定替换",
                                        {"expected": expected, "current": existing_draft["draftRevision"]})
            graph = ops_module.validate_graph(candidate["graph"])
            graph["mapRevision"] = semantic_revision(graph)
            draft = self._new_draft(record, graph, origin=candidate["origin"])
            draft["lineage"] = [candidate["origin"]]
            draft["generationMeta"] = {
                "origin": candidate["origin"],
                "generatedFromCodeRevision": candidate.get("sourceCodeRevision"),
                "unknowns": candidate.get("unknowns", []),
                "openQuestions": candidate.get("openQuestions", []),
            }
            record["draft"] = draft
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "apply_candidate", "origin": draft["origin"],
                                                     "at": _utcnow(), "draftRevision": draft["draftRevision"],
                                                     "candidateId": candidate["candidateId"]})
            return self._envelope(record)

    def _new_draft(self, record: dict, graph: dict, origin: str) -> dict:
        return {
            "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
            "baseMapRevision": None,
            "graph": graph,
            "baseGraph": graph,
            "origin": origin,
            "updatedAt": _utcnow(),
        }

    # ---------- drafts ----------

    def load_draft(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        return self._envelope(record)

    def apply_ops(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            return self._apply_ops_locked(workspace_id, request)

    def _apply_ops_locked(self, workspace_id: str, request: dict) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        expected = request.get("expectedDraftRevision")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿；先生成或导入候选图")
        if not isinstance(expected, str) or expected != draft["draftRevision"]:
            raise ContractError("REVISION_CONFLICT", "草稿已被他人修改；请刷新差异后重试",
                                {"expected": expected, "current": draft["draftRevision"]})
        operations = request.get("operations")
        if not isinstance(operations, list) or not operations:
            raise ContractError("VALIDATION_FAILED", "operations 必须是非空列表")
        graph = draft["graph"]
        applied = []
        for op in operations:
            graph = ops_module.apply_operation(graph, op)
            applied.append(op.get("type"))
        # direct edits go through the same evidence honesty guard as
        # generation (FINAL-1 finding 2)
        bound = record["identity"].get("codeRevision")
        graph = self._evidence_guard(graph, record, bound)
        # the guard can mutate evidence (semantic content): recompute the
        # graph's own revision field so identity never shows a stale digest
        # (FINAL-2 finding F1)
        graph["mapRevision"] = semantic_revision(graph)
        new_draft = {
            "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
            "baseMapRevision": draft.get("baseMapRevision"),
            "graph": graph,
            "baseGraph": draft.get("baseGraph") or draft["graph"],
            "origin": draft.get("origin") if draft.get("origin") != "ai_candidate" else "edited_candidate",
            "lineage": draft.get("lineage", [draft.get("origin")]),
            "generationMeta": draft.get("generationMeta"),
            "publishedMapRevision": draft.get("publishedMapRevision"),
            "updatedAt": _utcnow(),
        }
        record["draft"] = new_draft
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(workspace_id, {"type": "apply_ops", "at": _utcnow(),
                                                 "operations": applied,
                                                 "actor": request.get("actor", "local_user"),
                                                 "draftRevision": new_draft["draftRevision"]})
        return self._envelope(record)

    def node_impact(self, workspace_id: str, node_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        return ops_module.node_impact(draft["graph"], node_id)

    def draft_diff(self, workspace_id: str) -> dict:
        """Diff between the accepted candidate (baseGraph) and the current draft."""
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        base = draft.get("baseGraph") or {"nodes": [], "edges": []}
        return ops_module.diff_graphs(base, draft["graph"])

    # ---------- natural-language correction ----------

    def correction_preview(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            expected = request.get("expectedDraftRevision")
            if expected != draft["draftRevision"]:
                raise ContractError("REVISION_CONFLICT", "草稿已变化，请刷新后再发起纠正",
                                    {"expected": expected, "current": draft["draftRevision"]})
            instruction = (request.get("instruction") or "").strip()
            if not instruction:
                raise ContractError("VALIDATION_FAILED", "请描述要纠正的内容")
            selected = request.get("selectedNodeIds", [])
            if not isinstance(selected, list) or not selected:
                raise ContractError("VALIDATION_FAILED", "请选择要纠正的节点或区域")
            mode = request.get("mode", "production")
            if mode == DEV_SAMPLE_MODE:
                preview = self._sample_correction(record, draft, instruction, selected)
                origin = "dev_sample"
                labeled = "演示纠正预览（本地规则生成，非 AI）"
                note = preview["note"]
            elif mode == "rule_based":
                # explicit C rule engine route: real module, labeled rule_based
                reply = backend_c.nl_patch_candidate(draft["graph"], selected[0], instruction)
                operations = reply["operations"]
                probe_graph = draft["graph"]
                for op in operations:
                    probe_graph = ops_module.apply_operation(probe_graph, op)
                preview = {"operations": operations, "graph": probe_graph}
                origin = "rule_based"
                labeled = "规则纠正预览（C 规则引擎，非 AI）"
                note = (reply.get("labeled") or "由 C 规则引擎按所选节点生成；"
                        "只做局部操作，不代表 AI 理解。")
            else:
                # real model correction: bounded operations validated by the op
                # engine; without a configured model this is NOT_RUN, never a
                # silent fallback to a demo note.
                context_pack = record.get("lastContextPack") if request.get(
                    "includeSourceContext", True) else None
                reply = correction_module.correct_with_model(record, draft, instruction,
                                                             selected, context_pack)
                preview = {"operations": reply["operations"], "graph": reply["graph"]}
                origin = "ai_generated"
                labeled = "真实模型纠正预览（AI 候选，需人确认）"
                note = reply.get("explanation") or "模型返回的局部纠正操作。"
                if reply.get("unknowns") or reply.get("openQuestions"):
                    note = (note + " 未确定：" + "；".join(
                        list(reply.get("unknowns", [])) + list(reply.get("openQuestions", [])))).strip()
            # The preview (operations + the draft revision it was based on) is
            # stored server-side; applying later must name the proposal and
            # pass an expiry check, so a stale preview cannot overwrite newer
            # edits (MID-1 finding 9).
            proposal_id = f"prop_{secrets.token_hex(6)}"
            record["lastCorrectionPreview"] = {
                "proposalId": proposal_id,
                "baseDraftRevision": draft["draftRevision"],
                "baseMapRevision": draft["graph"].get("mapRevision"),
                "operations": preview["operations"],
                "graph": preview["graph"],
                "origin": origin,
                "labeled": labeled,
                "instruction": instruction,
                "storedAt": _utcnow(),
            }
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "correction_preview", "at": _utcnow(),
                                                     "proposalId": proposal_id,
                                                     "instruction": instruction,
                                                     "selected": selected, "origin": origin})
            return {
                "proposalId": proposal_id,
                "origin": origin,
                "labeled": labeled,
                "operations": preview["operations"],
                "baseDraftRevision": draft["draftRevision"],
                "diff": ops_module.diff_graphs(draft["graph"], preview["graph"]),
                "note": note,
            }

    def apply_correction(self, workspace_id: str, request: dict) -> dict:
        """Apply a stored correction preview by proposalId (expiry-checked)."""
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            preview = record.get("lastCorrectionPreview")
            if draft is None or not preview:
                raise ContractError("NOT_FOUND", "没有已存储的纠正预览")
            proposal_id = request.get("proposalId")
            if not isinstance(proposal_id, str) or proposal_id != preview["proposalId"]:
                raise ContractError("NOT_FOUND", "纠正预览不存在或已过期；请重新生成",
                                    {"expected": preview["proposalId"]})
            expected = request.get("expectedDraftRevision")
            if not isinstance(expected, str) or expected != preview["baseDraftRevision"]:
                raise ContractError("STALE_CONTEXT", "请求与预览基准不一致；请使用预览返回的 baseDraftRevision",
                                    {"previewBasis": preview["baseDraftRevision"], "expected": expected})
            if preview["baseDraftRevision"] != draft["draftRevision"]:
                # the draft moved on after the preview was taken: the preview
                # is void and must be regenerated (MID-1 finding 9)
                raise ContractError("STALE_CONTEXT", "纠正预览基于旧草稿；草稿已变化，预览作废",
                                    {"previewBasis": preview["baseDraftRevision"],
                                     "current": draft["draftRevision"]})
            graph = draft["graph"]
            applied = []
            for op in preview["operations"]:
                graph = ops_module.apply_operation(graph, op)
                applied.append(op.get("type"))
            bound = record["identity"].get("codeRevision")
            graph = self._evidence_guard(graph, record, bound)
            graph["mapRevision"] = semantic_revision(graph)  # FINAL-2 F1
            lineage = list(draft.get("lineage", [draft.get("origin")]))
            if preview["origin"] == "dev_sample" and "dev_sample" not in lineage:
                lineage.append("dev_sample")
            new_draft = {
                "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
                "baseMapRevision": draft.get("baseMapRevision"),
                "graph": graph,
                "baseGraph": draft.get("baseGraph") or draft["graph"],
                # sample-derived content keeps the sample marking: it can never
                # pass review as if it were clean (MID-1 finding 3)
                "origin": "dev_sample" if preview["origin"] == "dev_sample" else draft.get("origin"),
                "lineage": lineage,
                "generationMeta": draft.get("generationMeta"),
                "publishedMapRevision": draft.get("publishedMapRevision"),
                "updatedAt": _utcnow(),
            }
            record["draft"] = new_draft
            record["lastCorrectionPreview"] = None
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "apply_correction", "at": _utcnow(),
                                                     "proposalId": proposal_id,
                                                     "origin": preview["origin"],
                                                     "operations": applied,
                                                     "draftRevision": new_draft["draftRevision"]})
            return self._envelope(record)

    def _sample_correction(self, record: dict, draft: dict, instruction: str, selected: list[str]) -> dict:
        """Labeled dev-sample preview: deterministic heuristic, no model call.

        Only callable in explicit dev-sample mode; operations show the UI
        shape a real C backend must return.
        """
        graph = draft["graph"]
        target_id = selected[0]
        node = next((n for n in graph["nodes"] if n["id"] == target_id), None)
        if node is None:
            raise ContractError("NOT_FOUND", f"节点不存在: {target_id}")
        operations = [{"type": "update_node", "nodeId": target_id,
                       "fields": {"summary": node.get("summary", "") + "（演示纠正：请以真实后端替换此预览）"}}]
        preview_graph = ops_module.apply_operation(graph, operations[0])
        return {"operations": operations, "graph": preview_graph,
                "note": "演示纠正预览：由本地确定性规则生成，仅验证交互；不代表 AI 输出。"}

    # ---------- implementation fix tasks (persisted, A-side) ----------

    def list_fix_tasks(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        tasks = fix_tasks_module.load_tasks(self.store.root, workspace_id)
        return {"workspaceId": workspace_id, "tasks": tasks,
                "statuses": list(fix_tasks_module.STATUSES),
                "labeled": ("A 工作台持久化的实施任务；提交回挂后仍需人确认核查结论"
                            if tasks else "该工作区还没有修正任务")}

    def update_fix_task(self, workspace_id: str, task_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            task = fix_tasks_module.update_task(self.store.root, workspace_id, task_id, request)
            self.store.append_history(workspace_id, {
                "type": "fix_task_update", "at": _utcnow(), "taskId": task_id,
                "status": task["status"], "actor": request.get("actor")})
            return task

    def fix_task_markdown(self, workspace_id: str, task_id: str) -> dict:
        task = fix_tasks_module.load_task(self.store.root, workspace_id, task_id)
        return {"taskId": task_id, "markdown": fix_tasks_module.task_markdown(task),
                "filename": f"{task_id}.md"}

    # ---------- same-version handover (A compatibility export until D lands) --

    def export_handover(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        binding = record.get("backendB") or {}
        if not binding.get("workspaceId"):
            raise ContractError("VALIDATION_FAILED", "该工作区尚未接入版本服务，无法导出同版交接包")
        last_publish = record.get("lastPublish") or {}
        map_revision = last_publish.get("mapRevision")
        if not map_revision:
            raise ContractError("VALIDATION_FAILED", "尚未产生正式版本；交接包必须指向不可变版本")
        envelope = self._backend_b().export_version(binding["workspaceId"], map_revision)
        version = envelope["version"]
        tasks = fix_tasks_module.load_tasks(self.store.root, workspace_id)
        open_tasks = [{"taskId": task["taskId"], "status": task["status"],
                       "observation": task.get("observation", "")[:200],
                       "targetCodeRevision": task.get("targetCodeRevision")}
                      for task in tasks if task.get("status") != "verified"]
        package = {
            "packageType": "architecture_handover_v1",
            "producer": "A 工作台（D 的同版交接模块未接入时的兼容导出；结构与 CONTRACT_V1 一致）",
            "workspaceId": workspace_id,
            "mapId": version["mapId"],
            "mapRevision": version["mapRevision"],
            "mapSourceRevision": envelope["provenance"].get("mapSourceRevision"),
            "codeRepoId": version["codeRepoId"],
            "codeRevision": version["codeRevision"],
            "verifiedCodeRevision": version.get("verifiedCodeRevision"),
            "graphNature": version["status"],
            "reviewCoverage": version["reviewCoverage"],
            "limits": version["limits"],
            "unresolvedDeviations": record.get("deviations", []),
            "openFixTasks": open_tasks,
            "designHistory": record.get("designHistory", []),
            "graph": b_to_a_graph(version["graph"], version),
            "importHint": {
                "endpoint": "/api/archloop/import-handover",
                "requiredFields": ["mapId", "mapRevision", "mapSourceRevision", "repoPath"],
                "note": "第二副本必须按架构 Git 固定提交读取并核对来源；同版不等于同一套本地目录",
            },
        }
        self.store.append_history(workspace_id, {
            "type": "handover_export", "at": _utcnow(), "mapRevision": map_revision,
            "mapSourceRevision": package["mapSourceRevision"]})
        return package

    def import_handover(self, request: dict) -> dict:
        package = request.get("package")
        repo_path = (request.get("repoPath") or "").strip()
        if not isinstance(package, dict) or package.get("packageType") != "architecture_handover_v1":
            raise ContractError("VALIDATION_FAILED", "需要 architecture_handover_v1 交接包")
        if not repo_path:
            raise ContractError("VALIDATION_FAILED", "需要第二副本的仓库路径")
        for field in ("mapId", "mapRevision", "mapSourceRevision"):
            if not package.get(field):
                raise ContractError("VALIDATION_FAILED", f"交接包缺少 {field}")
        existing_workspace = request.get("workspaceId")
        if existing_workspace:
            # re-import / refresh inside an existing second copy: same
            # workspace, version read again from the Git bytes
            result = self.import_version(existing_workspace, {
                "mapRevision": package["mapRevision"],
                "mapSourceRevision": package["mapSourceRevision"],
                "expectedMapRevision": request.get("expectedMapRevision")})
            result["workspace"] = {"workspaceId": existing_workspace}
            result["identity"] = {"mapId": package["mapId"]}
        else:
            result = self.open_from_version({
                "mapId": package["mapId"], "mapRevision": package["mapRevision"],
                "mapSourceRevision": package["mapSourceRevision"], "repoPath": repo_path,
                "title": request.get("title") or "同版接手（交接包）",
                "expectedMapRevision": request.get("expectedMapRevision")})
        # a mismatch between the package's own graph and the Git bytes is a
        # tampered/stale package: the imported version wins, and the difference
        # is reported instead of being silently accepted
        package_graph = package.get("graph")
        imported_graph = result.get("graph")
        comparison = None
        if isinstance(package_graph, dict):
            same_content = self._graph_fingerprint(package_graph) == \
                self._graph_fingerprint(imported_graph)
            same_revision = package.get("mapRevision") == result["version"]["mapRevision"]
            comparison = {"contentMatches": same_content, "revisionMatches": same_revision}
            if not (same_content and same_revision):
                comparison["note"] = ("交接包内容与架构 Git 实际版本不一致（包可能被改过或过期）："
                                      "以 Git 版本为准，并请核对交接来源")
        result["handoverComparison"] = comparison
        return result

    @staticmethod
    def _graph_fingerprint(graph: dict) -> list:
        """Semantic fingerprint used to detect a tampered/stale handover package."""
        nodes = []
        for node in graph.get("nodes", []) or []:
            nodes.append((
                node.get("id"), node.get("title"), node.get("summary"), node.get("status"),
                tuple(sorted(str(step.get("stepId")) for step in node.get("process", []) or [])),
                tuple(sorted(str(item.get("path")) for item in node.get("evidence", []) or [])),
            ))
        edges = sorted((edge.get("from"), edge.get("to"), edge.get("type"), edge.get("label"))
                       for edge in graph.get("edges", []) or [])
        return [tuple(sorted(nodes, key=lambda item: str(item[0]))), tuple(edges)]

    # ---------- C module: process deviations and incremental proposals ----------

    def deviations(self, workspace_id: str, request: dict) -> dict:
        """C's deviation detection on the current draft (read-only, honest UNKNOWN)."""
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        traces = request.get("observedTraces")
        if traces is not None and not isinstance(traces, list):
            raise ContractError("VALIDATION_FAILED", "observedTraces 必须是列表（可为空）")
        result = backend_c.deviations_for(draft["graph"], traces or [])
        result["draftRevision"] = draft["draftRevision"]
        result["mapRevision"] = draft["graph"].get("mapRevision")
        result["observedTracesProvided"] = bool(traces)
        self.store.append_history(workspace_id, {
            "type": "deviation_check", "at": _utcnow(), "verdict": result.get("verdict"),
            "count": len(result.get("deviations", [])), "traces": bool(traces)})
        return result

    def incremental_proposal(self, workspace_id: str) -> dict:
        """C's incremental candidate for a real code change (candidate only)."""
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            identity = record["identity"]
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            if not identity.get("repoPath") or not identity.get("codeRevision"):
                raise ContractError("VALIDATION_FAILED", "该工作区没有关联代码")
            probe = self.probe_repo(identity["repoPath"])
            target = probe["head"]
            base = identity["codeRevision"]
            if target == base:
                return {"status": "no_change", "baseCodeRevision": base, "targetCodeRevision": target,
                        "operations": [], "labeled": "代码未变化；没有增量候选"}
            changes = self.diff_repo(identity["repoPath"], base, target)
            facts_diff = {
                "added_files": [c["path"] for c in changes if c["code"].startswith("A")],
                "modified_files": [c["path"] for c in changes if c["code"].startswith("M")],
                "deleted_files": [c["path"] for c in changes if c["code"].startswith("D")],
                "renamed_files": [{"from": c.get("oldPath"), "to": c["path"]}
                                  for c in changes if c["code"].startswith("R")],
            }
            reply = backend_c.incremental_candidate(draft["graph"], base, target, facts_diff)
            reply.update({"status": "ok", "baseCodeRevision": base, "targetCodeRevision": target,
                          "changeSummary": {"added": len(facts_diff["added_files"]),
                                            "modified": len(facts_diff["modified_files"]),
                                            "deleted": len(facts_diff["deleted_files"]),
                                            "renamed": len(facts_diff["renamed_files"])},
                          "changes": changes})
            self.store.append_history(workspace_id, {
                "type": "incremental_proposal", "at": _utcnow(), "base": base, "target": target,
                "proposalId": reply.get("proposalId"), "operations": len(reply.get("operations", []))})
            return reply

    # ---------- review & publish (B seam) ----------

    def submit_review(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            if request.get("origin") == "dev_sample" or draft.get("origin") == "dev_sample"                     or "dev_sample" in (draft.get("lineage") or []):
                reject_sample_review({"origin": "dev_sample"})
            decision = request.get("decision")
            if decision not in ("accept", "partial", "reject"):
                raise ContractError("VALIDATION_FAILED", "decision 必须是 accept/partial/reject")
            actor = (request.get("actor") or "").strip()
            if not actor:
                raise ContractError("VALIDATION_FAILED", "复核需要 actor（本机操作者声明）")
            expected_map = request.get("expectedMapRevision")
            if not isinstance(expected_map, str) or expected_map != draft["graph"].get("mapRevision"):
                raise ContractError("REVISION_CONFLICT", "图版本已变化；请按最新预览重试",
                                    {"expected": expected_map, "current": draft["graph"].get("mapRevision")})
            # Record the human decision first: the review happened even when
            # the version backend is missing; what must never happen is a
            # version. Everything up to the publish write-back stays inside
            # the workspace lock (FINAL-1 finding 4).
            self.store.append_history(workspace_id, {
                "type": "review_decision", "at": _utcnow(), "decision": decision,
                "actor": actor, "reason": request.get("reason", ""),
                "proposalId": request.get("proposalId"),
                "mapRevision": draft["graph"].get("mapRevision"),
                "delivery": "recorded_locally_pending_b_backend",
            })
            backend = self.adapter.backend("persistence", "production")
            if backend.get("kind") == "dev_sample":
                raise ContractError(
                    "BACKEND_UNAVAILABLE",
                    "B 的版本服务尚未接入：本次人审决定已记录在草稿历史，但没有产生任何正式认知版本。",
                    {"decision": decision, "mapRevision": draft["graph"].get("mapRevision")},
                )
            # A real backend is registered: delegate the publish transaction
            # with the reviewed content and the recorded decision.
            reply = call_backend(backend, "publish_reviewed_graph", {
                "workspaceId": record["workspaceId"],
                "mapRevision": draft["graph"].get("mapRevision"),
                "graph": draft["graph"],
                "decision": decision,
                "actor": actor,
                "reason": request.get("reason", ""),
                "proposalId": request.get("proposalId"),
            })
            if reply.get("status") == "published":
                published_revision = reply.get("mapRevision") or draft["graph"].get("mapRevision")
                # atomic re-check: the draft must still be the one that was
                # reviewed before the publish result is written back
                current = self.store.load_workspace(workspace_id)
                if current["draft"]["draftRevision"] != draft["draftRevision"]:
                    raise ContractError("REVISION_CONFLICT",
                                        "发布期间草稿又被修改；发布结果未写入，请重新复核",
                                        {"publishedMapRevision": published_revision})
                current["draft"]["publishedMapRevision"] = published_revision
                current["draft"]["mapSourceRevision"] = reply.get("mapSourceRevision")
                current["identity"]["mapSourceRevision"] = reply.get("mapSourceRevision")
                current["identity"]["verifiedCodeRevision"] = reply.get("verifiedCodeRevision")
                # published identity is a fact about the last publish, kept
                # separate from the current draft's identity (FINAL-2 F5)
                current["lastPublish"] = {
                    "mapRevision": published_revision,
                    # A-side hash of the graph that was published, so the
                    # envelope can compare like with like (BATCH-1 C-01)
                    "aMapRevision": draft["graph"].get("mapRevision"),
                    "mapSourceRevision": reply.get("mapSourceRevision"),
                    "verifiedCodeRevision": reply.get("verifiedCodeRevision"),
                    "actor": actor,
                    "at": _utcnow(),
                }
                current["updatedAt"] = _utcnow()
                self.store.save_workspace_record(current)
                self.store.append_history(workspace_id, {"type": "publish", "at": _utcnow(),
                                                         "mapRevision": published_revision,
                                                         "mapSourceRevision": reply.get("mapSourceRevision")})
                return self._envelope(current)
            raise ContractError("BACKEND_UNAVAILABLE",
                                "版本后端未确认发布结果；不显示成功。",
                                {"reply": reply.get("status")})

    # ---------- B version backend: real save / review / publish / history ----------

    def bind_backend_b(self, backend) -> None:
        """Bind the configured B service (single adapter layer, backend_b.py)."""
        self.backend_b = backend
        if backend is not None:
            self.adapter.register("persistence", {
                "kind": backend.KIND, "call": backend.call, "ref": backend.REF,
                "labeled": "B 的真实版本服务（架构草稿/人审/不可变版本）",
            })

    def _backend_b(self):
        backend_b = getattr(self, "backend_b", None)
        if backend_b is None or not backend_b.available:
            reason = getattr(backend_b, "reason", None) or "未配置专用数据根与架构 Git 工作副本"
            raise ContractError("BACKEND_UNAVAILABLE", f"B 的真实版本服务未接入：{reason}")
        return backend_b

    def backend_status(self) -> dict:
        backend_b = getattr(self, "backend_b", None)
        return {
            "versionService": backend_b.status() if backend_b is not None
            else {"available": False, "reason": "未绑定 B 版本服务", "kind": "unavailable"},
            "adapter": self.adapter.listing(),
            "generation": generate_module.generate_status(),
            "persistence": self._backend_label(),
        }

    @staticmethod
    def _require_meta(meta) -> dict:
        if not isinstance(meta, dict) or not meta.get("peer") or not meta.get("host") \
                or not meta.get("origin"):
            raise ContractError("VALIDATION_FAILED",
                                "缺少真实请求元数据：peer/host/origin 必须由服务端从请求注入")
        return meta

    @staticmethod
    def _sample_guard(draft: dict) -> None:
        if draft.get("origin") == "dev_sample" or "dev_sample" in (draft.get("lineage") or []):
            reject_sample_review({"origin": "dev_sample"})

    def sync_draft_to_backend(self, workspace_id: str, request: dict) -> dict:
        """Write the current A draft into B's real draft space (server-side)."""
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            backend_b = self._backend_b()
            result = backend_b.sync_draft(record, draft["graph"],
                                          origin=draft.get("origin", "manual"))
            binding = dict(result["binding"])
            binding["aDraftRevisionAtSync"] = draft["draftRevision"]
            binding["bBaseMapRevision"] = result["draft"]["baseMapRevision"]
            record["backendB"] = binding
            if not record.get("mapIdProvided"):
                # the version service assigns the durable graph identity; A's
                # identity follows it so both sides name the same map
                record["identity"]["mapId"] = binding.get("mapId")
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "backend_sync", "at": _utcnow(), "bDraftId": binding["draftId"],
                "bDraftRevision": binding["bDraftRevision"],
                "operations": len(result.get("operations", [])), "created": result.get("created")})
            return {"backend": self._backend_label(), "bDraftId": binding["draftId"],
                    "bDraftRevision": binding["bDraftRevision"],
                    "operations": result.get("operations", []),
                    "envelope": self._envelope(record)}

    def _ensure_synced(self, record: dict, backend_b) -> dict:
        """Auto-sync the A draft into B when A moved on since the last sync."""
        draft = record["draft"]
        binding = dict(record.get("backendB") or {})
        if binding.get("draftId") and binding.get("aDraftRevisionAtSync") == draft["draftRevision"]:
            return binding
        result = backend_b.sync_draft(record, draft["graph"], origin=draft.get("origin", "manual"))
        binding = dict(result["binding"])
        binding["aDraftRevisionAtSync"] = draft["draftRevision"]
        binding["bBaseMapRevision"] = result["draft"]["baseMapRevision"]
        record["backendB"] = binding
        if not record.get("mapIdProvided"):
            record["identity"]["mapId"] = binding.get("mapId")
        self.store.save_workspace_record(record)
        return binding

    def review_preview(self, workspace_id: str, request: dict, meta: dict) -> dict:
        """Server-side review preview through B's Gateway (real session values)."""
        meta = self._require_meta(meta)
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            self._sample_guard(draft)
            backend_b = self._backend_b()
            actor = (request.get("actor") or "").strip()
            if not actor:
                raise ContractError("VALIDATION_FAILED", "人审预览需要 actor（本机操作者声明）")
            self._ensure_synced(record, backend_b)
            session = backend_b.create_session(actor, meta)
            result = backend_b.preview_review(record, {
                "sessionId": session["sessionId"], "csrfToken": session["csrfToken"],
                "reason": request.get("reason", ""),
                "coverage": request.get("coverage"),
                "limits": request.get("limits"),
                "verifyCode": request.get("verifyCode"),
                "rejectedCandidates": request.get("rejectedCandidates"),
            }, meta)
            b_draft = backend_b.draft_state(record)
            record["backendB"]["lastPreview"] = {
                "previewDigest": result["previewDigest"],
                "confirmationToken": result["confirmationToken"], "actor": actor,
                "at": _utcnow(), "expiresInSeconds": result["expiresInSeconds"],
                "bDraftRevision": b_draft["draftRevision"],
                "aDraftRevision": draft["draftRevision"]}
            record["backendB"]["sessionSecret"] = {
                "sessionId": session["sessionId"], "csrfToken": session["csrfToken"],
                "actor": actor, "at": _utcnow()}
            self.store.save_workspace_record(record)
            preview = result["preview"]
            self.store.append_history(workspace_id, {
                "type": "review_preview", "at": _utcnow(), "actor": actor,
                "previewDigest": result["previewDigest"],
                "coverage": preview["reviewCoverage"], "bDraftRevision": b_draft["draftRevision"]})
            return {
                "previewDigest": result["previewDigest"],
                # the confirmation token stays on the server: the browser only
                # proves it saw THIS preview by echoing the digest (BATCH-1 B-01)
                "expiresInSeconds": result["expiresInSeconds"],
                "beforeGraph": (b_to_a_graph(preview["beforeGraph"], preview)
                                if preview.get("beforeGraph") else None),
                "afterGraph": b_to_a_graph(preview["afterGraph"], preview),
                "appliedOperations": preview["appliedOperations"],
                "rejectedCandidates": preview["rejectedCandidates"],
                "reviewCoverage": preview["reviewCoverage"],
                "limits": preview["limits"], "verifyCode": preview["verifyCode"],
                "bDraftRevision": b_draft["draftRevision"], "origin": preview["origin"],
                "labeled": "真实版本服务的人审预览：已绑定该草稿与代码版本，确认后才会产生版本",
            }

    def review_confirm(self, workspace_id: str, request: dict, meta: dict) -> dict:
        meta = self._require_meta(meta)
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            self._sample_guard(draft)
            backend_b = self._backend_b()
            binding = record.get("backendB") or {}
            last = binding.get("lastPreview")
            session = binding.get("sessionSecret") or {}
            if not last or not session:
                raise ContractError("HUMAN_REVIEW_REQUIRED", "没有先执行人审预览；请先预览再确认")
            if request.get("previewDigest") != last["previewDigest"]:
                raise ContractError("HUMAN_REVIEW_REQUIRED",
                                    "确认与已存储的预览不一致；请重新预览",
                                    {"expectedDigest": last["previewDigest"]})
            if last.get("aDraftRevision") != draft["draftRevision"]:
                # the draft was edited after the preview: the preview is void
                raise ContractError("REVISION_CONFLICT",
                                    "草稿在人审预览之后又被修改；预览作废，请重新预览",
                                    {"previewBasis": last.get("aDraftRevision"),
                                     "current": draft["draftRevision"]})
            result = backend_b.confirm_review(record, {
                "sessionId": session["sessionId"], "csrfToken": session["csrfToken"],
                "confirmationToken": last["confirmationToken"],  # server-side only
                "previewDigest": request["previewDigest"],
                "decision": request.get("decision"),
            }, meta)
            binding["reviewId"] = result["reviewId"]
            binding["reviewDecision"] = result["decision"]
            if result.get("publicationToken"):
                binding["publication"] = {
                    "token": result["publicationToken"], "reviewId": result["reviewId"],
                    "expectedMapRevision": binding.get("bBaseMapRevision"), "at": _utcnow()}
            record["backendB"] = binding
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "review_decision", "at": _utcnow(), "actor": last.get("actor"),
                "decision": result["decision"], "reviewId": result["reviewId"],
                "mapRevision": draft.get("graph", {}).get("mapRevision"),
                "delivery": "recorded_by_b_review_gateway_pending_publish"
                if result.get("publicationToken") else "rejected_by_b_review_gateway"})
            return {"reviewId": result["reviewId"], "decision": result["decision"],
                    "publicationAuthorized": bool(result.get("publicationToken")),
                    "verifiedCodeRevision": result.get("verifiedCodeRevision"),
                    "labeled": ("已确认：发布授权保存在服务端；点击发布产生不可变版本"
                                if result.get("publicationToken") else
                                "已拒绝：不产生发布授权，不产生版本")}

    def publish_version(self, workspace_id: str, request: dict, meta: dict) -> dict:
        meta = self._require_meta(meta)
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            self._sample_guard(draft)
            backend_b = self._backend_b()
            binding = record.get("backendB") or {}
            publication = binding.get("publication")
            if not publication:
                raise ContractError("HUMAN_REVIEW_REQUIRED",
                                    "没有已确认的人审授权；发布必须经过 预览→确认→发布")
            # publishing requires the human-review session itself to still be
            # valid: the Host/Origin check alone is not a session check
            # (BATCH-1 B-02; B's integration guide step 6)
            backend_b.assert_session_active(record, meta)
            reviewed_revision = (binding.get("lastPreview") or {}).get("aDraftRevision")
            if reviewed_revision is not None and reviewed_revision != draft["draftRevision"]:
                raise ContractError("REVISION_CONFLICT",
                                    "草稿在确认之后又被修改；当前页面与已审核内容不一致，请重新走人审",
                                    {"reviewed": reviewed_revision, "current": draft["draftRevision"]})
            envelope = backend_b.publish(record, {"publicationToken": publication["token"]}, meta)
            version = envelope["version"]
            provenance = envelope["provenance"]
            record["lastPublish"] = {
                "mapRevision": version["mapRevision"],
                "mapSourceRevision": provenance.get("mapSourceRevision"),
                "verifiedCodeRevision": version.get("verifiedCodeRevision"),
                "actor": (binding.get("lastPreview") or {}).get("actor"), "at": _utcnow()}
            record["identity"]["mapSourceRevision"] = provenance.get("mapSourceRevision")
            record["identity"]["verifiedCodeRevision"] = version.get("verifiedCodeRevision")
            draft["publishedMapRevision"] = version["mapRevision"]
            record["lastPublish"]["aMapRevision"] = draft["graph"].get("mapRevision")
            record.setdefault("publishedVersions", []).append({
                "mapRevision": version["mapRevision"],
                "aMapRevision": draft["graph"].get("mapRevision"),
                "mapSourceRevision": provenance.get("mapSourceRevision"),
                "codeRevision": version["codeRevision"],
                "verifiedCodeRevision": version.get("verifiedCodeRevision"),
                "status": version["status"], "at": _utcnow()})
            binding.pop("publication", None)
            binding.pop("lastPreview", None)
            record["backendB"] = binding
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "publish", "at": _utcnow(), "mapRevision": version["mapRevision"],
                "mapSourceRevision": provenance.get("mapSourceRevision"),
                "backend": backend_b.KIND})
            return {
                "version": {key: version[key] for key in
                            ("mapId", "mapRevision", "codeRepoId", "codeRevision",
                             "verifiedCodeRevision", "status", "origin")},
                "provenance": provenance,
                "graph": b_to_a_graph(version["graph"], version),
                "reviewCoverage": version["reviewCoverage"],
                "confirmation": version["confirmation"], "limits": version["limits"],
                "envelope": self._envelope(record),
                "labeled": "B 版本服务产生并经 Git 提交的不可变认知版本",
            }

    def version_history(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        binding = record.get("backendB") or {}
        versions = list(record.get("publishedVersions", []))
        return {"workspaceId": workspace_id, "versions": versions,
                "bWorkspaceId": binding.get("workspaceId"), "mapId": binding.get("mapId"),
                "currentMapRevision": (record.get("draft") or {}).get("publishedMapRevision"),
                "backend": self._backend_label()}

    def version_detail(self, workspace_id: str, map_revision: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        binding = record.get("backendB") or {}
        if not binding.get("workspaceId"):
            raise ContractError("VALIDATION_FAILED", "该工作区尚未接入版本服务")
        envelope = self._backend_b().export_version(binding["workspaceId"], map_revision)
        version = envelope["version"]
        return {"version": {key: version[key] for key in
                            ("mapId", "mapRevision", "codeRepoId", "codeRevision",
                             "verifiedCodeRevision", "status", "origin")},
                "provenance": envelope["provenance"],
                "graph": b_to_a_graph(version["graph"], version),
                "reviewCoverage": version["reviewCoverage"],
                "confirmation": version["confirmation"], "limits": version["limits"]}

    def import_version(self, workspace_id: str, request: dict) -> dict:
        """Second client: read the immutable Git bytes for a published revision."""
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            binding = record.get("backendB") or {}
            if not binding.get("workspaceId"):
                raise ContractError("VALIDATION_FAILED", "该工作区尚未接入版本服务")
            map_revision = request.get("mapRevision")
            map_source_revision = request.get("mapSourceRevision")
            if not map_revision or not map_source_revision:
                raise ContractError("VALIDATION_FAILED", "需要 mapRevision 与 mapSourceRevision")
            envelope = self._backend_b().import_git_version(
                binding["workspaceId"], map_revision=map_revision,
                map_source_revision=map_source_revision,
                expected_map_revision=request.get("expectedMapRevision"))
            version = envelope["version"]
            record["lastPublish"] = {
                "mapRevision": version["mapRevision"],
                "aMapRevision": (record.get("draft") or {}).get("graph", {}).get("mapRevision"),
                "mapSourceRevision": envelope["provenance"].get("mapSourceRevision"),
                "verifiedCodeRevision": version.get("verifiedCodeRevision"),
                "actor": "import_git_version", "at": _utcnow()}
            record.setdefault("publishedVersions", []).append({
                "mapRevision": version["mapRevision"],
                "mapSourceRevision": envelope["provenance"].get("mapSourceRevision"),
                "codeRevision": version["codeRevision"],
                "verifiedCodeRevision": version.get("verifiedCodeRevision"),
                "status": version["status"], "at": _utcnow(), "imported": True})
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "import_git_version", "at": _utcnow(),
                "mapRevision": version["mapRevision"],
                "mapSourceRevision": envelope["provenance"].get("mapSourceRevision")})
            return {"version": {key: version[key] for key in
                                ("mapId", "mapRevision", "codeRepoId", "codeRevision",
                                 "verifiedCodeRevision", "status", "origin")},
                    "provenance": envelope["provenance"],
                    "graph": b_to_a_graph(version["graph"], version),
                    "reviewCoverage": version["reviewCoverage"],
                    "confirmation": version["confirmation"], "limits": version["limits"],
                    "labeled": "第二副本从架构 Git 固定提交读取的同版内容"}

    def open_from_version(self, request: dict) -> dict:
        """Second copy: open the same graph version as a NEW workspace.

        The caller supplies the registered mapId, the immutable mapRevision and
        the architecture Git source SHA. The version bytes are read from Git
        and verified; a label in the request is never trusted.
        """
        map_id = (request.get("mapId") or "").strip()
        map_revision = (request.get("mapRevision") or "").strip()
        map_source_revision = (request.get("mapSourceRevision") or "").strip()
        repo_path = (request.get("repoPath") or "").strip()
        if not map_id or not map_revision or not map_source_revision or not repo_path:
            raise ContractError("VALIDATION_FAILED",
                                "需要 mapId/mapRevision/mapSourceRevision/repoPath")
        backend_b = self._backend_b()
        envelope = self.create_workspace({
            "context": "existing_project",
            "title": request.get("title") or "同版接手（第二副本）",
            "repoPath": repo_path, "mapId": map_id,
            "description": request.get("description", "按同版交接包打开同一认知版本")})
        workspace_id = envelope["workspace"]["workspaceId"]
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            binding = dict(record.get("backendB") or {})
            workspace_b = backend_b.ensure_workspace(record)
            binding.update({"workspaceId": workspace_b["workspaceId"],
                            "mapId": workspace_b["mapId"]})
            record["backendB"] = binding
            envelope_b = backend_b.import_git_version(
                binding["workspaceId"], map_revision=map_revision,
                map_source_revision=map_source_revision,
                expected_map_revision=request.get("expectedMapRevision"))
            version = envelope_b["version"]
            record["lastPublish"] = {
                "mapRevision": version["mapRevision"],
                "aMapRevision": (record.get("draft") or {}).get("graph", {}).get("mapRevision"),
                "mapSourceRevision": envelope_b["provenance"].get("mapSourceRevision"),
                "verifiedCodeRevision": version.get("verifiedCodeRevision"),
                "actor": "open_from_version", "at": _utcnow()}
            record.setdefault("publishedVersions", []).append({
                "mapRevision": version["mapRevision"],
                "mapSourceRevision": envelope_b["provenance"].get("mapSourceRevision"),
                "codeRevision": version["codeRevision"],
                "verifiedCodeRevision": version.get("verifiedCodeRevision"),
                "status": version["status"], "at": _utcnow(), "imported": True})
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "open_from_version", "at": _utcnow(),
                "mapId": version["mapId"], "mapRevision": version["mapRevision"],
                "mapSourceRevision": envelope_b["provenance"].get("mapSourceRevision")})
            result = self._envelope(record)
        result.update({
            "version": {key: version[key] for key in
                        ("mapId", "mapRevision", "codeRepoId", "codeRevision",
                         "verifiedCodeRevision", "status", "origin")},
            "provenance": envelope_b["provenance"],
            "graph": b_to_a_graph(version["graph"], version),
            "reviewCoverage": version["reviewCoverage"],
            "confirmation": version["confirmation"], "limits": version["limits"],
            "labeled": "第二副本从架构 Git 固定提交读取并核对来源后的同版内容"})
        return result

    def associate_code(self, workspace_id: str, request: dict) -> dict:
        """Planning workspace: explicitly associate a real repository (keeps design history)."""
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            if record["context"] != "planning":
                raise ContractError("VALIDATION_FAILED", "只有规划工作区需要关联代码")
            repo_path = (request.get("repoPath") or "").strip()
            if not repo_path:
                raise ContractError("VALIDATION_FAILED", "需要仓库路径")
            probe = self.probe_repo(repo_path)
            backend_b = self._backend_b()
            binding = record.get("backendB") or {}
            if not binding.get("workspaceId"):
                raise ContractError("VALIDATION_FAILED", "该工作区尚未接入版本服务")
            code_repo_id = backend_b.repo_id_for(probe["root"])
            backend_b.associate_code(binding["workspaceId"], code_repo_id=code_repo_id,
                                     code_revision=probe["head"],
                                     expected_map_revision=request.get("expectedMapRevision"))
            identity = record["identity"]
            confirmed_design = (record.get("lastPublish") or {}).get("mapRevision")
            if confirmed_design:
                # the confirmed design version stays in history: associating
                # code never rewrites what was confirmed as a design
                record.setdefault("designHistory", []).append(confirmed_design)
            identity["codeRepoId"] = code_repo_id
            identity["codeRevision"] = probe["head"]
            identity["repoPath"] = probe["root"]
            if not identity.get("mapId"):
                identity["mapId"] = binding.get("mapId")
            record["context"] = "mixed"
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "associate_code", "at": _utcnow(), "codeRepoId": code_repo_id,
                "codeRevision": probe["head"],
                "note": "规划图关联真实代码：设计确认不等于实现完成"})
            return self._envelope(record)

    # ---------- change recheck (P4) ----------

    def recheck(self, workspace_id: str) -> dict:
        with workspace_lock(workspace_id):
            return self._recheck_locked(workspace_id)

    def _recheck_locked(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        identity = record["identity"]
        if not identity.get("repoPath") or not identity.get("codeRevision"):
            raise ContractError("VALIDATION_FAILED", "该工作区没有关联代码，无法做代码变化复核")
        probe = self.probe_repo(identity["repoPath"])
        new_head = probe["head"]
        result = {
            "oldCodeRevision": identity["codeRevision"],
            "newCodeRevision": new_head,
            "changed": new_head != identity["codeRevision"],
        }
        if result["changed"]:
            changes = self.diff_repo(identity["repoPath"], identity["codeRevision"], new_head)
            result["comparison"] = {"baseRevision": identity["codeRevision"], "targetRevision": new_head,
                                    "changes": changes}
            # renames must flag nodes still citing the old path too
            # (FINAL-1 finding 6)
            changed_paths = {c["path"] for c in changes}
            changed_paths |= {c["oldPath"] for c in changes if c.get("oldPath")}
            draft = record.get("draft")
            stale_nodes = []
            if draft:
                for node in draft["graph"]["nodes"]:
                    hit = sorted({item["path"] for item in node.get("evidence", [])
                                  if item.get("kind", "code_fact") == "code_fact" and item["path"] in changed_paths})
                    if hit:
                        stale_nodes.append({"nodeId": node["id"], "title": node["title"], "paths": hit})
            result["staleNodes"] = stale_nodes
            result["note"] = "代码已前进；列出的节点声明的代码证据出现在差异中，需要人复核。不代表架构已变化。"
        else:
            result["staleNodes"] = []
        identity["latestObservedCodeRevision"] = new_head
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(record["workspaceId"], {"type": "recheck", "at": _utcnow(),
                                                          "old": result["oldCodeRevision"],
                                                          "new": new_head})
        return result

    def rebind_code_revision(self, workspace_id: str, request: dict) -> dict:
        """Re-bind the workspace to a newly reviewed code revision (P4 回挂).

        This is a local record: until D's verification lands the rebind never
        sets verifiedCodeRevision, so nothing here claims the new code was
        human-verified.
        """
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            identity = record["identity"]
            if not identity.get("repoPath"):
                raise ContractError("VALIDATION_FAILED", "该工作区没有关联代码")
            actor = (request.get("actor") or "").strip()
            if not actor:
                raise ContractError("VALIDATION_FAILED", "回挂需要 actor（本机操作者声明）")
            expected = request.get("expectedNewCodeRevision")
            probe = self.probe_repo(identity["repoPath"])
            if not is_full_sha(expected) or expected != probe["head"]:
                raise ContractError("STALE_CONTEXT", "回挂目标与仓库当前 HEAD 不一致；请先刷新复核",
                                    {"expected": expected, "head": probe["head"]})
            old = identity.get("codeRevision")
            identity["codeRevision"] = expected
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "rebind", "at": _utcnow(), "actor": actor,
                "from": old, "to": expected,
                "note": request.get("note", ""),
                "delivery": "local_rebind_pending_d_verification",
            })
            return self._envelope(record)

    # ---------- fix task (D seam) ----------

    def import_legacy_map(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            return self._import_legacy_locked(workspace_id, request)

    def _import_legacy_locked(self, workspace_id: str, request: dict) -> dict:
        """Import the legacy curated demo map as an unconfirmed draft.

        Compatibility seam (A instruction: legacy map gets a clear read-only
        compatible path into the new workspace). The import never claims the
        old demo graph was confirmed: every node becomes candidate/human_input
        with an explicit import note, and legacy relations become
        functional_collaboration — never expected_sequence, so imports cannot
        disguise themselves as runtime chains.
        """
        record = self.store.load_workspace(workspace_id)
        legacy = request.get("legacyMap")
        if not isinstance(legacy, dict) or not isinstance(legacy.get("nodes"), list):
            raise ContractError("VALIDATION_FAILED", "需要 legacyMap{note, nodes[], edges[]}")
        # replacing an existing draft is CAS-guarded like any other write
        # (FINAL-1 finding 1)
        existing_draft = record.get("draft")
        if existing_draft is not None:
            expected = request.get("expectedDraftRevision")
            if not isinstance(expected, str) or expected != existing_draft["draftRevision"]:
                raise ContractError("REVISION_CONFLICT", "已有草稿被修改过；请先查看差异再决定导入",
                                    {"expected": expected, "current": existing_draft["draftRevision"]})
        note = legacy.get("note", "")
        nodes = []
        for node in legacy["nodes"]:
            if not isinstance(node, dict) or not node.get("id"):
                raise ContractError("VALIDATION_FAILED", "legacy 节点缺少 id")
            evidence = [{"path": item.get("path", ""), "reason": item.get("reason", ""), "kind": "code_fact"}
                        for item in node.get("evidence", []) if isinstance(item, dict) and item.get("path")]
            nodes.append({
                "id": node["id"], "title": node.get("title", node["id"]),
                "summary": node.get("summary", ""), "status": "candidate",
                "provenance": "human_input",
                "entryPoints": [node["entryPoint"]] if node.get("entryPoint") else [],
                "interfaces": [], "evidence": evidence, "process": [],
                "importNote": f"来自 legacy 人工演示图：{note}",
            })
        edges = [{"from": edge.get("from"), "to": edge.get("to"),
                  "type": "functional_collaboration",
                  "label": f"{edge.get('label', '')}（legacy 导入，非运行链）"}
                 for edge in legacy.get("edges", []) if isinstance(edge, dict)]
        graph = {"nodes": nodes, "edges": edges}
        # structural validation before anything is stored: bad IDs or dangling
        # edges fail loudly instead of entering the workspace
        ops_module.validate_graph(graph)
        bound = record["identity"].get("codeRevision")
        graph = self._evidence_guard(graph, record, bound)
        # the guard can mutate evidence (semantic content): recompute the
        # graph's own revision field so identity never shows a stale digest
        # (FINAL-2 finding F1)
        graph["mapRevision"] = semantic_revision(graph)
        graph["mapRevision"] = semantic_revision(graph)
        # F2 (FINAL-3): an import that claims dev_sample origin stays tainted —
        # a sample graph cannot launder itself into a reviewable legacy_import
        # by being submitted as a "legacy map".
        import_origin = "legacy_import"
        if request.get("origin") == "dev_sample" or legacy.get("origin") == "dev_sample":
            import_origin = "dev_sample"
        draft = self._new_draft(record, graph, origin=import_origin)
        # replacing a sample draft does not wash its mark: the origin chain is
        # carried so review still refuses sample-tainted lineages (FINAL-2 F2)
        lineage = []
        if existing_draft is not None:
            lineage = list(existing_draft.get("lineage", [existing_draft.get("origin")]))
            draft["publishedMapRevision"] = existing_draft.get("publishedMapRevision")
        lineage.append(import_origin)
        draft["lineage"] = lineage
        record["draft"] = draft
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(workspace_id, {"type": "import_legacy", "at": _utcnow(),
                                                 "nodes": len(nodes), "edges": len(edges),
                                                 "draftRevision": draft["draftRevision"]})
        return self._envelope(record)

    def create_fix_task(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            if draft is None:
                raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
            mode = request.get("mode", "production")
            if mode == DEV_SAMPLE_MODE:
                return self._sample_fix_task(record, draft, request)
            # a registered real handoff backend (D, once delivered) owns the
            # delegation; without one, the workbench persists a real task
            # itself instead of falling back to a sample
            try:
                backend = self.adapter.backend("handoff", mode)
            except ContractError:
                backend = None
            if backend is not None and backend.get("kind") != "dev_sample":
                return self._legacy_fix_task_delegation(record, draft, request)
            task = fix_tasks_module.create_task(self.store.root, record, draft, request)
            task["envelope"] = self._envelope(record)
            self.store.append_history(workspace_id, {
                "type": "fix_task", "at": _utcnow(), "taskId": task["taskId"],
                "deviationId": task.get("deviationId"),
                "targetCodeRevision": task.get("targetCodeRevision")})
            return task

    def _sample_fix_task(self, record: dict, draft: dict, request: dict) -> dict:
        deviation = (request.get("deviation") or "").strip()
        if not deviation:
            raise ContractError("VALIDATION_FAILED", "请描述偏差内容")
        return {
            "taskType": "implementation_fix",
            "labeled": "演示数据 · 修正实现任务样例",
            "origin": "dev_sample",
            "deviationId": f"dev_{secrets.token_hex(4)}",
            "workspaceId": record["workspaceId"],
            "mapRevision": draft["graph"].get("mapRevision"),
            "expectedProcessRef": request.get("expectedProcessRef"),
            "observation": deviation,
            "evidence": request.get("evidence", []),
            "acceptance": request.get("acceptance", ""),
            "status": "queued",
            "note": "演示样例：真实任务请使用生产模式创建。",
        }

    def _legacy_fix_task_delegation(self, record: dict, draft: dict, request: dict) -> dict:
        """Delegate to a registered real handoff backend (D's module)."""
        deviation = (request.get("deviation") or "").strip()
        if not deviation:
            raise ContractError("VALIDATION_FAILED", "请描述偏差内容")
        backend = self.adapter.backend("handoff", request.get("mode", "production"))
        if backend.get("kind") == "dev_sample":
            task = {
                "taskType": "implementation_fix",
                "labeled": "演示数据 · 修正实现任务样例",
                "origin": "dev_sample",
                "deviationId": f"dev_{secrets.token_hex(4)}",
                "workspaceId": record["workspaceId"],
                "mapRevision": draft["graph"].get("mapRevision"),
                "expectedProcessRef": request.get("expectedProcessRef"),
                "observation": deviation,
                "evidence": request.get("evidence", []),
                "acceptance": request.get("acceptance", ""),
                "status": "queued",
                "note": "改图不会自动修改程序；实施者在独立分支交付后回挂 SHA 再验证。",
            }
            self.store.append_history(workspace_id, {"type": "fixtask_sample", "at": _utcnow(),
                                                     "deviationId": task["deviationId"]})
            return task
        # a registered real handoff backend receives the delegation
        # (FINAL-1 finding 9: do not refuse when a backend exists)
        return call_backend(backend, "create_fix_task", {
            "workspaceId": record["workspaceId"],
            "mapRevision": draft["graph"].get("mapRevision"),
            "expectedProcessRef": request.get("expectedProcessRef"),
            "deviation": deviation,
            "evidence": request.get("evidence", []),
            "acceptance": request.get("acceptance", ""),
        })
